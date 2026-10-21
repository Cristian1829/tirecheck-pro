import sqlite3
import json
import math
import pandas as pd
import numpy as np
import unicodedata
import os
import re
import hashlib
import hmac
import secrets
from datetime import datetime, date, timedelta
from contextlib import contextmanager
import sys

try:
    from zoneinfo import ZoneInfo
    BOGOTA_TZ = ZoneInfo("America/Bogota")
except Exception:
    from datetime import timezone
    BOGOTA_TZ = timezone(timedelta(hours=-5))

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)
_DB_DATA = os.path.join(_DATA_DIR, "inspecciones.db")
_DB_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inspecciones.db")
_DB_SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_inspecciones.db")

def verificar_y_poblar_seed():
    """
    Garantiza que si la base de datos en data/inspecciones.db no existe,
    está vacía o tiene 0 inspecciones (como ocurre al montar un volumen nuevo en Railway),
    se carguen inmediatamente todas las inspecciones y catálogos desde seed_inspecciones.db.
    """
    candidatos_seed = [_DB_SEED, _DB_ROOT]
    seed_valido = None
    for s in candidatos_seed:
        if os.path.exists(s) and os.path.getsize(s) > 10000:
            seed_valido = s
            break

    if not seed_valido:
        return

    necesita_poblado = False
    if not os.path.exists(_DB_DATA) or os.path.getsize(_DB_DATA) == 0:
        necesita_poblado = True
    else:
        try:
            conn = sqlite3.connect(_DB_DATA)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM inspecciones")
            row = cur.fetchone()
            if not row or row[0] == 0:
                necesita_poblado = True
            conn.close()
        except Exception:
            necesita_poblado = True

    if necesita_poblado:
        try:
            import shutil
            shutil.copy2(seed_valido, _DB_DATA)
            print(f"[DATABASE] ✅ Base de datos poblada automáticamente desde seed: {seed_valido} ({os.path.getsize(_DB_DATA)} bytes)")
        except Exception as e:
            print(f"[DATABASE] ⚠️ Error al copiar seed a {_DB_DATA}: {e}")

verificar_y_poblar_seed()
DB_PATH = _DB_DATA


def hash_password(password: str) -> str:
    """
    Genera un hash seguro para la contraseña usando PBKDF2-HMAC-SHA256 con 100,000 iteraciones
    y un salt aleatorio de 16 bytes. Retorna 'pbkdf2_sha256$<salt_hex>$<hash_hex>'.
    """
    if not isinstance(password, str):
        password = str(password)
    salt = secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000
    )
    return f"pbkdf2_sha256${salt}${hash_bytes.hex()}"

def verify_password(plain_password: str, stored_password: str) -> bool:
    """
    Verifica una contraseña en texto plano contra el hash almacenado usando tiempo constante.
    Si el hash almacenado usa formato 'pbkdf2_sha256$', verifica con PBKDF2.
    Si es una contraseña legada en texto plano, compara directamente con hmac.compare_digest.
    """
    if not isinstance(plain_password, str):
        plain_password = str(plain_password)
    if not isinstance(stored_password, str):
        stored_password = str(stored_password)
    
    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            parts = stored_password.split('$')
            if len(parts) != 3:
                return False
            _, salt, hash_hex = parts
            computed_bytes = hashlib.pbkdf2_hmac(
                'sha256',
                plain_password.encode('utf-8'),
                salt.encode('utf-8'),
                100_000
            )
            return hmac.compare_digest(computed_bytes.hex(), hash_hex)
        except Exception:
            return False
    else:
        return hmac.compare_digest(plain_password, stored_password)

def normalizar_texto(texto):
    if not isinstance(texto, str):
        return str(texto)
    nfkd = unicodedata.normalize('NFKD', texto)
    sin_tildes = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    limpio = re.sub(r'[\._\-]+', ' ', sin_tildes)
    limpio = re.sub(r'\s+', ' ', limpio)
    return limpio.strip().lower()

def clasificar_vehiculo(v):
    v_str = str(v).strip()
    if len(v_str) > 0 and v_str[0].isalpha():
        letters = sum(1 for c in v_str if c.isalpha())
        if letters == 3:
            return 'Cabezote'
        elif letters == 1:
            return 'Trailer'
    return 'Desconocido'

def to_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '':
            return default
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return default

def to_int(val, default=0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '':
            return default
        return int(float(str(val).replace(',', '.')))
    except (ValueError, TypeError):
        return default

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def asegurar_columna_vistas_permitidas(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(usuarios)")
        cols_usr = [r[1] for r in cursor.fetchall()]
        if cols_usr and 'vistas_permitidas' not in cols_usr:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN vistas_permitidas TEXT DEFAULT 'patio,diagnostico,kpis'")
            conn.commit()
    except Exception:
        pass

def normalizar_vida_y_banda(vida_input, banda_input=''):
    """
    Normaliza de forma estricta y determinista los valores de Vida y Banda de Reencauche:
    - Retorna tupla (vida_final, banda_final) con vida_final en ('ORIGINAL', 'REENCAUCHE').
    - Si vida viene vacía, nula, '-' o inválida:
        * Si tiene banda de reencauche especificada -> 'REENCAUCHE'.
        * En cualquier otro caso -> 'ORIGINAL'.
    - Si vida es 'ORIGINAL' -> banda_final siempre es '' (vacía).
    - Si vida es 'REENCAUCHE' -> banda_final es la banda en mayúsculas limpia.
    """
    v_raw = str(vida_input or '').strip().upper()
    b_raw = str(banda_input or '').strip().upper()
    if b_raw in ('-', 'NONE', 'NAN', 'NULL', 'NO APLICA', 'N/A'):
        b_raw = ''

    if v_raw in ('ORIGINAL', 'ORIG', 'NUEVA') or 'ORIG' in v_raw:
        vida_final = 'ORIGINAL'
    elif v_raw in ('REENCAUCHE', 'REEN', 'RECAUCHE', 'R1', 'R2', 'R3', 'R4') or 'REEN' in v_raw:
        vida_final = 'REENCAUCHE'
    elif b_raw:
        vida_final = 'REENCAUCHE'
    else:
        vida_final = 'ORIGINAL'

    banda_final = b_raw if vida_final == 'REENCAUCHE' else ''
    return vida_final, banda_final

def inicializar_bd():
    verificar_y_poblar_seed()
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS inspecciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                cliente TEXT,
                subcliente TEXT,
                tipo_operacion TEXT,
                placa TEXT NOT NULL,
                posicion INTEGER NOT NULL,
                kilometraje REAL,
                tipologia TEXT,
                marca TEXT,
                diseno TEXT,
                dimension TEXT,
                vida TEXT NOT NULL DEFAULT 'ORIGINAL',
                banda_reen TEXT,
                prof_ext REAL,
                prof_cent REAL,
                prof_int REAL,
                psi REAL,
                novedades TEXT,
                precio REAL,
                prof_inicial REAL,
                km_montaje REAL,
                foto_novedad TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migración automática en caso de que la tabla ya exista sin los nuevos campos
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(inspecciones)")
        cols_existentes = [row[1] for row in cursor.fetchall()]
        
        nuevas_columnas = [
            ("cliente", "TEXT"),
            ("subcliente", "TEXT"),
            ("tipo_operacion", "TEXT"),
            ("numero_interno", "TEXT"),
            ("usuario_registro", "TEXT"),
            ("foto_novedad", "TEXT")
        ]
        for col, tipo in nuevas_columnas:
            if col not in cols_existentes:
                cursor.execute(f"ALTER TABLE inspecciones ADD COLUMN {col} {tipo}")

        # Tabla de Usuarios con roles y clientes asignados
        # Tabla de Usuarios con roles y clientes asignados
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nombre_completo TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'inspector', -- 'admin', 'inspector'
                cliente_asignado TEXT DEFAULT '',     -- Si tiene un cliente fijo, varios separados por comas, o vacío para todos
                vistas_permitidas TEXT DEFAULT 'patio,diagnostico,kpis', -- Vistas autorizadas (basedatos y catalogos solo admin)
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Auto-migración segura de columna vistas_permitidas si la tabla ya existía
        asegurar_columna_vistas_permitidas(conn)

        # Insertar usuarios por defecto si no existen
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                VALUES ('admin', ?, 'Administrador General', 'admin', '', 'patio,basedatos,diagnostico,kpis,catalogos')
            """, (hash_password('admin123'),))
            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                VALUES ('jefe1', ?, 'Jefe de Llantas', 'jefatura', '', 'patio,basedatos,diagnostico,kpis,catalogos')
            """, (hash_password('1234'),))
            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                VALUES ('gerencia1', ?, 'Dirección / Gerencia', 'gerencia', '', 'basedatos,diagnostico,kpis')
            """, (hash_password('1234'),))
            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                VALUES ('inspector1', ?, 'Juan Pérez (Inspector)', 'inspector', '', 'patio,diagnostico,kpis')
            """, (hash_password('1234'),))
        else:
            # Auto-migración: convertir contraseñas en texto plano existentes a PBKDF2
            cursor.execute("SELECT id, password FROM usuarios")
            for u_id, u_pwd in cursor.fetchall():
                if u_pwd and not str(u_pwd).startswith("pbkdf2_sha256$"):
                    cursor.execute("UPDATE usuarios SET password = ? WHERE id = ?", (hash_password(u_pwd), u_id))

            # Asegurar usuarios base de jefatura y gerencia si aún no existen
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE LOWER(username) = 'jefe1'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                    VALUES ('jefe1', ?, 'Jefe de Llantas', 'jefatura', '', 'patio,basedatos,diagnostico,kpis,catalogos')
                """, (hash_password('1234'),))

            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE LOWER(username) = 'gerencia1'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                    VALUES ('gerencia1', ?, 'Dirección / Gerencia', 'gerencia', '', 'basedatos,diagnostico,kpis')
                """, (hash_password('1234'),))

        # Tabla de Configuración de Límites por Cliente (Ej: Límite de retiro/cambio de llanta)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_clientes (
                cliente TEXT PRIMARY KEY,
                limite_retiro_mm REAL DEFAULT 3.0,
                observaciones TEXT,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de Configuración de Límites de Retiro Granular por Cliente, Subcliente y Eje
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_limites_retiro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                subcliente TEXT NOT NULL DEFAULT 'TODOS',
                eje TEXT NOT NULL DEFAULT 'TODOS',
                limite_retiro_mm REAL NOT NULL DEFAULT 3.0,
                observaciones TEXT DEFAULT '',
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cliente, subcliente, eje)
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
            SELECT UPPER(TRIM(cliente)), 'TODOS', 'TODOS', limite_retiro_mm, UPPER(TRIM(IFNULL(observaciones, ''))), fecha_actualizacion
            FROM configuracion_clientes
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
        """)

        # Tabla de Configuración de Marcas Habituales por Cliente
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_marcas_cliente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                marca TEXT NOT NULL,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cliente, marca)
            )
        """)

        # Backfill inicial de marcas por cliente desde inspecciones históricas
        cursor.execute("SELECT COUNT(*) FROM configuracion_marcas_cliente")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT OR IGNORE INTO configuracion_marcas_cliente (cliente, marca)
                SELECT DISTINCT UPPER(TRIM(cliente)), TRIM(marca)
                FROM inspecciones
                WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                  AND marca IS NOT NULL AND TRIM(marca) != ''
            """)

        # Tabla de Padrón de Vehículos por Cliente (Auditoría de Cumplimiento vs Parque)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS padron_vehiculos_cliente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                subcliente TEXT DEFAULT '',
                placa TEXT NOT NULL,
                tipologia TEXT DEFAULT '',
                estado_operativo TEXT DEFAULT 'Activo', -- 'Activo', 'En Taller Mecánico', 'Fuera de Operación'
                activo INTEGER DEFAULT 1,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cliente, placa)
            )
        """)

        # Backfill inicial seguro del padrón desde inspecciones históricas
        cursor.execute("SELECT COUNT(*) FROM padron_vehiculos_cliente")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT OR IGNORE INTO padron_vehiculos_cliente (cliente, subcliente, placa, tipologia, estado_operativo, activo)
                SELECT DISTINCT UPPER(TRIM(cliente)), UPPER(TRIM(IFNULL(subcliente, ''))), UPPER(TRIM(placa)), IFNULL(tipologia, ''), 'Activo', 1
                FROM inspecciones
                WHERE placa IS NOT NULL AND TRIM(placa) != '' AND cliente IS NOT NULL AND TRIM(cliente) != ''
            """)

        # Tabla de Configuración Avanzada y Licenciamiento por Cliente (LIGHT vs PRO)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_avanzada_cliente (
                cliente TEXT PRIMARY KEY,
                tipo_licencia TEXT DEFAULT 'PRO', -- 'LIGHT' o 'PRO'
                mm_retiro_direccional REAL DEFAULT 4.0,
                mm_retiro_traccion REAL DEFAULT 3.0,
                mm_retiro_arrastre REAL DEFAULT 3.0,
                rango_semaforo_amarillo_mm REAL DEFAULT 2.0,
                criterio_profundidad_calculo TEXT DEFAULT 'MINIMO',
                psi_objetivo_direccional REAL DEFAULT 110.0,
                psi_objetivo_traccion REAL DEFAULT 100.0,
                psi_objetivo_arrastre REAL DEFAULT 100.0,
                tolerancia_psi_baja_pct REAL DEFAULT 10.0,
                tolerancia_psi_alta_pct REAL DEFAULT 10.0,
                tolerancia_desalineacion_hombros_mm REAL DEFAULT 2.0,
                tolerancia_mal_apareo_pacha_mm REAL DEFAULT 2.5,
                tolerancia_busqueda_recambio_mm REAL DEFAULT 1.5,
                tolerancia_simetria_eje_opuesto_mm REAL DEFAULT 3.5,
                margen_envio_reencauche_desmonte_mm REAL DEFAULT 1.5,
                umbral_diferencia_rotacion_ejes_mm REAL DEFAULT 3.0,
                diferencia_minima_par_direccional_mm REAL DEFAULT 3.0,
                modo_rotacion_ejes TEXT DEFAULT 'ESTANDAR_FIJO',
                porcentaje_aprobacion_reencauche REAL DEFAULT 85.0,
                stock_seguridad_default INTEGER DEFAULT 4,
                plantilla_kpis_json TEXT DEFAULT '{}',
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migración automática de columnas para configuracion_avanzada_cliente
        cursor.execute("PRAGMA table_info(configuracion_avanzada_cliente)")
        cols_cfg = [row[1] for row in cursor.fetchall()]
        cols_nuevas_cfg = [
            ("tolerancia_busqueda_recambio_mm", "REAL DEFAULT 1.5"),
            ("tolerancia_simetria_eje_opuesto_mm", "REAL DEFAULT 3.5"),
            ("margen_envio_reencauche_desmonte_mm", "REAL DEFAULT 1.5"),
            ("modo_rotacion_ejes", "TEXT DEFAULT 'ESTANDAR_FIJO'"),
            ("porcentaje_aprobacion_reencauche", "REAL DEFAULT 85.0"),
            ("stock_seguridad_default", "INTEGER DEFAULT 4")
        ]
        for col_n, col_t in cols_nuevas_cfg:
            if col_n not in cols_cfg:
                cursor.execute(f"ALTER TABLE configuracion_avanzada_cliente ADD COLUMN {col_n} {col_t}")

        # Poblar configuración inicial PRO para clientes existentes
        cursor.execute("""
            INSERT OR IGNORE INTO configuracion_avanzada_cliente (cliente, tipo_licencia)
            SELECT DISTINCT UPPER(TRIM(cliente)), 'PRO'
            FROM inspecciones
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
        """)

        # Tabla Maestra de Llantas e Inventario en las 7 Bodegas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llantas_maestro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_interno TEXT NOT NULL,
                cliente TEXT NOT NULL,
                subcliente TEXT DEFAULT '',
                tipo_operacion TEXT DEFAULT '',
                ubicacion_bodega TEXT NOT NULL DEFAULT 'BODEGA_1_NUEVAS',
                estado_actual TEXT NOT NULL DEFAULT 'En Stock - Nueva',
                placa_actual TEXT DEFAULT '',
                posicion_actual INTEGER DEFAULT 0,
                marca TEXT NOT NULL DEFAULT '',
                diseno TEXT DEFAULT '',
                dimension TEXT NOT NULL DEFAULT '295/80R22.5',
                vida_actual TEXT NOT NULL DEFAULT 'Original', -- 'Original', 'R1', 'R2', 'R3'
                num_reencauches INTEGER DEFAULT 0,
                banda_reen TEXT DEFAULT '',
                prof_inicial REAL NOT NULL DEFAULT 18.0,
                prof_ext REAL DEFAULT 18.0,
                prof_cent REAL DEFAULT 18.0,
                prof_int REAL DEFAULT 18.0,
                prof_actual_min REAL NOT NULL DEFAULT 18.0,
                psi_actual REAL DEFAULT 100.0,
                km_montaje_ciclo REAL DEFAULT 0.0,
                km_actual_vehiculo REAL DEFAULT 0.0,
                km_recorridos_ciclo REAL DEFAULT 0.0,
                km_acumulados_total REAL DEFAULT 0.0,
                costo_compra_original REAL DEFAULT 1450000.0,
                costo_ciclo_actual REAL DEFAULT 1450000.0,
                costo_reparaciones_ciclo_actual REAL DEFAULT 0.0,
                costo_acumulado_total REAL DEFAULT 1450000.0,
                reservada_para_placa TEXT DEFAULT NULL,
                reservada_posicion INTEGER DEFAULT NULL,
                fecha_envio_planta TEXT DEFAULT NULL,
                proveedor_actual TEXT DEFAULT '',
                causal_baja_fvu TEXT DEFAULT '',
                mm_perdidos_fvu REAL DEFAULT 0.0,
                dinero_perdido_fvu REAL DEFAULT 0.0,
                estado_garantia TEXT DEFAULT 'No Aplica', -- 'No Aplica', 'Posible Garantía', 'En Reclamación', 'Nota Crédito Reconocida', 'Rechazada'
                valor_reconocido_garantia REAL DEFAULT 0.0,
                numero_acta_ambiental TEXT DEFAULT '',
                fecha_disposicion TEXT DEFAULT NULL,
                observaciones TEXT DEFAULT '',
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cliente, numero_interno)
            )
        """)

        # Tabla de Kardex Histórico de Movimientos entre Bodegas y Vehículos
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kardex_movimientos_llanta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_movimiento TEXT NOT NULL,
                cliente TEXT NOT NULL,
                subcliente TEXT DEFAULT '',
                numero_interno TEXT NOT NULL,
                bodega_origen TEXT NOT NULL,
                bodega_destino TEXT NOT NULL,
                tipo_movimiento TEXT NOT NULL, -- 'ALTA_NUEVA', 'MONTAJE', 'DESMONTE_RECAMBIO', 'ENVIO_REENCAUCHE', 'RETORNO_REENCAUCHE', 'ENVIO_REPARACION', 'RETORNO_REPARACION', 'BAJA_FVU', 'CHATARRIZACION', 'AJUSTE_GARANTIA'
                placa TEXT DEFAULT '',
                posicion INTEGER DEFAULT 0,
                vida_ciclo TEXT DEFAULT 'Original',
                prof_min_mm REAL DEFAULT 0.0,
                km_vehiculo REAL DEFAULT 0.0,
                costo_asociado REAL DEFAULT 0.0,
                proveedor TEXT DEFAULT '',
                causal_o_motivo TEXT DEFAULT '',
                documento_soporte TEXT DEFAULT '',
                usuario_registro TEXT DEFAULT 'admin',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_llantas_maestro_cliente_bodega ON llantas_maestro (cliente, ubicacion_bodega, dimension)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_llantas_maestro_serial ON llantas_maestro (numero_interno, cliente)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kardex_serial_cliente ON kardex_movimientos_llanta (cliente, numero_interno, fecha_movimiento DESC)")

        # Tabla de Catálogo de Operaciones
        conn.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_operaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM catalogo_operaciones")
        if cursor.fetchone()[0] == 0:
            operaciones_seed = [
                ('CARGA SECA',),
                ('REFRIGERADO',),
                ('LÍQUIDOS',),
                ('PAQUETERÍA',),
                ('URBANO',),
                ('INTERMUNICIPAL',),
                ('TRANSPORTE DE PERSONAL',),
                ('VOLQUETA / CONSTRUCCIÓN',),
                ('OPERACIÓN MIXTA',)
            ]
            cursor.executemany("INSERT OR IGNORE INTO catalogo_operaciones (nombre) VALUES (?)", operaciones_seed)

        # Tabla de Catálogo de Tipologías
        conn.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_tipologias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                descripcion TEXT,
                cant_llantas INTEGER,
                esquema_json TEXT,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM catalogo_tipologias")
        if cursor.fetchone()[0] == 0:
            for s_path in ["seed_inspecciones.db", "data/inspecciones.db", os.path.join(os.path.dirname(__file__), "seed_inspecciones.db")]:
                if os.path.exists(s_path) and os.path.abspath(s_path) != os.path.abspath(DB_PATH):
                    try:
                        s_conn = sqlite3.connect(s_path)
                        s_cur = s_conn.cursor()
                        s_cur.execute("SELECT nombre, descripcion, cant_llantas, esquema_json FROM catalogo_tipologias")
                        rows = s_cur.fetchall()
                        cursor.executemany("INSERT OR IGNORE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, ?, ?, ?)", rows)
                        s_conn.close()
                        break
                    except Exception:
                        pass

        # Tabla de Catálogo de Llantas Nuevas y Reencauches (con profundidad inicial de fábrica)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_modelos_llantas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_llanta TEXT NOT NULL, /* Nueva / Reencauche */
                marca TEXT NOT NULL,
                diseno TEXT NOT NULL,
                dimension TEXT NOT NULL,
                prof_inicial REAL NOT NULL,
                descripcion TEXT,
                UNIQUE(tipo_llanta, marca, diseno, dimension)
            )
        """)
        
        # Poblar modelos estándar si está vacía
        cursor.execute("SELECT COUNT(*) FROM catalogo_modelos_llantas")
        if cursor.fetchone()[0] == 0:
            modelos_seed = [
                # Llantas Nuevas Originales
                ('Nueva', 'Michelin', 'X Multi D', '295/80R22.5', 21.5, 'Tracción Regional'),
                ('Nueva', 'Michelin', 'X Multi Z', '295/80R22.5', 16.5, 'Toda Posición / Direccional'),
                ('Nueva', 'Bridgestone', 'M726 EL', '295/80R22.5', 24.5, 'Tracción Larga Distancia'),
                ('Nueva', 'Bridgestone', 'R268 Ecopia', '295/80R22.5', 16.0, 'Direccional / Toda Posición'),
                ('Nueva', 'Goodyear', 'KMax D', '295/80R22.5', 22.0, 'Tracción Carretera'),
                ('Nueva', 'Goodyear', 'KMax S', '295/80R22.5', 16.0, 'Direccional Autopista'),
                ('Nueva', 'Pirelli', 'TG01', '295/80R22.5', 22.5, 'Tracción Mixta'),
                ('Nueva', 'Pirelli', 'FG01', '295/80R22.5', 16.5, 'Direccional Mixta'),
                ('Nueva', 'Hankook', 'DH35', '295/80R22.5', 20.5, 'Tracción Regional'),
                ('Nueva', 'Hankook', 'AH35', '295/80R22.5', 15.5, 'Direccional'),
                ('Nueva', 'Double Coin', 'RLB450', '11R22.5', 22.0, 'Tracción'),
                ('Nueva', 'Double Coin', 'RR9', '11R22.5', 15.0, 'Direccional'),
                # Reencauches / Bandas
                ('Reencauche', 'Bandag', 'BDM', '295/80R22.5', 21.0, 'Banda Tracción Alta Adherencia'),
                ('Reencauche', 'Bandag', 'B710', '295/80R22.5', 20.0, 'Banda Tracción Carretera'),
                ('Reencauche', 'Bandag', 'ECL Drive', '295/80R22.5', 22.0, 'Tracción Severa'),
                ('Reencauche', 'Bandag', 'B197 Trailer', '295/80R22.5', 14.5, 'Banda Trailer / Arrastre'),
                ('Reencauche', 'Marangoni', 'Ringtread RD-G', '295/80R22.5', 21.5, 'Anillo Tracción'),
                ('Reencauche', 'Marangoni', 'RTL Energeia', '295/80R22.5', 14.0, 'Anillo Remolque/Trailer'),
                ('Reencauche', 'Vipal', 'VT100', '295/80R22.5', 19.5, 'Tracción Urbana y Regional'),
                ('Reencauche', 'Vipal', 'VL110', '295/80R22.5', 14.0, 'Arrastre Liviano y Pesado')
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO catalogo_modelos_llantas (tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion)
                VALUES (?, ?, ?, ?, ?, ?)
            """, modelos_seed)

        # Tabla Maestra de Asociación Placa <-> Vehículo (Tipología, Cliente, etc.)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_vehiculos (
                placa TEXT PRIMARY KEY,
                tipologia TEXT NOT NULL,
                cliente TEXT DEFAULT '',
                subcliente TEXT DEFAULT '',
                tipo_operacion TEXT DEFAULT '',
                ultimo_km REAL DEFAULT 0.0,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migración automática inicial (Backfill): poblar catalogo_vehiculos desde inspecciones históricas
        cursor.execute("""
            INSERT OR IGNORE INTO catalogo_vehiculos (placa, tipologia, cliente, subcliente, tipo_operacion, ultimo_km, fecha_actualizacion)
            SELECT i.placa, i.tipologia, 
                   IFNULL(i.cliente, ''), 
                   IFNULL(i.subcliente, ''), 
                   IFNULL(i.tipo_operacion, ''), 
                   IFNULL(MAX(i.kilometraje), 0.0), 
                   CURRENT_TIMESTAMP
            FROM inspecciones i
            WHERE i.placa IS NOT NULL AND TRIM(i.placa) != '' AND i.tipologia IS NOT NULL AND TRIM(i.tipologia) != ''
            GROUP BY i.placa
        """)

        # Índices compuestos para optimizar búsquedas por placa, posición, fecha, número interno y cliente
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inspecciones_placa_pos_fecha ON inspecciones (placa, posicion, fecha DESC, id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inspecciones_placa_fecha ON inspecciones (placa, fecha DESC, id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inspecciones_num_interno ON inspecciones (numero_interno, cliente)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inspecciones_cliente_fecha ON inspecciones (cliente, subcliente, fecha)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_limites_retiro_busqueda ON configuracion_limites_retiro (cliente, subcliente, eje)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_marcas_cliente ON configuracion_marcas_cliente (cliente)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_padron_cliente ON padron_vehiculos_cliente (cliente, activo)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_config_avanzada_cliente ON configuracion_avanzada_cliente (cliente)")

        # Normalización automática: asegurar que todos los clientes estén en mayúsculas
        normalizar_clientes_mayusculas(conn)

        # Migración automática producción: PEPSICO FUNZA -> Cliente TELLANTAS, Sede PEPSICO FUNZA
        migrar_pepsico_a_tellantas(conn)

        # Ajuste de kilometraje específico para la placa S87341 solicitada para producción
        migrar_kilometraje_placa_s87341(conn)

        # Sincronización automática inicial (Backfill) de llantas_maestro desde inspecciones históricas
        sincronizar_maestro_desde_inspecciones(conn)

        conn.commit()

def normalizar_clientes_mayusculas(conn):
    """
    Normalización y migración automática para asegurar que todos los nombres de clientes
    y subclientes estén estrictamente en mayúsculas y sin duplicados en todas las tablas.
    """
    cursor = conn.cursor()
    # 1. Tabla inspecciones
    cursor.execute("UPDATE inspecciones SET cliente = UPPER(TRIM(cliente)) WHERE cliente IS NOT NULL AND cliente != UPPER(TRIM(cliente))")
    cursor.execute("UPDATE inspecciones SET subcliente = UPPER(TRIM(subcliente)) WHERE subcliente IS NOT NULL AND subcliente != UPPER(TRIM(subcliente))")

    # 2. Tabla catalogo_vehiculos
    cursor.execute("UPDATE catalogo_vehiculos SET cliente = UPPER(TRIM(cliente)) WHERE cliente IS NOT NULL AND cliente != UPPER(TRIM(cliente))")
    cursor.execute("UPDATE catalogo_vehiculos SET subcliente = UPPER(TRIM(subcliente)) WHERE subcliente IS NOT NULL AND subcliente != UPPER(TRIM(subcliente))")

    # 3. Tabla configuracion_clientes (PRIMARY KEY cliente)
    cursor.execute("SELECT cliente, limite_retiro_mm, observaciones, fecha_actualizacion FROM configuracion_clientes")
    for cli, lim, obs, f_act in cursor.fetchall():
        if cli:
            cli_up = cli.strip().upper()
            if cli != cli_up:
                cursor.execute("DELETE FROM configuracion_clientes WHERE cliente = ?", (cli,))
                cursor.execute("""
                    INSERT OR REPLACE INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
                    VALUES (?, ?, ?, ?)
                """, (cli_up, lim, obs, f_act))

    # 4. Tabla configuracion_limites_retiro (UNIQUE cliente, subcliente, eje)
    cursor.execute("SELECT id, cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion FROM configuracion_limites_retiro")
    for rid, cli, sub, eje, lim, obs, f_act in cursor.fetchall():
        if cli:
            cli_up = cli.strip().upper()
            sub_up = (sub or 'TODOS').strip().upper()
            eje_up = (eje or 'TODOS').strip().upper()
            if cli != cli_up or sub != sub_up or eje != eje_up:
                cursor.execute("DELETE FROM configuracion_limites_retiro WHERE id = ?", (rid,))
                cursor.execute("""
                    INSERT OR IGNORE INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cli_up, sub_up, eje_up, lim, obs, f_act))

    # 5. Tabla usuarios (cliente_asignado)
    cursor.execute("SELECT id, cliente_asignado FROM usuarios")
    for uid, c_asig in cursor.fetchall():
        if c_asig:
            vistos = set()
            clis_up = []
            for c in str(c_asig).split(','):
                clean = c.strip().upper()
                if clean and clean not in vistos:
                    vistos.add(clean)
                    clis_up.append(clean)
            nuevo_str = ', '.join(clis_up)
            if nuevo_str != str(c_asig).strip():
                cursor.execute("UPDATE usuarios SET cliente_asignado = ? WHERE id = ?", (nuevo_str, uid))

    # 6. Tabla configuracion_marcas_cliente
    cursor.execute("UPDATE configuracion_marcas_cliente SET cliente = UPPER(TRIM(cliente)) WHERE cliente IS NOT NULL AND cliente != UPPER(TRIM(cliente))")

    # 7. Sincronización automática de clientes detectados a configuracion_clientes y configuracion_avanzada_cliente
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llantas_maestro'")
        tiene_maestro = cursor.fetchone() is not None
        union_maestro = "UNION SELECT cliente FROM llantas_maestro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''" if tiene_maestro else ""
        cursor.execute(f"""
            INSERT OR IGNORE INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
            SELECT DISTINCT UPPER(TRIM(cliente)), 3.0, 'Cliente migrado automáticamente', CURRENT_TIMESTAMP
            FROM (
                SELECT cliente FROM inspecciones WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_limites_retiro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                {union_maestro}
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion)
            SELECT DISTINCT UPPER(TRIM(cliente)), 'PRO', 4.0, 3.0, 3.0, CURRENT_TIMESTAMP
            FROM configuracion_clientes
        """)
    except Exception:
        pass

    # 8. Migración y normalización preventiva de la columna 'vida'
    try:
        migrar_normalizar_vida_llantas(conn)
    except Exception as e:
        print(f"[INICIALIZAR_BD] Advertencia normalizando vida llantas: {e}")


def migrar_pepsico_a_tellantas(conn=None):
    """
    Migración automática para Producción:
    Todo registro donde el cliente sea 'PEPSICO FUNZA' (o variaciones de PEPSICO con FUNZA)
    se actualiza para que:
      - cliente = 'TELLANTAS'
      - subcliente / sede = 'PEPSICO FUNZA'
    Afecta todas las tablas operativas, catálogos, configuraciones y usuarios asignados.
    """
    if conn is None:
        with get_connection() as c_auto:
            return migrar_pepsico_a_tellantas(c_auto)

    try:
        cur = conn.cursor()

        # 1. Tabla inspecciones
        cur.execute("""
            UPDATE inspecciones
            SET cliente = 'TELLANTAS', subcliente = 'PEPSICO FUNZA'
            WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
               OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
               OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
        """)
        insps_afectadas = cur.rowcount

        # 2. Tabla catalogo_vehiculos
        cur.execute("""
            UPDATE catalogo_vehiculos
            SET cliente = 'TELLANTAS', subcliente = 'PEPSICO FUNZA'
            WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
               OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
               OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
        """)
        vehs_afectados = cur.rowcount

        # 3. Tabla llantas_maestro
        try:
            cur.execute("""
                UPDATE llantas_maestro
                SET cliente = 'TELLANTAS', subcliente = 'PEPSICO FUNZA'
                WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                   OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                   OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
            """)
        except Exception:
            pass

        # 4. Tabla kardex_movimientos_llanta
        try:
            cur.execute("""
                UPDATE kardex_movimientos_llanta
                SET cliente = 'TELLANTAS', subcliente = 'PEPSICO FUNZA'
                WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                   OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                   OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
            """)
        except Exception:
            pass

        # 5. Tabla padron_vehiculos_cliente
        try:
            cur.execute("""
                UPDATE padron_vehiculos_cliente
                SET cliente = 'TELLANTAS', subcliente = 'PEPSICO FUNZA'
                WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                   OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                   OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
            """)
        except Exception:
            pass

        # 6. Tabla configuracion_limites_retiro (UNIQUE cliente, subcliente, eje)
        try:
            cur.execute("""
                SELECT id, cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion
                FROM configuracion_limites_retiro
                WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                   OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                   OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
            """)
            for rid, cli, sub, eje, lim, obs, f_act in cur.fetchall():
                cur.execute("DELETE FROM configuracion_limites_retiro WHERE id = ?", (rid,))
                cur.execute("""
                    INSERT OR IGNORE INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
                    VALUES ('TELLANTAS', 'PEPSICO FUNZA', ?, ?, ?, ?)
                """, (eje or 'TODOS', lim, obs, f_act))
        except Exception:
            pass

        # 7. Tabla configuracion_marcas_cliente (PRIMARY KEY cliente)
        try:
            cur.execute("""
                SELECT cliente, marcas_habituales FROM configuracion_marcas_cliente
                WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                   OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
            """)
            marcas_pepsico = cur.fetchall()
            for cli_p, m_hab in marcas_pepsico:
                cur.execute("DELETE FROM configuracion_marcas_cliente WHERE cliente = ?", (cli_p,))
                cur.execute("SELECT marcas_habituales FROM configuracion_marcas_cliente WHERE cliente = 'TELLANTAS'")
                row_t = cur.fetchone()
                if row_t:
                    m_prev = [x.strip() for x in (row_t[0] or '').split(',') if x.strip()]
                    m_new = [x.strip() for x in (m_hab or '').split(',') if x.strip()]
                    m_fusion = list(dict.fromkeys(m_prev + m_new))
                    cur.execute("UPDATE configuracion_marcas_cliente SET marcas_habituales = ? WHERE cliente = 'TELLANTAS'", (', '.join(m_fusion),))
                else:
                    cur.execute("INSERT OR REPLACE INTO configuracion_marcas_cliente (cliente, marcas_habituales) VALUES ('TELLANTAS', ?)", (m_hab,))
        except Exception:
            pass

        # 8. Tabla configuracion_clientes (PRIMARY KEY cliente)
        try:
            cur.execute("SELECT limite_retiro_mm, observaciones, fecha_actualizacion FROM configuracion_clientes WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA' OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'")
            row_cfg = cur.fetchone()
            if row_cfg:
                cur.execute("DELETE FROM configuracion_clientes WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA' OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'")
                cur.execute("INSERT OR IGNORE INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion) VALUES ('TELLANTAS', ?, ?, ?)", (row_cfg[0], row_cfg[1], row_cfg[2]))
            else:
                cur.execute("INSERT OR IGNORE INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion) VALUES ('TELLANTAS', 3.0, 'Configuración cliente TELLANTAS', CURRENT_TIMESTAMP)")
        except Exception:
            pass

        # 9. Tabla configuracion_avanzada_cliente (PRIMARY KEY cliente)
        try:
            cur.execute("SELECT tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion FROM configuracion_avanzada_cliente WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA' OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'")
            row_av = cur.fetchone()
            if row_av:
                cur.execute("DELETE FROM configuracion_avanzada_cliente WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA' OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'")
                cur.execute("INSERT OR IGNORE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion) VALUES ('TELLANTAS', ?, ?, ?, ?, ?)", row_av)
            else:
                cur.execute("INSERT OR IGNORE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion) VALUES ('TELLANTAS', 'PRO', 4.0, 3.0, 3.0, CURRENT_TIMESTAMP)")
        except Exception:
            pass

        # 10. Tabla usuarios (cliente_asignado)
        try:
            cur.execute("SELECT id, cliente_asignado FROM usuarios WHERE cliente_asignado IS NOT NULL AND cliente_asignado != ''")
            for uid, c_asig in cur.fetchall():
                if not c_asig:
                    continue
                clis = [c.strip().upper() for c in str(c_asig).split(',') if c.strip()]
                tiene_pepsico = any('PEPSICO' in c and 'FUNZA' in c for c in clis) or any(c == 'PEPSICO FUNZA' for c in clis)
                if tiene_pepsico:
                    nuevos = []
                    for c in clis:
                        if ('PEPSICO' in c and 'FUNZA' in c) or c == 'PEPSICO FUNZA':
                            if 'TELLANTAS' not in nuevos:
                                nuevos.append('TELLANTAS')
                        else:
                            if c not in nuevos:
                                nuevos.append(c)
                    nuevo_str = ', '.join(nuevos)
                    cur.execute("UPDATE usuarios SET cliente_asignado = ? WHERE id = ?", (nuevo_str, uid))
        except Exception:
            pass

        # 11. Búsqueda y actualización dinámica en cualquier otra tabla que exista en la BD
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        todas_tablas = [r[0] for r in cur.fetchall()]
        tablas_gestionadas = {'inspecciones', 'catalogo_vehiculos', 'llantas_maestro', 'kardex_movimientos_llanta', 'padron_vehiculos_cliente', 'configuracion_limites_retiro', 'configuracion_marcas_cliente', 'configuracion_clientes', 'configuracion_avanzada_cliente', 'usuarios'}
        for t in todas_tablas:
            if t.startswith('sqlite_') or t in tablas_gestionadas:
                continue
            try:
                cur.execute(f"PRAGMA table_info({t})")
                cols = [c[1].lower() for c in cur.fetchall()]
                if 'cliente' in cols and 'subcliente' in cols:
                    cur.execute(f"""
                        UPDATE {t}
                        SET cliente = 'TELLANTAS', subcliente = 'PEPSICO FUNZA'
                        WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                           OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                           OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(subcliente, ''))) LIKE '%FUNZA%')
                    """)
                elif 'cliente' in cols and 'sede' in cols:
                    cur.execute(f"""
                        UPDATE {t}
                        SET cliente = 'TELLANTAS', sede = 'PEPSICO FUNZA'
                        WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                           OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                           OR (UPPER(TRIM(cliente)) = 'PEPSICO' AND UPPER(TRIM(IFNULL(sede, ''))) LIKE '%FUNZA%')
                    """)
                elif 'cliente' in cols:
                    cur.execute(f"""
                        UPDATE {t}
                        SET cliente = 'TELLANTAS'
                        WHERE UPPER(TRIM(cliente)) = 'PEPSICO FUNZA'
                           OR UPPER(TRIM(cliente)) LIKE 'PEPSICO%FUNZA%'
                    """)
            except Exception:
                pass

        conn.commit()
        print(f"[MIGRACION PRODUCCION] [OK] Migracion PEPSICO FUNZA -> TELLANTAS ejecutada. Inspecciones: {insps_afectadas}, Vehiculos: {vehs_afectados}")
        return {
            "status": "ok",
            "inspecciones_actualizadas": insps_afectadas,
            "vehiculos_actualizados": vehs_afectados
        }
    except Exception as e:
        print(f"[MIGRACION PRODUCCION] [ALERTA] Error en migracion: {e}")
        return {"status": "error", "error": str(e)}


def migrar_kilometraje_placa_s87341(conn=None):
    """
    Actualización directa en producción para la placa S87341:
    Ajusta el kilometraje a 23589 para todos los registros de la placa S87341,
    tanto en la tabla inspecciones como en catalogo_vehiculos.
    """
    if conn is None:
        with get_connection() as c_auto:
            return migrar_kilometraje_placa_s87341(c_auto)
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE inspecciones 
            SET kilometraje = 23589 
            WHERE UPPER(TRIM(placa)) = 'S87341'
        """)
        insps = cur.rowcount

        try:
            cur.execute("""
                UPDATE catalogo_vehiculos 
                SET ultimo_km = 23589 
                WHERE UPPER(TRIM(placa)) = 'S87341'
            """)
            vehs = cur.rowcount
        except Exception:
            vehs = 0

        conn.commit()
        if insps > 0 or vehs > 0:
            print(f"[MIGRACION PRODUCCION] Placa S87341 actualizada a 23589 km exitosamente ({insps} inspecciones, {vehs} vehículos en catálogo).")
        return {
            "status": "ok",
            "placa": "S87341",
            "nuevo_kilometraje": 23589,
            "inspecciones_actualizadas": insps,
            "vehiculos_actualizados": vehs
        }
    except Exception as e:
        print(f"[MIGRACION PRODUCCION] Error actualizando kilometraje S87341: {e}")
        return {"status": "error", "error": str(e)}


