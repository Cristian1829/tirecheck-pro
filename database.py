import sqlite3
import pandas as pd
import unicodedata
import os
import re
import hashlib
import hmac
import secrets
from datetime import datetime, date, timedelta
from contextlib import contextmanager

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
                vida TEXT,
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
        try:
            cursor.execute("PRAGMA table_info(usuarios)")
            cols_usr = [r[1] for r in cursor.fetchall()]
            if 'vistas_permitidas' not in cols_usr:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN vistas_permitidas TEXT DEFAULT 'patio,diagnostico,kpis'")
        except Exception:
            pass

        # Insertar usuarios por defecto si no existen
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas)
                VALUES ('admin', ?, 'Administrador General', 'admin', '', 'patio,basedatos,diagnostico,kpis,catalogos')
            """, (hash_password('admin123'),))
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

        conn.commit()

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

def obtener_perfil_vehiculo(placa: str) -> dict:
    pl = str(placa or '').strip().upper()
    if not pl:
        return {"encontrado": False, "placa": ""}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # 1. Buscar en la última inspección registrada previamente para esa placa
        cursor.execute("""
            SELECT placa, tipologia, cliente, subcliente, tipo_operacion, kilometraje
            FROM inspecciones
            WHERE UPPER(TRIM(placa)) = ? AND tipologia IS NOT NULL AND TRIM(tipologia) != ''
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, (pl,))
        row = cursor.fetchone()
        
        # 2. Si no ha tenido inspección previa, consultar el catálogo de vehículos
        if not row or not row[1]:
            cursor.execute("""
                SELECT placa, tipologia, cliente, subcliente, tipo_operacion, ultimo_km
                FROM catalogo_vehiculos
                WHERE UPPER(TRIM(placa)) = ?
            """, (pl,))
            row = cursor.fetchone()
        else:
            # Sincronizar catálogo con los datos de la última inspección
            sincronizar_vehiculo_catalogo(row[0], row[1], row[2], row[3], row[4], row[5])

    if row and row[1]:
        tip = row[1]
        posiciones = obtener_posiciones_por_tipologia(tip)
        esquema = obtener_esquema_tipologia(tip)
        return {
            "encontrado": True,
            "placa": row[0],
            "tipologia": tip,
            "cliente": row[2] or "",
            "subcliente": row[3] or "",
            "tipo_operacion": row[4] or "",
            "ultimo_km": to_float(row[5], 0.0),
            "cant_llantas": len(posiciones),
            "esquema": esquema,
            "posiciones": posiciones
        }
    
    return {"encontrado": False, "placa": pl}

def obtener_llanta_por_cliente(cliente: str, numero_interno: str, placa: str = "") -> dict | None:
    num_norm = str(numero_interno or '').strip().upper()
    cli_norm = str(cliente or '').strip()
    pl_norm = str(placa or '').strip().upper()
    
    if not num_norm:
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
    Regla: Requiere que transcurra el siguiente mes más 20 días calendario.
    Si la inspección previa fue en fecha F (ej. 2026-10-01 o 2026-10-15):
    - Mes siguiente: 2026-11.
    - Se requiere que transcurra el mes y pasen 20 días (a partir del día 21 del mes siguiente: 2026-11-21).
    O si la fecha base fue a finales de mes:
    Garantiza que transcurra 1 mes calendario completo + 20 días.
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

    fecha_dia_21_sig = date(año_sig, mes_sig, 21)
    fecha_50_dias = fecha_base + timedelta(days=50)
    return max(fecha_dia_21_sig, fecha_50_dias)