def migrar_normalizar_vida_llantas(conn=None):
    """
    Normalización y reparación preventiva de la columna 'vida' en inspecciones y tablas maestras:
    1. Si 'vida' es nula, vacía o '-', y tiene banda de reencauche asignada, se establece 'REENCAUCHE'.
    2. Si 'vida' es nula, vacía o '-', y NO tiene banda de reencauche, se establece 'ORIGINAL'.
    3. Normaliza variantes ('ORIG', 'NUEVA', 'REEN', etc.) a mayúsculas estándar 'ORIGINAL' y 'REENCAUCHE'.
    4. Garantiza que llantas_maestro y kardex_ciclo_vida tengan valores coherentes.
    """
    if conn is None:
        with get_connection() as c_auto:
            return migrar_normalizar_vida_llantas(c_auto)
    try:
        cur = conn.cursor()

        # 1. Asignar REENCAUCHE a los que no tienen vida válida pero sí tienen banda registrada
        cur.execute("""
            UPDATE inspecciones
            SET vida = 'REENCAUCHE'
            WHERE (vida IS NULL OR TRIM(vida) = '' OR TRIM(vida) = '-' OR UPPER(TRIM(vida)) IN ('NONE', 'NAN', 'NULL'))
              AND banda_reen IS NOT NULL
              AND TRIM(banda_reen) != ''
              AND TRIM(banda_reen) != '-'
              AND UPPER(TRIM(banda_reen)) NOT IN ('NONE', 'NAN', 'NULL')
        """)
        reencauches_corregidos = cur.rowcount

        # 2. Asignar ORIGINAL al resto de registros sin vida válida
        cur.execute("""
            UPDATE inspecciones
            SET vida = 'ORIGINAL'
            WHERE vida IS NULL
               OR TRIM(vida) = ''
               OR TRIM(vida) = '-'
               OR UPPER(TRIM(vida)) IN ('NONE', 'NAN', 'NULL')
        """)
        originales_corregidos = cur.rowcount

        # 3. Normalizar variantes a mayúsculas estándar
        cur.execute("""
            UPDATE inspecciones
            SET vida = 'ORIGINAL'
            WHERE UPPER(TRIM(vida)) IN ('ORIGINAL', 'ORIG', 'NUEVA', 'ORIGINAL (NUEVA)') AND vida != 'ORIGINAL'
        """)

        cur.execute("""
            UPDATE inspecciones
            SET vida = 'REENCAUCHE'
            WHERE UPPER(TRIM(vida)) IN ('REENCAUCHE', 'REEN', 'RECAUCHE', 'R1', 'R2', 'R3', 'R4') AND vida != 'REENCAUCHE'
        """)

        # 4. Asegurar coherencia en llantas_maestro
        try:
            cur.execute("""
                UPDATE llantas_maestro
                SET vida_actual = 'Original'
                WHERE vida_actual IS NULL OR TRIM(vida_actual) = '' OR TRIM(vida_actual) = '-' OR UPPER(TRIM(vida_actual)) IN ('NONE', 'NAN')
            """)
        except Exception:
            pass

        # 5. Asegurar coherencia en kardex_ciclo_vida
        try:
            cur.execute("""
                UPDATE kardex_ciclo_vida
                SET vida_ciclo = 'Original'
                WHERE vida_ciclo IS NULL OR TRIM(vida_ciclo) = '' OR TRIM(vida_ciclo) = '-' OR UPPER(TRIM(vida_ciclo)) IN ('NONE', 'NAN')
            """)
        except Exception:
            pass

        conn.commit()
        total_corregidos = reencauches_corregidos + originales_corregidos
        if total_corregidos > 0:
            print(f"[MIGRACION VIDA] Se corrigieron {total_corregidos} inspecciones sin vida registrada "
                  f"({originales_corregidos} Originales, {reencauches_corregidos} Reencauches).")
        return {
            "status": "ok",
            "originales_corregidos": originales_corregidos,
            "reencauches_corregidos": reencauches_corregidos,
            "total": total_corregidos
        }
    except Exception as e:
        print(f"[MIGRACION VIDA ERROR] Error al normalizar vida de inspecciones: {e}")
        return {"status": "error", "error": str(e)}


def sincronizar_kilometraje_por_vehiculo_y_fecha(conn=None):
    """
    Sincroniza y propaga el kilometraje de cada inspección a todas las llantas del mismo vehículo
    en la misma fecha de inspección. Si una llanta tiene kilometraje > 0, todas las demás llantas
    de esa misma placa y fecha deben tener exactamente ese mismo kilometraje.
    """
    def _ejecutar(c):
        cur = c.cursor()
        cur.execute("""
            SELECT UPPER(TRIM(placa)), SUBSTR(fecha, 1, 10), MAX(kilometraje)
            FROM inspecciones
            WHERE kilometraje > 0 AND placa IS NOT NULL AND TRIM(placa) != ''
            GROUP BY UPPER(TRIM(placa)), SUBSTR(fecha, 1, 10)
        """)
        grupos = cur.fetchall()
        actualizados = 0
        for pl, f_dia, max_km in grupos:
            if max_km and max_km > 0:
                cur.execute("""
                    UPDATE inspecciones
                    SET kilometraje = ?
                    WHERE UPPER(TRIM(placa)) = ?
                      AND SUBSTR(fecha, 1, 10) = ?
                      AND (kilometraje != ? OR kilometraje IS NULL OR kilometraje = 0)
                """, (max_km, pl, f_dia, max_km))
                actualizados += cur.rowcount
                cur.execute("""
                    UPDATE catalogo_vehiculos
                    SET ultimo_km = MAX(COALESCE(ultimo_km, 0), ?)
                    WHERE UPPER(TRIM(placa)) = ?
                """, (max_km, pl))
        if actualizados > 0:
            print(f"[SINCRONIZAR KM] Se unificó el kilometraje en {actualizados} llantas de inspecciones previas.")
        return actualizados

    if conn is not None:
        return _ejecutar(conn)
    with get_connection() as c:
        res = _ejecutar(c)
        c.commit()
        return res


def migrar_restar_pext_ciudad_limpia(conn=None, forzar=False):
    """
    Ajuste en producción para el cliente CIUDAD LIMPIA BOGOTA:
    Resta 1 al campo prof_ext (P.Ext) de todos los registros de inspecciones y llantas_maestro.
    Ejemplo: si prof_ext es 18, queda en 17.
    Usa la tabla _control_migraciones para garantizar ejecución idempotente (exactamente una vez),
    a menos que se invoque con forzar=True.
    """
    def _ejecutar(c):
        cur = c.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _control_migraciones (
                nombre TEXT PRIMARY KEY,
                fecha_ejecucion TEXT,
                filas_afectadas INTEGER
            )
        """)
        if not forzar:
            cur.execute("SELECT filas_afectadas FROM _control_migraciones WHERE nombre = 'restar_pext_ciudad_limpia_v1'")
            ya_ejecutado = cur.fetchone()
            if ya_ejecutado is not None:
                return {"status": "already_applied", "filas_afectadas": ya_ejecutado[0]}

        cur.execute("""
            UPDATE inspecciones
            SET prof_ext = CASE 
                WHEN CAST(prof_ext AS REAL) > 0 THEN ROUND(CAST(prof_ext AS REAL) - 1, 2)
                ELSE 0 
            END
            WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                   OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA' 
                   OR UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%')
              AND prof_ext IS NOT NULL
        """)
        insps_afectadas = cur.rowcount

        maestro_afectadas = 0
        try:
            cur.execute("""
                UPDATE llantas_maestro
                SET prof_ext = CASE 
                    WHEN CAST(prof_ext AS REAL) > 0 THEN ROUND(CAST(prof_ext AS REAL) - 1, 2)
                    ELSE 0 
                END,
                prof_actual_min = MIN(
                    CASE WHEN CAST(prof_ext AS REAL) > 0 THEN ROUND(CAST(prof_ext AS REAL) - 1, 2) ELSE 0 END,
                    IFNULL(prof_cent, 999),
                    IFNULL(prof_int, 999)
                )
                WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA' 
                       OR UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%')
                  AND prof_ext IS NOT NULL
            """)
            maestro_afectadas = cur.rowcount
        except Exception as e_m:
            print(f"[MIGRACION P.EXT] Nota en llantas_maestro: {e_m}")

        total = insps_afectadas + maestro_afectadas
        cur.execute("""
            INSERT INTO _control_migraciones (nombre, fecha_ejecucion, filas_afectadas)
            VALUES ('restar_pext_ciudad_limpia_v1', datetime('now'), ?)
            ON CONFLICT(nombre) DO UPDATE SET fecha_ejecucion = datetime('now'), filas_afectadas = ?
        """, (total, total))

        if insps_afectadas > 0 or maestro_afectadas > 0:
            print(f"[MIGRACION PRODUCCION] Cliente CIUDAD LIMPIA: Restado 1 a P.Ext en {insps_afectadas} inspecciones y {maestro_afectadas} llantas en maestro.")
        return {
            "status": "ok",
            "inspecciones_actualizadas": insps_afectadas,
            "maestro_actualizadas": maestro_afectadas,
            "total_afectadas": total
        }

    if conn is not None:
        return _ejecutar(conn)
    with get_connection() as c:
        res = _ejecutar(c)
        c.commit()
        return res


def migrar_normalizar_cliente_ciudad_limpia_bogota(conn=None, forzar=False):
    """
    Ajuste en producción para CIUDAD LIMPIA BOGOTA:
    Normaliza el nombre del cliente para que sea únicamente 'CIUDAD LIMPIA'
    y la sede/subcliente sea únicamente 'BOGOTA' en todos los registros.
    Garantiza idempotencia a través de _control_migraciones.
    """
    def _ejecutar(c):
        cur = c.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _control_migraciones (
                nombre TEXT PRIMARY KEY,
                fecha_ejecucion TEXT,
                filas_afectadas INTEGER
            )
        """)
        if not forzar:
            cur.execute("SELECT filas_afectadas FROM _control_migraciones WHERE nombre = 'normalizar_cliente_ciudad_limpia_bogota_v1'")
            ya_ejecutado = cur.fetchone()
            if ya_ejecutado is not None:
                return {"status": "already_applied", "filas_afectadas": ya_ejecutado[0]}

        # 1. Actualizar inspecciones
        cur.execute("""
            UPDATE inspecciones
            SET cliente = 'CIUDAD LIMPIA',
                subcliente = 'BOGOTA'
            WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                   OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTÁ' 
                   OR UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%'
                   OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA')
              AND (cliente != 'CIUDAD LIMPIA' OR IFNULL(subcliente, '') != 'BOGOTA')
        """)
        insps_afectadas = cur.rowcount

        # 2. Actualizar llantas_maestro
        maestro_afectadas = 0
        try:
            cur.execute("""
                UPDATE llantas_maestro
                SET cliente = 'CIUDAD LIMPIA',
                    subcliente = 'BOGOTA'
                WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTÁ' 
                       OR UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%'
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA')
                  AND (cliente != 'CIUDAD LIMPIA' OR IFNULL(subcliente, '') != 'BOGOTA')
            """)
            maestro_afectadas = cur.rowcount
        except Exception as e_m:
            print(f"[MIGRACION CLIENTE/SEDE] Nota en llantas_maestro: {e_m}")

        # 3. Actualizar kardex_movimientos_llanta
        kardex_afectadas = 0
        try:
            cur.execute("""
                UPDATE kardex_movimientos_llanta
                SET cliente = 'CIUDAD LIMPIA',
                    subcliente = 'BOGOTA'
                WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTÁ' 
                       OR UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%'
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA')
                  AND (cliente != 'CIUDAD LIMPIA' OR IFNULL(subcliente, '') != 'BOGOTA')
            """)
            kardex_afectadas = cur.rowcount
        except Exception as e_k:
            print(f"[MIGRACION CLIENTE/SEDE] Nota en kardex: {e_k}")

        # 4. Actualizar padron_vehiculos_cliente
        padron_afectadas = 0
        try:
            cur.execute("""
                UPDATE OR IGNORE padron_vehiculos_cliente
                SET cliente = 'CIUDAD LIMPIA',
                    subcliente = 'BOGOTA'
                WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTÁ' 
                       OR UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%')
                  AND (cliente != 'CIUDAD LIMPIA' OR IFNULL(subcliente, '') != 'BOGOTA')
            """)
            padron_afectadas = cur.rowcount
            cur.execute("""
                DELETE FROM padron_vehiculos_cliente
                WHERE (UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTA' 
                       OR UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA BOGOTÁ' 
                       OR (UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'))
            """)
        except Exception as e_p:
            print(f"[MIGRACION CLIENTE/SEDE] Nota en padron: {e_p}")

        # 5. Tablas de configuración
        try:
            cur.execute("""
                INSERT OR IGNORE INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
                SELECT 'CIUDAD LIMPIA', limite_retiro_mm, observaciones, fecha_actualizacion
                FROM configuracion_clientes
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'
            """)
            cur.execute("""
                DELETE FROM configuracion_clientes
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'
            """)
        except Exception:
            pass

        try:
            cur.execute("""
                INSERT OR IGNORE INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
                SELECT 'CIUDAD LIMPIA', 'BOGOTA', eje, limite_retiro_mm, observaciones, fecha_actualizacion
                FROM configuracion_limites_retiro
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND (cliente != 'CIUDAD LIMPIA' OR subcliente != 'BOGOTA')
            """)
            cur.execute("""
                DELETE FROM configuracion_limites_retiro
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND (cliente != 'CIUDAD LIMPIA' OR subcliente != 'BOGOTA')
            """)
        except Exception:
            pass

        try:
            cur.execute("""
                INSERT OR IGNORE INTO configuracion_marcas_cliente (cliente, marca, fecha_actualizacion)
                SELECT 'CIUDAD LIMPIA', marca, fecha_actualizacion
                FROM configuracion_marcas_cliente
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'
            """)
            cur.execute("""
                DELETE FROM configuracion_marcas_cliente
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'
            """)
        except Exception:
            pass

        try:
            cur.execute("""
                INSERT OR IGNORE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, rango_semaforo_amarillo_mm, criterio_profundidad_calculo, psi_objetivo_direccional, psi_objetivo_traccion, psi_objetivo_arrastre, tolerancia_psi_baja_pct, tolerancia_psi_alta_pct, tolerancia_desalineacion_hombros_mm, tolerancia_mal_apareo_pacha_mm, tolerancia_busqueda_recambio_mm, tolerancia_simetria_eje_opuesto_mm, margen_envio_reencauche_desmonte_mm, umbral_diferencia_rotacion_ejes_mm, diferencia_minima_par_direccional_mm, modo_rotacion_ejes, porcentaje_aprobacion_reencauche, stock_seguridad_default, plantilla_kpis_json, fecha_actualizacion)
                SELECT 'CIUDAD LIMPIA', tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, rango_semaforo_amarillo_mm, criterio_profundidad_calculo, psi_objetivo_direccional, psi_objetivo_traccion, psi_objetivo_arrastre, tolerancia_psi_baja_pct, tolerancia_psi_alta_pct, tolerancia_desalineacion_hombros_mm, tolerancia_mal_apareo_pacha_mm, tolerancia_busqueda_recambio_mm, tolerancia_simetria_eje_opuesto_mm, margen_envio_reencauche_desmonte_mm, umbral_diferencia_rotacion_ejes_mm, diferencia_minima_par_direccional_mm, modo_rotacion_ejes, porcentaje_aprobacion_reencauche, stock_seguridad_default, plantilla_kpis_json, fecha_actualizacion
                FROM configuracion_avanzada_cliente
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'
            """)
            cur.execute("""
                DELETE FROM configuracion_avanzada_cliente
                WHERE UPPER(TRIM(cliente)) LIKE 'CIUDAD LIMPIA%' AND cliente != 'CIUDAD LIMPIA'
            """)
        except Exception:
            pass

        try:
            cur.execute("""
                UPDATE usuarios
                SET cliente_asignado = REPLACE(REPLACE(cliente_asignado, 'CIUDAD LIMPIA BOGOTA', 'CIUDAD LIMPIA'), 'CIUDAD LIMPIA BOGOTÁ', 'CIUDAD LIMPIA')
                WHERE UPPER(cliente_asignado) LIKE '%CIUDAD LIMPIA BOGOTA%' OR UPPER(cliente_asignado) LIKE '%CIUDAD LIMPIA BOGOTÁ%'
            """)
        except Exception:
            pass

        total = insps_afectadas + maestro_afectadas + kardex_afectadas + padron_afectadas
        cur.execute("""
            INSERT INTO _control_migraciones (nombre, fecha_ejecucion, filas_afectadas)
            VALUES ('normalizar_cliente_ciudad_limpia_bogota_v1', datetime('now'), ?)
            ON CONFLICT(nombre) DO UPDATE SET fecha_ejecucion = datetime('now'), filas_afectadas = ?
        """, (total, total))

        if total > 0:
            print(f"[MIGRACION PRODUCCION] Cliente CIUDAD LIMPIA normalizado a sede BOGOTA en {insps_afectadas} inspecciones, {maestro_afectadas} llantas, {kardex_afectadas} kardex, {padron_afectadas} padrón.")
        return {
            "status": "ok",
            "inspecciones_actualizadas": insps_afectadas,
            "maestro_actualizadas": maestro_afectadas,
            "kardex_actualizadas": kardex_afectadas,
            "padron_actualizadas": padron_afectadas,
            "total_afectadas": total
        }

    if conn is not None:
        return _ejecutar(conn)
    with get_connection() as c:
        res = _ejecutar(c)
        c.commit()
        return res


def migrar_limite_ciudad_limpia_4mm(conn=None, forzar=False):
    """
    Ajuste en producción para CIUDAD LIMPIA:
    Configura el límite de cambio/retiro en 4.0 mm para todos los registros,
    posiciones y ejes en configuracion_limites_retiro, configuracion_clientes
    y configuracion_avanzada_cliente.
    Garantiza que cualquier ajuste posterior en el catálogo recalcule
    dinámicamente las proyecciones, semáforos e indicadores.
    """
    def _ejecutar(c):
        cur = c.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _control_migraciones (
                nombre TEXT PRIMARY KEY,
                fecha_ejecucion TEXT,
                filas_afectadas INTEGER
            )
        """)
        if not forzar:
            cur.execute("SELECT filas_afectadas FROM _control_migraciones WHERE nombre = 'limite_ciudad_limpia_4mm_v1'")
            ya_ejecutado = cur.fetchone()
            if ya_ejecutado is not None:
                return {"status": "already_applied", "filas_afectadas": ya_ejecutado[0]}

        cur.execute("DELETE FROM configuracion_limites_retiro WHERE UPPER(TRIM(cliente)) = 'CIUDAD LIMPIA'")
        cur.execute("""
            INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES ('CIUDAD LIMPIA', 'TODOS', 'TODOS', 4.0, 'POLITICA 4MM TODAS LAS POSICIONES', CURRENT_TIMESTAMP)
        """)

        cur.execute("""
            INSERT INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES ('CIUDAD LIMPIA', 4.0, 'POLITICA 4MM TODAS LAS POSICIONES', CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                limite_retiro_mm = 4.0,
                observaciones = 'POLITICA 4MM TODAS LAS POSICIONES',
                fecha_actualizacion = CURRENT_TIMESTAMP
        """)

        cur.execute("""
            INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion)
            VALUES ('CIUDAD LIMPIA', 4.0, 4.0, 4.0, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                mm_retiro_direccional = 4.0,
                mm_retiro_traccion = 4.0,
                mm_retiro_arrastre = 4.0,
                fecha_actualizacion = CURRENT_TIMESTAMP
        """)

        cur.execute("""
            INSERT INTO _control_migraciones (nombre, fecha_ejecucion, filas_afectadas)
            VALUES ('limite_ciudad_limpia_4mm_v1', datetime('now'), 1)
            ON CONFLICT(nombre) DO UPDATE SET fecha_ejecucion = datetime('now'), filas_afectadas = 1
        """)


        print("[MIGRACION PRODUCCION] Cliente CIUDAD LIMPIA configurado con límite universal de retiro de 4.0 mm.")
        return {
            "status": "ok",
            "reglas_configuradas": 1,
            "limite_retiro_mm": 4.0
        }

    if conn is not None:
        return _ejecutar(conn)
    with get_connection() as c:
        res = _ejecutar(c)
        c.commit()
        return res



def sincronizar_maestro_desde_inspecciones(conn=None):
    """
    Sincroniza automáticamente la tabla `llantas_maestro` desde el historial de `inspecciones`.
    Para cada combinación única de (cliente, numero_interno), toma el último estado registrado
    e inserta o actualiza la llanta en 'MONTADA_OPERACION' sin sobreescribir costos de reparaciones
    ni estados de garantía existentes.
    """
    def _ejecutar(c):
        c.execute("""
            SELECT cliente, numero_interno, placa, posicion, tipologia, marca, diseno, dimension,
                   vida, banda_reen, prof_ext, prof_cent, prof_int, psi, kilometraje, km_montaje,
                   precio, prof_inicial, subcliente, tipo_operacion, fecha, id
            FROM inspecciones
            WHERE numero_interno IS NOT NULL AND TRIM(numero_interno) != ''
              AND UPPER(TRIM(numero_interno)) != 'SN'
              AND cliente IS NOT NULL AND TRIM(cliente) != ''
            ORDER BY fecha ASC, id ASC
        """)
        filas = c.fetchall()
        if not filas:
            return

        # Quedarse con el último registro por (cliente, numero_interno)
        ultimos = {}
        primeros_km = {}
        for r in filas:
            cli = str(r[0]).strip().upper()
            serial = str(r[1]).strip().upper()
            k = (cli, serial)
            ultimos[k] = r
            if k not in primeros_km:
                primeros_km[k] = to_float(r[14])

        for (cli, serial), r in ultimos.items():
            placa = str(r[2] or '').strip().upper()
            pos = to_int(r[3], 0)
            tipo_veh = str(r[4] or '').strip().upper()
            marca = str(r[5] or '').strip().upper()
            diseno = str(r[6] or '').strip().upper()
            dim = str(r[7] or '295/80R22.5').strip().upper()
            vida = str(r[8] or 'Original').strip()
            banda = str(r[9] or '').strip().upper()
            pe = to_float(r[10])
            pc = to_float(r[11])
            pi = to_float(r[12])
            psi = to_float(r[13], 100.0)
            km_act = to_float(r[14])
            km_mont = to_float(r[15])
            pr = to_float(r[16], 1450000.0)
            p_ini = to_float(r[17], 18.0)
            subc = str(r[18] or '').strip().upper()
            tipo_op = str(r[19] or '').strip().upper()
            fecha_insp = str(r[20] or '')

            pos_validas = [x for x in (pe, pc, pi) if x > 0]
            p_min = min(pos_validas) if pos_validas else 0.0

            if km_mont > 0 and km_act >= km_mont:
                km_rod = km_act - km_mont
            else:
                km_base = primeros_km.get((cli, serial), km_act)
                km_rod = max(0.0, km_act - km_base)

            # Verificar si existe en llantas_maestro
            c.execute("SELECT id, ubicacion_bodega FROM llantas_maestro WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?", (cli, serial))
            row_m = c.fetchone()

            if not row_m:
                costo_base = pr if pr > 0 else 1450000.0
                c.execute("""
                    INSERT INTO llantas_maestro (
                        numero_interno, cliente, subcliente, tipo_operacion, ubicacion_bodega, estado_actual,
                        placa_actual, posicion_actual, marca, diseno, dimension, vida_actual, banda_reen,
                        prof_inicial, prof_ext, prof_cent, prof_int, prof_actual_min, psi_actual,
                        km_montaje_ciclo, km_actual_vehiculo, km_recorridos_ciclo, km_acumulados_total,
                        costo_compra_original, costo_ciclo_actual, costo_reparaciones_ciclo_actual, costo_acumulado_total
                    ) VALUES (?, ?, ?, ?, 'MONTADA_OPERACION', 'Montada en Vehículo',
                              ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?,
                              ?, ?, 0.0, ?)
                """, (
                    serial, cli, subc, tipo_op,
                    placa, pos, marca, diseno, dim, vida, banda,
                    p_ini, pe, pc, pi, p_min, psi,
                    km_mont, km_act, km_rod, km_rod,
                    costo_base, costo_base, costo_base
                ))
            else:
                ubi = row_m[1]
                # Si otra llanta ocupaba esa misma posición en el vehículo, desmontarla a Bodega 2
                if placa and pos > 0:
                    c.execute("""
                        SELECT id, numero_interno, prof_actual_min, vida_actual FROM llantas_maestro
                        WHERE UPPER(cliente) = ? AND ubicacion_bodega = 'MONTADA_OPERACION'
                          AND UPPER(placa_actual) = ? AND posicion_actual = ?
                          AND UPPER(numero_interno) != ?
                    """, (cli, placa, pos, serial))
                    ocupantes = c.fetchall()
                    for o_id, o_serial, o_prof, o_vida in ocupantes:
                        c.execute("""
                            UPDATE llantas_maestro SET
                                ubicacion_bodega = 'BODEGA_2_RECAMBIO',
                                estado_actual = 'En Stock - Reutilizable',
                                placa_actual = '',
                                posicion_actual = 0,
                                fecha_actualizacion = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (o_id,))
                        c.execute("""
                            INSERT INTO kardex_movimientos_llanta (
                                fecha_movimiento, cliente, subcliente, numero_interno,
                                bodega_origen, bodega_destino, tipo_movimiento,
                                placa, posicion, vida_ciclo, prof_min_mm, km_vehiculo,
                                causal_o_motivo, usuario_registro
                            ) VALUES (?, ?, ?, ?, 'MONTADA_OPERACION', 'BODEGA_2_RECAMBIO', 'DESMONTE_RECAMBIO',
                                      ?, ?, ?, ?, ?, ?, 'sistema')
                        """, (
                            fecha_insp or datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d'),
                            cli, subc, o_serial, placa, pos, o_vida, o_prof, km_act,
                            f"Desmonte automático por inspección de {serial} en pos {pos}"
                        ))

                if ubi != 'MONTADA_OPERACION':
                    # Si la llanta ya está chatarrizada, nunca vuelve a operación
                    if ubi == 'BODEGA_7_CHATARRIZADA':
                        continue

                    # Consultar fecha del último movimiento registrado en Kardex
                    c.execute("""
                        SELECT fecha_movimiento, id FROM kardex_movimientos_llanta
                        WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?
                        ORDER BY fecha_movimiento DESC, id DESC LIMIT 1
                    """, (cli, serial))
                    row_k = c.fetchone()
                    fecha_ult_k = str(row_k[0])[:10] if (row_k and row_k[0]) else ''
                    fecha_insp_s = str(fecha_insp)[:10]

                    # Corrección 4: Si la llanta está en bodega física, solo cambiar a MONTADA_OPERACION si la fecha es estrictamente posterior
                    if row_k and fecha_ult_k and fecha_insp_s <= fecha_ult_k:
                        continue

                    # Transición automática: llanta de bodega que fue montada en patio
                    c.execute("""
                        UPDATE llantas_maestro SET
                            ubicacion_bodega = 'MONTADA_OPERACION',
                            estado_actual = 'Montada en Vehículo',
                            placa_actual = ?,
                            posicion_actual = ?,
                            prof_ext = ?,
                            prof_cent = ?,
                            prof_int = ?,
                            prof_actual_min = ?,
                            psi_actual = ?,
                            km_actual_vehiculo = ?,
                            km_recorridos_ciclo = ?,
                            reservada_para_placa = NULL,
                            reservada_posicion = NULL,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (placa, pos, pe, pc, pi, p_min, psi, km_act, km_rod, row_m[0]))
                    c.execute("""
                        INSERT INTO kardex_movimientos_llanta (
                            fecha_movimiento, cliente, subcliente, numero_interno,
                            bodega_origen, bodega_destino, tipo_movimiento,
                            placa, posicion, vida_ciclo, prof_min_mm, km_vehiculo,
                            causal_o_motivo, usuario_registro
                        ) VALUES (?, ?, ?, ?, ?, 'MONTADA_OPERACION', 'MONTAJE',
                                  ?, ?, ?, ?, ?, 'Montaje detectado en inspección de patio', 'sistema')
                    """, (
                        fecha_insp or datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d'),
                        cli, subc, serial, ubi, placa, pos, vida, p_min, km_act
                    ))
                else:
                    c.execute("""
                        UPDATE llantas_maestro SET
                            placa_actual = ?,
                            posicion_actual = ?,
                            prof_ext = ?,
                            prof_cent = ?,
                            prof_int = ?,
                            prof_actual_min = ?,
                            psi_actual = ?,
                            km_actual_vehiculo = ?,
                            km_recorridos_ciclo = ?,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (placa, pos, pe, pc, pi, p_min, psi, km_act, km_rod, row_m[0]))

    if conn is not None:
        _ejecutar(conn.cursor())
    else:
        with get_connection() as c_conn:
            _ejecutar(c_conn.cursor())
            c_conn.commit()

# ==========================================
# CATÁLOGO DE VEHÍCULOS & ESPECIFICACIONES DE LLANTAS
# ==========================================

def sincronizar_vehiculo_catalogo(placa, tipologia, cliente='', subcliente='', tipo_operacion='', kilometraje=0.0, conn=None):
    pl = str(placa or '').strip().upper()
    tip = str(tipologia or '').strip().upper()
    if not pl or not tip or tip.lower() in ('nan', 'none'):
        return
    cli = '' if (pd.isna(cliente) or str(cliente).strip().lower() in ('nan', 'none')) else str(cliente).strip().upper()
    sub = '' if (pd.isna(subcliente) or str(subcliente).strip().lower() in ('nan', 'none')) else str(subcliente).strip().upper()
    op = '' if (pd.isna(tipo_operacion) or str(tipo_operacion).strip().lower() in ('nan', 'none')) else str(tipo_operacion).strip().upper()
    km = to_float(kilometraje, 0.0)

    sql = """
        INSERT INTO catalogo_vehiculos (placa, tipologia, cliente, subcliente, tipo_operacion, ultimo_km, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(placa) DO UPDATE SET
            tipologia = excluded.tipologia,
            cliente = CASE WHEN excluded.cliente != '' THEN excluded.cliente ELSE catalogo_vehiculos.cliente END,
            subcliente = CASE WHEN excluded.subcliente != '' THEN excluded.subcliente ELSE catalogo_vehiculos.subcliente END,
            tipo_operacion = CASE WHEN excluded.tipo_operacion != '' THEN excluded.tipo_operacion ELSE catalogo_vehiculos.tipo_operacion END,
            ultimo_km = MAX(catalogo_vehiculos.ultimo_km, excluded.ultimo_km),
            fecha_actualizacion = CURRENT_TIMESTAMP
    """
    params = (pl, tip, cli, sub, op, km)

    if conn is not None:
        cursor = conn.cursor()
        cursor.execute(sql, params)
    else:
        with get_connection() as c:
            cursor = c.cursor()
            cursor.execute(sql, params)
            c.commit()

def obtener_ultima_marca_diseno_vehiculo(placa: str) -> dict:
    pl = str(placa or '').strip().upper()
    if not pl:
        return {"encontrado": False, "placa": ""}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT marca, diseno, dimension, prof_inicial, fecha, posicion
            FROM inspecciones
            WHERE UPPER(TRIM(placa)) = ? AND marca IS NOT NULL AND TRIM(marca) != ''
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, (pl,))
        r = cursor.fetchone()
        if r:
            return {
                "encontrado": True,
                "placa": pl,
                "marca": r[0] or "",
                "diseno": r[1] or "",
                "dimension": r[2] or "",
                "prof_inicial": to_float(r[3], 0.0),
                "fecha": str(r[4])[:10] if r[4] else "",
                "posicion": r[5]
            }
    return {"encontrado": False, "placa": pl}