def validar_inspeccion_candados(datos, excluir_id=None, conn=None):
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
    vida_val = str(datos.get('vida', 'Original')).strip().capitalize()
    if es_posicion_direccional(tipologia_val, posicion) and vida_val.lower() == 'reencauche':
        return {
            'valido': False,
            'mensaje': (
                f'⛔ CANDADO DE SEGURIDAD VIAL: En el eje direccional (Posición {posicion}) '
                f'no se puede seleccionar en vida/condición Reencauche, únicamente condición Original.'
            )
        }

    # Asignación automática de número consecutivo TMP-001 si viene vacío
    num_interno = str(datos.get('numero_interno', '')).strip().upper()
    if not num_interno:
        num_interno = generar_siguiente_numero_interno_temporal(conn=conn)
        datos['numero_interno'] = num_interno

    # Consultar historial previo de esta placa
    def _ejecutar_consultas(c):
        cursor = c.cursor()
        # Mes de inspección (YYYY-MM)
        mes_inspeccion = fecha_str[:7] if len(fecha_str) >= 7 else datetime.now().strftime('%Y-%m')

        # Candado 1.5: Candado de No Duplicidad de Número Interno por Cliente y Subcliente en el mismo mes
        cliente_val = str(datos.get('cliente', '')).strip()
        subcliente_val = str(datos.get('subcliente', '')).strip()
        if num_interno and cliente_val:
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
                if posicion in pos_ya_registradas:
                    return {
                        'valido': False,
                        'alerta_mes': True,
                        'mensaje': f'⚠️ CANDADO DE SEGURIDAD: El vehículo {placa} ya fue inspeccionado en la Posición {posicion} en la fecha {f_ult_str}.'
                    }
            elif f_nueva_str < f_ult_str:
                return {
                    'valido': False,
                    'alerta_mes': True,
                    'mensaje': f'⚠️ CANDADO DE FECHA: La fecha de inspección ({f_nueva_str}) no puede ser anterior a la última inspección registrada ({f_ult_str}).'
                }
            else:
                # Fecha posterior: debe haber transcurrido el siguiente mes más 20 días
                f_base = datetime.strptime(f_ult_str, '%Y-%m-%d').date()
                f_nueva = datetime.strptime(f_nueva_str, '%Y-%m-%d').date()
                f_minima = calcular_fecha_minima_siguiente_inspeccion(f_base)
                if f_nueva < f_minima:
                    return {
                        'valido': False,
                        'alerta_mes': True,
                        'mensaje': (
                            f'⚠️ CANDADO DE FRECUENCIA: El vehículo {placa} ya fue inspeccionado en la Posición {posicion} el {f_ult_str}. '
                            f'Una nueva inspección requiere que transcurra el siguiente mes más 20 días '
                            f'(disponible a partir del {f_minima.strftime("%Y-%m-%d")}).'
                        )
                    }

        # Candado 3: Kilometraje actual no puede ser menor al de la última inspección
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

        # Candado 4: Profundidad no puede subir de una inspección a otra (tolerancia máx 1.0 mm)
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
    if not str(datos.get('numero_interno', '')).strip():
        datos['numero_interno'] = generar_siguiente_numero_interno_temporal()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                tipologia, marca, diseno, dimension, vida, banda_reen,
                prof_ext, prof_cent, prof_int, psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro, foto_novedad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(datos.get('fecha', datetime.now().strftime('%Y-%m-%d'))),
            str(datos.get('cliente', '')).strip().upper(),
            str(datos.get('subcliente', '')).strip().upper(),
            str(datos.get('tipo_operacion', '')).strip().upper(),
            str(datos.get('placa', '')).strip().upper(),
            to_int(datos.get('posicion', 1)),
            to_float(datos.get('kilometraje', 0)),
            str(datos.get('tipologia', '')).strip().upper(),
            str(datos.get('marca', '')).strip().upper(),
            str(datos.get('diseno', '')).strip().upper(),
            str(datos.get('dimension', '')).strip().upper(),
            str(datos.get('vida', 'ORIGINAL')).strip().upper(),
            str(datos.get('banda_reen', '')).strip().upper() if str(datos.get('vida', '')).strip().upper() == 'REENCAUCHE' else '',
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
        conn.commit()
        last_id = cursor.lastrowid
    sincronizar_vehiculo_catalogo(
        datos.get('placa'),
        datos.get('tipologia'),
        datos.get('cliente'),
        datos.get('subcliente'),
        datos.get('tipo_operacion'),
        datos.get('kilometraje')
    )
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
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE inspecciones SET
                fecha = ?, cliente = ?, subcliente = ?, tipo_operacion = ?, placa = ?,
                posicion = ?, kilometraje = ?, tipologia = ?, marca = ?, diseno = ?,
                dimension = ?, vida = ?, banda_reen = ?, prof_ext = ?, prof_cent = ?,
                prof_int = ?, psi = ?, novedades = ?, precio = ?, prof_inicial = ?,
                km_montaje = ?, numero_interno = ?, foto_novedad = ?
            WHERE id = ?
        """, (
            str(datos.get('fecha', '')),
            str(datos.get('cliente', '')).strip().upper(),
            str(datos.get('subcliente', '')).strip().upper(),
            str(datos.get('tipo_operacion', '')).strip().upper(),
            str(datos.get('placa', '')).strip().upper(),
            to_int(datos.get('posicion', 1)),
            to_float(datos.get('kilometraje', 0)),
            str(datos.get('tipologia', '')).strip().upper(),
            str(datos.get('marca', '')).strip().upper(),
            str(datos.get('diseno', '')).strip().upper(),
            str(datos.get('dimension', '')).strip().upper(),
            str(datos.get('vida', 'ORIGINAL')).strip().upper(),
            str(datos.get('banda_reen', '')).strip().upper() if str(datos.get('vida', '')).strip().upper() == 'REENCAUCHE' else '',
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
        conn.commit()
        ok = cursor.rowcount > 0
    if ok:
        sincronizar_vehiculo_catalogo(
            datos.get('placa'),
            datos.get('tipologia'),
            datos.get('cliente'),
            datos.get('subcliente'),
            datos.get('tipo_operacion'),
            datos.get('kilometraje')
        )
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
        'kilometraje': ['kilometraje', 'km', 'km actual', 'odometro'],
        'tipologia': ['tipologia', 'tipología', 'tipo', 'tipo vehiculo'],
        'marca': ['marca', 'marca llanta'],
        'diseno': ['diseno', 'diseño', 'dibujo', 'modelo'],
        'dimension': ['dimension', 'dimensión', 'medida', 'dim'],
        'vida': ['vida', 'estado vida', 'condicion'],
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
            vida_raw = str(row[col_encontradas['vida']]).strip() if 'vida' in col_encontradas and not pd.isna(row[col_encontradas['vida']]) else 'ORIGINAL'
            vida = vida_raw.upper() if vida_raw and vida_raw.upper() != 'NAN' else 'ORIGINAL'
            banda_raw = str(row[col_encontradas['banda_reen']]).strip() if 'banda_reen' in col_encontradas and not pd.isna(row[col_encontradas['banda_reen']]) else ''
            banda = banda_raw.upper() if banda_raw and banda_raw.upper() != 'NAN' and vida == 'REENCAUCHE' else ''

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
                'foto_novedad': ''
            }

            # Validar candados de seguridad por cada fila
            val = validar_inspeccion_candados(datos, conn=conn)
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
    
    for placa, group in df.groupby('placa'):
        if 'fecha' in group.columns and not group['fecha'].dropna().empty:
            fecha_max = group['fecha'].astype(str).str[:10].max()
            group = group[group['fecha'].astype(str).str[:10] == fecha_max]
        if 'id' in group.columns:
            group = group.sort_values('id').groupby('posicion', as_index=False).last()

        t_veh_val = group['tipo_calc'].iloc[0] if 'tipo_calc' in group else 'Desconocido'
        t_veh = 'Desconocido' if (pd.isna(t_veh_val) or str(t_veh_val).strip().lower() in ('nan', 'none', '')) else str(t_veh_val).strip()

        cli_val = group['cliente'].iloc[0] if ('cliente' in group and pd.notna(group['cliente'].iloc[0])) else ''
        cliente = '' if (pd.isna(cli_val) or str(cli_val).strip().lower() in ('nan', 'none')) else str(cli_val).strip()

        sub_val = group['subcliente'].iloc[0] if ('subcliente' in group and pd.notna(group['subcliente'].iloc[0])) else ''
        subcliente = '' if (pd.isna(sub_val) or str(sub_val).strip().lower() in ('nan', 'none')) else str(sub_val).strip()

        op_val = group['tipo_operacion'].iloc[0] if ('tipo_operacion' in group and pd.notna(group['tipo_operacion'].iloc[0])) else ''
        operacion = '' if (pd.isna(op_val) or str(op_val).strip().lower() in ('nan', 'none')) else str(op_val).strip()
        
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
                
                if razones:
                    plan_dual = True
                    detalles_dual.append(f"Dual {p_a}-{p_b}: {', '.join(razones)}")

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
                    r_min = max(limite_cambio_cliente + 1.0, pb_a - 1.0)
                    r_max = pb_a + 1.0
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
            'Detalle_Alineacion': "; ".join(detalles_alineacion) if detalles_alineacion else "OK",
            'Detalle_Dual': "; ".join(detalles_dual) if detalles_dual else "OK",
            'Detalle_Cambio': "; ".join(detalles_cambio) if detalles_cambio else "OK",
            'Detalle_Rotacion_Irregular': "; ".join(detalles_rot_irregular) if detalles_rot_irregular else "OK",
            'Detalle_Rotacion_Escalonado': "; ".join(detalles_rot_escalonado) if detalles_rot_escalonado else "OK",
            'Detalle_Calibracion_PSI': "; ".join(detalles_calibracion) if detalles_calibracion else "OK",
            'Recomendaciones_Dual': "; ".join(recomendaciones_dual) if recomendaciones_dual else "OK"
        })
        
    return pd.DataFrame(resultados)

inicializar_bd()




def obtener_valores_unicos_campo(campo, filtro_cliente='', filtro_marca=''):
    validos = ['cliente', 'subcliente', 'tipo_operacion', 'marca', 'diseno', 'dimension', 'banda_reen', 'vida']
    if campo not in validos:
        return []
    with get_connection() as conn:
        cursor = conn.cursor()
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

        return [v for v in valores_insp if v and str(v).strip()]

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
                if nov and nov.lower() not in ['sin novedad', 'ninguna', 'ok', 'normal']:
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
        return dict(zip(cols, row))

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

# --- CONFIGURACIÓN DE LÍMITES POR CLIENTE, SUBCLIENTE Y EJE ---
def _construir_cache_limites_retiro(conn=None):
    """
    Carga en memoria todas las reglas de límites de retiro de configuracion_limites_retiro
    y configuracion_clientes en una sola lectura para resolver en O(1) eliminando consultas N+1.
    Retorna una función resolver_limite(cliente, subcliente='TODOS', eje='TODOS') -> float.
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

        cursor.execute("SELECT cliente, limite_retiro_mm FROM configuracion_clientes")
        mapa_clientes = {}
        for row in cursor.fetchall():
            cl = str(row[0] or '').strip().upper()
            lim = to_float(row[1], 3.0)
            mapa_clientes[cl] = lim

        def resolver_limite(cliente='', subcliente='TODOS', eje='TODOS'):
            if pd.isna(cliente) or cliente is None:
                return 3.0
            c_norm = str(cliente).strip().upper()
            if not c_norm or c_norm in ('NAN', 'NONE'):
                return 3.0
            sub_norm = str(subcliente or 'TODOS').strip().upper() or 'TODOS'
            e_norm = str(eje or 'TODOS').strip().upper() or 'TODOS'

            # 1. Búsqueda exacta: (cliente, subcliente, eje)
            if (c_norm, sub_norm, e_norm) in mapa_granular:
                return mapa_granular[(c_norm, sub_norm, e_norm)]

            # 2. cliente + subcliente + TODOS
            if e_norm != 'TODOS' and (c_norm, sub_norm, 'TODOS') in mapa_granular:
                return mapa_granular[(c_norm, sub_norm, 'TODOS')]

            # 3. cliente + TODOS + eje
            if sub_norm != 'TODOS' and (c_norm, 'TODOS', e_norm) in mapa_granular:
                return mapa_granular[(c_norm, 'TODOS', e_norm)]

            # 4. cliente + TODOS + TODOS
            if (c_norm, 'TODOS', 'TODOS') in mapa_granular:
                return mapa_granular[(c_norm, 'TODOS', 'TODOS')]

            # 5. Fallback a tabla legada configuracion_clientes
            if c_norm in mapa_clientes:
                return mapa_clientes[c_norm]

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
        if sub == 'TODOS' and e == 'TODOS':
            cursor.execute('''
                INSERT INTO configuracion_clientes (cliente, limite_retiro_mm, observaciones, fecha_actualizacion)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cliente) DO UPDATE SET
                    limite_retiro_mm = excluded.limite_retiro_mm,
                    observaciones = excluded.observaciones,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            ''', (c, lim, obs))
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

def obtener_lista_clientes_unicos():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT cliente FROM (
                SELECT cliente FROM inspecciones WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_limites_retiro WHERE cliente IS NOT NULL AND TRIM(cliente) != ''
                UNION
                SELECT cliente FROM configuracion_clientes
            ) ORDER BY cliente ASC
        ''')
        return [r[0] for r in cursor.fetchall()]

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

def actualizar_tipologia(nombre_antiguo, nombre_nuevo, descripcion='', cant_llantas=10, config_ejes=None):
    nom_a = (nombre_antiguo or '').strip().upper()
    nom_n = (nombre_nuevo or '').strip().upper()
    if not nom_a or not nom_n:
        return False
    cant = int(cant_llantas or 10)
    desc = str(descripcion or '').strip().upper()
    
    # Si especificó config_ejes, armar esquema
    esquema_nuevo = None
    if config_ejes:
        codigos = [c.strip().lower() for c in config_ejes.split(',') if c.strip()]
        if codigos:
            esquema_nuevo = []
            pos_act = 1
            for idx, c in enumerate(codigos):
                eje_num = idx + 1
                if c in ('dir', 'direccional', 'delantero'):
                    esquema_nuevo.append({
                        'eje': eje_num, 'nombre': f'Eje {eje_num} (Direccional)', 'tipo': 'direccional',
                        'posiciones': [{'pos': pos_act, 'lado': 'izq', 'rol': 'direccional', 'dual': False}, {'pos': pos_act+1, 'lado': 'der', 'rol': 'direccional', 'dual': False}]
                    })
                    pos_act += 2
                elif c in ('trac', 'traccion', 'tracción', 'dual'):
                    esquema_nuevo.append({
                        'eje': eje_num, 'nombre': f'Eje {eje_num} (Tracción)', 'tipo': 'traccion',
                        'posiciones': [
                            {'pos': pos_act, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_act+1},
                            {'pos': pos_act+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_act},
                            {'pos': pos_act+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_act+3},
                            {'pos': pos_act+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_act+2}
                        ]
                    })
                    pos_act += 4
                elif c in ('libre', 'arrastre', 'loco'):
                    esquema_nuevo.append({
                        'eje': eje_num, 'nombre': f'Eje {eje_num} (Libre / Arrastre)', 'tipo': 'libre',
                        'posiciones': [
                            {'pos': pos_act, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_act+1},
                            {'pos': pos_act+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_act},
                            {'pos': pos_act+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_act+3},
                            {'pos': pos_act+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_act+2}
                        ]
                    })
                    pos_act += 4
                elif c in ('remolque', 'trailer'):
                    esquema_nuevo.append({
                        'eje': eje_num, 'nombre': f'Eje {eje_num} (Trailer / Remolque)', 'tipo': 'remolque',
                        'posiciones': [
                            {'pos': pos_act, 'lado': 'izq', 'rol': 'ext', 'dual': True, 'par': pos_act+1},
                            {'pos': pos_act+1, 'lado': 'izq', 'rol': 'int', 'dual': True, 'par': pos_act},
                            {'pos': pos_act+2, 'lado': 'der', 'rol': 'int', 'dual': True, 'par': pos_act+3},
                            {'pos': pos_act+3, 'lado': 'der', 'rol': 'ext', 'dual': True, 'par': pos_act+2}
                        ]
                    })
                    pos_act += 4
                else:
                    esquema_nuevo.append({
                        'eje': eje_num, 'nombre': f'Eje {eje_num}', 'tipo': 'traccion',
                        'posiciones': [{'pos': pos_act, 'lado': 'izq', 'rol': 'sencillo', 'dual': False}, {'pos': pos_act+1, 'lado': 'der', 'rol': 'sencillo', 'dual': False}]
                    })
                    pos_act += 2

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT esquema_json FROM catalogo_tipologias WHERE UPPER(nombre) = ?', (nom_a,))
        row = cursor.fetchone()
        esquema_json = row[0] if row and row[0] else None
        cursor.execute('DELETE FROM catalogo_tipologias WHERE UPPER(nombre) = ?', (nom_a,))
        conn.commit()

    if esquema_nuevo:
        return guardar_tipologia(nom_n, desc, cant, esquema_custom=esquema_nuevo)
    elif esquema_json and nom_a == nom_n:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, ?, ?, ?)',
                           (nom_n, desc, cant, esquema_json))
            conn.commit()
        return True
    else:
        return guardar_tipologia(nom_n, desc, cant)

def eliminar_tipologia(nombre):
    nom = (nombre or '').strip().upper()
    if not nom:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM catalogo_tipologias WHERE UPPER(nombre) = ?', (nom,))
        conn.commit()
    return True

def obtener_catalogo_modelos():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion FROM catalogo_modelos_llantas ORDER BY tipo_llanta ASC, marca ASC, diseno ASC')
        cols = ['id', 'tipo_llanta', 'marca', 'diseno', 'dimension', 'prof_inicial', 'descripcion']
        return [dict(zip(cols, r)) for r in cursor.fetchall()]

def buscar_profundidad_inicial(marca, diseno, dimension='', vida='Original'):
    m = (marca or '').strip().lower()
    d = (diseno or '').strip().lower()
    dim = (dimension or '').strip().lower()
    tipo = 'Reencauche' if str(vida).strip().lower() == 'reencauche' else 'Nueva'
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) AND LOWER(dimension) = LOWER(?) LIMIT 1', (tipo, m, d, dim))
        r = cursor.fetchone()
        if r:
            return r[0]
        cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(marca) = LOWER(?) AND LOWER(diseno) = LOWER(?) LIMIT 1', (tipo, m, d))
        r = cursor.fetchone()
        if r:
            return r[0]
        cursor.execute('SELECT prof_inicial FROM catalogo_modelos_llantas WHERE LOWER(tipo_llanta) = LOWER(?) AND LOWER(diseno) = LOWER(?) LIMIT 1', (tipo, d))
        r = cursor.fetchone()
        if r:
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
    with get_connection() as conn:
        query = """
            SELECT id, fecha, placa, posicion, kilometraje, numero_interno,
                   marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int,
                   prof_inicial, km_montaje, precio, cliente, subcliente, tipo_operacion
            FROM inspecciones
            WHERE numero_interno IS NOT NULL AND TRIM(numero_interno) != ''
        """
        params = []
        if numero_interno and str(numero_interno).strip():
            query += " AND UPPER(TRIM(numero_interno)) LIKE UPPER(TRIM(?))"
            params.append(f"%{str(numero_interno).strip()}%")
        
        for k_campo in ['cliente', 'subcliente', 'tipo_operacion', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen']:
            v_val = filtros.get(k_campo)
            if v_val and str(v_val).strip() and str(v_val).strip() != 'Todos':
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

    # Filtrar por usuario si es inspector y no es admin
    usuario_filtro = filtros.get('usuario')
    if usuario_filtro:
        usr_info = obtener_usuario_por_username(usuario_filtro)
        if usr_info and usr_info.get('rol') != 'admin':
            cli_asig = usr_info.get('cliente_asignado')
            clis = parsear_clientes_asignados(cli_asig)
            if clis:
                clis_lower = [c.lower() for c in clis]
                resultados = [r for r in resultados if str(r.get('cliente') or '').strip().lower() in clis_lower]
            else:
                resultados = [r for r in resultados if str(r.get('usuario_registro') or '').strip().lower() == str(usuario_filtro).strip().lower()]

    return resultados

# ==========================================
# GESTIÓN Y AUTENTICACIÓN DE USUARIOS
# ==========================================

def parsear_clientes_asignados(cliente_asignado) -> list:
    """Convierte el string de cliente_asignado (uno o varios separados por comas) en lista limpia."""
    if not cliente_asignado:
        return []
    return [c.strip() for c in str(cliente_asignado).split(',') if c.strip()]

def parsear_vistas_permitidas(vistas, rol='inspector') -> list:
    """
    Retorna la lista de vistas autorizadas.
    REGLA: Solo el admin puede acceder a 'basedatos'.
    Los inspectores pueden acceder a 'patio', 'diagnostico', 'kpis' y 'catalogos' (en modo consulta).
    """
    if str(rol).strip().lower() == 'admin':
        return ['patio', 'basedatos', 'diagnostico', 'kpis', 'catalogos']
    if not vistas:
        return ['patio', 'diagnostico', 'kpis', 'catalogos']
    raw = [v.strip().lower() for v in str(vistas).split(',') if v.strip()]
    # Filtrar estrictamente: inspectores nunca pueden acceder a basedatos
    permitidas = [v for v in raw if v in ('patio', 'diagnostico', 'kpis', 'catalogos')]
    return permitidas if permitidas else ['patio']

def autenticar_usuario(username, password):
    u = (username or '').strip()
    p = (password or '').strip()
    if not u or not p:
        return None
    with get_connection() as conn:
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
            d['vistas_permitidas'] = parsear_vistas_permitidas(d.get('vistas_permitidas'), d.get('rol'))
            filas.append(d)
        return filas

def crear_usuario(username, password, nombre_completo, rol='inspector', cliente_asignado='', vistas_permitidas=None):
    u = (username or '').strip().lower()
    p = (password or '').strip()
    nom = (nombre_completo or '').strip()
    r = (rol or 'inspector').strip().lower()
    cli = (cliente_asignado or '').strip()
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
            params.append(cliente_asignado.strip())
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