def obtener_perfil_vehiculo(placa: str) -> dict:
    pl = str(placa or '').strip().upper()
    if not pl:
        return {
            "encontrado": False,
            "placa": "",
            "ultima_fecha_inspeccion": "",
            "fecha_minima_permitida": "",
            "en_periodo_restringido": False,
            "dias_para_nueva_inspeccion": 0,
            "inspeccion_hoy": False,
            "ultima_marca": "",
            "ultimo_diseno": ""
        }
    
    with get_connection() as conn:
        cursor = conn.cursor()

        # 0. Consultar la última inspección registrada de esta placa (para frecuencia, marca y diseño)
        cursor.execute("""
            SELECT fecha, marca, diseno, dimension, kilometraje, posicion
            FROM inspecciones
            WHERE UPPER(TRIM(placa)) = ?
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, (pl,))
        row_ult = cursor.fetchone()

        f_ult_str = ""
        marca_ult = ""
        diseno_ult = ""
        dim_ult = ""
        f_minima_str = ""
        en_periodo_restringido = False
        dias_restantes = 0
        inspeccion_hoy = False
        cant_pos_ult_fecha = 0

        if row_ult and row_ult[0]:
            f_ult_str = str(row_ult[0]).strip()[:10]
            marca_ult = str(row_ult[1] or "").strip()
            diseno_ult = str(row_ult[2] or "").strip()
            dim_ult = str(row_ult[3] or "").strip()

            try:
                f_base = datetime.strptime(f_ult_str, '%Y-%m-%d').date()
                f_minima = calcular_fecha_minima_siguiente_inspeccion(f_base)
                f_minima_str = f_minima.strftime('%Y-%m-%d')
                hoy = date.today()
                en_periodo_restringido = (hoy < f_minima)
                dias_restantes = max(0, (f_minima - hoy).days) if en_periodo_restringido else 0
                inspeccion_hoy = (f_ult_str == hoy.strftime('%Y-%m-%d'))
            except Exception:
                f_minima_str = ""
                en_periodo_restringido = False
                dias_restantes = 0
                inspeccion_hoy = False

            try:
                cursor.execute("""
                    SELECT COUNT(DISTINCT posicion) FROM inspecciones
                    WHERE UPPER(TRIM(placa)) = ? AND SUBSTR(fecha, 1, 10) = ?
                """, (pl, f_ult_str))
                r_cnt = cursor.fetchone()
                cant_pos_ult_fecha = r_cnt[0] if r_cnt else 0
            except Exception:
                cant_pos_ult_fecha = 0

        # 1. Buscar en la última inspección registrada previamente para esa placa con tipología
        cursor.execute("""
            SELECT placa, tipologia, cliente, subcliente, tipo_operacion, kilometraje, dimension
            FROM inspecciones
            WHERE UPPER(TRIM(placa)) = ? AND tipologia IS NOT NULL AND TRIM(tipologia) != ''
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, (pl,))
        row = cursor.fetchone()
        
        # 2. Si no ha tenido inspección previa con tipología, consultar el catálogo de vehículos
        if not row or not row[1]:
            cursor.execute("""
                SELECT placa, tipologia, cliente, subcliente, tipo_operacion, ultimo_km
                FROM catalogo_vehiculos
                WHERE UPPER(TRIM(placa)) = ?
            """, (pl,))
            row = cursor.fetchone()
            dim_vehiculo = dim_ult
            if not dim_vehiculo and row and row[0]:
                cursor.execute("""
                    SELECT dimension FROM inspecciones 
                    WHERE UPPER(TRIM(placa)) = ? AND dimension IS NOT NULL AND TRIM(dimension) != ''
                    ORDER BY fecha DESC, id DESC LIMIT 1
                """, (pl,))
                r_dim = cursor.fetchone()
                if r_dim and r_dim[0]:
                    dim_vehiculo = str(r_dim[0]).strip()
        else:
            dim_vehiculo = str(row[6]).strip() if len(row) > 6 and row[6] else dim_ult
            # Sincronizar catálogo con los datos de la última inspección
            sincronizar_vehiculo_catalogo(row[0], row[1], row[2], row[3], row[4], row[5])

    if row and row[1]:
        tip = row[1]
        posiciones = obtener_posiciones_por_tipologia(tip)
        esquema = obtener_esquema_tipologia(tip)
        ultimo_km_val = to_float(row[5], 0.0)
        if ultimo_km_val <= 0:
            cursor.execute("SELECT MAX(kilometraje) FROM inspecciones WHERE UPPER(TRIM(placa)) = ?", (pl,))
            r_max_km = cursor.fetchone()
            if r_max_km and r_max_km[0]:
                ultimo_km_val = to_float(r_max_km[0], 0.0)
        return {
            "encontrado": True,
            "placa": row[0],
            "tipologia": tip,
            "cliente": row[2] or "",
            "subcliente": row[3] or "",
            "tipo_operacion": row[4] or "",
            "ultimo_km": ultimo_km_val,
            "dimension": dim_vehiculo,
            "cant_llantas": len(posiciones),
            "esquema": esquema,
            "posiciones": posiciones,
            # Control de frecuencia técnica e historial de inspección
            "ultima_fecha_inspeccion": f_ult_str,
            "fecha_minima_permitida": f_minima_str,
            "en_periodo_restringido": en_periodo_restringido,
            "dias_para_nueva_inspeccion": dias_restantes,
            "inspeccion_hoy": inspeccion_hoy,
            "cant_posiciones_ult_inspeccion": cant_pos_ult_fecha,
            "ultima_marca": marca_ult,
            "ultimo_diseno": diseno_ult
        }
    
    return {
        "encontrado": False,
        "placa": pl,
        "ultima_fecha_inspeccion": f_ult_str,
        "fecha_minima_permitida": f_minima_str,
        "en_periodo_restringido": en_periodo_restringido,
        "dias_para_nueva_inspeccion": dias_restantes,
        "inspeccion_hoy": inspeccion_hoy,
        "cant_posiciones_ult_inspeccion": cant_pos_ult_fecha,
        "ultima_marca": marca_ult,
        "ultimo_diseno": diseno_ult
    }

def obtener_llanta_por_cliente(cliente: str, numero_interno: str, placa: str = "") -> dict | None:
    num_norm = str(numero_interno or '').strip().upper()
    cli_norm = str(cliente or '').strip()
    pl_norm = str(placa or '').strip().upper()
    
    if not num_norm or num_norm == 'SN':
        return None
    
    # Si no se pasó cliente pero sí placa, intentar inferir cliente
    if not cli_norm and pl_norm:
        perf = obtener_perfil_vehiculo(pl_norm)
        if perf.get("encontrado") and perf.get("cliente"):
            cli_norm = perf["cliente"].strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        if cli_norm:
            cursor.execute("""
                SELECT cliente, subcliente, placa, posicion, fecha, marca, diseno, dimension, vida, banda_reen,
                       prof_inicial, precio, km_montaje, prof_ext, prof_cent, prof_int, novedades
                FROM inspecciones
                WHERE UPPER(TRIM(numero_interno)) = ? AND UPPER(TRIM(cliente)) = UPPER(TRIM(?))
                ORDER BY fecha DESC, id DESC LIMIT 1
            """, (num_norm, cli_norm))
        else:
            cursor.execute("""
                SELECT cliente, subcliente, placa, posicion, fecha, marca, diseno, dimension, vida, banda_reen,
                       prof_inicial, precio, km_montaje, prof_ext, prof_cent, prof_int, novedades
                FROM inspecciones
                WHERE UPPER(TRIM(numero_interno)) = ?
                ORDER BY fecha DESC, id DESC LIMIT 1
            """, (num_norm,))
        
        row = cursor.fetchone()
        if row:
            p_ext = to_float(row[13])
            p_cent = to_float(row[14])
            p_int = to_float(row[15])
            profs = [p for p in (p_ext, p_cent, p_int) if p > 0]
            prof_min = min(profs) if profs else 0.0
            return {
                "encontrado": True,
                "numero_interno": num_norm,
                "cliente": row[0] or "",
                "subcliente": row[1] or "",
                "ult_placa": row[2] or "",
                "ult_posicion": to_int(row[3], 1),
                "ult_fecha": row[4] or "",
                "marca": row[5] or "",
                "diseno": row[6] or "",
                "dimension": row[7] or "",
                "vida": row[8] or "Original",
                "banda_reen": row[9] or "",
                "prof_inicial": to_float(row[10]),
                "precio": to_float(row[11]),
                "km_montaje": to_float(row[12]),
                "ult_prof_ext": p_ext,
                "ult_prof_cent": p_cent,
                "ult_prof_int": p_int,
                "ult_prof_min": prof_min,
                "ult_novedades": row[16] or ""
            }
    return None

def obtener_posiciones_por_tipologia(tipologia):
    """
    Retorna el listado de números de posición correspondientes a la tipología seleccionada,
    consultando dinámicamente su esquema configurado.
    """
    import json
    t_nom = str(tipologia or '').strip().lower()
    if t_nom:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT nombre, cant_llantas, esquema_json FROM catalogo_tipologias')
                filas = cursor.fetchall()
                
                # 1. Coincidencia exacta primero
                for r in filas:
                    if r[0] and str(r[0]).strip().lower() == t_nom:
                        if r[2]:
                            try:
                                esq = json.loads(r[2])
                                pos_set = []
                                for eje in esq:
                                    for p in eje.get('posiciones', []):
                                        pos_set.append(int(p['pos']))
                                if pos_set:
                                    return sorted(list(set(pos_set)))
                            except Exception:
                                pass
                        if r[1]:
                            return list(range(1, int(r[1]) + 1))
                
                # 2. Coincidencia parcial si no hay exacta
                for r in filas:
                    nom_row = str(r[0] or '').strip().lower()
                    if nom_row and (t_nom in nom_row or nom_row in t_nom):
                        if r[2]:
                            try:
                                esq = json.loads(r[2])
                                pos_set = []
                                for eje in esq:
                                    for p in eje.get('posiciones', []):
                                        pos_set.append(int(p['pos']))
                                if pos_set:
                                    return sorted(list(set(pos_set)))
                            except Exception:
                                pass
                        if r[1]:
                            return list(range(1, int(r[1]) + 1))
                
                # 2b. Coincidencia por palabras clave
                palabras = [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', t_nom).split() if len(w) >= 2]
                if palabras:
                    for r in filas:
                        nom_row = str(r[0] or '').strip().lower()
                        if all(p in nom_row for p in palabras):
                            if r[2]:
                                try:
                                    esq = json.loads(r[2])
                                    pos_set = []
                                    for eje in esq:
                                        for p in eje.get('posiciones', []):
                                            pos_set.append(int(p['pos']))
                                    if pos_set:
                                        return sorted(list(set(pos_set)))
                                except Exception:
                                    pass
                            if r[1]:
                                return list(range(1, int(r[1]) + 1))
        except Exception:
            pass

    # Reglas heurísticas de respaldo
    if "cuatro manos" in t_nom or "4 manos" in t_nom or "8x4" in t_nom or "biarticulado" in t_nom:
        return list(range(1, 15)) if "biarticulado" in t_nom else list(range(1, 13))
    elif "trailer" in t_nom or "remolque" in t_nom:
        return list(range(1, 13))
    elif "camioneta" in t_nom or "liviano" in t_nom or "4x2" in t_nom:
        return [1, 2, 3, 4]
    elif "volqueta" in t_nom or "camilero" in t_nom or "articulado" in t_nom:
        return list(range(1, 11))
    elif "camion sencillo" in t_nom or "sencillo" in t_nom or "turbo" in t_nom:
        return [1, 2, 3, 4, 5, 6]
    else:
        return list(range(1, 11))

def generar_siguiente_numero_interno_temporal(conn=None):
    """
    Genera el siguiente número interno temporal consecutivo con formato TMP-001, TMP-002, etc.
    Garantiza que no se repita consultando todos los códigos TMP-% existentes en inspecciones.
    """
    def _calcular(cursor):
        cursor.execute("SELECT numero_interno FROM inspecciones WHERE UPPER(TRIM(numero_interno)) LIKE 'TMP-%'")
        filas = cursor.fetchall()
        max_num = 0
        existentes = set()
        for f in filas:
            val = str(f[0] or '').strip().upper()
            existentes.add(val)
            partes = val.split('-')
            if len(partes) >= 2 and partes[1].isdigit():
                try:
                    n = int(partes[1])
                    if n > max_num:
                        max_num = n
                except Exception:
                    pass
        siguiente = max_num + 1
        codigo = f"TMP-{siguiente:03d}"
        while codigo in existentes:
            siguiente += 1
            codigo = f"TMP-{siguiente:03d}"
        return codigo

    if conn is not None:
        return _calcular(conn.cursor())
    else:
        with get_connection() as c:
            return _calcular(c.cursor())

def es_posicion_direccional(tipologia, posicion):
    """
    Determina si una posición dada pertenece a un eje direccional.
    Verifica el esquema de tipología en BD o heurística estándar.
    """
    pos = to_int(posicion, 1)
    esquema = obtener_esquema_tipologia(tipologia)
    if esquema:
        for eje in esquema:
            tipo_eje = str(eje.get('tipo', '')).strip().lower()
            es_dir_eje = 'direccional' in tipo_eje or tipo_eje == 'dir'
            for p in eje.get('posiciones', []):
                if to_int(p.get('pos')) == pos:
                    rol = str(p.get('rol', '')).strip().lower()
                    if es_dir_eje or 'dir' in rol:
                        return True
                    return False
    # Heurística de respaldo para pruebas o esquemas sin BD
    t_norm = str(tipologia or '').lower()
    if 'cuatro manos' in t_norm or '8x4' in t_norm or 'biarticulado' in t_norm:
        return pos in [1, 2, 3, 4]
    return pos in [1, 2]

def calcular_fecha_minima_siguiente_inspeccion(fecha_base):
    """
    Calcula la fecha mínima en la que se puede realizar una nueva inspección a un vehículo.
    Regla: La nueva inspección se habilita a partir del día 20 del mes siguiente a la inspección previa.
    Ejemplo:
    - Inspección previa: 2026-10-20 (Octubre) -> Nueva inspección permitida: 2026-11-20 (20 de Noviembre).
    - Inspección previa: 2026-08-10 (Agosto)  -> Nueva inspección permitida: 2026-09-20 (20 de Septiembre).
    """
    if isinstance(fecha_base, str):
        fecha_base = datetime.strptime(str(fecha_base)[:10], '%Y-%m-%d').date()
    elif isinstance(fecha_base, datetime):
        fecha_base = fecha_base.date()

    año = fecha_base.year
    mes = fecha_base.month
    if mes == 12:
        año_sig = año + 1
        mes_sig = 1
    else:
        año_sig = año
        mes_sig = mes + 1

    return date(año_sig, mes_sig, 20)

def validar_inspeccion_candados(datos, excluir_id=None, conn=None, es_cargue_masivo=False):
    """
    Evalúa los candados de seguridad de inspección:
    1. Máximo 27 mm en llantas R22.5 o de carga pesada.
    2. Las profundidades (ext, cent, int) NO pueden ser mayores a la Profundidad Inicial (prof_inicial).
    3. Autogeneración de consecutivo TMP-xxx si no se ingresa número interno.
    4. En eje direccional solo se permite condición Original (prohibido Reencauche).
    5. Candado de No Duplicidad de Número Interno por Cliente / Subcliente en el mismo mes.
    6. Frecuencia de inspección: nueva inspección requiere el siguiente mes más 20 días.
    7. Kilometraje actual no puede ser menor al de la inspección anterior de la placa.
    8. La profundidad no puede subir entre inspecciones (desgaste negativo), con tolerancia máx 1 mm.
    """
    if datos.get('_es_cargue_masivo'):
        es_cargue_masivo = True

    placa = str(datos.get('placa', '')).strip().upper()
    if not placa:
        return {'valido': False, 'mensaje': 'Por favor ingresa la Placa del vehículo.'}

    fecha_str = str(datos.get('fecha', datetime.now().strftime('%Y-%m-%d'))).strip()
    km_actual = to_float(datos.get('kilometraje', 0))
    posicion = to_int(datos.get('posicion', 1))
    tipologia_val = str(datos.get('tipologia', '')).strip()
    dimension = str(datos.get('dimension', '')).strip().upper()
    prof_inicial = to_float(datos.get('prof_inicial', 0))

    p_ext = to_float(datos.get('prof_ext', 0))
    p_cent = to_float(datos.get('prof_cent', 0))
    p_int = to_float(datos.get('prof_int', 0))
    profs = [p_ext, p_cent, p_int]

    # Candado 1: Límite de profundidad (máximo físico 27.0 mm)
    if any(p > 27.0 for p in profs):
        dim_txt = f"En dimensión {dimension}, n" if dimension else "N"
        return {
            'valido': False,
            'mensaje': f'⛔ CANDADO DE SEGURIDAD: {dim_txt}inguna profundidad puede superar los 27.0 mm (Valores ingresados: {profs}).'
        }

    # Candado 1.2: Ninguna profundidad puede superar la Profundidad Inicial de la llanta
    if prof_inicial > 0:
        if any(p > prof_inicial for p in profs):
            return {
                'valido': False,
                'mensaje': f'⛔ CANDADO DE SEGURIDAD: Ninguna de las 3 profundidades ({profs}) puede ser mayor a la Profundidad Inicial ({prof_inicial} mm) de la llanta.'
            }

    # Candado 1.3: Eje Direccional - No se puede seleccionar Reencauche (solo Original)
    vida_val, banda_val = normalizar_vida_y_banda(datos.get('vida'), datos.get('banda_reen'))
    datos['vida'] = vida_val
    datos['banda_reen'] = banda_val
    if es_posicion_direccional(tipologia_val, posicion) and vida_val == 'REENCAUCHE':
        return {
            'valido': False,
            'mensaje': (
                f'⛔ CANDADO DE SEGURIDAD VIAL: En el eje direccional (Posición {posicion}) '
                f'no se puede seleccionar en vida/condición Reencauche, únicamente condición Original.'
            )
        }

    # Asignación automática de número consecutivo TMP-001 si viene vacío
    # Si viene en minúsculas (ej. 'sn'), se normaliza directamente a mayúsculas ('SN')
    num_interno = str(datos.get('numero_interno', '')).strip().upper()
    if not num_interno:
        num_interno = generar_siguiente_numero_interno_temporal(conn=conn)
        datos['numero_interno'] = num_interno
    else:
        datos['numero_interno'] = num_interno

    # Consultar historial previo de esta placa
    def _ejecutar_consultas(c):
        cursor = c.cursor()
        # Mes de inspección (YYYY-MM)
        mes_inspeccion = fecha_str[:7] if len(fecha_str) >= 7 else datetime.now().strftime('%Y-%m')

        # Candado 1.5: Candado de No Duplicidad de Número Interno por Cliente y Subcliente en el mismo mes
        # En la versión LIGHT se permite ingresar las veces que sea necesario la palabra "SN" (Sin Número).
        cliente_val = str(datos.get('cliente', '')).strip()
        subcliente_val = str(datos.get('subcliente', '')).strip()

        licencia = str(datos.get('tipo_licencia') or '').strip().upper()
        if not licencia and cliente_val:
            cursor.execute(
                "SELECT tipo_licencia FROM configuracion_avanzada_cliente WHERE UPPER(TRIM(cliente)) = UPPER(TRIM(?))",
                (cliente_val,)
            )
            row_lic = cursor.fetchone()
            if row_lic and row_lic[0]:
                licencia = str(row_lic[0]).strip().upper()
        if not licencia:
            licencia = 'PRO'

        es_version_light = (licencia == 'LIGHT')
        permitir_sn_repetido = (es_version_light and num_interno == 'SN')

        if num_interno and cliente_val and not permitir_sn_repetido:
            sql_dup = '''
                SELECT placa, posicion, cliente, subcliente, fecha, id FROM inspecciones
                WHERE UPPER(TRIM(numero_interno)) = ?
                  AND UPPER(TRIM(cliente)) = UPPER(TRIM(?))
                  AND strftime('%Y-%m', fecha) = ?
                  AND (UPPER(TRIM(placa)) != ? OR posicion != ?)
            '''
            params_dup = [num_interno, cliente_val, mes_inspeccion, placa, posicion]
            if excluir_id is not None:
                sql_dup += ' AND id != ?'
                params_dup.append(to_int(excluir_id))
            sql_dup += ' ORDER BY fecha DESC, id DESC LIMIT 1'

            cursor.execute(sql_dup, tuple(params_dup))
            dup_row = cursor.fetchone()
            if dup_row:
                return {
                    'valido': False,
                    'mensaje': f'⛔ CANDADO DE NÚMERO INTERNO: La llanta "{num_interno}" ya está asignada en el cliente "{cliente_val}" al vehículo {dup_row[0]}, Posición {dup_row[1]} en el mes de inspección ({dup_row[4]}). No se permiten números de llanta duplicados en el mismo mes.'
                }

        # Candado 2: Frecuencia de inspección vehicular y de posición
        # A un vehículo se le pueden realizar múltiples inspecciones, pero una nueva inspección
        # no se puede realizar hasta que pase el siguiente mes más 20 días.
        sql_ant_vehiculo = """
            SELECT fecha, posicion FROM inspecciones 
            WHERE placa = ?
        """
        params_ant_v = [placa]
        if excluir_id is not None:
            sql_ant_vehiculo += " AND id != ?"
            params_ant_v.append(to_int(excluir_id))
        sql_ant_vehiculo += " ORDER BY fecha DESC, id DESC"
        cursor.execute(sql_ant_vehiculo, tuple(params_ant_v))
        filas_ant = cursor.fetchall()
        if filas_ant:
            f_ult_str = str(filas_ant[0][0]).strip()[:10]
            f_nueva_str = fecha_str[:10]
            if f_nueva_str == f_ult_str:
                # Misma fecha (misma jornada): verificar si esta posición específica ya fue inspeccionada
                pos_ya_registradas = [r[1] for r in filas_ant if str(r[0]).strip()[:10] == f_ult_str]
                if posicion in pos_ya_registradas and not es_cargue_masivo:
                    return {
                        'valido': False,
                        'alerta_mes': True,
                        'mensaje': f'⚠️ CANDADO DE SEGURIDAD: El vehículo {placa} ya fue inspeccionado en la Posición {posicion} en la fecha {f_ult_str}.'
                    }
            elif f_nueva_str < f_ult_str:
                if not es_cargue_masivo:
                    return {
                        'valido': False,
                        'alerta_mes': True,
                        'mensaje': f'⚠️ CANDADO DE FECHA: La fecha de inspección ({f_nueva_str}) no puede ser anterior a la última inspección registrada ({f_ult_str}).'
                    }
            else:
                # Fecha posterior: debe haber transcurrido el siguiente mes más 20 días (solo en captura en vivo)
                if not es_cargue_masivo:
                    f_base = datetime.strptime(f_ult_str, '%Y-%m-%d').date()
                    f_nueva = datetime.strptime(f_nueva_str, '%Y-%m-%d').date()
                    f_minima = calcular_fecha_minima_siguiente_inspeccion(f_base)
                    if f_nueva < f_minima:
                        return {
                            'valido': False,
                            'alerta_mes': True,
                            'mensaje': (
                                f'⚠️ CANDADO DE FRECUENCIA: El vehículo {placa} ya fue inspeccionado en la Posición {posicion} el {f_ult_str}. '
                                f'Una nueva inspección se habilita a partir del día 20 del mes siguiente ({f_minima.strftime("%Y-%m-%d")}).'
                            )
                        }

        # Candado 3: Kilometraje actual no puede ser menor al de la última inspección (solo en captura secuencial)
        if not es_cargue_masivo:
            sql_km = """
                SELECT kilometraje, fecha FROM inspecciones 
                WHERE placa = ? AND kilometraje > 0
            """
            params_km = [placa]
            if excluir_id is not None:
                sql_km += " AND id != ?"
                params_km.append(to_int(excluir_id))
            sql_km += " ORDER BY fecha DESC, id DESC LIMIT 1"

            cursor.execute(sql_km, tuple(params_km))
            prev_km_row = cursor.fetchone()
            if prev_km_row:
                prev_km = prev_km_row[0]
                if km_actual > 0 and km_actual < prev_km:
                    return {
                        'valido': False,
                        'mensaje': f'⛔ CANDADO DE KILOMETRAJE: El kilometraje ({km_actual:,.0f} km) no puede ser menor al de la inspección anterior ({prev_km:,.0f} km el {prev_km_row[1]}).'
                    }

        # Candado 4: Profundidad no puede subir de una inspección a otra (tolerancia máx 1.0 mm, solo en captura secuencial)
        if not es_cargue_masivo:
            sql_prof = """
                SELECT prof_ext, prof_cent, prof_int, fecha FROM inspecciones 
                WHERE placa = ? AND posicion = ?
            """
            params_prof = [placa, posicion]
            if excluir_id is not None:
                sql_prof += " AND id != ?"
                params_prof.append(to_int(excluir_id))
            sql_prof += " ORDER BY fecha DESC, id DESC LIMIT 1"

            cursor.execute(sql_prof, tuple(params_prof))
            prev_prof_row = cursor.fetchone()
            if prev_prof_row:
                prev_ext, prev_cent, prev_int, f_prev = prev_prof_row
                max_subida_permitida = 1.0
                
                # Comparar el promedio o puntos si eran mayores a 0
                if prev_ext > 0 and (p_ext - prev_ext) > max_subida_permitida:
                    return {
                        'valido': False,
                        'mensaje': f'⛔ CANDADO DE DESGASTE: En Pos {posicion}, la Prof. Exterior subió de {prev_ext} mm a {p_ext} mm (Supera la tolerancia de 1.0 mm).'
                    }
                if prev_cent > 0 and (p_cent - prev_cent) > max_subida_permitida:
                    return {
                        'valido': False,
                        'mensaje': f'⛔ CANDADO DE DESGASTE: En Pos {posicion}, la Prof. Central subió de {prev_cent} mm a {p_cent} mm (Supera la tolerancia de 1.0 mm).'
                    }
                if prev_int > 0 and (p_int - prev_int) > max_subida_permitida:
                    return {
                        'valido': False,
                        'mensaje': f'⛔ CANDADO DE DESGASTE: En Pos {posicion}, la Prof. Interior subió de {prev_int} mm a {p_int} mm (Supera la tolerancia de 1.0 mm).'
                    }

        return {'valido': True, 'mensaje': 'Validaciones de seguridad aprobadas.'}

    if conn is not None:
        return _ejecutar_consultas(conn)
    else:
        with get_connection() as c:
            return _ejecutar_consultas(c)

def insertar_inspeccion(datos):
    num_int_norm = str(datos.get('numero_interno', '')).strip().upper()
    if not num_int_norm:
        datos['numero_interno'] = generar_siguiente_numero_interno_temporal()
    else:
        datos['numero_interno'] = num_int_norm
    vida_final, banda_final = normalizar_vida_y_banda(datos.get('vida'), datos.get('banda_reen'))
    placa_norm = str(datos.get('placa', '')).strip().upper()
    fecha_norm = str(datos.get('fecha', datetime.now().strftime('%Y-%m-%d'))).strip()
    fecha_dia = fecha_norm[:10]
    km_final = to_float(datos.get('kilometraje', 0))

    with get_connection() as conn:
        cursor = conn.cursor()
        # Si kilometraje viene en 0, buscar si otra llanta de este vehículo en la misma fecha ya tiene kilometraje
        if km_final <= 0 and placa_norm and fecha_dia:
            cursor.execute("""
                SELECT kilometraje FROM inspecciones
                WHERE UPPER(TRIM(placa)) = ? AND SUBSTR(fecha, 1, 10) = ? AND kilometraje > 0
                ORDER BY id DESC LIMIT 1
            """, (placa_norm, fecha_dia))
            r_km_prev = cursor.fetchone()
            if r_km_prev and r_km_prev[0] and r_km_prev[0] > 0:
                km_final = to_float(r_km_prev[0])
                datos['kilometraje'] = km_final

        cursor.execute("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                tipologia, marca, diseno, dimension, vida, banda_reen,
                prof_ext, prof_cent, prof_int, psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro, foto_novedad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha_norm,
            str(datos.get('cliente', '')).strip().upper(),
            str(datos.get('subcliente', '')).strip().upper(),
            str(datos.get('tipo_operacion', '')).strip().upper(),
            placa_norm,
            to_int(datos.get('posicion', 1)),
            km_final,
            str(datos.get('tipologia', '')).strip().upper(),
            str(datos.get('marca', '')).strip().upper(),
            str(datos.get('diseno', '')).strip().upper(),
            str(datos.get('dimension', '')).strip().upper(),
            vida_final,
            banda_final,
            to_float(datos.get('prof_ext', 0)),
            to_float(datos.get('prof_cent', 0)),
            to_float(datos.get('prof_int', 0)),
            to_float(datos.get('psi', 0)),
            str(datos.get('novedades', '')).strip().upper(),
            to_float(datos.get('precio', 0)),
            to_float(datos.get('prof_inicial', 0)),
            to_float(datos.get('km_montaje', 0)),
            str(datos.get('numero_interno', '')).strip().upper(),
            str(datos.get('usuario_registro', '')).strip().upper(),
            str(datos.get('foto_novedad', '')).strip()
        ))
        last_id = cursor.lastrowid

        # Si el kilometraje registrado es > 0, sincronizar y propagar a TODAS las llantas de este vehículo en esta fecha
        if km_final > 0 and placa_norm and fecha_dia:
            cursor.execute("""
                UPDATE inspecciones
                SET kilometraje = ?
                WHERE UPPER(TRIM(placa)) = ?
                  AND SUBSTR(fecha, 1, 10) = ?
                  AND (kilometraje != ? OR kilometraje IS NULL OR kilometraje = 0)
            """, (km_final, placa_norm, fecha_dia, km_final))
            cursor.execute("""
                UPDATE catalogo_vehiculos
                SET ultimo_km = MAX(COALESCE(ultimo_km, 0), ?)
                WHERE UPPER(TRIM(placa)) = ?
            """, (km_final, placa_norm))
        conn.commit()
    sincronizar_vehiculo_catalogo(
        datos.get('placa'),
        datos.get('tipologia'),
        datos.get('cliente'),
        datos.get('subcliente'),
        datos.get('tipo_operacion'),
        datos.get('kilometraje')
    )
    sincronizar_marca_cliente(
        datos.get('cliente'),
        datos.get('marca')
    )
    sincronizar_maestro_desde_inspecciones()
    return last_id

def obtener_todas_inspecciones(usuario=None):
    with get_connection() as conn:
        query = """
            SELECT id, fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                   tipologia, marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int,
                   psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro, foto_novedad
            FROM inspecciones
        """
        params = []
        if usuario:
            usr_info = obtener_usuario_por_username(usuario)
            if usr_info and usr_info.get('rol') != 'admin':
                # Si tiene uno o varios clientes asignados, filtra por esa lista. Si no tiene cliente asignado (vacío), acceso a todas las flotas.
                clis = parsear_clientes_asignados(usr_info.get('cliente_asignado'))
                if clis:
                    placeholders = ', '.join(['UPPER(TRIM(?))'] * len(clis))
                    query += f" WHERE UPPER(TRIM(cliente)) IN ({placeholders})"
                    params.extend([c.upper() for c in clis])
        query += " ORDER BY id DESC"
        return pd.read_sql_query(query, conn, params=params)


def actualizar_inspeccion(inspeccion_id, datos):
    """
    Actualiza la información de una llanta o inspección específica por su ID.
    Todos los campos de texto se persisten en mayúsculas.
    """
    vida_final, banda_final = normalizar_vida_y_banda(datos.get('vida'), datos.get('banda_reen'))
    placa_norm = str(datos.get('placa', '')).strip().upper()
    fecha_norm = str(datos.get('fecha', '')).strip()
    fecha_dia = fecha_norm[:10]
    km_final = to_float(datos.get('kilometraje', 0))

    with get_connection() as conn:
        cursor = conn.cursor()
        # Si kilometraje viene en 0, heredar de otra llanta de este vehículo en la misma fecha si existe
        if km_final <= 0 and placa_norm and fecha_dia:
            cursor.execute("""
                SELECT kilometraje FROM inspecciones
                WHERE UPPER(TRIM(placa)) = ? AND SUBSTR(fecha, 1, 10) = ? AND kilometraje > 0 AND id != ?
                ORDER BY id DESC LIMIT 1
            """, (placa_norm, fecha_dia, inspeccion_id))
            r_km_prev = cursor.fetchone()
            if r_km_prev and r_km_prev[0] and r_km_prev[0] > 0:
                km_final = to_float(r_km_prev[0])
                datos['kilometraje'] = km_final

        cursor.execute("""
            UPDATE inspecciones SET
                fecha = ?, cliente = ?, subcliente = ?, tipo_operacion = ?, placa = ?,
                posicion = ?, kilometraje = ?, tipologia = ?, marca = ?, diseno = ?,
                dimension = ?, vida = ?, banda_reen = ?, prof_ext = ?, prof_cent = ?,
                prof_int = ?, psi = ?, novedades = ?, precio = ?, prof_inicial = ?,
                km_montaje = ?, numero_interno = ?, foto_novedad = ?
            WHERE id = ?
        """, (
            fecha_norm,
            str(datos.get('cliente', '')).strip().upper(),
            str(datos.get('subcliente', '')).strip().upper(),
            str(datos.get('tipo_operacion', '')).strip().upper(),
            placa_norm,
            to_int(datos.get('posicion', 1)),
            km_final,
            str(datos.get('tipologia', '')).strip().upper(),
            str(datos.get('marca', '')).strip().upper(),
            str(datos.get('diseno', '')).strip().upper(),
            str(datos.get('dimension', '')).strip().upper(),
            vida_final,
            banda_final,
            to_float(datos.get('prof_ext', 0)),
            to_float(datos.get('prof_cent', 0)),
            to_float(datos.get('prof_int', 0)),
            to_float(datos.get('psi', 0)),
            str(datos.get('novedades', '')).strip().upper(),
            to_float(datos.get('precio', 0)),
            to_float(datos.get('prof_inicial', 0)),
            to_float(datos.get('km_montaje', 0)),
            str(datos.get('numero_interno', '')).strip().upper(),
            str(datos.get('foto_novedad', '')).strip(),
            inspeccion_id
        ))
        ok = cursor.rowcount > 0

        # Si el kilometraje registrado es > 0, sincronizar y propagar a TODAS las llantas de este vehículo en esta fecha
        if km_final > 0 and placa_norm and fecha_dia:
            cursor.execute("""
                UPDATE inspecciones
                SET kilometraje = ?
                WHERE UPPER(TRIM(placa)) = ?
                  AND SUBSTR(fecha, 1, 10) = ?
                  AND (kilometraje != ? OR kilometraje IS NULL OR kilometraje = 0)
            """, (km_final, placa_norm, fecha_dia, km_final))
            cursor.execute("""
                UPDATE catalogo_vehiculos
                SET ultimo_km = MAX(COALESCE(ultimo_km, 0), ?)
                WHERE UPPER(TRIM(placa)) = ?
            """, (km_final, placa_norm))
        conn.commit()
    if ok:
        sincronizar_vehiculo_catalogo(
            datos.get('placa'),
            datos.get('tipologia'),
            datos.get('cliente'),
            datos.get('subcliente'),
            datos.get('tipo_operacion'),
            datos.get('kilometraje')
        )
        sincronizar_marca_cliente(
            datos.get('cliente'),
            datos.get('marca')
        )
        sincronizar_maestro_desde_inspecciones()
    return ok

def eliminar_inspeccion(inspeccion_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM inspecciones WHERE id = ?", (inspeccion_id,))
        conn.commit()

def vaciar_inspecciones():
    with get_connection() as conn:
        conn.execute("DELETE FROM inspecciones")
        conn.commit()

def cargar_excel_a_bd(file_path):
    df = pd.read_excel(file_path, sheet_name=0)
    cols_norm_map = {normalizar_texto(c): c for c in df.columns}
    
    alias_map = {
        'fecha': ['fecha', 'fec', 'fecha inspeccion'],
        'cliente': ['cliente', 'empresa', 'cuenta'],
        'subcliente': ['subcliente', 'sede', 'proyecto', 'subcuenta'],
        'tipo_operacion': ['tipo operacion', 'operacion', 'tipo de operacion', 'servicio'],
        'placa': ['placa', 'vehiculo', 'vehículo', 'equipo'],
        'posicion': ['posicion', 'posición', 'posicion montaje', 'posición montaje', 'pos'],
        'kilometraje': ['kilometraje', 'kilometraje actual', 'km', 'km actual', 'km_actual', 'odometro'],
        'tipologia': ['tipologia', 'tipología', 'tipo', 'tipo vehiculo'],
        'marca': ['marca', 'marca llanta'],
        'diseno': ['diseno', 'diseño', 'dibujo', 'modelo'],
        'dimension': ['dimension', 'dimensión', 'medida', 'dim'],
        'vida': ['vida', 'estado vida', 'condicion', 'condición', 'vida útil', 'vida util', 'tipo vida', 'condicion / vida', 'condición / vida', 'estado llanta'],
        'banda_reen': ['banda reen', 'banda reencauche', 'banda', 'marca banda'],
        'prof_ext': ['prof ext', 'prof. exterior', 'ult. prof exterior', 'prof exterior', 'exterior'],
        'prof_cent': ['prof cent', 'prof centro', 'prof. central', 'prof central', 'centro', 'central'],
        'prof_int': ['prof int', 'prof. interior', 'ult. prof interior', 'prof interior', 'interior'],
        'psi': ['psi', 'presion', 'presión'],
        'novedades': ['novedades', 'observaciones', 'novedad', 'detalle'],
        'precio': ['precio', 'costo', 'valor'],
        'prof_inicial': ['prof inicial', 'prof. inicial', 'profundidad original'],
        'km_montaje': ['km montaje', 'km. montaje', 'kilometraje montaje'],
        'numero_interno': ['numero interno', 'número interno', 'no. interno', 'no interno', 'id llanta', 'id_llanta', 'codigo llanta', 'código llanta']
    }
    
    col_encontradas = {}
    for canonico, lista in alias_map.items():
        for item in lista:
            norm = normalizar_texto(item)
            if norm in cols_norm_map:
                col_encontradas[canonico] = cols_norm_map[norm]
                break

    registros_insertados = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for idx, row in df.iterrows():
            placa_raw = row[col_encontradas['placa']] if 'placa' in col_encontradas and not pd.isna(row[col_encontradas['placa']]) else ''
            placa = str(placa_raw).strip().upper()
            if not placa or placa == 'NAN':
                continue
            
            pos = to_int(row[col_encontradas['posicion']]) if 'posicion' in col_encontradas else 1

            # Normalizar fecha a formato YYYY-MM-DD
            fecha_raw = row[col_encontradas['fecha']] if 'fecha' in col_encontradas and not pd.isna(row[col_encontradas['fecha']]) else None
            fecha_dt = pd.to_datetime(fecha_raw, errors='coerce') if fecha_raw is not None else pd.NaT
            if pd.isna(fecha_dt):
                fecha = datetime.now().strftime('%Y-%m-%d')
            else:
                fecha = fecha_dt.strftime('%Y-%m-%d')

            # Normalizar vida y banda
            vida_raw = row[col_encontradas['vida']] if 'vida' in col_encontradas and not pd.isna(row[col_encontradas['vida']]) else ''
            banda_raw = row[col_encontradas['banda_reen']] if 'banda_reen' in col_encontradas and not pd.isna(row[col_encontradas['banda_reen']]) else ''
            vida, banda = normalizar_vida_y_banda(vida_raw, banda_raw)

            # Número interno con generación automática de consecutivo si viene vacío
            num_interno_raw = str(row[col_encontradas['numero_interno']]).strip().upper() if 'numero_interno' in col_encontradas and not pd.isna(row[col_encontradas['numero_interno']]) else ''
            num_interno = num_interno_raw if num_interno_raw and num_interno_raw != 'NAN' else ''
            if not num_interno:
                num_interno = generar_siguiente_numero_interno_temporal(conn=conn)

            datos = {
                'fecha': fecha,
                'cliente': str(row[col_encontradas['cliente']]).strip().upper() if 'cliente' in col_encontradas and not pd.isna(row[col_encontradas['cliente']]) and str(row[col_encontradas['cliente']]).strip().upper() != 'NAN' else '',
                'subcliente': str(row[col_encontradas['subcliente']]).strip().upper() if 'subcliente' in col_encontradas and not pd.isna(row[col_encontradas['subcliente']]) and str(row[col_encontradas['subcliente']]).strip().upper() != 'NAN' else '',
                'tipo_operacion': str(row[col_encontradas['tipo_operacion']]).strip().upper() if 'tipo_operacion' in col_encontradas and not pd.isna(row[col_encontradas['tipo_operacion']]) and str(row[col_encontradas['tipo_operacion']]).strip().upper() != 'NAN' else '',
                'placa': placa,
                'posicion': pos,
                'kilometraje': to_float(row[col_encontradas['kilometraje']]) if 'kilometraje' in col_encontradas else 0.0,
                'tipologia': str(row[col_encontradas['tipologia']]).strip().upper() if 'tipologia' in col_encontradas and not pd.isna(row[col_encontradas['tipologia']]) and str(row[col_encontradas['tipologia']]).strip().upper() != 'NAN' else '',
                'marca': str(row[col_encontradas['marca']]).strip().upper() if 'marca' in col_encontradas and not pd.isna(row[col_encontradas['marca']]) and str(row[col_encontradas['marca']]).strip().upper() != 'NAN' else '',
                'diseno': str(row[col_encontradas['diseno']]).strip().upper() if 'diseno' in col_encontradas and not pd.isna(row[col_encontradas['diseno']]) and str(row[col_encontradas['diseno']]).strip().upper() != 'NAN' else '',
                'dimension': str(row[col_encontradas['dimension']]).strip().upper() if 'dimension' in col_encontradas and not pd.isna(row[col_encontradas['dimension']]) and str(row[col_encontradas['dimension']]).strip().upper() != 'NAN' else '',
                'vida': vida,
                'banda_reen': banda,
                'prof_ext': to_float(row[col_encontradas['prof_ext']]) if 'prof_ext' in col_encontradas else 0.0,
                'prof_cent': to_float(row[col_encontradas['prof_cent']]) if 'prof_cent' in col_encontradas else 0.0,
                'prof_int': to_float(row[col_encontradas['prof_int']]) if 'prof_int' in col_encontradas else 0.0,
                'psi': to_float(row[col_encontradas['psi']]) if 'psi' in col_encontradas else 0.0,
                'novedades': str(row[col_encontradas['novedades']]).strip().upper() if 'novedades' in col_encontradas and not pd.isna(row[col_encontradas['novedades']]) and str(row[col_encontradas['novedades']]).strip().upper() != 'NAN' else '',
                'precio': to_float(row[col_encontradas['precio']]) if 'precio' in col_encontradas else 0.0,
                'prof_inicial': to_float(row[col_encontradas['prof_inicial']]) if 'prof_inicial' in col_encontradas else 0.0,
                'km_montaje': to_float(row[col_encontradas['km_montaje']]) if 'km_montaje' in col_encontradas else 0.0,
                'numero_interno': num_interno,
                'usuario_registro': 'EXCEL_IMPORT',
                'foto_novedad': '',
                '_es_cargue_masivo': True
            }

            # Validar candados de seguridad por cada fila (omitiendo candados secuenciales/fechas para cargue masivo histórico)
            val = validar_inspeccion_candados(datos, conn=conn, es_cargue_masivo=True)
            if not val.get('valido', True):
                raise ValueError(f"Fila {idx + 2} (Placa {placa}, Pos {pos}): {val.get('mensaje')}")

            # Asegurar número interno asignado en caso de autogeneración
            num_final = str(datos.get('numero_interno', num_interno)).strip().upper()

            cursor.execute("""
                INSERT INTO inspecciones (
                    fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                    tipologia, marca, diseno, dimension, vida, banda_reen,
                    prof_ext, prof_cent, prof_int, psi, novedades, precio, prof_inicial, km_montaje, numero_interno,
                    usuario_registro, foto_novedad
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datos['fecha'],
                datos['cliente'],
                datos['subcliente'],
                datos['tipo_operacion'],
                datos['placa'],
                datos['posicion'],
                datos['kilometraje'],
                datos['tipologia'],
                datos['marca'],
                datos['diseno'],
                datos['dimension'],
                datos['vida'],
                datos['banda_reen'],
                datos['prof_ext'],
                datos['prof_cent'],
                datos['prof_int'],
                datos['psi'],
                datos['novedades'],
                datos['precio'],
                datos['prof_inicial'],
                datos['km_montaje'],
                num_final,
                datos['usuario_registro'],
                datos['foto_novedad']
            ))
            sincronizar_vehiculo_catalogo(
                datos['placa'],
                datos['tipologia'],
                datos['cliente'],
                datos['subcliente'],
                datos['tipo_operacion'],
                datos['kilometraje'],
                conn=conn
            )
            sincronizar_marca_cliente(
                datos['cliente'],
                datos['marca'],
                conn=conn
            )
            registros_insertados += 1
        conn.commit()
    return registros_insertados

def analizar_inspecciones_df(df_inspecciones):
    if df_inspecciones.empty:
        return pd.DataFrame()

    df = df_inspecciones.copy()
    
    df['posicion'] = pd.to_numeric(df['posicion'], errors='coerce').fillna(0).astype(int)
    def calc_prof_min(row):
        vals = [to_float(row[c]) for c in ['prof_ext', 'prof_cent', 'prof_int']]
        positivos = [v for v in vals if v > 0]
        if positivos:
            return min(positivos)
        return min(vals) if vals else 0.0

    df['prof_min'] = df.apply(calc_prof_min, axis=1)

    def resolver_tipo(row):
        t = str(row.get('tipologia', '')).strip()
        if t and t.lower() != 'nan':
            return t
        return clasificar_vehiculo(row['placa'])

    df['tipo_calc'] = df.apply(resolver_tipo, axis=1)

    resultados = []
    resolver_limite = _construir_cache_limites_retiro()
    llantas_b2_usadas = set()
    
    for placa, group in df.groupby('placa'):
        if 'fecha' in group.columns and not group['fecha'].dropna().empty:
            fecha_max = group['fecha'].astype(str).str[:10].max()
            group = group[group['fecha'].astype(str).str[:10] == fecha_max]
        if 'id' in group.columns:
            group = group.sort_values('id').groupby('posicion', as_index=False).last()

        t_veh_val = group['tipo_calc'].iloc[0] if 'tipo_calc' in group else 'Desconocido'
        t_veh = 'Desconocido' if (pd.isna(t_veh_val) or str(t_veh_val).strip().lower() in ('nan', 'none', '')) else str(t_veh_val).strip()

        cli_val = group['cliente'].iloc[0] if ('cliente' in group and pd.notna(group['cliente'].iloc[0])) else ''
        cliente = '' if (pd.isna(cli_val) or str(cli_val).strip().lower() in ('nan', 'none')) else str(cli_val).strip().upper()

        sub_val = group['subcliente'].iloc[0] if ('subcliente' in group and pd.notna(group['subcliente'].iloc[0])) else ''
        subcliente = '' if (pd.isna(sub_val) or str(sub_val).strip().lower() in ('nan', 'none')) else str(sub_val).strip().upper()

        op_val = group['tipo_operacion'].iloc[0] if ('tipo_operacion' in group and pd.notna(group['tipo_operacion'].iloc[0])) else ''
        operacion = '' if (pd.isna(op_val) or str(op_val).strip().lower() in ('nan', 'none')) else str(op_val).strip().upper()
        
        max_pos = group['posicion'].max()
        es_cuatro_manos = ('cuatro manos' in t_veh.lower() or max_pos >= 12 and 'cabezote' in t_veh.lower())
        
        # 1. Alineación Direccional
        plan_alineacion = False
        detalles_alineacion = []

        if 'cabezote' in t_veh.lower() or 'camion' in t_veh.lower() or 'volqueta' in t_veh.lower():
            pos_dir = [1, 2, 3, 4] if es_cuatro_manos else [1, 2]
            for p in pos_dir:
                r = group[group['posicion'] == p]
                if not r.empty:
                    diff = abs(r['prof_int'].values[0] - r['prof_ext'].values[0])
                    if diff >= 2:
                        plan_alineacion = True
                        detalles_alineacion.append(f"Pos {p} (dif {diff:.1f}mm)")
        elif 'trailer' in t_veh.lower():
            for _, r in group.iterrows():
                diff = abs(r['prof_int'] - r['prof_ext'])
                if diff >= 2:
                    plan_alineacion = True
                    detalles_alineacion.append(f"Pos {int(r['posicion'])} (dif {diff:.1f}mm)")
                    
        # Obtener límite de cambio/retiro programado para este cliente (o 3.0 mm por defecto) en memoria O(1)
        limite_cambio_cliente = resolver_limite(cliente, subcliente)

        # 2. Dual Mal Apareado y Recomendación Inteligente de Emparejamiento
        plan_dual = False
        detalles_dual = []
        recomendaciones_dual = []

        pairs = [(3,4), (5,6), (7,8), (9,10)] if ('cabezote' in t_veh.lower() and not es_cuatro_manos) else \
                [(5,6), (7,8), (9,10), (11,12)] if ('cabezote' in t_veh.lower() and es_cuatro_manos) else \
                [(1,2), (3,4), (5,6), (7,8), (9,10), (11,12)]
                
        for p_a, p_b in pairs:
            t_a = group[group['posicion'] == p_a]
            t_b = group[group['posicion'] == p_b]
            if not t_a.empty and not t_b.empty:
                pb_a = to_float(t_a['prof_min'].values[0])
                pb_b = to_float(t_b['prof_min'].values[0])
                dim_a = str(t_a['dimension'].values[0]).strip()
                dim_b = str(t_b['dimension'].values[0]).strip()

                diff_pb = abs(pb_a - pb_b)
                razones = []
                if diff_pb >= 2:
                    razones.append(f"desgaste dif {diff_pb:.1f}mm ({pb_a:.1f} vs {pb_b:.1f})")
                if dim_a and dim_b and dim_a != dim_b:
                    razones.append(f"dims distintas ({dim_a} vs {dim_b})")

                # Cruce Inteligente con Bodega 2 en Duales Mal Apareados (KPI 08)
                if razones:
                    plan_dual = True
                    detalles_dual.append(f"Dual {p_a}-{p_b}: {', '.join(razones)}")

                    # Buscar candidata en Bodega 2 (Recambio) para aparear
                    try:
                        mm_alta = max(pb_a, pb_b)
                        pos_alta = p_a if pb_a >= pb_b else p_b
                        mm_baja = min(pb_a, pb_b)
                        pos_baja = p_b if pb_a >= pb_b else p_a
                        dim_dual = dim_a or dim_b

                        with get_connection() as c_b2:
                            cur_b2 = c_b2.cursor()
                            cur_b2.execute("""
                                SELECT numero_interno, prof_actual_min FROM llantas_maestro
                                WHERE UPPER(cliente) = ?
                                  AND ubicacion_bodega = 'BODEGA_2_RECAMBIO'
                                  AND (reservada_para_placa IS NULL OR reservada_para_placa = '' OR reservada_para_placa = ?)
                                  AND UPPER(dimension) = ?
                                  AND prof_actual_min > (? + 1.5)
                                  AND ABS(prof_actual_min - ?) <= 1.5
                                ORDER BY ABS(prof_actual_min - ?) ASC
                            """, (cliente, placa, dim_dual.upper(), limite_cambio_cliente, mm_alta, mm_alta))
                            candidatas_b2 = cur_b2.fetchall()
                            cand_b2 = None
                            for c_cand in candidatas_b2:
                                if c_cand[0] not in llantas_b2_usadas:
                                    cand_b2 = c_cand
                                    llantas_b2_usadas.add(c_cand[0])
                                    break

                            if cand_b2:
                                recomendaciones_dual.append(
                                    f"Cruce Bodega 2: Desmontar Pos {pos_baja} ({mm_baja:.1f}mm) y MONTAR llanta N° {cand_b2[0]} ({cand_b2[1]:.1f}mm) disponible en Bodega 2 (Recambio)."
                                )
                    except Exception:
                        pass

                # Recomendación de emparejamiento cuando una llanta va a cambio y la otra tiene buen remanente
                a_para_cambio = (pb_a > 0 and pb_a <= limite_cambio_cliente)
                b_para_cambio = (pb_b > 0 and pb_b <= limite_cambio_cliente)

                if a_para_cambio and not b_para_cambio and pb_b >= (limite_cambio_cliente + 2.0):
                    r_min = max(limite_cambio_cliente + 1.0, pb_b - 1.0)
                    r_max = pb_b + 1.0
                    recomendaciones_dual.append(
                        f"Pos {p_a} en retiro ({pb_a:.1f}mm) vs Pos {p_b} ({pb_b:.1f}mm): Se recomienda instalar en Pos {p_a} una llanta con remanente entre {r_min:.1f} y {r_max:.1f} mm para emparejar el dual, o cambiar ambas llantas para dejarlas parejas."
                    )
                elif b_para_cambio and not a_para_cambio and pb_a >= (limite_cambio_cliente + 2.0):
                    r_min = max(limite_cambio_cliente + 1.0, pb_b - 1.0)
                    r_max = pb_b + 1.0
                    recomendaciones_dual.append(
                        f"Pos {p_b} en retiro ({pb_b:.1f}mm) vs Pos {p_a} ({pb_a:.1f}mm): Se recomienda instalar en Pos {p_b} una llanta con remanente entre {r_min:.1f} y {r_max:.1f} mm para emparejar el dual, o cambiar ambas llantas para dejarlas parejas."
                    )
                    
        desc_tipo = f"{t_veh}{' (Cuatro Manos)' if es_cuatro_manos else ''}"
        
        # 3. Sugerencia de Cambio de Llanta (por profundidad crítica <= límite del cliente o 3.0 mm)
        plan_cambio = False
        detalles_cambio = []
        for _, r in group.iterrows():
            pos_r = int(r['posicion'])
            pb_r = to_float(r['prof_min'])
            if pb_r > 0 and pb_r <= limite_cambio_cliente:
                plan_cambio = True
                detalles_cambio.append(f"Pos {pos_r} ({pb_r:.1f}mm <= {limite_cambio_cliente:.1f}mm)")

        # Regla de Par Direccional (KPI 05): evaluar ejes direccionales (1, 2) y en 4 manos (3, 4)
        pares_dir = [(1, 2), (3, 4)] if es_cuatro_manos else [(1, 2)] if ('cabezote' in t_veh.lower() or 'camion' in t_veh.lower() or 'volqueta' in t_veh.lower()) else []
        for pd_a, pd_b in pares_dir:
            ta = group[group['posicion'] == pd_a]
            tb = group[group['posicion'] == pd_b]
            if not ta.empty and not tb.empty:
                pa_val = to_float(ta['prof_min'].values[0])
                pb_val = to_float(tb['prof_min'].values[0])
                pa_ini = to_float(ta['prof_inicial'].values[0] if 'prof_inicial' in ta.columns else 18.0, 18.0)
                pb_ini = to_float(tb['prof_inicial'].values[0] if 'prof_inicial' in tb.columns else 18.0, 18.0)

                pa_ret = (pa_val > 0 and pa_val <= limite_cambio_cliente)
                pb_ret = (pb_val > 0 and pb_val <= limite_cambio_cliente)

                if pa_ret and not pb_ret and (pb_ini - pb_val) > 3.0:
                    plan_cambio = True
                    detalles_cambio.append(f"Ajuste Par Direccional: cambiar también Pos {pd_b} ({pb_val:.1f}mm) y pasarla a Bodega 2 (Recambio)")
                elif pb_ret and not pa_ret and (pa_ini - pa_val) > 3.0:
                    plan_cambio = True
                    detalles_cambio.append(f"Ajuste Par Direccional: cambiar también Pos {pd_a} ({pa_val:.1f}mm) y pasarla a Bodega 2 (Recambio)")

        # 4. Alertas Adicionales: Rotación por Desgaste Irregular / Escalonado y Calibración de Presión
        plan_rotacion_irregular = False
        detalles_rot_irregular = []

        plan_rotacion_escalonado = False
        detalles_rot_escalonado = []

        plan_calibracion_psi = False
        detalles_calibracion = []

        # Determinar posiciones direccionales para excluir de tracción/libre
        pos_direccionales = [1, 2, 3, 4] if es_cuatro_manos else [1, 2] if ('cabezote' in t_veh.lower() or 'camion' in t_veh.lower() or 'volqueta' in t_veh.lower()) else []

        for _, r in group.iterrows():
            pos_i = int(r['posicion'])
            nov_i = str(r.get('novedades', '') or '').lower()
            psi_i = to_float(r.get('psi', 100))
            p_ext = to_float(r.get('prof_ext', 0))
            p_int = to_float(r.get('prof_int', 0))
            diff_ext_int = abs(p_ext - p_int)

            # a. Desgaste Irregular en Tracción / Eje Libre
            es_no_direccional = (pos_i not in pos_direccionales)
            if es_no_direccional:
                tiene_obs_irregular = ('desgaste irregular' in nov_i or 'desgaste disparejo' in nov_i or 'irregular' in nov_i)
                if diff_ext_int >= 2.0 or tiene_obs_irregular:
                    plan_rotacion_irregular = True
                    motivo = f"dif ext/int {diff_ext_int:.1f}mm" if diff_ext_int >= 2.0 else "observación 'desgaste irregular'"
                    detalles_rot_irregular.append(f"Pos {pos_i} ({motivo})")

            # b. Desgaste Escalonado en Eje de Tracción (o arrastre)
            if 'escalonado' in nov_i or 'diente de sierra' in nov_i:
                plan_rotacion_escalonado = True
                detalles_rot_escalonado.append(f"Pos {pos_i} (desgaste escalonado)")

            # c. Calibración de Presión
            if 'baja presion' in nov_i or 'baja presión' in nov_i or (psi_i > 0 and psi_i < 90):
                plan_calibracion_psi = True
                detalles_calibracion.append(f"Pos {pos_i} ({psi_i:.0f} PSI)")

        # d. Detección de Dimensiones Heterogéneas en la misma unidad (No recomendado)
        dims_map = {}
        for _, r in group.iterrows():
            pos_i = int(r['posicion'])
            dim_i = str(r.get('dimension', '') or '').strip().upper()
            if dim_i and dim_i not in ('NAN', 'NONE', '-', 'NULL', '0'):
                dims_map.setdefault(dim_i, []).append(pos_i)

        plan_dims_heterogeneas = len(dims_map) > 1
        detalles_dims_heterogeneas = []
        if plan_dims_heterogeneas:
            partes_dims = [f"{d} (Pos {', '.join(str(p) for p in sorted(pos_list))})" for d, pos_list in sorted(dims_map.items())]
            detalles_dims_heterogeneas.append(f"Dimensiones mixtas ({'; '.join(partes_dims)} - No recomendado mezclar)")

        resultados.append({
            'Vehículo/Placa': placa,
            'Fecha': group['fecha'].max() if 'fecha' in group and not group['fecha'].dropna().empty else '',
            'Cliente': cliente,
            'Subcliente': subcliente,
            'Operación': operacion,
            'Tipo': desc_tipo,
            'Km': 0.0 if ('kilometraje' not in group or pd.isna(group['kilometraje'].max())) else to_float(group['kilometraje'].max()),
            'Llantas Inspeccionadas': len(group),

            'Limite_Retiro_mm': limite_cambio_cliente,
            'Plan_Alineacion': "SÍ" if plan_alineacion else "NO",
            'Plan_Dual_Mal_Apareado': "SÍ" if plan_dual else "NO",
            'Plan_Cambio_Llanta': "SÍ" if plan_cambio else "NO",
            'Plan_Rotacion_Irregular': "SÍ" if plan_rotacion_irregular else "NO",
            'Plan_Rotacion_Escalonado': "SÍ" if plan_rotacion_escalonado else "NO",
            'Plan_Calibracion_PSI': "SÍ" if plan_calibracion_psi else "NO",
            'Plan_Dimensiones_Heterogeneas': "SÍ" if plan_dims_heterogeneas else "NO",
            'Detalle_Alineacion': "; ".join(detalles_alineacion) if detalles_alineacion else "OK",
            'Detalle_Dual': "; ".join(detalles_dual) if detalles_dual else "OK",
            'Detalle_Cambio': "; ".join(detalles_cambio) if detalles_cambio else "OK",
            'Detalle_Rotacion_Irregular': "; ".join(detalles_rot_irregular) if detalles_rot_irregular else "OK",
            'Detalle_Rotacion_Escalonado': "; ".join(detalles_rot_escalonado) if detalles_rot_escalonado else "OK",
            'Detalle_Calibracion_PSI': "; ".join(detalles_calibracion) if detalles_calibracion else "OK",
            'Detalle_Dimensiones_Heterogeneas': "; ".join(detalles_dims_heterogeneas) if detalles_dims_heterogeneas else "OK",
            'Recomendaciones_Dual': "; ".join(recomendaciones_dual) if recomendaciones_dual else "OK"
        })
        
    df_res = pd.DataFrame(resultados)
    if not df_res.empty and 'Fecha' in df_res.columns:
        fecha_sort = pd.to_datetime(df_res['Fecha'], errors='coerce')
        df_res['_sort_fecha'] = fecha_sort
        df_res = df_res.sort_values(
            by=['_sort_fecha', 'Vehículo/Placa'],
            ascending=[False, True],
            na_position='last'
        ).drop(columns=['_sort_fecha']).reset_index(drop=True)
    return df_res

if "pytest" not in sys.modules and not os.environ.get("PYTEST_CURRENT_TEST"):
    inicializar_bd()




def obtener_valores_unicos_campo(campo, filtro_cliente='', filtro_marca='', todas=False):
    validos = ['cliente', 'subcliente', 'tipo_operacion', 'marca', 'diseno', 'dimension', 'banda_reen', 'vida']
    if campo not in validos:
        return []
    with get_connection() as conn:
        cursor = conn.cursor()

        # Si se consulta marca para un cliente específico y no se pidieron todas
        if campo == 'marca' and filtro_cliente and not todas:
            cli_norm = str(filtro_cliente).strip().upper()
            cursor.execute("""
                SELECT DISTINCT marca
                FROM configuracion_marcas_cliente
                WHERE UPPER(TRIM(cliente)) = ?
                ORDER BY marca ASC
            """, (cli_norm,))
            marcas_cfg = [r[0] for r in cursor.fetchall() if r[0] and str(r[0]).strip()]
            if marcas_cfg:
                return marcas_cfg
            # Fallback al histórico de inspecciones de ese cliente si aún no tiene configuración explícita
            cursor.execute("""
                SELECT DISTINCT marca
                FROM inspecciones
                WHERE UPPER(TRIM(cliente)) = ? AND marca IS NOT NULL AND TRIM(marca) != ''
                ORDER BY marca ASC
            """, (cli_norm,))
            marcas_insp = [r[0] for r in cursor.fetchall() if r[0] and str(r[0]).strip()]
            if marcas_insp:
                return sorted(list(set(marcas_insp)))
            # Si no tiene marcas configuradas ni en historial, continúa al catálogo general

        query = f"SELECT DISTINCT {campo} FROM inspecciones WHERE {campo} IS NOT NULL AND TRIM({campo}) != ''"
        params = []
        if filtro_cliente and campo == 'subcliente':
            query += " AND UPPER(TRIM(cliente)) = UPPER(TRIM(?))"
            params.append(str(filtro_cliente).strip())
        if filtro_marca and campo == 'diseno':
            query += " AND UPPER(TRIM(marca)) = UPPER(TRIM(?))"
            params.append(str(filtro_marca).strip())
        query += f" ORDER BY {campo} ASC"
        cursor.execute(query, params)
        valores_insp = [r[0] for r in cursor.fetchall()]

        # Complementar con catálogos si aplica
        if campo == 'tipo_operacion':
            cursor.execute("SELECT nombre FROM catalogo_operaciones")
            valores_insp = sorted(list(set(valores_insp + [r[0] for r in cursor.fetchall()])))
        elif campo == 'diseno' and filtro_marca:
            cursor.execute("SELECT DISTINCT diseno FROM catalogo_modelos_llantas WHERE UPPER(TRIM(marca)) = UPPER(TRIM(?)) AND diseno IS NOT NULL AND TRIM(diseno) != ''", (str(filtro_marca).strip(),))
            valores_insp = sorted(list(set(valores_insp + [r[0] for r in cursor.fetchall()])))
        elif campo in ('marca', 'diseno', 'dimension'):
            cursor.execute(f"SELECT DISTINCT {campo} FROM catalogo_modelos_llantas WHERE {campo} IS NOT NULL AND TRIM({campo}) != ''")
            valores_insp = sorted(list(set(valores_insp + [r[0] for r in cursor.fetchall()])))
        elif campo == 'banda_reen':
            cursor.execute("SELECT DISTINCT diseno FROM catalogo_modelos_llantas WHERE tipo_llanta = 'Reencauche'")
            valores_insp = sorted(list(set(valores_insp + [r[0] for r in cursor.fetchall()])))
        elif campo == 'cliente':
            cursor.execute("SELECT cliente FROM configuracion_clientes")
            valores_insp = sorted(list(set(valores_insp + [r[0] for r in cursor.fetchall()])))

        if campo in ('cliente', 'subcliente', 'tipo_operacion'):
            valores_insp = sorted(list(set(str(v).strip().upper() for v in valores_insp if v and str(v).strip())))

        return [v for v in valores_insp if v and str(v).strip()]

def es_novedad_alerta(texto: str) -> bool:
    """
    Determina si una observación o novedad reportada corresponde a una alerta mecánica real.
    Retorna False si el texto está vacío o si coincide con descripciones benignas
    o estados normales (ej. 'ok', 'normal', 'desgaste normal y parejo').
    """
    if not texto or not isinstance(texto, str):
        return False
    limpio = " ".join(texto.strip().lower().split()).rstrip(".;,")
    if not limpio:
        return False
    frases_benignas = {
        'ok', 'normal', 'sin novedad', 'sin novedades', 'ninguna', 'ninguno',
        'buen estado', 'desgaste normal', 'desgaste normal y parejo', 'desgaste parejo',
        'optimo', 'óptimo', 'en buen estado', 'bien', 'sin problema', 'sin problemas'
    }
    return limpio not in frases_benignas

def obtener_posiciones_inspeccionadas_detalle(placa, fecha=None):
    """
    Retorna información detallada de las posiciones inspeccionadas para una placa:
    - lista de posiciones inspeccionadas
    - lista de posiciones que tienen novedad / daño registrado
    - mapa de novedades por posición
    """
    pl = str(placa or '').strip().upper()
    if not pl:
        return {"posiciones": [], "posiciones_con_novedad": [], "novedades": {}}
    with get_connection() as conn:
        cursor = conn.cursor()
        if fecha:
            f_str = str(fecha).strip()[:10]
            cursor.execute('''
                SELECT posicion, novedades
                FROM inspecciones
                WHERE UPPER(TRIM(placa)) = ? AND substr(fecha, 1, 10) = ?
                ORDER BY id ASC
            ''', (pl, f_str))
        else:
            return {"posiciones": [], "posiciones_con_novedad": [], "novedades": {}}
        
        posiciones = []
        posiciones_con_novedad = []
        novedades_map = {}
        for r in cursor.fetchall():
            if r[0] is not None:
                p = int(r[0])
                if p not in posiciones:
                    posiciones.append(p)
                nov = str(r[1] or '').strip()
                if es_novedad_alerta(nov):
                    if p not in posiciones_con_novedad:
                        posiciones_con_novedad.append(p)
                    novedades_map[p] = nov

        posiciones.sort()
        posiciones_con_novedad.sort()
        return {
            "posiciones": posiciones,
            "posiciones_con_novedad": posiciones_con_novedad,
            "novedades": novedades_map
        }

def obtener_posiciones_inspeccionadas_actuales(placa, fecha=None):
    """
    Retorna la lista de posiciones que ya han sido inspeccionadas para una placa dada
    en una fecha específica (o en el mes actual si no se proporciona fecha).
    """
    det = obtener_posiciones_inspeccionadas_detalle(placa, fecha)
    return det.get("posiciones", [])

def obtener_ultima_inspeccion_posicion(placa, posicion):
    pl = str(placa or '').strip().upper()
    pos = to_int(posicion, 1)
    if not pl:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, fecha, cliente, subcliente, tipo_operacion, placa, posicion,
                   kilometraje, tipologia, marca, diseno, dimension, vida, banda_reen,
                   prof_ext, prof_cent, prof_int, psi, novedades, precio, prof_inicial,
                   km_montaje, numero_interno
            FROM inspecciones
            WHERE UPPER(TRIM(placa)) = ? AND posicion = ?
            ORDER BY fecha DESC, id DESC LIMIT 1
        ''', (pl, pos))
        row = cursor.fetchone()
        if not row:
            return None
        cols = [
            'id', 'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'posicion',
            'kilometraje', 'tipologia', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen',
            'prof_ext', 'prof_cent', 'prof_int', 'psi', 'novedades', 'precio', 'prof_inicial',
            'km_montaje', 'numero_interno'
        ]
        d_res = dict(zip(cols, row))
        if to_float(d_res.get('kilometraje', 0)) <= 0 and d_res.get('fecha'):
            f_dia = str(d_res['fecha'])[:10]
            cursor.execute("""
                SELECT kilometraje FROM inspecciones
                WHERE UPPER(TRIM(placa)) = ? AND SUBSTR(fecha, 1, 10) = ? AND kilometraje > 0
                ORDER BY id DESC LIMIT 1
            """, (pl, f_dia))
            r_km = cursor.fetchone()
            if r_km and r_km[0] and r_km[0] > 0:
                d_res['kilometraje'] = to_float(r_km[0])
        return d_res

def buscar_modelos_llantas_filtro(termino=''):
    t = f"%{str(termino or '').strip().lower()}%"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion
            FROM catalogo_modelos_llantas
            WHERE LOWER(marca) LIKE ? OR LOWER(diseno) LIKE ? OR LOWER(dimension) LIKE ? OR LOWER(tipo_llanta) LIKE ?
            ORDER BY marca ASC, diseno ASC LIMIT 25
        ''', (t, t, t, t))
        cols = ['id', 'tipo_llanta', 'marca', 'diseno', 'dimension', 'prof_inicial', 'descripcion']
        return [dict(zip(cols, r)) for r in cursor.fetchall()]

def _quitar_tildes(s):
    if not s or pd.isna(s):
        return ''
    s_str = str(s).strip().upper()
    if s_str in ('NAN', 'NONE', '-'):
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', s_str) if unicodedata.category(c) != 'Mn')

# --- CONFIGURACIÓN DE LÍMITES POR CLIENTE, SUBCLIENTE Y EJE ---
def _construir_cache_limites_retiro(conn=None):
    """
    Carga en memoria todas las reglas de límites de retiro de configuracion_limites_retiro
    y configuracion_clientes en una sola lectura para resolver en O(1) eliminando consultas N+1.
    Retorna una función resolver_limite(cliente, subcliente='TODOS', eje='TODOS') -> float.
    Aplica jerarquía dinámica en cascada:
    1. Cliente + Subcliente + Eje
    2. Cliente + Subcliente + TODOS
    3. Cliente + TODOS + Eje
    4. Cliente + TODOS + TODOS
    5. Fallback a tabla legada configuracion_clientes
    6. Default sistema (3.0 mm)
    """
    def _cargar(c):
        cursor = c.cursor()
        cursor.execute("SELECT cliente, subcliente, eje, limite_retiro_mm FROM configuracion_limites_retiro")
        mapa_granular = {}
        for row in cursor.fetchall():
            cl = str(row[0] or '').strip().upper()
            sub = str(row[1] or 'TODOS').strip().upper() or 'TODOS'
            ej = str(row[2] or 'TODOS').strip().upper() or 'TODOS'
            lim = to_float(row[3], 3.0)
            mapa_granular[(cl, sub, ej)] = lim
            mapa_granular[(_quitar_tildes(cl), _quitar_tildes(sub), _quitar_tildes(ej))] = lim

        cursor.execute("SELECT cliente, limite_retiro_mm FROM configuracion_clientes")
        mapa_clientes = {}
        for row in cursor.fetchall():
            cl = str(row[0] or '').strip().upper()
            lim = to_float(row[1], 3.0)
            mapa_clientes[cl] = lim
            mapa_clientes[_quitar_tildes(cl)] = lim

        def resolver_limite(cliente='', subcliente='TODOS', eje='TODOS'):
            if pd.isna(cliente) or cliente is None:
                return 3.0
            c_norm = str(cliente).strip().upper()
            if not c_norm or c_norm in ('NAN', 'NONE'):
                return 3.0
            sub_norm = str(subcliente or 'TODOS').strip().upper() or 'TODOS'
            e_norm = str(eje or 'TODOS').strip().upper() or 'TODOS'

            c_sin = _quitar_tildes(c_norm)
            sub_sin = _quitar_tildes(sub_norm) or 'TODOS'
            e_sin = _quitar_tildes(e_norm) or 'TODOS'

            # 1. Búsqueda exacta: (cliente, subcliente, eje)
            if (c_norm, sub_norm, e_norm) in mapa_granular:
                return mapa_granular[(c_norm, sub_norm, e_norm)]
            if (c_sin, sub_sin, e_sin) in mapa_granular:
                return mapa_granular[(c_sin, sub_sin, e_sin)]

            # 2. cliente + subcliente + TODOS
            if e_norm != 'TODOS':
                if (c_norm, sub_norm, 'TODOS') in mapa_granular:
                    return mapa_granular[(c_norm, sub_norm, 'TODOS')]
                if (c_sin, sub_sin, 'TODOS') in mapa_granular:
                    return mapa_granular[(c_sin, sub_sin, 'TODOS')]

            # 3. cliente + TODOS + eje
            if sub_norm != 'TODOS':
                if (c_norm, 'TODOS', e_norm) in mapa_granular:
                    return mapa_granular[(c_norm, 'TODOS', e_norm)]
                if (c_sin, 'TODOS', e_sin) in mapa_granular:
                    return mapa_granular[(c_sin, 'TODOS', e_sin)]

            # 4. cliente + TODOS + TODOS
            if (c_norm, 'TODOS', 'TODOS') in mapa_granular:
                return mapa_granular[(c_norm, 'TODOS', 'TODOS')]
            if (c_sin, 'TODOS', 'TODOS') in mapa_granular:
                return mapa_granular[(c_sin, 'TODOS', 'TODOS')]

            # 5. Fallback a tabla legada configuracion_clientes
            if c_norm in mapa_clientes:
                return mapa_clientes[c_norm]
            if c_sin in mapa_clientes:
                return mapa_clientes[c_sin]

            return 3.0

        return resolver_limite

    if conn is not None:
        return _cargar(conn)
    else:
        with get_connection() as c:
            return _cargar(c)

def obtener_limite_retiro_cliente(cliente='', subcliente='TODOS', eje='TODOS', conn=None):
    resolver = _construir_cache_limites_retiro(conn=conn)
    return resolver(cliente, subcliente, eje)

def _cargar_mapa_tipologias_ejes(conn=None):
    """
    Carga en memoria el mapa de (tipologia_norm, posicion) -> tipo_eje ('DIRECCIONAL', 'TRACCIÓN', 'LIBRE', 'REPUESTO')
    a partir de catalogo_tipologias y sus esquemas JSON.
    """
    def _cargar(c):
        mapa = {}
        try:
            cursor = c.cursor()
            cursor.execute("SELECT nombre, esquema_json FROM catalogo_tipologias")
            for nom, esq_str in cursor.fetchall():
                if not nom or not esq_str:
                    continue
                nom_norm = _quitar_tildes(nom)
                try:
                    esq = json.loads(esq_str)
                    pos_map = {}
                    for eje_obj in esq:
                        t = str(eje_obj.get('tipo', '')).strip().lower()
                        if 'dir' in t:
                            t_eje = 'DIRECCIONAL'
                        elif 'trac' in t:
                            t_eje = 'TRACCIÓN'
                        elif 'rep' in t:
                            t_eje = 'REPUESTO'
                        else:
                            t_eje = 'LIBRE'
                        for p_obj in eje_obj.get('posiciones', []):
                            if 'pos' in p_obj:
                                pos_map[int(p_obj['pos'])] = t_eje
                    if pos_map:
                        mapa[nom_norm] = pos_map
                except Exception:
                    pass
        except Exception:
            pass
        return mapa

    if conn is not None:
        return _cargar(conn)
    else:
        with get_connection() as c:
            return _cargar(c)

def obtener_tipo_eje_posicion(tipologia, posicion, max_pos=None, mapa_tipologias=None):
    """
    Determina si la posición evaluada pertenece a eje DIRECCIONAL, TRACCIÓN, LIBRE o REPUESTO
    consultando el catálogo o por heurística técnica de transporte.
    """
    try:
        pos = int(posicion)
    except (ValueError, TypeError):
        return 'TRACCIÓN'

    if pos >= 90:
        return 'REPUESTO'

    t_norm = _quitar_tildes(tipologia)
    if mapa_tipologias:
        # 1. Búsqueda exacta
        if t_norm in mapa_tipologias and pos in mapa_tipologias[t_norm]:
            return mapa_tipologias[t_norm][pos]
        # 2. Búsqueda parcial
        for k, p_map in mapa_tipologias.items():
            if (t_norm and (t_norm in k or k in t_norm)) and pos in p_map:
                return p_map[pos]

    # Heurística de ingeniería de transporte
    t_lower = str(tipologia or '').lower()
    if 'trailer' in t_lower or 'remolque' in t_lower:
        return 'LIBRE'

    es_cuatro_manos = ('cuatro manos' in t_lower or (max_pos and max_pos >= 12 and 'cabezote' in t_lower))
    if es_cuatro_manos:
        if pos in (1, 2, 3, 4):
            return 'DIRECCIONAL'
        return 'TRACCIÓN'
    else:
        if pos in (1, 2):
            return 'DIRECCIONAL'
        return 'TRACCIÓN'

def calcular_matriz_semaforos_posicion(df_inspecciones, conn=None):
    """
    Construye la Matriz de Semáforos por Posición evaluando cada llanta montada contra
    la política de retiro técnico personalizada (por cliente, sede y tipo de eje).

    A. Reglas de Cálculo de Profundidad Mínima (PB):
       PB = min({p in {prof_ext, prof_cent, prof_int} | p > 0})
       Si todas las mediciones son <= 0, se considera sin datos o llanta en casco (PB = 0.0).

    B. Jerarquía Dinámica del Límite de Retiro (L):
       1. Cliente + Subcliente (Sede) + Eje específico
       2. Cliente + Subcliente (Sede) (todos los ejes de esa sede)
       3. Cliente + Eje específico
       4. Cliente general (política global del cliente)
       5. Valor por defecto del sistema (3.0 mm)

    C. Umbrales del Semáforo para cada posición i:
       🔴 Rojo: PB <= L -> Retiro Inmediato (Cambio YA)
       🟡 Amarillo: L < PB <= L + 2.0 mm -> Próxima a Cambio (Alerta Preventiva)
       🟢 Verde: PB > L + 2.0 mm -> Estado Óptimo (Normal)
       ⚪ Gris: PB <= 0 -> Sin Datos / Pendiente
    """
    if df_inspecciones is None or df_inspecciones.empty:
        return {
            'posiciones': [],
            'filas': [],
            'totales_posicion': {},
            'resumen_global': {'total_vehiculos': 0, 'total_llantas': 0, 'rojo': 0, 'amarillo': 0, 'verde': 0, 'gris': 0}
        }

    resolver_limite = _construir_cache_limites_retiro(conn=conn)
    mapa_tips = _cargar_mapa_tipologias_ejes(conn=conn)

    df = df_inspecciones.copy()
    if 'posicion' not in df.columns or 'placa' not in df.columns:
        return {
            'posiciones': [],
            'filas': [],
            'totales_posicion': {},
            'resumen_global': {'total_vehiculos': 0, 'total_llantas': 0, 'rojo': 0, 'amarillo': 0, 'verde': 0, 'gris': 0}
        }

    df['posicion'] = pd.to_numeric(df['posicion'], errors='coerce')
    df = df.dropna(subset=['posicion']).copy()
    df['posicion'] = df['posicion'].astype(int)

    posiciones_set = set(df['posicion'].unique())
    posiciones = [int(p) for p in sorted(list(posiciones_set))]

    filas = []
    totales_posicion = {int(p): {'rojo': 0, 'amarillo': 0, 'verde': 0, 'gris': 0, 'total': 0} for p in posiciones}
    resumen_global = {'total_vehiculos': 0, 'total_llantas': 0, 'rojo': 0, 'amarillo': 0, 'verde': 0, 'gris': 0}

    for placa, group in df.groupby('placa', sort=False):
        # Mismo criterio que analizar_inspecciones_df: fecha más reciente y última inspección por posición
        if 'fecha' in group.columns and not group['fecha'].dropna().empty:
            fecha_max = group['fecha'].astype(str).str[:10].max()
            group = group[group['fecha'].astype(str).str[:10] == fecha_max]
        if 'id' in group.columns:
            group_ult = group.sort_values('id').groupby('posicion', as_index=False).last()
        else:
            group_ult = group.drop_duplicates(subset=['posicion'], keep='last')

        cli = str(group_ult['cliente'].iloc[0] or '').strip().upper() if 'cliente' in group_ult.columns else ''
        sub = str(group_ult['subcliente'].iloc[0] or '').strip().upper() if 'subcliente' in group_ult.columns else ''
        op = str(group_ult['tipo_operacion'].iloc[0] or '').strip().upper() if 'tipo_operacion' in group_ult.columns else ''
        tip = str(group_ult['tipologia'].iloc[0] or '').strip() if 'tipologia' in group_ult.columns else ''
        km_max = to_float(group_ult['kilometraje'].max()) if 'kilometraje' in group_ult.columns else 0.0
        fecha_max_str = str(group_ult['fecha'].max() or '') if 'fecha' in group_ult.columns else ''
        max_p = group_ult['posicion'].max()

        pos_dict = {}
        conteo_veh = {'rojo': 0, 'amarillo': 0, 'verde': 0, 'gris': 0, 'total': 0}

        for _, r in group_ult.iterrows():
            pos = int(r['posicion'])
            pe = to_float(r.get('prof_ext', 0), 0.0)
            pc = to_float(r.get('prof_cent', 0), 0.0)
            pi = to_float(r.get('prof_int', 0), 0.0)

            # A. Profundidad Mínima (PB): min({p in {prof_ext, prof_cent, prof_int} | p > 0})
            validos = [p for p in (pe, pc, pi) if p > 0]
            if validos:
                pb = round(float(min(validos)), 1)
            else:
                pb = 0.0

            # B. Jerarquía Dinámica del Límite de Retiro
            eje_tipo = obtener_tipo_eje_posicion(tip, pos, max_pos=max_p, mapa_tipologias=mapa_tips)
            limite = resolver_limite(cli, sub, eje_tipo)

            # C. Umbrales del Semáforo
            if pb <= 0:
                color = 'gris'
                estado = 'Sin Datos / Casco'
                icono = '⚪'
                accion = 'Revisión física o registro de datos'
            elif pb <= limite:
                color = 'rojo'
                estado = 'Retiro Inmediato'
                icono = '🔴'
                accion = 'Programar desmontaje urgente para reencauche o baja definitiva'
            elif pb <= (limite + 2.0):
                color = 'amarillo'
                estado = 'Próxima a Cambio'
                icono = '🟡'
                accion = 'Monitoreo cercano. Alistar inventario de reemplazo (15 a 30 días)'
            else:
                color = 'verde'
                estado = 'Estado Óptimo'
                icono = '🟢'
                accion = 'Llantas con vida útil remanente suficiente. Mantener calibración PSI'

            pos_dict[pos] = {
                'pb': pb,
                'limite': limite,
                'eje': eje_tipo,
                'color': color,
                'estado': estado,
                'icono': icono,
                'accion': accion,
                'prof_ext': pe,
                'prof_cent': pc,
                'prof_int': pi
            }

            conteo_veh[color] += 1
            conteo_veh['total'] += 1

            if pos in totales_posicion:
                totales_posicion[pos][color] += 1
                totales_posicion[pos]['total'] += 1

            resumen_global[color] += 1
            resumen_global['total_llantas'] += 1

        resumen_global['total_vehiculos'] += 1

        filas.append({
            'placa': placa,
            'cliente': cli,
            'subcliente': sub,
            'tipo_operacion': op,
            'tipologia': tip,
            'km': km_max,
            'fecha': fecha_max_str,
            'posiciones': pos_dict,
            'conteo': conteo_veh
        })

    return {
        'posiciones': posiciones,
        'filas': filas,
        'totales_posicion': totales_posicion,
        'resumen_global': resumen_global
    }


def guardar_limite_retiro_cliente(cliente, limite_retiro_mm, observaciones='', subcliente='TODOS', eje='TODOS'):
    if pd.isna(cliente) or cliente is None:
        return False
    c = str(cliente).strip().upper()
    if not c or c in ('NAN', 'NONE'):
        return False
    sub = str(subcliente or 'TODOS').strip().upper() or 'TODOS'
    e = str(eje or 'TODOS').strip().upper() or 'TODOS'
    obs = str(observaciones or '').strip().upper()
    lim = to_float(limite_retiro_mm, 3.0)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente, subcliente, eje) DO UPDATE SET
                limite_retiro_mm = excluded.limite_retiro_mm,
                observaciones = excluded.observaciones,
                fecha_actualizacion = CURRENT_TIMESTAMP
        ''', (c, sub, e, lim, obs))
        if (sub in ('TODOS', 'BOGOTA', '') or True) and e == 'TODOS':
            cursor.execute('''
                INSERT INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cliente) DO UPDATE SET
                    limite_retiro_mm = excluded.limite_retiro_mm,
                    observaciones = excluded.observaciones,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            ''', (c, lim, obs))
            cursor.execute('''
                INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cliente) DO UPDATE SET
                    mm_retiro_direccional = excluded.mm_retiro_direccional,
                    mm_retiro_traccion = excluded.mm_retiro_traccion,
                    mm_retiro_arrastre = excluded.mm_retiro_arrastre,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            ''', (c, lim, lim, lim))
        elif 'DIR' in e:
            cursor.execute('''
                INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_direccional, fecha_actualizacion)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cliente) DO UPDATE SET
                    mm_retiro_direccional = excluded.mm_retiro_direccional,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            ''', (c, lim))
        elif 'TRAC' in e:
            cursor.execute('''
                INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_traccion, fecha_actualizacion)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cliente) DO UPDATE SET
                    mm_retiro_traccion = excluded.mm_retiro_traccion,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            ''', (c, lim))
        conn.commit()
    return True

def obtener_todas_configuraciones_clientes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion
            FROM configuracion_limites_retiro
            ORDER BY cliente ASC, subcliente ASC, eje ASC
        ''')
        cols = ['id', 'cliente', 'subcliente', 'eje', 'limite_retiro_mm', 'observaciones', 'fecha_actualizacion']
        return [dict(zip(cols, r)) for r in cursor.fetchall()]

def eliminar_limite_retiro_cliente(limite_id):
    try:
        lid = int(limite_id)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM configuracion_limites_retiro WHERE id = ?', (lid,))
            conn.commit()
        return True
    except Exception:
        return False

def actualizar_limite_retiro_cliente(limite_id, cliente, limite_retiro_mm, observaciones='', subcliente='TODOS', eje='TODOS'):
    lid = int(limite_id)
    c = str(cliente or '').strip().upper()
    sub = str(subcliente or 'TODOS').strip().upper() or 'TODOS'
    e = str(eje or 'TODOS').strip().upper() or 'TODOS'
    obs = str(observaciones or '').strip().upper()
    lim = to_float(limite_retiro_mm, 3.0)

    if not c or c in ('NAN', 'NONE'):
        raise ValueError("El nombre del cliente es obligatorio.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM configuracion_limites_retiro
            WHERE UPPER(TRIM(cliente)) = ? AND UPPER(TRIM(subcliente)) = ? AND UPPER(TRIM(eje)) = ? AND id != ?
        ''', (c, sub, e, lid))
        if cursor.fetchone():
            raise ValueError(f"Ya existe una regla de límite para el cliente '{c}', sede '{sub}' y eje '{e}'.")

        cursor.execute('''
            UPDATE configuracion_limites_retiro
            SET cliente = ?, subcliente = ?, eje = ?, limite_retiro_mm = ?, observaciones = ?, fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (c, sub, e, lim, obs, lid))
        if cursor.rowcount == 0:
            guardar_limite_retiro_cliente(c, lim, obs, sub, e)
        else:
            if (sub in ('TODOS', 'BOGOTA', '') or True) and e == 'TODOS':
                cursor.execute('''
                    INSERT INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(cliente) DO UPDATE SET
                        limite_retiro_mm = excluded.limite_retiro_mm,
                        observaciones = excluded.observaciones,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                ''', (c, lim, obs))
                cursor.execute('''
                    INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(cliente) DO UPDATE SET
                        mm_retiro_direccional = excluded.mm_retiro_direccional,
                        mm_retiro_traccion = excluded.mm_retiro_traccion,
                        mm_retiro_arrastre = excluded.mm_retiro_arrastre,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                ''', (c, lim, lim, lim))
            elif 'DIR' in e:
                cursor.execute('''
                    INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_direccional, fecha_actualizacion)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(cliente) DO UPDATE SET
                        mm_retiro_direccional = excluded.mm_retiro_direccional,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                ''', (c, lim))
            elif 'TRAC' in e:
                cursor.execute('''
                    INSERT INTO configuracion_avanzada_cliente (cliente, mm_retiro_traccion, fecha_actualizacion)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(cliente) DO UPDATE SET
                        mm_retiro_traccion = excluded.mm_retiro_traccion,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                ''', (c, lim))
        conn.commit()
    return True


def obtener_lista_clientes_unicos():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT UPPER(TRIM(cliente)) FROM (
                SELECT cliente FROM inspecciones WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_limites_retiro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_clientes
                UNION
                SELECT cliente FROM configuracion_avanzada_cliente
                UNION
                SELECT cliente FROM configuracion_marcas_cliente WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM llantas_maestro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
            ) ORDER BY 1 ASC
        ''')
        return [r[0] for r in cursor.fetchall() if r[0]]

def obtener_directorio_clientes() -> list:
    """
    Retorna el directorio maestro consolidado de clientes y flotas con métricas operativas:
    - Cliente / Razón Social
    - Tipo de Licencia (PRO / LIGHT)
    - Límite de retiro base (mm)
    - Sedes / Subclientes
    - N° Vehículos asociados
    - N° Inspecciones históricas
    - N° Llantas registradas en bodegas
    - N° Marcas habituales parametrizadas
    - Observaciones y fecha de actualización
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Lista de todos los clientes únicos registrados
        cursor.execute('''
            SELECT DISTINCT UPPER(TRIM(cliente)) FROM (
                SELECT cliente FROM inspecciones WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_limites_retiro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_clientes WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_avanzada_cliente WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_marcas_cliente WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM llantas_maestro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
            ) ORDER BY 1 ASC
        ''')
        clientes_unicos = [r[0] for r in cursor.fetchall() if r[0]]

        # 2. Diccionario de configuracion_clientes
        cursor.execute("SELECT UPPER(TRIM(cliente)), limite_retiro_mm, observaciones, fecha_actualizacion FROM configuracion_clientes")
        cfg_cli = {r[0]: {"limite": to_float(r[1], 3.0), "obs": r[2] or "", "fecha": str(r[3] or "")} for r in cursor.fetchall() if r[0]}

        # 3. Diccionario de configuracion_avanzada_cliente
        cursor.execute("SELECT UPPER(TRIM(cliente)), tipo_licencia, fecha_actualizacion FROM configuracion_avanzada_cliente")
        cfg_adv = {r[0]: {"licencia": str(r[1] or "PRO").upper(), "fecha": str(r[2] or "")} for r in cursor.fetchall() if r[0]}

        # 4. Sedes / subclientes por cliente
        cursor.execute('''
            SELECT DISTINCT UPPER(TRIM(cliente)), UPPER(TRIM(subcliente))
            FROM (
                SELECT cliente, subcliente FROM inspecciones WHERE subcliente IS NOT NULL AND TRIM(subcliente) != '' AND UPPER(TRIM(subcliente)) NOT IN ('TODOS', 'NAN', 'NONE')
                UNION
                SELECT cliente, subcliente FROM configuracion_limites_retiro WHERE subcliente IS NOT NULL AND TRIM(subcliente) != '' AND UPPER(TRIM(subcliente)) NOT IN ('TODOS', 'NAN', 'NONE')
                UNION
                SELECT cliente, subcliente FROM llantas_maestro WHERE subcliente IS NOT NULL AND TRIM(subcliente) != '' AND UPPER(TRIM(subcliente)) NOT IN ('TODOS', 'NAN', 'NONE')
            )
        ''')
        subclientes_map = {}
        for c, sub in cursor.fetchall():
            if c and sub:
                subclientes_map.setdefault(c, []).append(sub)

        # 5. Cantidad de vehículos (padrón + inspecciones)
        cursor.execute('''
            SELECT UPPER(TRIM(cliente)), COUNT(DISTINCT UPPER(TRIM(placa)))
            FROM (
                SELECT cliente, placa FROM inspecciones WHERE placa IS NOT NULL AND TRIM(placa) != ''
                UNION
                SELECT cliente, placa FROM padron_vehiculos_cliente WHERE placa IS NOT NULL AND TRIM(placa) != ''
            ) GROUP BY 1
        ''')
        vehiculos_map = {r[0]: r[1] for r in cursor.fetchall() if r[0]}

        # 6. Cantidad de inspecciones registradas
        cursor.execute("SELECT UPPER(TRIM(cliente)), COUNT(*) FROM inspecciones WHERE cliente IS NOT NULL AND TRIM(cliente) != '' GROUP BY 1")
        inspecciones_map = {r[0]: r[1] for r in cursor.fetchall() if r[0]}

        # 7. Cantidad de llantas registradas en bodegas
        cursor.execute("SELECT UPPER(TRIM(cliente)), COUNT(*) FROM llantas_maestro WHERE cliente IS NOT NULL AND TRIM(cliente) != '' GROUP BY 1")
        llantas_map = {r[0]: r[1] for r in cursor.fetchall() if r[0]}

        # 8. Cantidad de marcas habituales asociadas
        cursor.execute("SELECT UPPER(TRIM(cliente)), COUNT(DISTINCT marca) FROM configuracion_marcas_cliente WHERE cliente IS NOT NULL AND TRIM(cliente) != '' GROUP BY 1")
        marcas_map = {r[0]: r[1] for r in cursor.fetchall() if r[0]}

        directorio = []
        for c in clientes_unicos:
            lic = cfg_adv.get(c, {}).get("licencia", "PRO")
            lim = cfg_cli.get(c, {}).get("limite", 3.0)
            obs = cfg_cli.get(c, {}).get("obs", "")
            fecha = cfg_cli.get(c, {}).get("fecha") or cfg_adv.get(c, {}).get("fecha") or ""
            subs = sorted(list(set(subclientes_map.get(c, []))))

            directorio.append({
                "cliente": c,
                "tipo_licencia": lic,
                "limite_retiro_mm": lim,
                "subclientes": subs,
                "subclientes_str": ", ".join(subs) if subs else "Principal",
                "vehiculos_count": vehiculos_map.get(c, 0),
                "inspecciones_count": inspecciones_map.get(c, 0),
                "llantas_count": llantas_map.get(c, 0),
                "marcas_count": marcas_map.get(c, 0),
                "observaciones": obs,
                "fecha_actualizacion": fecha
            })

        return directorio

def crear_o_actualizar_cliente(datos: dict) -> dict:
    """
    Crea o actualiza un cliente / flota en el sistema:
    - Normaliza nombre en mayúsculas
    - Configura tipo de licencia (PRO / LIGHT)
    - Configura límite de retiro por defecto
    - Crea reglas base en configuracion_limites_retiro y sedes/subclientes
    """
    c = str(datos.get('cliente') or '').strip().upper()
    if not c or c in ('NAN', 'NONE', 'NULL'):
        raise ValueError("El nombre o razón social del cliente es obligatorio.")

    lic = str(datos.get('tipo_licencia') or 'PRO').strip().upper()
    if lic not in ('PRO', 'LIGHT'):
        lic = 'PRO'

    lim = to_float(datos.get('limite_retiro_mm'), 3.0)
    obs = str(datos.get('observaciones') or '').strip()
    subclientes_input = datos.get('subclientes') or ''

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. configuracion_clientes
        cursor.execute('''
            INSERT INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                limite_retiro_mm = excluded.limite_retiro_mm,
                observaciones = CASE WHEN excluded.observaciones != '' THEN excluded.observaciones ELSE configuracion_clientes.observaciones END,
                fecha_actualizacion = CURRENT_TIMESTAMP
        ''', (c, lim, obs))

        # 2. configuracion_avanzada_cliente
        cursor.execute('''
            INSERT INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                tipo_licencia = excluded.tipo_licencia,
                fecha_actualizacion = CURRENT_TIMESTAMP
        ''', (c, lic, lim, lim, lim))

        # 3. Regla por defecto en configuracion_limites_retiro
        cursor.execute('''
            INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES (?, 'TODOS', 'TODOS', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente, subcliente, eje) DO UPDATE SET
                limite_retiro_mm = excluded.limite_retiro_mm,
                observaciones = excluded.observaciones,
                fecha_actualizacion = CURRENT_TIMESTAMP
        ''', (c, lim, obs))

        # 4. Sedes / subclientes si se proporcionaron
        if subclientes_input:
            if isinstance(subclientes_input, str):
                subs_list = [s.strip().upper() for s in subclientes_input.replace(';', ',').split(',') if s.strip()]
            else:
                subs_list = [str(s).strip().upper() for s in subclientes_input if str(s).strip()]

            for sub in subs_list:
                if sub and sub not in ('TODOS', 'NAN', 'NONE'):
                    cursor.execute('''
                        INSERT OR IGNORE INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
                        VALUES (?, ?, 'TODOS', ?, ?, CURRENT_TIMESTAMP)
                    ''', (c, sub, lim, f"Sede {sub} de {c}"))

        conn.commit()

    return {"ok": True, "cliente": c, "mensaje": f"Cliente '{c}' guardado exitosamente."}

def eliminar_cliente_directorio(cliente: str) -> dict:
    """
    Elimina un cliente del directorio si no tiene historial de inspecciones o llantas en bodega.
    """
    c = str(cliente or '').strip().upper()
    if not c:
        raise ValueError("Nombre de cliente inválido.")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Validar si tiene inspecciones
        cursor.execute("SELECT COUNT(*) FROM inspecciones WHERE UPPER(TRIM(cliente)) = ?", (c,))
        cnt_insp = cursor.fetchone()[0]
        if cnt_insp > 0:
            return {"ok": False, "mensaje": f"No se puede eliminar el cliente '{c}' porque tiene {cnt_insp} inspecciones registradas en el historial."}

        cursor.execute("SELECT COUNT(*) FROM llantas_maestro WHERE UPPER(TRIM(cliente)) = ?", (c,))
        cnt_ll = cursor.fetchone()[0]
        if cnt_ll > 0:
            return {"ok": False, "mensaje": f"No se puede eliminar el cliente '{c}' porque tiene {cnt_ll} llantas en inventario de bodegas."}

        cursor.execute("DELETE FROM configuracion_clientes WHERE UPPER(TRIM(cliente)) = ?", (c,))
        cursor.execute("DELETE FROM configuracion_avanzada_cliente WHERE UPPER(TRIM(cliente)) = ?", (c,))
        cursor.execute("DELETE FROM configuracion_limites_retiro WHERE UPPER(TRIM(cliente)) = ?", (c,))
        cursor.execute("DELETE FROM configuracion_marcas_cliente WHERE UPPER(TRIM(cliente)) = ?", (c,))
        cursor.execute("DELETE FROM padron_vehiculos_cliente WHERE UPPER(TRIM(cliente)) = ?", (c,))
        conn.commit()

    return {"ok": True, "cliente": c, "mensaje": f"Cliente '{c}' eliminado exitosamente."}

# ==========================================
# CONFIGURACIÓN DE MARCAS POR CLIENTE
# ==========================================

def sincronizar_marca_cliente(cliente, marca, conn=None):
    """
    Registra o actualiza la asociación cliente <-> marca en configuracion_marcas_cliente.
    """
    cli = str(cliente or '').strip().upper()
    m = str(marca or '').strip()
    if not cli or not m or cli in ('NAN', 'NONE') or m in ('NAN', 'NONE'):
        return
    sql = """
        INSERT INTO configuracion_marcas_cliente (cliente, marca, fecha_actualizacion)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(cliente, marca) DO UPDATE SET fecha_actualizacion = CURRENT_TIMESTAMP
    """
    if conn:
        conn.execute(sql, (cli, m))
    else:
        with get_connection() as c:
            c.execute(sql, (cli, m))
            c.commit()

def guardar_marca_cliente(cliente: str, marca: str) -> bool:
    """
    Asocia explícitamente una marca a un cliente en configuracion_marcas_cliente.
    """
    cli = str(cliente or '').strip().upper()
    m = str(marca or '').strip()
    if not cli or not m:
        return False
    sincronizar_marca_cliente(cli, m)
    return True

def obtener_marcas_por_cliente(cliente: str) -> list:
    """
    Retorna la lista de marcas asociadas a un cliente específico.
    """
    cli = str(cliente or '').strip().upper()
    if not cli:
        return []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT marca
            FROM configuracion_marcas_cliente
            WHERE UPPER(TRIM(cliente)) = ?
            ORDER BY marca ASC
        """, (cli,))
        return [r[0] for r in cursor.fetchall() if r[0] and str(r[0]).strip()]

def eliminar_marca_cliente(cliente: str, marca: str) -> bool:
    """
    Desvincula una marca de un cliente por nombres.
    """
    cli = str(cliente or '').strip().upper()
    m = str(marca or '').strip()
    if not cli or not m:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM configuracion_marcas_cliente
            WHERE UPPER(TRIM(cliente)) = ? AND UPPER(TRIM(marca)) = UPPER(TRIM(?))
        """, (cli, m))
        conn.commit()
        return cursor.rowcount > 0

def eliminar_marca_cliente_por_id(marca_id: int) -> bool:
    """
    Elimina una asociación cliente <-> marca por su ID primario.
    """
    try:
        mid = int(marca_id)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM configuracion_marcas_cliente WHERE id = ?", (mid,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False

def obtener_todas_configuraciones_marcas() -> list:
    """
    Retorna todas las configuraciones cliente <-> marca registradas.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, cliente, marca, fecha_actualizacion
            FROM configuracion_marcas_cliente
            ORDER BY cliente ASC, marca ASC
        """)
        cols = ['id', 'cliente', 'marca', 'fecha_actualizacion']
        return [dict(zip(cols, r)) for r in cursor.fetchall()]

# --- CATALOGOS DINAMICOS ---
def obtener_todas_operaciones():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT nombre FROM catalogo_operaciones ORDER BY nombre ASC')
        return [r[0] for r in cursor.fetchall()]

def guardar_operacion(nombre):
    nom = (nombre or '').strip().upper()
    if not nom:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO catalogo_operaciones (nombre) VALUES (?)', (nom,))
        conn.commit()
        return nom

def obtener_todas_tipologias():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT nombre, descripcion, cant_llantas, esquema_json FROM catalogo_tipologias ORDER BY nombre ASC')
        res = []
        for r in cursor.fetchall():
            import json
            res.append({'nombre': r[0], 'descripcion': r[1], 'cant_llantas': r[2], 'esquema': json.loads(r[3]) if r[3] else []})
        return res

def generar_esquema_desde_composicion(ejes_dir=1, tipo_dir='sencilla', ejes_trac=2, tipo_trac='dual', ejes_libres=0, tipo_libres='dual', cant_repuestos=0):
    """
    Construye el esquema dinámico JSON de posiciones y ejes basado en la composición:
    - Ejes Direccionales (Delanteros): cantidad y si es sencilla (2 llantas) o dual (4 llantas)
    - Ejes de Tracción (Fuerza): cantidad y si es dual (4 llantas) o sencilla (2 llantas)
    - Ejes Libres / Arrastre / Trailer: cantidad y si es dual (4 llantas) o sencilla (2 llantas)
    - Llanta(s) de Repuesto: 0, 1 o 2 llantas
    """
    ejes_dir = max(0, int(ejes_dir or 0))
    ejes_trac = max(0, int(ejes_trac or 0))
    ejes_libres = max(0, int(ejes_libres or 0))
    cant_repuestos = max(0, min(2, int(cant_repuestos or 0)))
    
    tipo_dir = str(tipo_dir or 'sencilla').strip().lower()
    tipo_trac = str(tipo_trac or 'dual').strip().lower()
    tipo_libres = str(tipo_libres or 'dual').strip().lower()
    
    esquema = []
    pos_act = 1
    num_eje_global = 1
    
    # 1. Ejes Direccionales
    for _ in range(ejes_dir):
        if 'dual' in tipo_dir:
            posiciones = [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_act+1},
                {'pos': pos_act+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_act},
                {'pos': pos_act+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_act+3},
                {'pos': pos_act+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_act+2}
            ]
            pos_act += 4
        else:
            posiciones = [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'dir', 'dual': False},
                {'pos': pos_act+1, 'lado': 'der', 'rol': 'dir', 'dual': False}
            ]
            pos_act += 2
        esquema.append({
            'eje': num_eje_global,
            'nombre': f'Eje {num_eje_global} (Direccional)',
            'tipo': 'direccional',
            'posiciones': posiciones
        })
        num_eje_global += 1
        
    # 2. Ejes de Tracción
    for _ in range(ejes_trac):
        if 'sencilla' in tipo_trac:
            posiciones = [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'sen', 'dual': False},
                {'pos': pos_act+1, 'lado': 'der', 'rol': 'sen', 'dual': False}
            ]
            pos_act += 2
        else:
            posiciones = [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_act+1},
                {'pos': pos_act+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_act},
                {'pos': pos_act+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_act+3},
                {'pos': pos_act+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_act+2}
            ]
            pos_act += 4
        esquema.append({
            'eje': num_eje_global,
            'nombre': f'Eje {num_eje_global} (Tracción)',
            'tipo': 'traccion',
            'posiciones': posiciones
        })
        num_eje_global += 1
        
    # 3. Ejes Libres / Arrastre / Trailer
    for _ in range(ejes_libres):
        if 'sencilla' in tipo_libres:
            posiciones = [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'sen', 'dual': False},
                {'pos': pos_act+1, 'lado': 'der', 'rol': 'sen', 'dual': False}
            ]
            pos_act += 2
        else:
            posiciones = [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_act+1},
                {'pos': pos_act+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_act},
                {'pos': pos_act+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_act+3},
                {'pos': pos_act+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_act+2}
            ]
            pos_act += 4
        esquema.append({
            'eje': num_eje_global,
            'nombre': f'Eje {num_eje_global} (Libre / Arrastre)',
            'tipo': 'libre',
            'posiciones': posiciones
        })
        num_eje_global += 1
        
    # 4. Llantas de Repuesto
    if cant_repuestos == 1:
        esquema.append({
            'eje': 99,
            'nombre': 'Repuesto',
            'tipo': 'repuesto',
            'posiciones': [{'pos': pos_act, 'lado': 'izq', 'rol': 'rep', 'dual': False}]
        })
        pos_act += 1
    elif cant_repuestos >= 2:
        esquema.append({
            'eje': 99,
            'nombre': 'Repuestos',
            'tipo': 'repuesto',
            'posiciones': [
                {'pos': pos_act, 'lado': 'izq', 'rol': 'rep', 'dual': False},
                {'pos': pos_act+1, 'lado': 'der', 'rol': 'rep', 'dual': False}
            ]
        })
        pos_act += 2
        
    total_llantas = pos_act - 1
    return esquema, total_llantas

def guardar_tipologia(nombre, descripcion='', cant_llantas=None, esquema_custom=None,
                      ejes_dir=None, tipo_dir='sencilla',
                      ejes_trac=None, tipo_trac='dual',
                      ejes_libres=None, tipo_libres='dual',
                      cant_repuestos=0):
    nom = (nombre or '').strip().upper()
    if not nom:
        return None
    import json
    desc = str(descripcion or '').strip().upper()

    # Si se especificó composición de ejes (ejes_dir, ejes_trac, etc.)
    if ejes_dir is not None or ejes_trac is not None or ejes_libres is not None:
        esquema, cant_calculada = generar_esquema_desde_composicion(
            ejes_dir=ejes_dir or 0,
            tipo_dir=tipo_dir,
            ejes_trac=ejes_trac or 0,
            tipo_trac=tipo_trac,
            ejes_libres=ejes_libres or 0,
            tipo_libres=tipo_libres,
            cant_repuestos=cant_repuestos
        )
        cant = cant_calculada
    elif esquema_custom and isinstance(esquema_custom, list) and len(esquema_custom) > 0:
        esquema = esquema_custom
        cant = sum(len(eje.get('posiciones', [])) for eje in esquema)
    else:
        cant = int(cant_llantas or 10)
        nom_l = nom.lower()
        if 'biarticulado' in nom_l:
            cant = 14
            esquema = [
                {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]},
                {'eje': 2, 'nombre': 'Eje 2 (Tracción)', 'tipo': 'traccion', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 4}, {'pos': 4, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 3}, {'pos': 5, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 6}, {'pos': 6, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 5}]},
                {'eje': 3, 'nombre': 'Eje 3 (Libre / Arrastre)', 'tipo': 'libre', 'posiciones': [{'pos': 7, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 8}, {'pos': 8, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 7}, {'pos': 9, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 10}, {'pos': 10, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 9}]},
                {'eje': 4, 'nombre': 'Eje 4 (Libre / Arrastre)', 'tipo': 'libre', 'posiciones': [{'pos': 11, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 12}, {'pos': 12, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 11}, {'pos': 13, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 14}, {'pos': 14, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 13}]}
            ]
        elif 'articulado' in nom_l and 'bi' not in nom_l:
            cant = 10
            esquema = [
                {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]},
                {'eje': 2, 'nombre': 'Eje 2 (Tracción)', 'tipo': 'traccion', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 4}, {'pos': 4, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 3}, {'pos': 5, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 6}, {'pos': 6, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 5}]},
                {'eje': 3, 'nombre': 'Eje 3 (Libre / Arrastre)', 'tipo': 'libre', 'posiciones': [{'pos': 7, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': 8}, {'pos': 8, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': 7}, {'pos': 9, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': 10}, {'pos': 10, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': 9}]}
            ]
        else:
            esquema = [
                {'eje': 1, 'nombre': 'Eje 1 (Direccional)', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': 2, 'lado': 'der', 'rol': 'direccional', 'dual': False}]}
            ]
            resto = cant - 2
            pos_actual = 3
            eje_num = 2
            while resto > 0:
                if resto >= 4:
                    esquema.append({
                        'eje': eje_num,
                        'nombre': f'Eje {eje_num} (Dual)',
                        'tipo': 'traccion',
                        'posiciones': [
                            {'pos': pos_actual, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_actual+1},
                            {'pos': pos_actual+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_actual},
                            {'pos': pos_actual+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_actual+3},
                            {'pos': pos_actual+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_actual+2}
                        ]
                    })
                    pos_actual += 4
                    resto -= 4
                else:
                    esquema.append({
                        'eje': eje_num,
                        'nombre': f'Eje {eje_num}',
                        'tipo': 'traccion',
                        'posiciones': [
                            {'pos': pos_actual, 'lado': 'izq', 'rol': 'sencillo', 'dual': False},
                            {'pos': pos_actual+1, 'lado': 'der', 'rol': 'sencillo', 'dual': False}
                        ]
                    })
                    pos_actual += 2
                    resto -= 2
                eje_num += 1

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, ?, ?, ?)',
                       (nom, desc, cant, json.dumps(esquema)))
        conn.commit()
    return nom

def obtener_esquema_tipologia(tipologia_nombre):
    import json
    t_norm = str(tipologia_nombre or '').strip().lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT nombre, cant_llantas, esquema_json FROM catalogo_tipologias')
            filas = cursor.fetchall()
            # 1. Coincidencia exacta primero
            for r in filas:
                if r[0] and str(r[0]).strip().lower() == t_norm:
                    return json.loads(r[2]) if r[2] else []
            # 2. Coincidencia parcial si no hay exacta
            for r in filas:
                nom_row = str(r[0] or '').strip().lower()
                if nom_row and (t_norm in nom_row or nom_row in t_norm):
                    return json.loads(r[2]) if r[2] else []
            # 2b. Coincidencia por palabras clave
            palabras = [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', t_norm).split() if len(w) >= 2]
            if palabras:
                for r in filas:
                    nom_row = str(r[0] or '').strip().lower()
                    if all(p in nom_row for p in palabras):
                        return json.loads(r[2]) if r[2] else []
    except Exception:
        pass

    # 4. Esquema heurístico estándar de respaldo para entornos de prueba o tipologías nuevas
    if "cuatro manos" in t_norm or "8x4" in t_norm or "biarticulado" in t_norm:
        return [
            {'eje': 1, 'nombre': 'Eje 1', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'dir'}, {'pos': 2, 'lado': 'der', 'rol': 'dir'}]},
            {'eje': 2, 'nombre': 'Eje 2', 'tipo': 'direccional', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'dir'}, {'pos': 4, 'lado': 'der', 'rol': 'dir'}]},
            {'eje': 3, 'nombre': 'Eje 3', 'tipo': 'traccion', 'posiciones': [{'pos': 5, 'lado': 'izq', 'rol': 'ext'}, {'pos': 6, 'lado': 'izq', 'rol': 'int'}, {'pos': 7, 'lado': 'der', 'rol': 'int'}, {'pos': 8, 'lado': 'der', 'rol': 'ext'}]},
            {'eje': 4, 'nombre': 'Eje 4', 'tipo': 'traccion', 'posiciones': [{'pos': 9, 'lado': 'izq', 'rol': 'ext'}, {'pos': 10, 'lado': 'izq', 'rol': 'int'}, {'pos': 11, 'lado': 'der', 'rol': 'int'}, {'pos': 12, 'lado': 'der', 'rol': 'ext'}]}
        ]
    elif "articulado" in t_norm or "dobletroque" in t_norm or "6x4" in t_norm or "10" in t_norm:
        return [
            {'eje': 1, 'nombre': 'Eje 1', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'dir'}, {'pos': 2, 'lado': 'der', 'rol': 'dir'}]},
            {'eje': 2, 'nombre': 'Eje 2', 'tipo': 'traccion', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'ext'}, {'pos': 4, 'lado': 'izq', 'rol': 'int'}, {'pos': 5, 'lado': 'der', 'rol': 'int'}, {'pos': 6, 'lado': 'der', 'rol': 'ext'}]},
            {'eje': 3, 'nombre': 'Eje 3', 'tipo': 'traccion', 'posiciones': [{'pos': 7, 'lado': 'izq', 'rol': 'ext'}, {'pos': 8, 'lado': 'izq', 'rol': 'int'}, {'pos': 9, 'lado': 'der', 'rol': 'int'}, {'pos': 10, 'lado': 'der', 'rol': 'ext'}]}
        ]
    elif "repuesto" in t_norm:
        return [
            {'eje': 1, 'nombre': 'Eje 1', 'tipo': 'remolque', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'ext'}, {'pos': 2, 'lado': 'izq', 'rol': 'int'}, {'pos': 3, 'lado': 'der', 'rol': 'int'}, {'pos': 4, 'lado': 'der', 'rol': 'ext'}]},
            {'eje': 2, 'nombre': 'Eje 2', 'tipo': 'remolque', 'posiciones': [{'pos': 5, 'lado': 'izq', 'rol': 'ext'}, {'pos': 6, 'lado': 'izq', 'rol': 'int'}, {'pos': 7, 'lado': 'der', 'rol': 'int'}, {'pos': 8, 'lado': 'der', 'rol': 'ext'}]},
            {'eje': 99, 'nombre': 'Repuesto', 'tipo': 'repuesto', 'posiciones': [{'pos': 9, 'lado': 'izq', 'rol': 'rep'}]}
        ]
    else: # 2 ejes (C2, Camion Sencillo 4x2, etc.)
        return [
            {'eje': 1, 'nombre': 'Eje 1', 'tipo': 'direccional', 'posiciones': [{'pos': 1, 'lado': 'izq', 'rol': 'dir'}, {'pos': 2, 'lado': 'der', 'rol': 'dir'}]},
            {'eje': 2, 'nombre': 'Eje 2', 'tipo': 'traccion', 'posiciones': [{'pos': 3, 'lado': 'izq', 'rol': 'ext'}, {'pos': 4, 'lado': 'izq', 'rol': 'int'}, {'pos': 5, 'lado': 'der', 'rol': 'int'}, {'pos': 6, 'lado': 'der', 'rol': 'ext'}]}
        ]

def actualizar_operacion(nombre_antiguo, nombre_nuevo):
    nom_a = (nombre_antiguo or '').strip().upper()
    nom_n = (nombre_nuevo or '').strip().upper()
    if not nom_a or not nom_n:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE catalogo_operaciones SET nombre = ? WHERE UPPER(nombre) = ?', (nom_n, nom_a))
        cursor.execute('UPDATE inspecciones SET tipo_operacion = ? WHERE UPPER(tipo_operacion) = ?', (nom_n, nom_a))
        conn.commit()
    return True

def eliminar_operacion(nombre):
    nom = (nombre or '').strip().upper()
    if not nom:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM catalogo_operaciones WHERE UPPER(nombre) = ?', (nom,))
        conn.commit()
    return True

def contar_usos_tipologia(nombre):
    nom = (nombre or '').strip().upper()
    if not nom:
        return {'inspecciones': 0, 'vehiculos': 0, 'total': 0}
    nom_norm = normalizar_texto(nom)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT tipologia FROM inspecciones WHERE tipologia IS NOT NULL AND TRIM(tipologia) != ""')
        insp_count = sum(1 for (t,) in cursor.fetchall() if (t or '').strip().upper() == nom or normalizar_texto(t) == nom_norm)
        cursor.execute('SELECT tipologia FROM catalogo_vehiculos WHERE tipologia IS NOT NULL AND TRIM(tipologia) != ""')
        veh_count = sum(1 for (t,) in cursor.fetchall() if (t or '').strip().upper() == nom or normalizar_texto(t) == nom_norm)
    return {'inspecciones': insp_count, 'vehiculos': veh_count, 'total': insp_count + veh_count}

def eliminar_tipologia(nombre):
    nom = (nombre or '').strip().upper()
    if not nom:
        return False
    usos = contar_usos_tipologia(nom)
    if usos['total'] > 0:
        raise ValueError(
            f"No se puede eliminar la tipología '{nom}' porque está siendo utilizada en "
            f"{usos['inspecciones']} inspección(es) y {usos['vehiculos']} vehículo(s) de la base de datos."
        )
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM catalogo_tipologias WHERE UPPER(TRIM(nombre)) = ?', (nom,))
        conn.commit()
    return True

def actualizar_tipologia(nombre_antiguo, nombre_nuevo, descripcion='', cant_llantas=None,
                         ejes_dir=None, tipo_dir='sencilla',
                         ejes_trac=None, tipo_trac='dual',
                         ejes_libres=None, tipo_libres='dual',
                         cant_repuestos=None, esquema_custom=None, config_ejes=None):
    nom_a = (nombre_antiguo or '').strip().upper()
    nom_n = (nombre_nuevo or '').strip().upper()
    if not nom_a or not nom_n:
        raise ValueError("El nombre actual y el nuevo nombre de la tipología son obligatorios.")

    desc = str(descripcion or '').strip().upper()
    import json

    # Si se especificó composición de ejes desde el modal visual
    if ejes_dir is not None or ejes_trac is not None or ejes_libres is not None:
        esquema, cant_calculada = generar_esquema_desde_composicion(
            ejes_dir=ejes_dir or 0,
            tipo_dir=tipo_dir,
            ejes_trac=ejes_trac or 0,
            tipo_trac=tipo_trac,
            ejes_libres=ejes_libres or 0,
            tipo_libres=tipo_libres,
            cant_repuestos=cant_repuestos or 0
        )
        cant = cant_calculada
        esquema_json = json.dumps(esquema)
    elif esquema_custom and isinstance(esquema_custom, list) and len(esquema_custom) > 0:
        esquema_json = json.dumps(esquema_custom)
        cant = sum(len(eje.get('posiciones', [])) for eje in esquema_custom)
    else:
        # Mantener el esquema existente
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT esquema_json, cant_llantas FROM catalogo_tipologias WHERE UPPER(TRIM(nombre)) = ?', (nom_a,))
            row = cursor.fetchone()
            if row:
                esquema_json = row[0]
                cant = int(cant_llantas or row[1] or 10)
            else:
                esquema_json = '[]'
                cant = int(cant_llantas or 10)

    with get_connection() as conn:
        cursor = conn.cursor()
        if nom_a == nom_n:
            cursor.execute('''
                UPDATE catalogo_tipologias
                SET descripcion = ?, cant_llantas = ?, esquema_json = ?
                WHERE UPPER(TRIM(nombre)) = ?
            ''', (desc, cant, esquema_json, nom_a))
        else:
            cursor.execute('SELECT COUNT(*) FROM catalogo_tipologias WHERE UPPER(TRIM(nombre)) = ?', (nom_n,))
            if cursor.fetchone()[0] > 0:
                raise ValueError(f"Ya existe una tipología registrada con el nombre '{nom_n}'.")

            cursor.execute('''
                UPDATE catalogo_tipologias
                SET nombre = ?, descripcion = ?, cant_llantas = ?, esquema_json = ?
                WHERE UPPER(TRIM(nombre)) = ?
            ''', (nom_n, desc, cant, esquema_json, nom_a))

            # Actualizar en cascada en la base de datos de inspecciones y vehículos
            cursor.execute('UPDATE inspecciones SET tipologia = ? WHERE UPPER(TRIM(tipologia)) = ?', (nom_n, nom_a))
            cursor.execute('UPDATE catalogo_vehiculos SET tipologia = ? WHERE UPPER(TRIM(tipologia)) = ?', (nom_n, nom_a))

        conn.commit()
    return True

def obtener_catalogo_modelos():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion FROM catalogo_modelos_llantas ORDER BY tipo_llanta ASC, marca ASC, diseno ASC')
        cols = ['id', 'tipo_llanta', 'marca', 'diseno', 'dimension', 'prof_inicial', 'descripcion']
        return [dict(zip(cols, r)) for r in cursor.fetchall()]

def buscar_profundidad_inicial(marca, diseno, dimension='', vida='Original', banda=''):
    m = (marca or '').strip()
    d = (diseno or '').strip()
    dim = (dimension or '').strip()
    b = (banda or '').strip()
    es_reencauche = str(vida).strip().lower() == 'reencauche'
    tipo = 'Reencauche' if es_reencauche else 'Nueva'

    # Evitar textos placeholder de interfaz
    if '(seleccionar' in m.lower(): m = ''
    if '(seleccionar' in d.lower(): d = ''
    if '(seleccionar' in b.lower(): b = ''

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Si es Reencauche y se proporcionó una banda, buscar prioritariamente la banda en catálogo
        if es_reencauche and b:
            if dim:
                cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = "reencauche" AND LOWER(diseno) = LOWER(?) AND LOWER(dimension) = LOWER(?) LIMIT 1', (b, dim))
                r = cursor.fetchone()
                if r and r[0] > 0:
                    return r[0]
            cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = "reencauche" AND LOWER(diseno) = LOWER(?) LIMIT 1', (b,))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]
            cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = "reencauche" AND (LOWER(marca || " " || diseno) LIKE ? OR LOWER(diseno) LIKE ?) LIMIT 1', (f"%{b.lower()}%", f"%{b.lower()}%"))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

        # 2. Búsqueda directa en catálogo con tipo de llanta (Nueva / Reencauche)
        if m and d:
            if dim:
                cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) AND LOWER(dimension) = LOWER(?) LIMIT 1', (tipo, m, d, dim))
                r = cursor.fetchone()
                if r and r[0] > 0:
                    return r[0]
            cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) LIMIT 1', (tipo, m, d))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

        if d:
            if dim:
                cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(diseno) = LOWER(?) AND LOWER(dimension) = LOWER(?) LIMIT 1', (tipo, d, dim))
                r = cursor.fetchone()
                if r and r[0] > 0:
                    return r[0]
            cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(diseno) = LOWER(?) LIMIT 1', (tipo, d))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

        # 3. Fallback en catálogo sin filtro de tipo_llanta
        if m and d:
            if dim:
                cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) AND LOWER(dimension) = LOWER(?) LIMIT 1', (m, d, dim))
                r = cursor.fetchone()
                if r and r[0] > 0:
                    return r[0]
            cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) LIMIT 1', (m, d))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

        if d:
            cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(diseno) = LOWER(?) LIMIT 1', (d,))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

        # 4. Fallback en historial de inspecciones previas
        if m and d:
            cursor.execute('''
                SELECT prof_inicial FROM inspecciones
                WHERE LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) AND prof_inicial > 0
                ORDER BY fecha DESC, id DESC LIMIT 1
            ''', (m, d))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

        if d:
            cursor.execute('''
                SELECT prof_inicial FROM inspecciones
                WHERE LOWER(diseno) = LOWER(?) AND prof_inicial > 0
                ORDER BY fecha DESC, id DESC LIMIT 1
            ''', (d,))
            r = cursor.fetchone()
            if r and r[0] > 0:
                return r[0]

    return 0.0

def guardar_modelo_llanta(tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion=''):
    tipo = str(tipo_llanta or 'NUEVA').strip().upper()
    m = str(marca or '').strip().upper()
    d = str(diseno or '').strip().upper()
    dim = str(dimension or '').strip().upper()
    prof = to_float(prof_inicial, 0.0)
    desc = str(descripcion or '').strip().upper()
    if not m or not d:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO catalogo_modelos_llantas (tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion) VALUES (?, ?, ?, ?, ?, ?)', (tipo, m, d, dim, prof, desc))
        conn.commit()
    return True

def actualizar_modelo_llanta(modelo_id, tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion='', actualizar_bd=True):
    mid = int(modelo_id)
    tipo = str(tipo_llanta or 'NUEVA').strip().capitalize()
    m_new = str(marca or '').strip()
    d_new = str(diseno or '').strip()
    dim_new = str(dimension or '').strip()
    prof_new = to_float(prof_inicial, 0.0)
    desc_new = str(descripcion or '').strip()

    if not m_new or not d_new or prof_new <= 0:
        raise ValueError("Marca, diseño y una profundidad inicial mayor a 0 son obligatorios.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT tipo_llanta, marca, diseno, dimension, prof_inicial FROM catalogo_modelos_llantas WHERE id = ?', (mid,))
        row_prev = cursor.fetchone()
        if not row_prev:
            raise ValueError(f"No se encontró el modelo con ID {mid}.")

        tipo_old, m_old, d_old, dim_old, prof_old = row_prev

        # Actualizar en catalogo_modelos_llantas
        cursor.execute('''
            UPDATE catalogo_modelos_llantas
            SET tipo_llanta = ?, marca = ?, diseno = ?, dimension = ?, prof_inicial = ?, descripcion = ?
            WHERE id = ?
        ''', (tipo, m_new, d_new, dim_new, prof_new, desc_new, mid))

        filas_actualizadas = 0
        if actualizar_bd:
            # Sincronizar en la tabla de inspecciones: ajustar prof_inicial de las llantas correspondientes
            m_old_u = str(m_old or '').strip().upper()
            d_old_u = str(d_old or '').strip().upper()
            m_new_u = m_new.strip().upper()
            d_new_u = d_new.strip().upper()

            d_old_clean = re.sub(r'[\s\-_]+', '', d_old_u)
            d_new_clean = re.sub(r'[\s\-_]+', '', d_new_u)

            dim_old_clean = re.sub(r'[\s\-_]+', '', str(dim_old or '').strip().upper())
            dim_new_clean = re.sub(r'[\s\-_]+', '', dim_new.strip().upper())

            cursor.execute('SELECT id, marca, diseno, dimension, banda_reen FROM inspecciones')
            todas_insp = cursor.fetchall()
            ids_coincidentes = []

            for i_id, i_marca, i_diseno, i_dim, i_banda in todas_insp:
                im_u = str(i_marca or '').strip().upper()
                id_u = str(i_diseno or '').strip().upper()
                id_clean = re.sub(r'[\s\-_]+', '', id_u)
                ib_u = str(i_banda or '').strip().upper()
                ib_clean = re.sub(r'[\s\-_]+', '', ib_u)
                idim_clean = re.sub(r'[\s\-_]+', '', str(i_dim or '').strip().upper())

                marca_match = (
                    im_u in (m_old_u, m_new_u) or
                    ib_u in (m_old_u, m_new_u) or
                    (m_old_u and m_old_u in im_u) or
                    (m_new_u and m_new_u in im_u)
                )

                diseno_match = (
                    id_u in (d_old_u, d_new_u) or
                    (id_clean and id_clean in (d_old_clean, d_new_clean)) or
                    (ib_clean and ib_clean in (d_old_clean, d_new_clean)) or
                    ib_u in (d_old_u, d_new_u)
                )

                if marca_match and diseno_match:
                    if dim_new_clean and idim_clean:
                        if idim_clean not in (dim_old_clean, dim_new_clean):
                            continue
                    ids_coincidentes.append(i_id)

            if ids_coincidentes:
                placeholders = ','.join(['?'] * len(ids_coincidentes))
                cursor.execute(f'''
                    UPDATE inspecciones
                    SET prof_inicial = ?
                    WHERE id IN ({placeholders})
                ''', [prof_new] + ids_coincidentes)
                filas_actualizadas = cursor.rowcount

        conn.commit()

    return {
        'status': 'ok',
        'modelo_id': mid,
        'filas_actualizadas': filas_actualizadas,
        'prof_inicial': prof_new,
        'mensaje': f'Modelo actualizado con éxito. Se actualizó la profundidad inicial ({prof_new} mm) en {filas_actualizadas} inspección(es) de la base de datos.'
    }

def eliminar_modelo_llanta(modelo_id):
    mid = int(modelo_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM catalogo_modelos_llantas WHERE id = ?', (mid,))
        conn.commit()
    return True

def obtener_trazabilidad_kpis_llanta(numero_interno='', filtros=None):
    """
    Calcula trazabilidad e indicadores clave de desempeno (KPIs) por llanta:
    - CPK (Costo Por Kilometro): Precio / Km Rodados
    - Desgaste Total (mm): prof_inicial - min(prof_ext, prof_cent, prof_int)
    - Km Rodados: km_actual - km_montaje (o delta entre inspecciones)
    - Rendimiento (Km/mm): Km Rodados / Desgaste
    - Proyeccion Total Km: Rendimiento * mm_utiles
    - % Desgaste y CPK Proyectado
    Permite filtrar por cliente, subcliente, tipo_operacion, marca, diseno, dimension, vida, banda_reen.
    """
    filtros = filtros or {}
    usuario_filtro = filtros.get('usuario')
    clis_autorizados = None
    if usuario_filtro:
        usr_info = obtener_usuario_por_username(usuario_filtro)
        if usr_info and usr_info.get('rol') != 'admin' and str(usr_info.get('username')).lower() != 'admin':
            clis = parsear_clientes_asignados(usr_info.get('cliente_asignado'))
            if clis:
                clis_autorizados = [c.strip().upper() for c in clis if c.strip()]

    with get_connection() as conn:
        query = """
            SELECT id, fecha, placa, posicion, kilometraje, numero_interno,
                   marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int,
                   prof_inicial, km_montaje, precio, cliente, subcliente, tipo_operacion,
                   usuario_registro
            FROM inspecciones
            WHERE numero_interno IS NOT NULL AND TRIM(numero_interno) != ''
        """
        params = []
        if numero_interno and str(numero_interno).strip():
            query += " AND UPPER(TRIM(numero_interno)) LIKE UPPER(TRIM(?))"
            params.append(f"%{str(numero_interno).strip()}%")

        # Filtro de cliente respetando permisos del perfil
        cliente_solicitado = filtros.get('cliente')
        if cliente_solicitado and str(cliente_solicitado).strip() and str(cliente_solicitado).strip().upper() != 'TODOS':
            cli_sol_up = str(cliente_solicitado).strip().upper()
            if clis_autorizados is not None:
                if cli_sol_up in clis_autorizados:
                    query += " AND UPPER(TRIM(cliente)) = ?"
                    params.append(cli_sol_up)
                else:
                    return []
            else:
                query += " AND UPPER(TRIM(cliente)) = ?"
                params.append(cli_sol_up)
        elif clis_autorizados is not None:
            placeholders = ', '.join(['?'] * len(clis_autorizados))
            query += f" AND UPPER(TRIM(cliente)) IN ({placeholders})"
            params.extend(clis_autorizados)

        for k_campo in ['subcliente', 'tipo_operacion', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen']:
            v_val = filtros.get(k_campo)
            if v_val and str(v_val).strip() and str(v_val).strip().upper() != 'TODOS':
                query += f" AND UPPER(TRIM({k_campo})) = UPPER(TRIM(?))"
                params.append(str(v_val).strip())

        query += " ORDER BY numero_interno ASC, fecha ASC, id ASC"
        df = pd.read_sql_query(query, conn, params=params)
        resolver_limite = _construir_cache_limites_retiro(conn=conn)

    if df.empty:
        return []

    resultados = []
    for num, group in df.groupby('numero_interno'):
        group = group.sort_values(by=['fecha', 'id'])
        primera = group.iloc[0]
        ultima = group.iloc[-1]

        prof_ini = to_float(ultima['prof_inicial'])
        if prof_ini <= 0:
            prof_ini = to_float(primera['prof_inicial'])

        km_mont = to_float(ultima['km_montaje'])
        if km_mont <= 0:
            km_mont = to_float(primera['km_montaje'])

        km_ult = to_float(ultima['kilometraje'])
        km_pri = to_float(primera['kilometraje'])

        if km_mont > 0 and km_ult >= km_mont:
            km_rodados = km_ult - km_mont
        elif km_ult > km_pri:
            km_rodados = km_ult - km_pri
        else:
            km_rodados = 0.0

        p_ext = to_float(ultima['prof_ext'])
        p_cen = to_float(ultima['prof_cent'])
        p_int = to_float(ultima['prof_int'])
        profs_validas = [p for p in (p_ext, p_cen, p_int) if p > 0]
        prof_actual_min = min(profs_validas) if profs_validas else 0.0

        desgaste_mm = max(0.0, prof_ini - prof_actual_min) if (prof_ini > 0 and prof_actual_min > 0) else 0.0
        km_por_mm = (km_rodados / desgaste_mm) if (desgaste_mm > 0.05 and km_rodados > 0) else 0.0

        precio = to_float(ultima['precio'])
        if precio <= 0:
            precio = to_float(primera['precio'])
        cpk = (precio / km_rodados) if (km_rodados > 0 and precio > 0) else 0.0

        cliente_nom = str(ultima.get('cliente', '') or primera.get('cliente', '')).strip()
        subcliente_nom = str(ultima.get('subcliente', '') or primera.get('subcliente', '')).strip()
        limite_cambio = resolver_limite(cliente_nom, subcliente_nom)

        # Proyección útil de vida calculada hasta el límite de cambio programado por cliente (por defecto 3.0 mm)
        mm_utiles = max(0.0, prof_ini - limite_cambio) if prof_ini > limite_cambio else 0.0
        proyeccion_total_km = (km_por_mm * mm_utiles) if km_por_mm > 0 else 0.0
        km_restantes = max(0.0, proyeccion_total_km - km_rodados) if proyeccion_total_km > 0 else 0.0
        
        # Porcentaje de desgaste respecto a la profundidad útil de la llanta
        if mm_utiles > 0 and desgaste_mm >= 0:
            pct_desgaste = min(100.0, (desgaste_mm / mm_utiles) * 100.0)
        else:
            pct_desgaste = 0.0

        # CPK Proyectado = Precio / Proyección Total Km (si hay proyección estimada)
        cpk_proyectado = (precio / proyeccion_total_km) if (precio > 0 and proyeccion_total_km > 0) else 0.0

        # Sugerencia de cambio si la profundidad actual más baja ya alcanzó o superó el límite de cambio
        requiere_cambio = (prof_actual_min > 0 and prof_actual_min <= limite_cambio)

        resultados.append({
            'numero_interno': num,
            'placa': ultima['placa'],
            'posicion': ultima['posicion'],
            'marca': ultima['marca'],
            'diseno': ultima['diseno'],
            'dimension': ultima['dimension'],
            'vida': ultima['vida'],
            'banda_reen': ultima.get('banda_reen', ''),
            'cliente': ultima.get('cliente', ''),
            'subcliente': ultima.get('subcliente', ''),
            'tipo_operacion': ultima.get('tipo_operacion', ''),
            'fecha_ult_insp': ultima['fecha'],
            'total_inspecciones': len(group),
            'prof_inicial': round(prof_ini, 1),
            'prof_actual_min': round(prof_actual_min, 1),
            'desgaste_mm': round(desgaste_mm, 1),
            'porcentaje_desgaste': round(pct_desgaste, 1),
            'km_montaje': round(km_mont, 0),
            'km_actual': round(km_ult, 0),
            'km_rodados': round(km_rodados, 0),
            'km_por_mm': round(km_por_mm, 1),
            'precio': round(precio, 2),
            'cpk': round(cpk, 4),
            'cpk_proyectado': round(cpk_proyectado, 4),
            'limite_retiro_mm': round(limite_cambio, 1),
            'proyeccion_total_km': round(proyeccion_total_km, 0),
            'km_restantes': round(km_restantes, 0),
            'requiere_cambio': 'SÍ' if requiere_cambio else 'NO',
            'usuario_registro': ultima.get('usuario_registro', '')
        })

    return resultados

# ==========================================
# GESTIÓN Y AUTENTICACIÓN DE USUARIOS
# ==========================================

def parsear_clientes_asignados(cliente_asignado) -> list:
    """Convierte el string de cliente_asignado (uno o varios separados por comas) en lista limpia en mayúsculas."""
    if not cliente_asignado:
        return []
    vistos = set()
    res = []
    for c in str(cliente_asignado).split(','):
        clean = c.strip().upper()
        if clean and clean not in vistos:
            vistos.add(clean)
            res.append(clean)
    return res

def parsear_vistas_permitidas(vistas, rol='inspector') -> list:
    """
    Retorna la lista de vistas autorizadas según el rol:
    - admin: Todas las 5 vistas ('patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos').
    - jefatura: Por defecto todas ('patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos') o las asignadas.
    - gerencia: Por defecto ('basedatos', 'diagnostico', 'kpis'). Opcionalmente 'patio' o 'catalogos'.
    - inspector: 'patio', 'diagnostico', 'kpis', 'catalogos' (REGLA: NUNCA 'basedatos').
    """
    rol_clean = str(rol).strip().lower()
    if rol_clean in ('admin', 'administrador'):
        return ['patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos']

    if not vistas:
        if rol_clean in ('jefatura', 'jefe', 'jefe_llantas'):
            return ['patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos']
        elif rol_clean in ('gerencia', 'gerente'):
            return ['basedatos', 'diagnostico', 'kpis']
        else:
            return ['patio', 'diagnostico', 'kpis', 'catalogos']

    raw = [v.strip().lower() for v in str(vistas).split(',') if v.strip()]
    if rol_clean in ('jefatura', 'jefe', 'jefe_llantas', 'gerencia', 'gerente'):
        permitidas = [v for v in raw if v in ('patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos')]
    else:
        # Filtrar estrictamente: inspectores nunca pueden acceder a basedatos
        permitidas = [v for v in raw if v in ('patio', 'diagnostico', 'kpis', 'catalogos')]
    return permitidas if permitidas else ['patio']

def autenticar_usuario(username, password):
    u = (username or '').strip()
    p = (password or '').strip()
    if not u or not p:
        return None
    with get_connection() as conn:
        asegurar_columna_vistas_permitidas(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password, nombre_completo, rol, cliente_asignado, activo,
                   COALESCE(vistas_permitidas, 'patio,diagnostico,kpis')
            FROM usuarios
            WHERE LOWER(username) = LOWER(?) AND activo = 1
        """, (u,))
        row = cursor.fetchone()
        if not row:
            return None
        uid, db_username, stored_pwd, nombre_completo, rol, cliente_asignado, activo, raw_vistas = row
        if verify_password(p, stored_pwd):
            # Auto-migración en caso de que aún tuviera contraseña legada en texto plano
            if not stored_pwd.startswith("pbkdf2_sha256$"):
                nuevo_hash = hash_password(p)
                cursor.execute("UPDATE usuarios SET password = ? WHERE id = ?", (nuevo_hash, uid))
                conn.commit()
            clis = parsear_clientes_asignados(cliente_asignado)
            vistas = parsear_vistas_permitidas(raw_vistas, rol)
            return {
                'id': uid,
                'username': db_username,
                'nombre_completo': nombre_completo,
                'rol': rol,
                'cliente_asignado': cliente_asignado or '',
                'clientes_asignados': clis,
                'vistas_permitidas': vistas,
                'activo': bool(activo)
            }
    return None

def obtener_usuario_por_username(username):
    u = (username or '').strip()
    if not u:
        return None
    with get_connection() as conn:
        asegurar_columna_vistas_permitidas(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, nombre_completo, rol, cliente_asignado, activo,
                   COALESCE(vistas_permitidas, 'patio,diagnostico,kpis')
            FROM usuarios
            WHERE LOWER(username) = LOWER(?)
        """, (u,))
        row = cursor.fetchone()
        if row:
            clis = parsear_clientes_asignados(row[4])
            vistas = parsear_vistas_permitidas(row[6], row[3])
            return {
                'id': row[0],
                'username': row[1],
                'nombre_completo': row[2],
                'rol': row[3],
                'cliente_asignado': row[4] or '',
                'clientes_asignados': clis,
                'vistas_permitidas': vistas,
                'activo': bool(row[5])
            }
    return None

def listar_usuarios():
    with get_connection() as conn:
        asegurar_columna_vistas_permitidas(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, nombre_completo, rol, cliente_asignado, activo, fecha_creacion,
                   COALESCE(vistas_permitidas, 'patio,diagnostico,kpis')
            FROM usuarios
            ORDER BY id ASC
        """)
        cols = ['id', 'username', 'nombre_completo', 'rol', 'cliente_asignado', 'activo', 'fecha_creacion', 'vistas_permitidas']
        filas = []
        for r in cursor.fetchall():
            d = dict(zip(cols, r))
            d['clientes_asignados'] = parsear_clientes_asignados(d.get('cliente_asignado'))
            v_list = parsear_vistas_permitidas(d.get('vistas_permitidas'), d.get('rol'))
            d['vistas_permitidas'] = ','.join(v_list) if isinstance(v_list, list) else str(v_list or '')
            filas.append(d)
        return filas

def crear_usuario(username, password, nombre_completo, rol='inspector', cliente_asignado='', vistas_permitidas=None):
    u = (username or '').strip().lower()
    p = (password or '').strip()
    nom = (nombre_completo or '').strip()
    r = (rol or 'inspector').strip().lower()
    cli = ', '.join(parsear_clientes_asignados(cliente_asignado))
    if not u or not p or not nom:
        return False
    if len(p) < 4:
        return False
    
    # Resolver vistas autorizadas según rol
    if r == 'admin':
        vistas_str = 'patio,basedatos,diagnostico,kpis,catalogos'
    else:
        vistas_limpias = parsear_vistas_permitidas(vistas_permitidas, r)
        vistas_str = ','.join(vistas_limpias)

    hashed_pwd = hash_password(p)
    with get_connection() as conn:
        asegurar_columna_vistas_permitidas(conn)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (u, hashed_pwd, nom, r, cli, vistas_str))
            conn.commit()
            return True
        except Exception:
            return False

def actualizar_usuario(username, nombre_completo=None, password=None, rol=None, cliente_asignado=None, activo=None, vistas_permitidas=None):
    u = (username or '').strip().lower()
    with get_connection() as conn:
        asegurar_columna_vistas_permitidas(conn)
        cursor = conn.cursor()
        updates = []
        params = []
        if nombre_completo is not None:
            updates.append("nombre_completo = ?")
            params.append(nombre_completo.strip())
        if password is not None and str(password).strip():
            p_str = str(password).strip()
            if len(p_str) < 4:
                return False
            updates.append("password = ?")
            params.append(hash_password(p_str))
        
        rol_final = None
        if rol is not None:
            rol_final = rol.strip().lower()
            updates.append("rol = ?")
            params.append(rol_final)
        else:
            # Obtener rol actual para validar vistas
            cursor.execute("SELECT rol FROM usuarios WHERE LOWER(username) = LOWER(?)", (u,))
            row_rol = cursor.fetchone()
            if row_rol:
                rol_final = row_rol[0]

        if vistas_permitidas is not None:
            if rol_final == 'admin':
                v_str = 'patio,basedatos,diagnostico,kpis,catalogos'
            else:
                v_limpias = parsear_vistas_permitidas(vistas_permitidas, rol_final)
                v_str = ','.join(v_limpias)
            updates.append("vistas_permitidas = ?")
            params.append(v_str)

        if cliente_asignado is not None:
            updates.append("cliente_asignado = ?")
            params.append(', '.join(parsear_clientes_asignados(cliente_asignado)))
        if activo is not None:
            updates.append("activo = ?")
            params.append(1 if activo else 0)
        if not updates:
            return False
        params.append(u)
        cursor.execute(f"UPDATE usuarios SET {', '.join(updates)} WHERE LOWER(username) = LOWER(?)", params)
        conn.commit()
        return cursor.rowcount > 0

def restablecer_password_usuario(username: str, nueva_password: str) -> bool:
    """
    Restablece la contraseña de un usuario específico validando que tenga al menos 4 caracteres,
    la hashea con PBKDF2 y actualiza el registro en la BD.
    """
    u = (username or '').strip().lower()
    p = (nueva_password or '').strip()
    if not u or len(p) < 4:
        return False
    hashed = hash_password(p)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET password = ? WHERE LOWER(username) = LOWER(?)", (hashed, u))
        conn.commit()
        return cursor.rowcount > 0

def eliminar_usuario(username):
    u = (username or '').strip().lower()
    if u == 'admin':
        return False # No eliminar el superadmin
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE LOWER(username) = LOWER(?)", (u,))
        conn.commit()
        return True

def obtener_datos_inspeccion_vehiculo(placa, fecha=None):
    """
    Obtiene todos los datos y mediciones de la inspección de un vehículo específico para generar el informe PDF.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if fecha:
            cursor.execute("""
                SELECT id, fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                       tipologia, marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int,
                       psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro, foto_novedad
                FROM inspecciones
                WHERE UPPER(TRIM(placa)) = UPPER(TRIM(?)) AND fecha = ?
                ORDER BY posicion ASC
            """, (placa, fecha))
        else:
            cursor.execute("""
                SELECT id, fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                       tipologia, marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int,
                       psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro, foto_novedad
                FROM inspecciones
                WHERE UPPER(TRIM(placa)) = UPPER(TRIM(?))
                  AND fecha = (SELECT MAX(fecha) FROM inspecciones WHERE UPPER(TRIM(placa)) = UPPER(TRIM(?)))
                ORDER BY posicion ASC
            """, (placa, placa))
        
        cols = ['id', 'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'posicion', 'kilometraje',
                'tipologia', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int',
                'psi', 'novedades', 'precio', 'prof_inicial', 'km_montaje', 'numero_interno', 'usuario_registro', 'foto_novedad']
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        return rows


# ==============================================================================
# MÓDULO DE TABLERO ANALÍTICO Y LICENCIAMIENTO LIGHT VS PRO (KPIs 01 a 19)
# ==============================================================================

def contar_vehiculos_padron(cliente: str) -> int:
    """Retorna el número de vehículos activos registrados en el padrón del cliente."""
    if not cliente or str(cliente).strip().upper() == 'TODOS':
        query = "SELECT COUNT(*) FROM padron_vehiculos_cliente WHERE activo = 1"
        params = ()
    else:
        query = "SELECT COUNT(*) FROM padron_vehiculos_cliente WHERE UPPER(TRIM(cliente)) = UPPER(TRIM(?)) AND activo = 1"
        params = (cliente,)
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def obtener_licencia_cliente(cliente: str) -> str:
    """
    Retorna 'LIGHT' o 'PRO' para el cliente especificado. Por defecto 'PRO'.
    """
    if not cliente or str(cliente).strip().upper() == 'TODOS':
        return 'PRO'
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tipo_licencia FROM configuracion_avanzada_cliente WHERE UPPER(TRIM(cliente)) = UPPER(TRIM(?))",
                (cliente,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                modo = str(row[0]).strip().upper()
                return modo if modo in ('LIGHT', 'PRO') else 'PRO'
    except Exception:
        pass
    return 'PRO'


def guardar_licencia_cliente(cliente: str, tipo_licencia: str, plantilla_kpis_json: str = "{}") -> bool:
    """
    Guarda o actualiza la licencia ('LIGHT' o 'PRO') y la plantilla de KPIs para un cliente.
    """
    cli_limpio = str(cliente).strip().upper()
    if not cli_limpio:
        return False
    tipo = str(tipo_licencia).strip().upper()
    if tipo not in ('LIGHT', 'PRO'):
        tipo = 'PRO'
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO configuracion_avanzada_cliente (cliente, tipo_licencia, plantilla_kpis_json, fecha_actualizacion)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cliente) DO UPDATE SET
                    tipo_licencia = excluded.tipo_licencia,
                    plantilla_kpis_json = excluded.plantilla_kpis_json,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            """, (cli_limpio, tipo, plantilla_kpis_json))
            conn.commit()
            return True
    except Exception:
        return False


def obtener_configuracion_avanzada_cliente(cliente: str) -> dict:
    """
    Retorna el diccionario con la configuración avanzada y tolerancias del cliente.
    Si no existe, retorna los valores técnicos recomendados por defecto.
    """
    defaults = {
        "cliente": cliente,
        "tipo_licencia": "PRO",
        "mm_retiro_direccional": 4.0,
        "mm_retiro_traccion": 3.0,
        "mm_retiro_arrastre": 3.0,
        "rango_semaforo_amarillo_mm": 2.0,
        "criterio_profundidad_calculo": "MINIMO",
        "psi_objetivo_direccional": 110.0,
        "psi_objetivo_traccion": 100.0,
        "psi_objetivo_arrastre": 100.0,
        "tolerancia_psi_baja_pct": 10.0,
        "tolerancia_psi_alta_pct": 10.0,
        "tolerancia_desalineacion_hombros_mm": 2.0,
        "tolerancia_mal_apareo_pacha_mm": 2.5,
        "umbral_diferencia_rotacion_ejes_mm": 3.0,
        "diferencia_minima_par_direccional_mm": 3.0,
        "plantilla_kpis_json": "{}"
    }
    if not cliente or str(cliente).strip().upper() == 'TODOS':
        return defaults
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre,
                       rango_semaforo_amarillo_mm, criterio_profundidad_calculo,
                       psi_objetivo_direccional, psi_objetivo_traccion, psi_objetivo_arrastre,
                       tolerancia_psi_baja_pct, tolerancia_psi_alta_pct,
                       tolerancia_desalineacion_hombros_mm, tolerancia_mal_apareo_pacha_mm,
                       umbral_diferencia_rotacion_ejes_mm, diferencia_minima_par_direccional_mm,
                       plantilla_kpis_json
                FROM configuracion_avanzada_cliente
                WHERE UPPER(TRIM(cliente)) = UPPER(TRIM(?))
            """, (cliente,))
            row = cursor.fetchone()
            if row:
                cols = [
                    "tipo_licencia", "mm_retiro_direccional", "mm_retiro_traccion", "mm_retiro_arrastre",
                    "rango_semaforo_amarillo_mm", "criterio_profundidad_calculo",
                    "psi_objetivo_direccional", "psi_objetivo_traccion", "psi_objetivo_arrastre",
                    "tolerancia_psi_baja_pct", "tolerancia_psi_alta_pct",
                    "tolerancia_desalineacion_hombros_mm", "tolerancia_mal_apareo_pacha_mm",
                    "umbral_diferencia_rotacion_ejes_mm", "diferencia_minima_par_direccional_mm",
                    "plantilla_kpis_json"
                ]
                d = dict(zip(cols, row))
                d["cliente"] = cliente
                return d
    except Exception:
        pass
    return defaults


def _mes_a_espanol(val_str: str) -> str:
    """Convierte '2025-01' o '2025-01-15' a formato 'Ene 25'."""
    meses = {
        '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr',
        '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Ago',
        '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'
    }
    s = str(val_str).strip()
    if len(s) >= 7 and '-' in s:
        partes = s[:7].split('-')
        if len(partes) == 2:
            anio, mes = partes[0], partes[1]
            nombre_mes = meses.get(mes, mes)
            return f"{nombre_mes} {anio[-2:]}"
    return s


def obtener_datos_graficos_diagnostico(filtros: dict = None) -> dict:
    """
    Calcula los datos analíticos completos y blindados para el Tablero Ejecutivo
    de Diagnóstico y Licenciamiento LIGHT vs PRO (KPIs 01 a 19).
    """
    filtros = filtros or {}
    cliente = str(filtros.get("cliente", "")).strip().upper()
    subcliente = str(filtros.get("subcliente", "")).strip().upper()
    tipo_operacion = str(filtros.get("tipo_operacion", "")).strip().upper()
    tipologia = str(filtros.get("tipologia", "")).strip().upper()
    marca = str(filtros.get("marca", "")).strip().upper()
    dimension = str(filtros.get("dimension", "")).strip().upper()
    eje_temporal = str(filtros.get("eje_temporal", "mes")).strip().lower()
    usuario = str(filtros.get("usuario", "")).strip()

    licencia = obtener_licencia_cliente(cliente)
    cfg = obtener_configuracion_avanzada_cliente(cliente)

    mm_retiro_dir = to_float(cfg.get("mm_retiro_direccional"), 4.0)
    mm_retiro_trac = to_float(cfg.get("mm_retiro_traccion"), 3.0)
    tol_psi_baja = to_float(cfg.get("tolerancia_psi_baja_pct"), 10.0)
    tol_psi_alta = to_float(cfg.get("tolerancia_psi_alta_pct"), 10.0)
    psi_obj_dir = to_float(cfg.get("psi_objetivo_direccional"), 110.0)
    psi_obj_trac = to_float(cfg.get("psi_objetivo_traccion"), 100.0)
    tol_desalineacion = to_float(cfg.get("tolerancia_desalineacion_hombros_mm"), 2.0)

    # Estructura de respuesta por defecto segura
    resultado = {
        "licencia": licencia,
        "kpis": {
            "vehiculos": "0 Vehículos",
            "subVehiculos": "0 Llantas Auditadas",
            "cumplimientoParquePct": 0.0,
            "impactoPesos": 0.0,
            "perdidaMm": 0.0,
            "proyeccionProm": 0,
            "kmRecorridosProm": 0,
            "cpkProm": 0.0,
            "kmMmProm": 0.0,
            "pctDesgasteProm": 0.0,
            "mmGastadosProm": 0.0,
            "profActualProm": 0.0,
            "pctReencauche": 0.0,
            "pctAlineacionOk": 100.0
        },
        "gauges": {
            "pctDesgaste": 0.0,
            "txtDesgaste": "0,0 mm gastados",
            "proyActual": 0,
            "proyMeta": 100000,
            "txtMeta": "Meta: 100.000 km (0,0%)"
        },
        "proyMaxMin": {"labels": [], "prom": [], "max": [], "min": []},
        "perdidaMes": {"labels": [], "mm2025": [], "mm2026": [], "dinero": []},
        "proyRango": {
            "labels": ["1. 0–40%", "2. 40.1–60%", "3. 60.1–80%", "4. 80.1–99.9%", "5. 100%"],
            "valores": [0, 0, 0, 0, 0]
        },
        "alineacionMes": {"labels": [], "alerta": [], "ok": []},
        "cpkMarca": {"labels": [], "cpk": [], "kmmm": []},
        "planesMes": {"labels": [], "cambios": [], "duales": [], "alineacion": [], "rotacion": []},
        "danos": {"labels": [], "valores": []},
        "ciclo": {"labels": [], "original": [], "reencauche": [], "pctReenc": []},
        "presiones": {"labels": ["En Norma (OK)", "Baja Presión", "Sobreinflado"], "valores": [0, 0, 0]},
        "fvuProfBaja": {"labels": [], "max": [], "prom": [], "min": []}
    }

    try:
        df_raw = obtener_todas_inspecciones(usuario=usuario)
        if df_raw.empty:
            return resultado

        df = df_raw.copy()

        # Filtrado estándar
        if cliente and cliente != "TODOS":
            df = df[df["cliente"].astype(str).str.upper().str.strip() == cliente]
        if subcliente and subcliente != "TODOS":
            df = df[df["subcliente"].astype(str).str.upper().str.strip() == subcliente]
        if tipo_operacion and tipo_operacion != "TODOS":
            df = df[df["tipo_operacion"].astype(str).str.upper().str.strip() == tipo_operacion]
        if tipologia and tipologia != "TODOS":
            df = df[df["tipologia"].astype(str).str.upper().str.strip() == tipologia]
        if marca and marca != "TODOS":
            df = df[df["marca"].astype(str).str.upper().str.strip() == marca]
        if dimension and dimension != "TODOS":
            df = df[df["dimension"].astype(str).str.upper().str.strip() == dimension]

        if df.empty:
            return resultado

        # Cálculo vectorizado y protegido campo a campo
        pos_list = [to_int(p) for p in df['posicion']]
        pe_list = [to_float(p) for p in df['prof_ext']]
        pc_list = [to_float(p) for p in df['prof_cent']]
        pi_list = [to_float(p) for p in df['prof_int']]
        psi_list = [to_float(p) for p in df['psi']]
        precio_list = [to_float(p) for p in df['precio']]
        pini_list = [to_float(p) for p in df['prof_inicial']]
        km_act_list = [to_float(p) for p in df['kilometraje']]
        km_mont_list = [to_float(p) for p in df['km_montaje']]

        n_rows = len(df)
        p_min_col = []
        p_ini_col = []
        lim_retiro_col = []
        mm_utiles_col = []
        delta_mm_col = []
        pct_desgaste_col = []
        km_rodados_col = []
        es_asentamiento_col = []
        km_mm_col = []
        proy_total_col = []
        cpk_col = []
        es_madura_col = []
        mm_perdidos_col = []
        perdida_dinero_col = []
        estado_psi_col = []
        es_reencauche_col = []

        resolver_limite = _construir_cache_limites_retiro()
        mapa_tips = _cargar_mapa_tipologias_ejes()

        for idx in range(n_rows):
            pos = pos_list[idx]
            es_dir = (pos in (1, 2))
            pe = pe_list[idx]
            pc = pc_list[idx]
            pi = pi_list[idx]
            psi = psi_list[idx]

            # 1. Profundidad mínima Pmin
            positivos = [x for x in (pe, pc, pi) if x > 0]
            p_min = min(positivos) if positivos else 0.0
            p_min_col.append(p_min)

            # 2. Profundidad inicial y límite de retiro dinámico desde el catálogo
            p_ini = pini_list[idx] if pini_list[idx] > 0 else (16.0 if es_dir else 18.0)
            p_ini_col.append(p_ini)

            cli_row = str(df['cliente'].iloc[idx] if 'cliente' in df else cliente or '').strip().upper()
            sub_row = str(df['subcliente'].iloc[idx] if 'subcliente' in df else subcliente or '').strip().upper()
            tip_row = str(df['tipologia'].iloc[idx] if 'tipologia' in df else '').strip()
            eje_tipo = obtener_tipo_eje_posicion(tip_row, pos, mapa_tipologias=mapa_tips)
            lim_ret = resolver_limite(cli_row, sub_row, eje_tipo)
            if lim_ret <= 0:
                lim_ret = mm_retiro_dir if es_dir else mm_retiro_trac
            lim_retiro_col.append(lim_ret)


            mm_ut = max(1.0, p_ini - lim_ret)
            mm_utiles_col.append(mm_ut)

            d_mm = max(0.0, p_ini - p_min)
            delta_mm_col.append(d_mm)

            pct_d = min(100.0, max(0.0, (d_mm / mm_ut) * 100.0))
            pct_desgaste_col.append(pct_d)

            # 3. Kilometraje y blindaje de asentamiento
            km_rod = max(0.0, km_act_list[idx] - km_mont_list[idx])
            km_rodados_col.append(km_rod)

            asent = (d_mm < 0.5) or (km_rod < 500.0)
            es_asentamiento_col.append(asent)

            if asent:
                km_mm = 0.0
                proy = 0.0
                cpk_val = 0.0
            else:
                km_mm = km_rod / max(0.1, d_mm)
                proy = km_mm * mm_ut
                pr = precio_list[idx] if precio_list[idx] > 0 else 1450000.0
                cpk_val = pr / max(1.0, proy)

            km_mm_col.append(km_mm)
            proy_total_col.append(proy)
            cpk_col.append(cpk_val)

            # 4. Filtro de madurez para techos KPI 15
            es_mad = (d_mm >= 1.5) or (pct_d >= 10.0)
            es_madura_col.append(es_mad)

            # 5. Desalineación e Impacto Económico
            dif_hombros = abs(pe - pi)
            alerta_alin = (dif_hombros >= tol_desalineacion)
            if alerta_alin:
                mm_perd = max(pe, pc, pi) - min(pe, pc, pi)
                pr = precio_list[idx] if precio_list[idx] > 0 else 1450000.0
                costo_mm = pr / mm_ut
                perd_dinero = mm_perd * costo_mm
            else:
                mm_perd = 0.0
                perd_dinero = 0.0

            mm_perdidos_col.append(mm_perd)
            perdida_dinero_col.append(perd_dinero)

            # 6. Presión PSI Real contra objetivo
            psi_obj = psi_obj_dir if es_dir else psi_obj_trac
            lim_inf = psi_obj * (1.0 - tol_psi_baja / 100.0)
            lim_sup = psi_obj * (1.0 + tol_psi_alta / 100.0)
            if psi < lim_inf:
                estado_psi = "Baja Presión"
            elif psi > lim_sup:
                estado_psi = "Sobreinflado"
            else:
                estado_psi = "En Norma (OK)"
            estado_psi_col.append(estado_psi)

            # 7. Reencauche
            v_str = str(df['vida'].iloc[idx] if 'vida' in df else '').upper()
            b_str = str(df['banda_reen'].iloc[idx] if 'banda_reen' in df else '').strip()
            es_reenc = bool(re.search(r'REENC|R1|R2|R3', v_str) or (b_str and b_str.lower() not in ('nan', 'none', '')))
            es_reencauche_col.append(es_reenc)

        df['calc_p_min'] = p_min_col
        df['calc_p_ini'] = p_ini_col
        df['calc_lim_retiro'] = lim_retiro_col
        df['calc_mm_utiles'] = mm_utiles_col
        df['calc_delta_mm'] = delta_mm_col
        df['calc_pct_desgaste'] = pct_desgaste_col
        df['calc_km_rodados'] = km_rodados_col
        df['calc_es_asentamiento'] = es_asentamiento_col
        df['calc_km_mm'] = km_mm_col
        df['calc_proy_total'] = proy_total_col
        df['calc_cpk'] = cpk_col
        df['calc_es_madura'] = es_madura_col
        df['calc_mm_perdidos'] = mm_perdidos_col
        df['calc_perdida_dinero'] = perdida_dinero_col
        df['calc_estado_psi'] = estado_psi_col
        df['calc_es_reencauche'] = es_reencauche_col

        # Columna de corte / periodo temporal (YYYY-MM o número de inspección)
        df['fecha_str'] = df['fecha'].astype(str).str[:10]
        df['periodo_mes'] = df['fecha_str'].apply(lambda x: x[:7] if len(x) >= 7 else 'Actual')

        # ----------------------------------------------------------------------
        # MUESTRA AUDITADA (Último Corte por Vehículo)
        # ----------------------------------------------------------------------
        # Agrupar por placa y tomar la fecha más reciente
        grupos_corte = []
        for placa_v, grp in df.groupby('placa'):
            f_max = grp['fecha_str'].max()
            grp_rec = grp[grp['fecha_str'] == f_max]
            if 'id' in grp_rec.columns:
                grp_rec = grp_rec.sort_values('id').groupby('posicion', as_index=False).last()
            grupos_corte.append(grp_rec)

        df_ultimo_corte = pd.concat(grupos_corte, ignore_index=True) if grupos_corte else pd.DataFrame()

        if not df_ultimo_corte.empty:
            vehiculos_cnt = df_ultimo_corte['placa'].nunique()
            llantas_cnt = len(df_ultimo_corte)
            total_padron = contar_vehiculos_padron(cliente)
            if total_padron > 0:
                cumplimiento_pct = round(min(100.0, (vehiculos_cnt / total_padron) * 100.0), 1)
            else:
                cumplimiento_pct = 100.0

            impacto_dinero = round(float(df_ultimo_corte['calc_perdida_dinero'].sum()))
            perdida_mm_tot = round(float(df_ultimo_corte['calc_mm_perdidos'].sum()), 1)

            llantas_activas = df_ultimo_corte[~df_ultimo_corte['calc_es_asentamiento']]
            proy_prom = round(float(llantas_activas['calc_proy_total'].mean())) if not llantas_activas.empty else 0
            km_rec_prom = round(float(df_ultimo_corte['calc_km_rodados'].mean()))
            cpk_prom = round(float(llantas_activas['calc_cpk'].mean()), 1) if not llantas_activas.empty else 0.0
            km_mm_prom = round(float(llantas_activas['calc_km_mm'].mean()), 1) if not llantas_activas.empty else 0.0

            pct_desg_prom = round(float(df_ultimo_corte['calc_pct_desgaste'].mean()), 1)
            mm_gast_prom = round(float(df_ultimo_corte['calc_delta_mm'].mean()), 1)
            prof_act_prom = round(float(df_ultimo_corte['calc_p_min'].mean()), 1)

            reenc_cnt = int(df_ultimo_corte['calc_es_reencauche'].sum())
            pct_reenc = round((reenc_cnt / max(1, llantas_cnt)) * 100.0, 1)

            ok_alin_cnt = int((df_ultimo_corte['calc_mm_perdidos'] == 0.0).sum())
            pct_alin_ok = round((ok_alin_cnt / max(1, llantas_cnt)) * 100.0, 1)

            resultado["kpis"] = {
                "vehiculos": f"{vehiculos_cnt:,} Vehículos".replace(',', '.'),
                "subVehiculos": f"{llantas_cnt:,} Llantas Auditadas".replace(',', '.'),
                "cumplimientoParquePct": float(cumplimiento_pct),
                "impactoPesos": float(impacto_dinero),
                "perdidaMm": float(perdida_mm_tot),
                "proyeccionProm": int(proy_prom),
                "kmRecorridosProm": int(km_rec_prom),
                "cpkProm": float(cpk_prom),
                "kmMmProm": float(km_mm_prom),
                "pctDesgasteProm": float(pct_desg_prom),
                "mmGastadosProm": float(mm_gast_prom),
                "profActualProm": float(prof_act_prom),
                "pctReencauche": float(pct_reenc),
                "pctAlineacionOk": float(pct_alin_ok)
            }

            # Tacómetros Gauges (KPI 12 y 13)
            proy_meta = 109885 if proy_prom == 0 else int(max(proy_prom * 1.25, 95000))
            dif_pct = round(((proy_prom - proy_meta) / proy_meta) * 100.0, 1) if proy_meta > 0 else 0.0
            signo = "+" if dif_pct >= 0 else ""
            txt_meta = f"Meta: {proy_meta:,} km ({signo}{str(dif_pct).replace('.', ',')}%)".replace(',', '.')

            resultado["gauges"] = {
                "pctDesgaste": float(pct_desg_prom),
                "txtDesgaste": f"{str(mm_gast_prom).replace('.', ',')} mm gastados",
                "proyActual": int(proy_prom),
                "proyMeta": int(proy_meta),
                "txtMeta": txt_meta
            }

            # Estado de Presiones Real (KPI 09) en corte actual
            pres_counts = df_ultimo_corte['calc_estado_psi'].value_counts()
            resultado["presiones"] = {
                "labels": ["En Norma (OK)", "Baja Presión", "Sobreinflado"],
                "valores": [
                    int(pres_counts.get("En Norma (OK)", 0)),
                    int(pres_counts.get("Baja Presión", 0)),
                    int(pres_counts.get("Sobreinflado", 0))
                ]
            }

            # Curva de Madurez por Rango de Desgaste (KPI 16)
            tramos = [
                ("1. 0–40%", (df_ultimo_corte['calc_pct_desgaste'] >= 0.0) & (df_ultimo_corte['calc_pct_desgaste'] <= 40.0)),
                ("2. 40.1–60%", (df_ultimo_corte['calc_pct_desgaste'] > 40.0) & (df_ultimo_corte['calc_pct_desgaste'] <= 60.0)),
                ("3. 60.1–80%", (df_ultimo_corte['calc_pct_desgaste'] > 60.0) & (df_ultimo_corte['calc_pct_desgaste'] <= 80.0)),
                ("4. 80.1–99.9%", (df_ultimo_corte['calc_pct_desgaste'] > 80.0) & (df_ultimo_corte['calc_pct_desgaste'] < 100.0)),
                ("5. 100%", (df_ultimo_corte['calc_pct_desgaste'] >= 100.0) | (df_ultimo_corte['calc_p_min'] <= df_ultimo_corte['calc_lim_retiro']))
            ]
            rango_vals = []
            for t_nom, mask in tramos:
                sub_tr = df_ultimo_corte[mask]
                sub_tr_proy = sub_tr[sub_tr['calc_proy_total'] > 0]
                if not sub_tr_proy.empty:
                    val_t = round(float(sub_tr_proy['calc_proy_total'].mean()))
                elif not sub_tr.empty:
                    val_t = round(float(sub_tr['calc_km_rodados'].mean()))
                else:
                    val_t = 0
                rango_vals.append(val_t)
            resultado["proyRango"] = {
                "labels": [t[0] for t in tramos],
                "valores": rango_vals
            }

            # CPK y Km/mm por Diseño / Marca (KPI 14)
            df_cpk_base = df_ultimo_corte[~df_ultimo_corte['calc_es_asentamiento']]
            if df_cpk_base.empty:
                df_cpk_base = df_ultimo_corte

            campo_agrup = 'diseno' if df_cpk_base['diseno'].dropna().nunique() > 1 else 'marca'
            top_disenos = df_cpk_base[campo_agrup].replace('', np.nan).dropna().value_counts().head(5).index.tolist()

            cpk_labels = []
            cpk_vals = []
            kmmm_vals = []
            for dis in top_disenos:
                sub_d = df_cpk_base[df_cpk_base[campo_agrup] == dis]
                cpk_labels.append(str(dis))
                cpk_mean = sub_d['calc_cpk'].replace(0, np.nan).dropna().mean()
                kmmm_mean = sub_d['calc_km_mm'].replace(0, np.nan).dropna().mean()
                cpk_vals.append(round(float(cpk_mean), 1) if pd.notna(cpk_mean) else 0.0)
                kmmm_vals.append(round(float(kmmm_mean), 1) if pd.notna(kmmm_mean) else 0.0)

            resultado["cpkMarca"] = {
                "labels": cpk_labels,
                "cpk": cpk_vals,
                "kmmm": kmmm_vals
            }

            # Pareto de Daños / Novedades (KPI 10)
            palabras_clave_danos = [
                "Asentamiento", "Corte Costado", "Oxidación", "Impacto Banda",
                "Desgaste Irregular", "Desalineación", "Dual Mal Apareado", "Baja Presión"
            ]
            danos_dict = {d: 0 for d in palabras_clave_danos}
            for nov in df_ultimo_corte['novedades'].fillna(''):
                n_str = str(nov).strip()
                if not n_str or n_str.lower() in ('ok', 'normal', 'ninguna', 'nan'):
                    continue
                match = False
                for d_k in palabras_clave_danos:
                    if d_k.lower() in n_str.lower():
                        danos_dict[d_k] += 1
                        match = True
                if not match:
                    danos_dict["Desgaste Irregular"] = danos_dict.get("Desgaste Irregular", 0) + 1

            danos_ordenados = sorted([(k, v) for k, v in danos_dict.items() if v > 0], key=lambda x: x[1], reverse=True)
            if not danos_ordenados:
                danos_ordenados = [("Sin Novedades", llantas_cnt)]
            resultado["danos"] = {
                "labels": [d[0] for d in danos_ordenados[:6]],
                "valores": [d[1] for d in danos_ordenados[:6]]
            }

        # ----------------------------------------------------------------------
        # EVOLUCIÓN TEMPORAL (Por Mes o por Corte N° INSP)
        # ----------------------------------------------------------------------
        if eje_temporal == 'insp':
            fechas_unicas = sorted([f for f in df['fecha_str'].unique() if f and f != 'nan'])[-8:]
            periodos = [(f"Insp {i+1}", f) for i, f in enumerate(fechas_unicas)]
        else:
            meses_unicos = sorted([m for m in df['periodo_mes'].unique() if m and m != 'nan'])[-8:]
            periodos = [(_mes_a_espanol(m), m) for m in meses_unicos]

        labels_p = []
        prom_p = []
        max_p = []
        min_p = []

        mm_p = []
        dinero_p = []

        alerta_p = []
        ok_p = []

        cambios_p = []
        duales_p = []
        alin_p = []
        rot_p = []

        orig_p = []
        reenc_p = []
        pct_reenc_p = []

        fvu_max_p = []
        fvu_prom_p = []
        fvu_min_p = []

        for p_label, p_key in periodos:
            if eje_temporal == 'insp':
                sub_df = df[df['fecha_str'] == p_key]
            else:
                sub_df = df[df['periodo_mes'] == p_key]

            # Tomar último estado por vehículo dentro de este periodo
            sub_corte = []
            for _, grp in sub_df.groupby('placa'):
                f_max = grp['fecha_str'].max()
                g_f = grp[grp['fecha_str'] == f_max]
                if 'id' in g_f.columns:
                    g_f = g_f.sort_values('id').groupby('posicion', as_index=False).last()
                sub_corte.append(g_f)
            df_p = pd.concat(sub_corte, ignore_index=True) if sub_corte else pd.DataFrame()

            if df_p.empty:
                continue

            labels_p.append(p_label)

            # KPI 15: Proyección Máx/Mín con filtro de madurez
            llantas_maduras = df_p[df_p['calc_es_madura'] & (~df_p['calc_es_asentamiento']) & (df_p['calc_proy_total'] > 0)]
            if not llantas_maduras.empty:
                prom_p.append(round(float(llantas_maduras['calc_proy_total'].mean())))
                max_p.append(round(float(llantas_maduras['calc_proy_total'].max())))
                min_p.append(round(float(llantas_maduras['calc_proy_total'].min())))
            else:
                con_proy = df_p[df_p['calc_proy_total'] > 0]
                if not con_proy.empty:
                    prom_p.append(round(float(con_proy['calc_proy_total'].mean())))
                    max_p.append(round(float(con_proy['calc_proy_total'].max())))
                    min_p.append(round(float(con_proy['calc_proy_total'].min())))
                else:
                    prom_p.append(0)
                    max_p.append(0)
                    min_p.append(0)

            # KPI 11: Pérdida mm y Dinero
            mm_p.append(round(float(df_p['calc_mm_perdidos'].sum()), 1))
            dinero_p.append(round(float(df_p['calc_perdida_dinero'].sum())))

            # KPI 06: Alineación % Alerta vs % OK
            total_ll = len(df_p)
            alerta_cnt = int((df_p['calc_mm_perdidos'] > 0).sum())
            pct_al = round((alerta_cnt / max(1, total_ll)) * 100.0, 1)
            pct_o = round(100.0 - pct_al, 1)
            alerta_p.append(pct_al)
            ok_p.append(pct_o)

            # KPI 05, 07, 08: Planes de Acción
            cambios_cnt = int((df_p['calc_p_min'] <= df_p['calc_lim_retiro']).sum())
            duales_cnt = int(df_p['novedades'].astype(str).str.upper().str.contains('DUAL|APARE', na=False).sum())
            rot_cnt = int(df_p['novedades'].astype(str).str.upper().str.contains('ROTAC', na=False).sum())
            cambios_p.append(cambios_cnt)
            duales_p.append(duales_cnt)
            alin_p.append(alerta_cnt)
            rot_p.append(rot_cnt)

            # KPI 03: Ciclo Original vs Reencauche
            r_cnt = int(df_p['calc_es_reencauche'].sum())
            o_cnt = int(total_ll - r_cnt)
            orig_p.append(o_cnt)
            reenc_p.append(r_cnt)
            pct_reenc_p.append(round((r_cnt / max(1, total_ll)) * 100.0, 1))

            # KPI 19: FVU Bajas / Retiro
            bajas = df_p[(df_p['calc_p_min'] <= df_p['calc_lim_retiro']) | df_p['novedades'].astype(str).str.upper().str.contains('BAJA|CAMBIO|RETIRO', na=False)]
            if not bajas.empty:
                fvu_max_p.append(round(float(bajas['calc_p_min'].max()), 1))
                fvu_prom_p.append(round(float(bajas['calc_p_min'].mean()), 1))
                fvu_min_p.append(round(float(bajas['calc_p_min'].min()), 1))
            else:
                fvu_max_p.append(round(float(df_p['calc_p_min'].min()), 1))
                fvu_prom_p.append(round(float(df_p['calc_p_min'].mean()), 1))
                fvu_min_p.append(0.0)

        resultado["proyMaxMin"] = {
            "labels": labels_p,
            "prom": prom_p,
            "max": max_p,
            "min": min_p
        }

        # Desglose de Pérdida por Mes (soporte para barras comparativas si hay años distintos)
        resultado["perdidaMes"] = {
            "labels": labels_p,
            "mm2025": mm_p,
            "mm2026": mm_p,
            "dinero": dinero_p
        }

        resultado["alineacionMes"] = {
            "labels": labels_p,
            "alerta": alerta_p,
            "ok": ok_p
        }

        resultado["planesMes"] = {
            "labels": labels_p,
            "cambios": cambios_p,
            "duales": duales_p,
            "alineacion": alin_p,
            "rotacion": rot_p
        }

        resultado["ciclo"] = {
            "labels": labels_p,
            "original": orig_p,
            "reencauche": reenc_p,
            "pctReenc": pct_reenc_p
        }

        resultado["fvuProfBaja"] = {
            "labels": labels_p,
            "max": fvu_max_p,
            "prom": fvu_prom_p,
            "min": fvu_min_p
        }

    except Exception:
        import traceback
        traceback.print_exc()

    return resultado


# =============================================================================
# MÓDULO DE LAS 7 BODEGAS, KARDEX DE CICLO DE VIDA, GARANTÍAS Y BALANCE MRP (KPI 20)
# =============================================================================

def crear_llanta_en_bodega(datos: dict) -> dict:
    """
    Da de alta una nueva carcasa o llanta comprada en una de las bodegas (por defecto BODEGA_1_NUEVAS).
    Registra automáticamente el movimiento 'ALTA_NUEVA' en el Kardex.
    """
    cliente = str(datos.get('cliente', '')).strip().upper()
    subcliente = str(datos.get('subcliente', '')).strip().upper()
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()

    if not cliente:
        return {"ok": False, "mensaje": "El nombre del cliente es obligatorio"}
    if not numero_interno:
        return {"ok": False, "mensaje": "El número interno / serial de la llanta es obligatorio"}

    ubicacion = str(datos.get('ubicacion_bodega', 'BODEGA_1_NUEVAS')).strip().upper()
    marca = str(datos.get('marca', '')).strip().upper()
    diseno = str(datos.get('diseno', '')).strip().upper()
    dimension = str(datos.get('dimension', '295/80R22.5')).strip().upper()
    vida = str(datos.get('vida_actual', 'Original')).strip()
    banda = str(datos.get('banda_reen', '')).strip().upper()
    prof_ini = to_float(datos.get('prof_inicial', 18.0), 18.0)
    prof_act = to_float(datos.get('prof_actual_min', prof_ini), prof_ini)
    costo = to_float(datos.get('costo_compra', 1450000.0), 1450000.0)
    proveedor = str(datos.get('proveedor_actual', '')).strip()
    obs = str(datos.get('observaciones', '')).strip()
    user = str(datos.get('usuario_registro', 'admin')).strip()

    estados_nombre = {
        'BODEGA_1_NUEVAS': 'En Stock - Nueva',
        'BODEGA_2_RECAMBIO': 'En Stock - Reutilizable',
        'BODEGA_3_REENCAUCHE': 'Enviada a Reencauche',
        'BODEGA_4_REENCAUCHADAS': 'En Stock - Reencauchada',
        'BODEGA_5_REPARACION': 'En Reparación Mayor',
        'BODEGA_6_FVU': 'FVU / Desecho',
        'BODEGA_7_CHATARRIZADA': 'Disposición Final / Chatarrizada',
        'MONTADA_OPERACION': 'Montada en Vehículo'
    }
    estado_act = estados_nombre.get(ubicacion, 'En Stock - Nueva')

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM llantas_maestro WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?", (cliente, numero_interno))
        if cursor.fetchone():
            return {"ok": False, "mensaje": f"La llanta {numero_interno} ya existe en el inventario de {cliente}"}

        cursor.execute("""
            INSERT INTO llantas_maestro (
                numero_interno, cliente, subcliente, ubicacion_bodega, estado_actual,
                marca, diseno, dimension, vida_actual, banda_reen,
                prof_inicial, prof_ext, prof_cent, prof_int, prof_actual_min,
                costo_compra_original, costo_ciclo_actual, costo_reparaciones_ciclo_actual, costo_acumulado_total,
                proveedor_actual, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?)
        """, (
            numero_interno, cliente, subcliente, ubicacion, estado_act,
            marca, diseno, dimension, vida, banda,
            prof_ini, prof_act, prof_act, prof_act, prof_act,
            costo, costo, costo,
            proveedor, obs
        ))
        llanta_id = cursor.lastrowid

        # Kardex
        fecha_mov = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO kardex_movimientos_llanta (
                fecha_movimiento, cliente, subcliente, numero_interno,
                bodega_origen, bodega_destino, tipo_movimiento,
                vida_ciclo, prof_min_mm, costo_asociado, proveedor,
                causal_o_motivo, usuario_registro
            ) VALUES (?, ?, ?, ?, 'EXTERNO', ?, 'ALTA_NUEVA', ?, ?, ?, ?, 'Alta inicial en inventario de bodega', ?)
        """, (
            fecha_mov, cliente, subcliente, numero_interno,
            ubicacion, vida, prof_act, costo, proveedor, user
        ))

        conn.commit()

    return {"ok": True, "mensaje": f"Llanta {numero_interno} dada de alta en {estado_act}", "id": llanta_id}


def registrar_movimiento_bodega(datos: dict) -> dict:
    """
    Ejecuta una transición transaccional atómica entre las 7 bodegas y operación rodante.
    Actualiza llantas_maestro e inserta el evento en kardex_movimientos_llanta.
    """
    cliente = str(datos.get('cliente', '')).strip().upper()
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    bodega_destino = str(datos.get('bodega_destino', '')).strip().upper()

    if not cliente or not numero_interno or not bodega_destino:
        return {"ok": False, "mensaje": "Cliente, número interno y bodega destino son obligatorios"}

    fecha_mov = str(datos.get('fecha_movimiento') or datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')).strip()
    placa = str(datos.get('placa', '')).strip().upper()
    posicion = to_int(datos.get('posicion', 0))
    prof_min_in = datos.get('prof_min_mm')
    nueva_prof_ini = datos.get('nueva_prof_inicial')
    banda_reen = str(datos.get('banda_reen', '')).strip().upper()
    km_veh = to_float(datos.get('km_vehiculo', 0.0))
    costo_asoc = to_float(datos.get('costo_asociado', 0.0))
    proveedor = str(datos.get('proveedor', '')).strip()
    causal = str(datos.get('causal_o_motivo', '')).strip()
    doc_soporte = str(datos.get('documento_soporte', '')).strip()
    user = str(datos.get('usuario_registro', 'admin')).strip()

    estados_nombre = {
        'BODEGA_1_NUEVAS': 'En Stock - Nueva',
        'BODEGA_2_RECAMBIO': 'En Stock - Reutilizable',
        'BODEGA_3_REENCAUCHE': 'Enviada a Reencauche',
        'BODEGA_4_REENCAUCHADAS': 'En Stock - Reencauchada',
        'BODEGA_5_REPARACION': 'En Reparación Mayor',
        'BODEGA_6_FVU': 'FVU / Desecho',
        'BODEGA_7_CHATARRIZADA': 'Disposición Final / Chatarrizada',
        'MONTADA_OPERACION': 'Montada en Vehículo'
    }

    if bodega_destino not in estados_nombre:
        return {"ok": False, "mensaje": f"Bodega destino inválida: {bodega_destino}"}

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llantas_maestro WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?", (cliente, numero_interno))
        col_names = [d[0] for d in cursor.description]
        row = cursor.fetchone()

        if not row:
            return {"ok": False, "mensaje": f"La llanta {numero_interno} no se encuentra en llantas_maestro"}

        cur = dict(zip(col_names, row))
        bodega_origen = cur['ubicacion_bodega']
        subcliente = cur.get('subcliente', '')

        # Corrección 3: Máquina de Estados Estricta (Bloquear Transiciones Absurdas entre Bodegas)
        if bodega_origen == 'BODEGA_7_CHATARRIZADA':
            return {"ok": False, "mensaje": "⛔ Una carcasa chatarrizada con acta ambiental tiene baja definitiva y no puede reingresar al inventario."}

        if bodega_origen == bodega_destino:
            if bodega_destino != 'MONTADA_OPERACION' or (placa == cur.get('placa_actual', '') and posicion == to_int(cur.get('posicion_actual', 0))):
                return {"ok": False, "mensaje": "La llanta ya se encuentra en esa bodega o posición."}

        if bodega_origen == 'BODEGA_1_NUEVAS' and bodega_destino == 'BODEGA_3_REENCAUCHE':
            return {"ok": False, "mensaje": "⛔ Una llanta nueva sin rodar no puede ser enviada a reencauche."}

        # Variables mutables
        num_reen = to_int(cur.get('num_reencauches', 0))
        vida_act = str(cur.get('vida_actual', 'Original'))
        p_ini = to_float(cur.get('prof_inicial', 18.0))
        p_act = to_float(cur.get('prof_actual_min', 18.0))
        costo_ciclo = to_float(cur.get('costo_ciclo_actual', 1450000.0))
        costo_rep_ciclo = to_float(cur.get('costo_reparaciones_ciclo_actual', 0.0))
        costo_acum = to_float(cur.get('costo_acumulado_total', costo_ciclo))
        km_ciclo = to_float(cur.get('km_recorridos_ciclo', 0.0))
        f_envio_planta = cur.get('fecha_envio_planta')
        proveedor_act = proveedor or cur.get('proveedor_actual', '')
        causal_baja = cur.get('causal_baja_fvu', '')
        mm_perd = to_float(cur.get('mm_perdidos_fvu', 0.0))
        dinero_perd = to_float(cur.get('dinero_perdido_fvu', 0.0))
        estado_gar = str(cur.get('estado_garantia', 'No Aplica'))
        val_gar = to_float(cur.get('valor_reconocido_garantia', 0.0))
        acta_amb = cur.get('numero_acta_ambiental', '')
        f_disp = cur.get('fecha_disposicion')

        placa_origen = cur.get('placa_actual', '')
        pos_origen = to_int(cur.get('posicion_actual', 0))

        # Corrección 3: No enviar a Bodega 2 si la profundidad está en o por debajo del límite de retiro
        if bodega_destino == 'BODEGA_2_RECAMBIO':
            cfg = obtener_configuracion_avanzada_cliente(cliente)
            lim_ret = to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
            p_eval = to_float(prof_min_in) if prof_min_in is not None else p_act
            if p_eval <= lim_ret:
                return {"ok": False, "mensaje": f"⛔ No se puede enviar a Bodega 2 de Recambio: la profundidad ({p_eval:.1f} mm) está en o por debajo del límite de retiro ({lim_ret:.1f} mm). Debe enviarse a Bodega 3 (Reencauche) o Bodega 6 (FVU)."}

        # Corrección 2: Candado de Seguridad Vial al Montar desde Bodega hacia un Vehículo (MONTADA_OPERACION)
        if bodega_destino == 'MONTADA_OPERACION':
            if not placa or posicion < 1:
                return {"ok": False, "mensaje": "Para montar en operación se requiere placa válida y posición >= 1."}
            perfil_v = obtener_perfil_vehiculo(placa)
            tipologia_v = perfil_v.get('tipologia', '')
            if es_posicion_direccional(tipologia_v, posicion):
                if vida_act.upper() != 'ORIGINAL' or bodega_origen == 'BODEGA_4_REENCAUCHADAS':
                    return {"ok": False, "mensaje": "⛔ CANDADO VIAL: No se puede montar una llanta reencauchada en posición direccional."}

        placa_act = cur.get('placa_actual', '')
        pos_act = to_int(cur.get('posicion_actual', 0))

        tipo_mov = "TRASLADO_BODEGA"

        # 1. Retorno de Reencauche (Bodega 3 -> Bodega 4)
        if bodega_origen == 'BODEGA_3_REENCAUCHE' and bodega_destino == 'BODEGA_4_REENCAUCHADAS':
            tipo_mov = 'RETORNO_REENCAUCHE'
            num_reen += 1
            vida_act = f"R{num_reen}"
            p_ini = to_float(nueva_prof_ini, 18.0) if nueva_prof_ini is not None else 18.0
            p_act = p_ini
            banda = banda_reen or cur.get('banda_reen', '')
            costo_ciclo = max(0.0, costo_asoc)
            costo_rep_ciclo = 0.0
            km_ciclo = 0.0
            costo_acum += costo_ciclo
            f_envio_planta = None
            placa_act = ''
            pos_act = 0

        # 2. Envío a Planta de Reencauche (Hacia Bodega 3)
        elif bodega_destino == 'BODEGA_3_REENCAUCHE':
            tipo_mov = 'ENVIO_REENCAUCHE'
            f_envio_planta = fecha_mov
            placa_act = ''
            pos_act = 0
            if prof_min_in is not None:
                p_act = to_float(prof_min_in)

        # 3. Envío o Retorno de Reparación Mayor (Bodega 5) (Corrección 5: No Duplicar Costo)
        elif bodega_destino == 'BODEGA_5_REPARACION':
            tipo_mov = 'ENVIO_REPARACION'
            placa_act = ''
            pos_act = 0
            if prof_min_in is not None:
                p_act = to_float(prof_min_in)
            if costo_asoc > 0:
                costo_rep_ciclo += costo_asoc
                costo_acum += costo_asoc
        elif bodega_origen == 'BODEGA_5_REPARACION':
            tipo_mov = 'RETORNO_REPARACION'
            if prof_min_in is not None:
                p_act = to_float(prof_min_in)
            # Evitar duplicar costo si ya se sumó en la entrada a Bodega 5
            cursor.execute("""
                SELECT costo_asociado FROM kardex_movimientos_llanta
                WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?
                  AND bodega_destino = 'BODEGA_5_REPARACION'
                ORDER BY id DESC LIMIT 1
            """, (cliente, numero_interno))
            row_prev_b5 = cursor.fetchone()
            costo_prev_b5 = to_float(row_prev_b5[0]) if row_prev_b5 else 0.0
            if costo_asoc > 0:
                if costo_prev_b5 == 0.0:
                    costo_rep_ciclo += costo_asoc
                    costo_acum += costo_asoc
                elif costo_asoc > costo_prev_b5:
                    delta = costo_asoc - costo_prev_b5
                    costo_rep_ciclo += delta
                    costo_acum += delta

        # 4. Envío a Pila de Desecho / Fin de Vida Útil (Bodega 6 FVU) (Corrección 7)
        elif bodega_destino == 'BODEGA_6_FVU':
            tipo_mov = 'BAJA_FVU'
            causal_baja = causal or 'Fin de Vida Útil'
            placa_act = ''
            pos_act = 0
            if prof_min_in is not None:
                p_act = to_float(prof_min_in)

            cfg = obtener_configuracion_avanzada_cliente(cliente)
            lim_ret = to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
            if p_act <= lim_ret:
                mm_perd = 0.0
                dinero_perd = 0.0
                estado_gar = 'No Aplica (Vida Cumplida)'
            else:
                mm_perd = p_act - lim_ret
                mm_ut = max(1.0, p_ini - lim_ret)
                costo_mm = (costo_ciclo + costo_rep_ciclo) / mm_ut
                dinero_perd = max(0.0, (mm_perd * costo_mm) - val_gar)
                pct_desgaste = max(0.0, (p_ini - p_act) / mm_ut) * 100.0
                if pct_desgaste < 30.0 and estado_gar in ('No Aplica', ''):
                    estado_gar = 'Posible Garantía'

        # 5. Chatarrización / Disposición Final Ambiental (Bodega 7)
        elif bodega_destino == 'BODEGA_7_CHATARRIZADA':
            tipo_mov = 'CHATARRIZACION'
            acta_amb = doc_soporte or f"ACTA-{datetime.now(BOGOTA_TZ).strftime('%Y%m')}-{numero_interno}"
            f_disp = fecha_mov
            proveedor_act = proveedor or cur.get('proveedor_actual', '')
            placa_act = ''
            pos_act = 0

        # 6. Montaje en Vehículo (Hacia MONTADA_OPERACION)
        elif bodega_destino == 'MONTADA_OPERACION':
            tipo_mov = 'MONTAJE'
            placa_act = placa
            pos_act = posicion
            if prof_min_in is not None:
                p_act = to_float(prof_min_in)

            # Regla de Integridad de Flota: Si ya existía otra llanta en esa misma posición del vehículo,
            # se desmonta automáticamente hacia BODEGA_2_RECAMBIO para no tener duplicidad en la posición.
            if placa_act and pos_act > 0:
                cursor.execute("""
                    SELECT id, numero_interno, prof_actual_min, vida_actual FROM llantas_maestro
                    WHERE UPPER(cliente) = ? AND ubicacion_bodega = 'MONTADA_OPERACION'
                      AND UPPER(placa_actual) = ? AND posicion_actual = ?
                      AND UPPER(numero_interno) != ?
                """, (cliente, placa_act, pos_act, numero_interno))
                llantas_ocupantes = cursor.fetchall()
                for o_id, o_serial, o_prof, o_vida in llantas_ocupantes:
                    cursor.execute("""
                        UPDATE llantas_maestro SET
                            ubicacion_bodega = 'BODEGA_2_RECAMBIO',
                            estado_actual = 'En Stock - Reutilizable',
                            placa_actual = '',
                            posicion_actual = 0,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (o_id,))
                    cursor.execute("""
                        INSERT INTO kardex_movimientos_llanta (
                            fecha_movimiento, cliente, subcliente, numero_interno,
                            bodega_origen, bodega_destino, tipo_movimiento,
                            placa, posicion, vida_ciclo, prof_min_mm, km_vehiculo,
                            causal_o_motivo, documento_soporte, usuario_registro
                        ) VALUES (?, ?, ?, ?, 'MONTADA_OPERACION', 'BODEGA_2_RECAMBIO', 'DESMONTE_RECAMBIO',
                                  ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        fecha_mov, cliente, subcliente, o_serial,
                        placa_act, pos_act, o_vida, o_prof, km_veh,
                        f"Desmonte automático por montaje de llanta {numero_interno} en pos {pos_act}",
                        doc_soporte, user
                    ))

        # 7. Desmonte hacia Bodega 2 (Recambio)
        elif bodega_destino == 'BODEGA_2_RECAMBIO':
            tipo_mov = 'DESMONTE_RECAMBIO'
            placa_act = ''
            pos_act = 0
            if prof_min_in is not None:
                p_act = to_float(prof_min_in)
        else:
            placa_act = ''
            pos_act = 0

        estado_nuevo = estados_nombre.get(bodega_destino, 'En Stock')

        # Corrección 4: Limpieza estricta de placa y posición si no está montada en operación
        if bodega_destino != 'MONTADA_OPERACION':
            placa_act = ''
            pos_act = 0

        # Para el Kardex: registrar placa y posición de destino o de origen
        k_placa = placa_act if bodega_destino == 'MONTADA_OPERACION' else (placa or placa_origen)
        k_pos = pos_act if bodega_destino == 'MONTADA_OPERACION' else (posicion if posicion > 0 else pos_origen)

        # Actualizar llantas_maestro
        cursor.execute("""
            UPDATE llantas_maestro SET
                ubicacion_bodega = ?,
                estado_actual = ?,
                placa_actual = ?,
                posicion_actual = ?,
                vida_actual = ?,
                num_reencauches = ?,
                banda_reen = ?,
                prof_inicial = ?,
                prof_ext = ?,
                prof_cent = ?,
                prof_int = ?,
                prof_actual_min = ?,
                costo_ciclo_actual = ?,
                costo_reparaciones_ciclo_actual = ?,
                costo_acumulado_total = ?,
                km_recorridos_ciclo = ?,
                fecha_envio_planta = ?,
                proveedor_actual = ?,
                causal_baja_fvu = ?,
                mm_perdidos_fvu = ?,
                dinero_perdido_fvu = ?,
                estado_garantia = ?,
                numero_acta_ambiental = ?,
                fecha_disposicion = ?,
                reservada_para_placa = CASE WHEN ? = 'MONTADA_OPERACION' THEN NULL ELSE reservada_para_placa END,
                reservada_posicion = CASE WHEN ? = 'MONTADA_OPERACION' THEN NULL ELSE reservada_posicion END,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            bodega_destino, estado_nuevo, placa_act, pos_act,
            vida_act, num_reen, banda_reen or cur.get('banda_reen', ''),
            p_ini, p_act, p_act, p_act, p_act,
            costo_ciclo, costo_rep_ciclo, costo_acum, km_ciclo,
            f_envio_planta, proveedor_act, causal_baja, mm_perd, dinero_perd,
            estado_gar, acta_amb, f_disp, bodega_destino, bodega_destino, cur['id']
        ))

        # Registrar en Kardex
        cursor.execute("""
            INSERT INTO kardex_movimientos_llanta (
                fecha_movimiento, cliente, subcliente, numero_interno,
                bodega_origen, bodega_destino, tipo_movimiento,
                placa, posicion, vida_ciclo, prof_min_mm, km_vehiculo,
                costo_asociado, proveedor, causal_o_motivo, documento_soporte,
                usuario_registro
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha_mov, cliente, subcliente, numero_interno,
            bodega_origen, bodega_destino, tipo_mov,
            k_placa, k_pos, vida_act, p_act, km_veh,
            costo_asoc, proveedor_act, causal, doc_soporte, user
        ))

        conn.commit()

    return {
        "ok": True,
        "mensaje": f"Llanta {numero_interno} trasladada a {estado_nuevo}",
        "ubicacion_nueva": bodega_destino,
        "tipo_movimiento": tipo_mov
    }


def actualizar_garantia_llanta(datos: dict) -> dict:
    """
    Actualiza el estado de reclamación y valor reconocido de garantía de una carcasa en Bodega 6 FVU.
    Recalcula automáticamente el dinero perdido neto descontando la nota de crédito reconocida.
    """
    cliente = str(datos.get('cliente', '')).strip().upper()
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    nuevo_estado = str(datos.get('estado_garantia', 'No Aplica')).strip()
    val_reconocido = to_float(datos.get('valor_reconocido_garantia', 0.0))
    user = str(datos.get('usuario_registro', 'admin')).strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llantas_maestro WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?", (cliente, numero_interno))
        col_names = [d[0] for d in cursor.description]
        row = cursor.fetchone()

        if not row:
            return {"ok": False, "mensaje": f"No se encontró la llanta {numero_interno}"}

        ll = dict(zip(col_names, row))
        p_ini = to_float(ll.get('prof_inicial', 18.0))
        p_act = to_float(ll.get('prof_actual_min', 18.0))
        c_ciclo = to_float(ll.get('costo_ciclo_actual', 1450000.0))
        c_rep = to_float(ll.get('costo_reparaciones_ciclo_actual', 0.0))

        cfg = obtener_configuracion_avanzada_cliente(cliente)
        lim_ret = to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
        if p_act <= lim_ret:
            mm_perd = 0.0
            dinero_perd = 0.0
            nuevo_estado = 'No Aplica (Vida Cumplida)'
        else:
            mm_ut = max(1.0, p_ini - lim_ret)
            mm_perd = max(0.0, p_act - lim_ret)
            costo_mm = (c_ciclo + c_rep) / mm_ut
            dinero_perd = max(0.0, (mm_perd * costo_mm) - val_reconocido)

        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_garantia = ?,
                valor_reconocido_garantia = ?,
                mm_perdidos_fvu = ?,
                dinero_perdido_fvu = ?,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (nuevo_estado, val_reconocido, mm_perd, dinero_perd, ll['id']))

        fecha_mov = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO kardex_movimientos_llanta (
                fecha_movimiento, cliente, subcliente, numero_interno,
                bodega_origen, bodega_destino, tipo_movimiento,
                vida_ciclo, prof_min_mm, costo_asociado,
                causal_o_motivo, usuario_registro
            ) VALUES (?, ?, ?, ?, 'BODEGA_6_FVU', 'BODEGA_6_FVU', 'AJUSTE_GARANTIA', ?, ?, ?, ?, ?)
        """, (
            fecha_mov, cliente, ll.get('subcliente', ''), numero_interno,
            ll.get('vida_actual', 'Original'), p_act, val_reconocido,
            f"Garantía: {nuevo_estado} | Valor Reconocido: ${val_reconocido:,.0f}", user
        ))

        conn.commit()

    return {
        "ok": True,
        "mensaje": f"Garantía de {numero_interno} actualizada a '{nuevo_estado}'",
        "dinero_perdido_fvu": dinero_perd
    }


def obtener_kardex_llanta(cliente: str, numero_interno: str) -> dict:
    """
    Retorna la trazabilidad cronológica completa (Kardex) de una llanta específica.
    """
    cliente = str(cliente or '').strip().upper()
    numero_interno = str(numero_interno or '').strip().upper()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llantas_maestro WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?", (cliente, numero_interno))
        cols_m = [d[0] for d in cursor.description]
        row_m = cursor.fetchone()
        llanta_info = dict(zip(cols_m, row_m)) if row_m else {}

        cursor.execute("""
            SELECT id, fecha_movimiento, bodega_origen, bodega_destino, tipo_movimiento,
                   placa, posicion, vida_ciclo, prof_min_mm, km_vehiculo, costo_asociado,
                   proveedor, causal_o_motivo, documento_soporte, usuario_registro, fecha_creacion
            FROM kardex_movimientos_llanta
            WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?
            ORDER BY fecha_movimiento DESC, id DESC
        """, (cliente, numero_interno))
        cols_k = [d[0] for d in cursor.description]
        movimientos = [dict(zip(cols_k, r)) for r in cursor.fetchall()]

    return {
        "llanta": llanta_info,
        "movimientos": movimientos,
        "total_eventos": len(movimientos)
    }


def listar_inventario_bodegas(filtros: dict = None) -> dict:
    """
    Lista las llantas de `llantas_maestro` filtradas por cliente, subcliente, bodega, dimensión y búsqueda.
    """
    filtros = filtros or {}
    cliente = str(filtros.get('cliente', '')).strip().upper()
    subcliente = str(filtros.get('subcliente', '')).strip().upper()
    ubicacion = str(filtros.get('ubicacion_bodega', '')).strip().upper()
    dimension = str(filtros.get('dimension', '')).strip().upper()
    q = str(filtros.get('q', '')).strip().upper()

    query = "SELECT * FROM llantas_maestro WHERE 1=1"
    params = []

    if cliente and cliente != "TODOS":
        query += " AND UPPER(cliente) = ?"
        params.append(cliente)
    if subcliente and subcliente != "TODOS":
        query += " AND UPPER(subcliente) = ?"
        params.append(subcliente)
    if ubicacion and ubicacion != "TODAS":
        query += " AND UPPER(ubicacion_bodega) = ?"
        params.append(ubicacion)
    if dimension and dimension != "TODAS":
        query += " AND UPPER(dimension) = ?"
        params.append(dimension)
    if q:
        query += " AND (UPPER(numero_interno) LIKE ? OR UPPER(marca) LIKE ? OR UPPER(placa_actual) LIKE ?)"
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q])

    query += " ORDER BY fecha_actualizacion DESC, id DESC"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        cols = [d[0] for d in cursor.description]
        llantas = [dict(zip(cols, r)) for r in cursor.fetchall()]

        hoy = date.today()
        for item in llantas:
            item["reservada_para_dual"] = bool(item.get("reservada_para_placa"))
            if item.get("fecha_envio_planta"):
                try:
                    f_env = datetime.strptime(str(item["fecha_envio_planta"])[:10], '%Y-%m-%d').date()
                    item["dias_en_planta"] = max(0, (hoy - f_env).days)
                except Exception:
                    item["dias_en_planta"] = 0
            else:
                item["dias_en_planta"] = 0

    return {
        "total": len(llantas),
        "llantas": llantas
    }


def obtener_balance_bodegas_mrp(filtros: dict = None) -> dict:
    """
    Calcula el Balance Ejecutivo de las 7 Bodegas, Inventario Valorizado, Alertas
    y la Matriz de Compras Sugeridas MRP (KPI 20).
    Exclusivo de la licencia PRO.
    """
    filtros = filtros or {}
    cliente = str(filtros.get('cliente', '')).strip().upper()
    subcliente = str(filtros.get('subcliente', '')).strip().upper()
    dimension_filtro = str(filtros.get('dimension', '')).strip().upper()

    licencia = obtener_licencia_cliente(cliente)
    cfg = obtener_configuracion_avanzada_cliente(cliente)

    pct_aprob = to_float(cfg.get('porcentaje_aprobacion_reencauche', 85.0), 85.0)
    stock_seg_def = to_int(cfg.get('stock_seguridad_default', 4), 4)
    lim_dir = to_float(cfg.get('mm_retiro_direccional', 4.0), 4.0)
    lim_trac = to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
    dif_par_dir = to_float(cfg.get('diferencia_minima_par_direccional_mm', 3.0), 3.0)

    # Estructura base de bodegas
    bodegas_resumen = {
        'BODEGA_1_NUEVAS': {'nombre': 'Bodega 1: Llantas Nuevas', 'cantidad': 0, 'valor_cop': 0.0, 'color': '#06B6D4'},
        'BODEGA_2_RECAMBIO': {'nombre': 'Bodega 2: Recambio / Reutilizables', 'cantidad': 0, 'valor_cop': 0.0, 'libres': 0, 'reservadas': 0, 'color': '#10B981'},
        'BODEGA_3_REENCAUCHE': {'nombre': 'Bodega 3: En Planta Reencauche', 'cantidad': 0, 'valor_cop': 0.0, 'alerta_mas_15_dias': 0, 'color': '#6366F1'},
        'BODEGA_4_REENCAUCHADAS': {'nombre': 'Bodega 4: Reencauchadas Listas', 'cantidad': 0, 'valor_cop': 0.0, 'color': '#0D9488'},
        'BODEGA_5_REPARACION': {'nombre': 'Bodega 5: En Reparación Mayor', 'cantidad': 0, 'valor_cop': 0.0, 'costo_reparaciones_acum': 0.0, 'color': '#F59E0B'},
        'BODEGA_6_FVU': {'nombre': 'Bodega 6: Pila Desecho / FVU', 'cantidad': 0, 'valor_cop': 0.0, 'dinero_perdido_fvu': 0.0, 'posible_garantia_cnt': 0, 'valor_garantia_recuperado': 0.0, 'color': '#EF4444'},
        'BODEGA_7_CHATARRIZADA': {'nombre': 'Bodega 7: Disposición Final', 'cantidad': 0, 'valor_cop': 0.0, 'color': '#64748B'},
        'MONTADA_OPERACION': {'nombre': 'En Operación (Rodando)', 'cantidad': 0, 'valor_cop': 0.0, 'color': '#3B82F6'}
    }

    with get_connection() as conn:
        cursor = conn.cursor()
        query_m = "SELECT * FROM llantas_maestro WHERE 1=1"
        params_m = []
        if cliente and cliente != "TODOS":
            query_m += " AND UPPER(cliente) = ?"
            params_m.append(cliente)
        if subcliente and subcliente != "TODOS":
            query_m += " AND UPPER(subcliente) = ?"
            params_m.append(subcliente)

        cursor.execute(query_m, params_m)
        cols_m = [d[0] for d in cursor.description]
        llantas_todas = [dict(zip(cols_m, r)) for r in cursor.fetchall()]

    hoy = datetime.now(BOGOTA_TZ).date()

    for ll in llantas_todas:
        ubi = ll.get('ubicacion_bodega', 'BODEGA_1_NUEVAS')
        if ubi not in bodegas_resumen:
            continue

        b_entry = bodegas_resumen[ubi]
        b_entry['cantidad'] += 1

        costo_c = to_float(ll.get('costo_ciclo_actual', 0.0))
        costo_r = to_float(ll.get('costo_reparaciones_ciclo_actual', 0.0))
        b_entry['valor_cop'] += (costo_c + costo_r)

        if ubi == 'BODEGA_2_RECAMBIO':
            if ll.get('reservada_para_placa'):
                b_entry['reservadas'] += 1
            else:
                b_entry['libres'] += 1
        elif ubi == 'BODEGA_3_REENCAUCHE':
            f_env = ll.get('fecha_envio_planta')
            if f_env:
                try:
                    f_dt = datetime.strptime(str(f_env)[:10], '%Y-%m-%d').date()
                    if (hoy - f_dt).days > 15:
                        b_entry['alerta_mas_15_dias'] += 1
                except Exception:
                    pass
        elif ubi == 'BODEGA_5_REPARACION':
            b_entry['costo_reparaciones_acum'] += costo_r
        elif ubi == 'BODEGA_6_FVU':
            b_entry['dinero_perdido_fvu'] += to_float(ll.get('dinero_perdido_fvu', 0.0))
            if ll.get('estado_garantia') in ('Posible Garantía', 'En Reclamación'):
                b_entry['posible_garantia_cnt'] += 1
            b_entry['valor_garantia_recuperado'] += to_float(ll.get('valor_reconocido_garantia', 0.0))

    # Matriz MRP por dimensión
    dimensiones_set = sorted(list({ll.get('dimension', '295/80R22.5') for ll in llantas_todas if ll.get('dimension')}))
    if not dimensiones_set:
        dimensiones_set = ['295/80R22.5']
    if dimension_filtro and dimension_filtro != 'TODAS':
        dimensiones_set = [d for d in dimensiones_set if d.upper() == dimension_filtro.upper()] or [dimension_filtro]

    matriz_mrp = []

    # Obtener últimas inspecciones por vehículo para evaluar demanda en patio
    df_raw = obtener_todas_inspecciones()
    if not df_raw.empty and cliente and cliente != "TODOS":
        df_raw = df_raw[df_raw['cliente'].astype(str).str.upper().str.strip() == cliente]
    if not df_raw.empty and subcliente and subcliente != "TODOS":
        df_raw = df_raw[df_raw['subcliente'].astype(str).str.upper().str.strip() == subcliente]

    # Agrupar última inspección por placa
    df_patio = pd.DataFrame()
    if not df_raw.empty:
        corte_vehiculos = []
        for _, grp in df_raw.groupby('placa'):
            f_max = grp['fecha'].astype(str).max()
            g_f = grp[grp['fecha'].astype(str) == f_max]
            corte_vehiculos.append(g_f)
        if corte_vehiculos:
            df_patio = pd.concat(corte_vehiculos, ignore_index=True)

    for dim in dimensiones_set:
        # 1. Demanda en patio por límite de retiro y par direccional
        demanda_dir = 0
        demanda_trac = 0

        if not df_patio.empty:
            df_dim = df_patio[df_patio['dimension'].astype(str).str.upper().str.strip() == dim.upper()]
            for placa_v, grp_p in df_dim.groupby('placa'):
                pos_list = [to_int(p) for p in grp_p['posicion']]
                # Evaluar par direccional (pos 1 y 2)
                p1 = grp_p[grp_p['posicion'] == 1]
                p2 = grp_p[grp_p['posicion'] == 2]

                p1_ret = False
                p2_ret = False
                p1_min = 99.0
                p2_min = 99.0
                p1_ini = 18.0
                p2_ini = 18.0

                if not p1.empty:
                    pe = to_float(p1['prof_ext'].values[0])
                    pc = to_float(p1['prof_cent'].values[0])
                    pi = to_float(p1['prof_int'].values[0])
                    p1_ini = to_float(p1['prof_inicial'].values[0], 18.0)
                    vals = [x for x in (pe, pc, pi) if x > 0]
                    p1_min = min(vals) if vals else 0.0
                    p1_ret = (p1_min <= lim_dir)

                if not p2.empty:
                    pe = to_float(p2['prof_ext'].values[0])
                    pc = to_float(p2['prof_cent'].values[0])
                    pi = to_float(p2['prof_int'].values[0])
                    p2_ini = to_float(p2['prof_inicial'].values[0], 18.0)
                    vals = [x for x in (pe, pc, pi) if x > 0]
                    p2_min = min(vals) if vals else 0.0
                    p2_ret = (p2_min <= lim_dir)

                # Si ambas están en retiro
                if p1_ret and p2_ret:
                    demanda_dir += 2
                # Si exactamente 1 está en retiro: regla de ajuste par direccional
                elif p1_ret and not p2_ret:
                    demanda_dir += 1
                    if (p2_ini - p2_min) > dif_par_dir:
                        demanda_dir += 1  # Ajuste par direccional
                elif p2_ret and not p1_ret:
                    demanda_dir += 1
                    if (p1_ini - p1_min) > dif_par_dir:
                        demanda_dir += 1  # Ajuste par direccional

                # Posiciones de tracción / arrastre (pos > 2)
                for _, row_tr in grp_p[grp_p['posicion'] > 2].iterrows():
                    pe = to_float(row_tr['prof_ext'])
                    pc = to_float(row_tr['prof_cent'])
                    pi = to_float(row_tr['prof_int'])
                    vals = [x for x in (pe, pc, pi) if x > 0]
                    p_m = min(vals) if vals else 0.0
                    if p_m <= lim_trac:
                        demanda_trac += 1

        demanda_flota = demanda_dir + demanda_trac

        # 2. Bajas FVU de esta dimensión
        ll_dim_fvu = [ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_6_FVU']
        bajas_fvu = len(ll_dim_fvu)

        # 3. Stock de seguridad
        stock_seg = stock_seg_def

        # 4. Necesidad Bruta
        necesidad_bruta = demanda_flota + bajas_fvu + stock_seg

        # 5. Disponibilidad en Bodegas
        b1_nuevas = len([ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_1_NUEVAS'])
        b2_recambio_libres = len([ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_2_RECAMBIO' and not ll.get('reservada_para_placa')])
        b2_recambio_libres_utiles = len([ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_2_RECAMBIO' and not ll.get('reservada_para_placa') and to_float(ll.get('prof_actual_min', 0.0)) > lim_trac])
        b3_planta = len([ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_3_REENCAUCHE'])
        b4_reenc_listas = len([ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_4_REENCAUCHADAS'])
        b5_reparacion = len([ll for ll in llantas_todas if ll.get('dimension', '').upper() == dim.upper() and ll.get('ubicacion_bodega') == 'BODEGA_5_REPARACION'])

        retorno_planta_estimado = int(math.floor(b3_planta * (pct_aprob / 100.0)))

        # Balance de Eje Direccional (Corrección 1: Prohibido cubrir Demanda Direccional con Reencauches)
        compra_nuevas_dir = max(0, demanda_dir - b1_nuevas)
        b1_restante = max(0, b1_nuevas - demanda_dir)

        # Balance de Tracción / Arrastre + Stock de Seguridad + Reposición FVU
        necesidad_no_dir = demanda_trac + bajas_fvu + stock_seg
        stock_util_no_dir = b1_restante + b2_recambio_libres_utiles + b4_reenc_listas + retorno_planta_estimado + b5_reparacion
        compra_adicional_reenc = max(0, necesidad_no_dir - stock_util_no_dir)

        # Compra Neta Total Sugerida (KPI 20)
        compra_neta = compra_nuevas_dir + compra_adicional_reenc
        stock_disponible_util = b1_nuevas + b2_recambio_libres_utiles + b4_reenc_listas + retorno_planta_estimado + b5_reparacion

        matriz_mrp.append({
            'dimension': dim,
            'demanda_flota': demanda_flota,
            'demanda_direccional': demanda_dir,
            'demanda_traccion': demanda_trac,
            'reposicion_bajas_fvu': bajas_fvu,
            'stock_seguridad': stock_seg,
            'necesidad_bruta': necesidad_bruta,
            'b1_nuevas': b1_nuevas,
            'b1_restante': b1_restante,
            'b2_recambio_libres': b2_recambio_libres,
            'b2_recambio_libres_utiles': b2_recambio_libres_utiles,
            'b3_planta': b3_planta,
            'retorno_planta_estimado': retorno_planta_estimado,
            'b4_reenc_listas': b4_reenc_listas,
            'b5_reparacion': b5_reparacion,
            'stock_disponible_util': stock_disponible_util,
            'stock_util_no_direccional': stock_util_no_dir,
            'compra_neta_sugerida': compra_neta,
            'compra_nuevas_direccional': compra_nuevas_dir,
            'compra_adicional_reencauche': compra_adicional_reenc
        })

    return {
        "licencia": licencia,
        "disponible_en_licencia": (licencia == 'PRO'),
        "bodegas": bodegas_resumen,
        "matriz_mrp": matriz_mrp,
        "total_carcasas_inventario": len(llantas_todas)
    }


def obtener_directorio_clientes():
    """
    Retorna la lista completa y consolidada de clientes/flotas registrados en el sistema,
    cruzando la configuración general, plan de licenciamiento (LIGHT vs PRO),
    límites de retiro base, sedes/subclientes, conteo de vehículos en padrón,
    inspecciones históricas, llantas en las 7 bodegas y marcas habituales asignadas.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Base de clientes desde configuracion_clientes
        cursor.execute("""
            SELECT UPPER(TRIM(cliente)), limite_retiro_mm, IFNULL(observaciones, ''), fecha_actualizacion
            FROM configuracion_clientes
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
            ORDER BY cliente ASC
        """)
        clientes_cfg = {
            r[0]: {
                "cliente": r[0],
                "limite_retiro_mm": to_float(r[1], 3.0),
                "observaciones": r[2] or "",
                "fecha_actualizacion": str(r[3] or "")
            }
            for r in cursor.fetchall()
        }

        # Asegurar clientes que pudieran estar en otras tablas pero no en configuracion_clientes
        cursor.execute("SELECT DISTINCT UPPER(TRIM(cliente)) FROM inspecciones WHERE cliente IS NOT NULL AND TRIM(cliente) != ''")
        for (c,) in cursor.fetchall():
            if c and c not in clientes_cfg:
                clientes_cfg[c] = {
                    "cliente": c,
                    "limite_retiro_mm": 3.0,
                    "observaciones": "Detectado desde historial de inspecciones",
                    "fecha_actualizacion": ""
                }

        cursor.execute("SELECT DISTINCT UPPER(TRIM(cliente)) FROM configuracion_limites_retiro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''")
        for (c,) in cursor.fetchall():
            if c and c not in clientes_cfg:
                clientes_cfg[c] = {
                    "cliente": c,
                    "limite_retiro_mm": 3.0,
                    "observaciones": "Detectado desde límites de retiro",
                    "fecha_actualizacion": ""
                }

        # 2. Licenciamiento avanzado (LIGHT vs PRO)
        cursor.execute("SELECT UPPER(TRIM(cliente)), tipo_licencia FROM configuracion_avanzada_cliente")
        licencias = {r[0]: (r[1] or 'PRO').upper() for r in cursor.fetchall()}

        # 3. Sedes / Subclientes únicos detectados
        subclientes_dict = {}
        cursor.execute("""
            SELECT DISTINCT UPPER(TRIM(cliente)), UPPER(TRIM(subcliente))
            FROM configuracion_limites_retiro
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
              AND subcliente IS NOT NULL AND TRIM(subcliente) != '' AND UPPER(TRIM(subcliente)) != 'TODOS'
        """)
        for c, s in cursor.fetchall():
            subclientes_dict.setdefault(c, set()).add(s)

        cursor.execute("""
            SELECT DISTINCT UPPER(TRIM(cliente)), UPPER(TRIM(subcliente))
            FROM inspecciones
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
              AND subcliente IS NOT NULL AND TRIM(subcliente) != '' AND UPPER(TRIM(subcliente)) != 'TODOS'
        """)
        for c, s in cursor.fetchall():
            subclientes_dict.setdefault(c, set()).add(s)

        # 4. Conteo de vehículos por cliente
        cursor.execute("""
            SELECT UPPER(TRIM(cliente)), COUNT(DISTINCT placa)
            FROM padron_vehiculos_cliente
            WHERE activo = 1 AND cliente IS NOT NULL AND TRIM(cliente) != ''
            GROUP BY UPPER(TRIM(cliente))
        """)
        vehiculos_padron = {r[0]: r[1] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT UPPER(TRIM(cliente)), COUNT(DISTINCT placa)
            FROM catalogo_vehiculos
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
            GROUP BY UPPER(TRIM(cliente))
        """)
        vehiculos_cat = {r[0]: r[1] for r in cursor.fetchall()}

        # 5. Conteo de inspecciones históricas
        cursor.execute("""
            SELECT UPPER(TRIM(cliente)), COUNT(*)
            FROM inspecciones
            WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
            GROUP BY UPPER(TRIM(cliente))
        """)
        inspecciones_conteo = {r[0]: r[1] for r in cursor.fetchall()}

        # 6. Conteo de llantas en inventario / bodegas
        try:
            cursor.execute("""
                SELECT UPPER(TRIM(cliente)), COUNT(*)
                FROM llantas_maestro
                WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                GROUP BY UPPER(TRIM(cliente))
            """)
            llantas_conteo = {r[0]: r[1] for r in cursor.fetchall()}
        except Exception:
            llantas_conteo = {}

        # 7. Marcas habituales asignadas
        marcas_dict = {}
        try:
            cursor.execute("""
                SELECT UPPER(TRIM(cliente)), UPPER(TRIM(marca))
                FROM configuracion_marcas_cliente
                WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                  AND marca IS NOT NULL AND TRIM(marca) != ''
                ORDER BY marca ASC
            """)
            for c, m in cursor.fetchall():
                marcas_dict.setdefault(c, []).append(m)
        except Exception:
            marcas_dict = {}

        # Ensamblar resultado consolidado
        resultado = []
        for c_nombre, item in sorted(clientes_cfg.items(), key=lambda x: x[0]):
            sub_list = sorted(list(subclientes_dict.get(c_nombre, set())))
            v_cnt = max(vehiculos_padron.get(c_nombre, 0), vehiculos_cat.get(c_nombre, 0))
            insp_cnt = inspecciones_conteo.get(c_nombre, 0)
            ll_cnt = llantas_conteo.get(c_nombre, 0)
            m_list = marcas_dict.get(c_nombre, [])

            # Puede eliminarse solo si no tiene historial operativo de inspecciones ni llantas
            puede_eliminar = (insp_cnt == 0 and ll_cnt == 0)

            resultado.append({
                "cliente": c_nombre,
                "tipo_licencia": licencias.get(c_nombre, "PRO"),
                "limite_retiro_mm": item["limite_retiro_mm"],
                "observaciones": item["observaciones"],
                "fecha_actualizacion": item["fecha_actualizacion"],
                "subclientes": sub_list,
                "cant_vehiculos": v_cnt,
                "vehiculos_count": v_cnt,
                "cant_inspecciones": insp_cnt,
                "inspecciones_count": insp_cnt,
                "cant_llantas": ll_cnt,
                "llantas_count": ll_cnt,
                "marcas": m_list,
                "marcas_count": len(m_list),
                "puede_eliminar": puede_eliminar
            })

        return resultado


def crear_o_actualizar_cliente(datos: dict):
    """
    Crea o actualiza un cliente/flota en el sistema garantizando integridad y normalización en mayúsculas:
    - Inserta/actualiza en configuracion_clientes (límite base y observaciones).
    - Inserta/actualiza en configuracion_avanzada_cliente (licencia PRO/LIGHT).
    - Registra la regla base en configuracion_limites_retiro (TODOS/TODOS).
    - Si se especifican sedes/subclientes, registra sus reglas correspondientes.
    """
    raw_cliente = str(datos.get("cliente", "")).strip().upper()
    if not raw_cliente:
        return {"ok": False, "mensaje": "El nombre del cliente o razón social es obligatorio."}

    tipo_licencia = str(datos.get("tipo_licencia", "PRO")).strip().upper()
    if tipo_licencia not in ("PRO", "LIGHT"):
        tipo_licencia = "PRO"

    limite_retiro_mm = to_float(datos.get("limite_retiro_mm", 3.0), 3.0)
    if limite_retiro_mm <= 0:
        limite_retiro_mm = 3.0

    observaciones = str(datos.get("observaciones", "")).strip()

    # Procesar subclientes / sedes
    subclientes_input = datos.get("subclientes", "")
    subclientes_lista = []
    if isinstance(subclientes_input, list):
        subclientes_lista = [str(s).strip().upper() for s in subclientes_input if str(s).strip()]
    elif isinstance(subclientes_input, str) and subclientes_input.strip():
        partes = [p.strip().upper() for p in re.split(r'[,;\n]+', subclientes_input)]
        subclientes_lista = [p for p in partes if p and p != 'TODOS']

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Guardar en configuracion_clientes
        cursor.execute("""
            INSERT INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                limite_retiro_mm = excluded.limite_retiro_mm,
                observaciones = excluded.observaciones,
                fecha_actualizacion = CURRENT_TIMESTAMP
        """, (raw_cliente, limite_retiro_mm, observaciones))

        # 2. Guardar en configuracion_avanzada_cliente
        cursor.execute("""
            INSERT INTO configuracion_avanzada_cliente (cliente, tipo_licencia, fecha_actualizacion)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                tipo_licencia = excluded.tipo_licencia,
                fecha_actualizacion = CURRENT_TIMESTAMP
        """, (raw_cliente, tipo_licencia))

        # 3. Regla global por defecto en configuracion_limites_retiro
        cursor.execute("""
            INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
            VALUES (?, 'TODOS', 'TODOS', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente, subcliente, eje) DO UPDATE SET
                limite_retiro_mm = excluded.limite_retiro_mm,
                observaciones = excluded.observaciones,
                fecha_actualizacion = CURRENT_TIMESTAMP
        """, (raw_cliente, limite_retiro_mm, observaciones))

        # 4. Insertar subclientes/sedes si fueron indicados
        for sub in subclientes_lista:
            cursor.execute("""
                INSERT OR IGNORE INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm, observaciones, fecha_actualizacion)
                VALUES (?, ?, 'TODOS', ?, ?, CURRENT_TIMESTAMP)
            """, (raw_cliente, sub, limite_retiro_mm, f"Sede registrada: {sub}"))

        conn.commit()

    return {
        "ok": True,
        "cliente": raw_cliente,
        "mensaje": f"Cliente '{raw_cliente}' guardado exitosamente con licencia {tipo_licencia}."
    }


def eliminar_cliente_directorio(cliente: str):
    """
    Elimina un cliente del sistema aplicando un candado de seguridad estricto:
    No se permite eliminar clientes que ya tengan inspecciones registradas o
    llantas en inventario / bodegas para preservar la trazabilidad histórica y auditoría contable.
    """
    raw_cliente = str(cliente).strip().upper()
    if not raw_cliente:
        return {"ok": False, "mensaje": "Nombre de cliente inválido."}

    with get_connection() as conn:
        cursor = conn.cursor()

        # Candado 1: Inspecciones
        cursor.execute("SELECT COUNT(*) FROM inspecciones WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
        cnt_insp = cursor.fetchone()[0]
        if cnt_insp > 0:
            return {
                "ok": False,
                "mensaje": f"No se puede eliminar el cliente '{raw_cliente}' porque tiene {cnt_insp} inspecciones registradas en el historial."
            }

        # Candado 2: Llantas en bodegas
        try:
            cursor.execute("SELECT COUNT(*) FROM llantas_maestro WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
            cnt_ll = cursor.fetchone()[0]
            if cnt_ll > 0:
                return {
                    "ok": False,
                    "mensaje": f"No se puede eliminar el cliente '{raw_cliente}' porque tiene {cnt_ll} llantas registradas en inventario / bodegas."
                }
        except Exception:
            pass

        # Eliminar de tablas de configuración y catálogos asociados
        cursor.execute("DELETE FROM configuracion_clientes WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
        cursor.execute("DELETE FROM configuracion_avanzada_cliente WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
        cursor.execute("DELETE FROM configuracion_limites_retiro WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
        cursor.execute("DELETE FROM configuracion_marcas_cliente WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
        cursor.execute("DELETE FROM padron_vehiculos_cliente WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))
        cursor.execute("DELETE FROM catalogo_vehiculos WHERE UPPER(TRIM(cliente)) = ?", (raw_cliente,))

        conn.commit()

    return {
        "ok": True,
        "cliente": raw_cliente,
        "mensaje": f"Cliente '{raw_cliente}' eliminado exitosamente del catálogo."
    }


