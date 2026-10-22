# -*- coding: utf-8 -*-
"""
Módulo de Gestión de las 7 Bodegas, Taller en Patio y Hoja de Vida de Neumáticos (Life Sheet).
Implementación según especificación: docs/prompt_antigravity_ide_implementaci_n_de_las_7_bodegas_y_hoja_de_vida_de_neum_ticos.md
"""

import os
import math
from datetime import datetime, date
import pytz

BOGOTA_TZ = pytz.timezone('America/Bogota')

# Mapeo canónico de nombres de bodega y alias
MAP_ESTADOS_CANONICOS = {
    'bodega_1_nuevas': 'Bodega_1_Nuevas',
    'b1': 'Bodega_1_Nuevas',
    'nuevas': 'Bodega_1_Nuevas',
    'bodega_2_reutilizable': 'Bodega_2_Reutilizable',
    'b2': 'Bodega_2_Reutilizable',
    'reutilizable': 'Bodega_2_Reutilizable',
    'recambio': 'Bodega_2_Reutilizable',
    'bodega_3_reencauche': 'Bodega_3_Reencauche',
    'b3': 'Bodega_3_Reencauche',
    'reencauche': 'Bodega_3_Reencauche',
    'bodega_4_enplanta': 'Bodega_4_EnPlanta',
    'b4': 'Bodega_4_EnPlanta',
    'planta': 'Bodega_4_EnPlanta',
    'en_planta': 'Bodega_4_EnPlanta',
    'bodega_5_reparacion': 'Bodega_5_Reparacion',
    'b5': 'Bodega_5_Reparacion',
    'reparacion': 'Bodega_5_Reparacion',
    'bodega_6_garantia': 'Bodega_6_Garantia',
    'b6': 'Bodega_6_Garantia',
    'garantia': 'Bodega_6_Garantia',
    'bodega_7_fvu': 'Bodega_7_FVU',
    'b7': 'Bodega_7_FVU',
    'fvu': 'Bodega_7_FVU',
    'chatarra': 'Bodega_7_FVU',
    'montada': 'Montada',
    'montada_operacion': 'Montada'
}

def normalizar_estado_bodega(valor: str) -> str:
    if not valor:
        return 'Bodega_1_Nuevas'
    v_clean = str(valor).strip().lower().replace(' ', '_')
    return MAP_ESTADOS_CANONICOS.get(v_clean, str(valor).strip())


def sincronizar_hoja_vida_desde_inspecciones(conn=None):
    """
    Backfill automático: Garantiza que todas las llantas inspeccionadas
    tengan registro en llantas_maestro, llantas_ciclos, llantas_movimientos y novedades.
    """
    import database
    def _ejecutar(c):
        c.execute("""
            SELECT cliente, numero_interno, placa, posicion, tipologia, marca, diseno, dimension,
                   vida, banda_reen, prof_ext, prof_cent, prof_int, psi, kilometraje, km_montaje,
                   precio, prof_inicial, subcliente, novedades, fecha, id
            FROM inspecciones
            WHERE numero_interno IS NOT NULL AND TRIM(numero_interno) != ''
              AND UPPER(TRIM(numero_interno)) != 'SN'
              AND cliente IS NOT NULL AND TRIM(cliente) != ''
            ORDER BY fecha ASC, id ASC
        """)
        filas = c.fetchall()
        if not filas:
            return

        for r in filas:
            cli = str(r[0]).strip().upper()
            serial = str(r[1]).strip().upper()
            placa = str(r[2] or '').strip().upper()
            pos = database.to_int(r[3], 0)
            marca = str(r[5] or '').strip().upper()
            diseno = str(r[6] or '').strip().upper()
            dim = str(r[7] or '295/80R22.5').strip().upper()
            vida = str(r[8] or 'Original').strip()
            banda = str(r[9] or '').strip().upper()
            pe = database.to_float(r[10])
            pc = database.to_float(r[11])
            pi = database.to_float(r[12])
            psi = database.to_float(r[13], 100.0)
            km_act = database.to_float(r[14])
            km_mont = database.to_float(r[15])
            pr = database.to_float(r[16], 1450000.0)
            p_ini = database.to_float(r[17], 16.0)
            subc = str(r[18] or 'Principal').strip()
            nov = str(r[19] or '').strip()
            fecha_i = str(r[20] or '')[:10]

            pos_vals = [x for x in (pe, pc, pi) if x > 0]
            p_min = min(pos_vals) if pos_vals else p_ini

            # Verificar si existe en llantas_maestro
            c.execute("SELECT id, estado_actual, ciclo_actual FROM llantas_maestro WHERE UPPER(cliente_propietario) = ? AND UPPER(numero_interno) = ?", (cli, serial))
            row_m = c.fetchone()

            es_reenc = 'REENC' in vida.upper() or 'R' in vida.upper()
            num_ciclo = 2 if es_reenc else 1

            if not row_m:
                c.execute("""
                    INSERT INTO llantas_maestro (
                        numero_interno, cliente_propietario, subcliente_sede, cliente, subcliente,
                        marca_origen, diseno_origen, marca, diseno, dimension,
                        precio_compra_inicial, prof_inicial_nueva, prof_inicial,
                        prof_ext, prof_cent, prof_int, prof_actual_min, psi_actual,
                        estado_actual, ubicacion_bodega, placa_actual, posicion_actual,
                        ciclo_actual, vida_actual, banda_reen, km_montaje_actual, km_actual_vehiculo,
                        km_acumulados_total, costo_compra_original, costo_ciclo_actual, costo_acumulado_total,
                        fecha_alta, fecha_ultimo_movimiento
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        'Montada', 'MONTADA_OPERACION', ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?
                    )
                """, (
                    serial, cli, subc, cli, subc,
                    marca, diseno, marca, diseno, dim,
                    pr, p_ini, p_ini,
                    pe, pc, pi, p_min, psi,
                    placa, pos,
                    num_ciclo, vida, banda, km_mont, km_act,
                    km_act, pr, pr, pr,
                    fecha_i, fecha_i
                ))
                # Ciclo inicial
                c.execute("""
                    INSERT INTO llantas_ciclos (
                        numero_interno, cliente_propietario, numero_ciclo, tipo_ciclo,
                        proveedor_banda, diseno_banda, prof_inicial_ciclo, prof_final_ciclo,
                        km_inicial_ciclo, km_recorridos_ciclo, costo_ciclo, estado_ciclo, fecha_inicio_ciclo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, 'En_Servicio', ?)
                """, (
                    serial, cli, num_ciclo, 'Original' if num_ciclo == 1 else 'Reencauche 1',
                    'Fábrica' if num_ciclo == 1 else (banda or 'Renovadora'),
                    diseno if num_ciclo == 1 else (banda or 'Banda Reencauche'),
                    p_ini, p_min, km_act, pr, fecha_i
                ))
                # Movimiento inicial MONTAJE
                c.execute("""
                    INSERT INTO llantas_movimientos (
                        fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                        bodega_origen, bodega_destino, placa_destino, posicion_destino,
                        odometro_vehiculo, profundidad_momento, psi_momento, costo_asociado,
                        motivo, usuario_responsable
                    ) VALUES (?, ?, ?, 'MONTAJE', 'EXTERNO', 'Montada', ?, ?, ?, ?, ?, ?, 'Inspección inicial en patio', 'sistema')
                """, (
                    fecha_i, serial, cli, placa, pos, km_act, p_min, psi, pr
                ))
            else:
                # Si ya existe y está Montada, actualizar odómetro y profundidades
                c.execute("""
                    UPDATE llantas_maestro SET
                        prof_actual_min = ?,
                        prof_ext = ?,
                        prof_cent = ?,
                        prof_int = ?,
                        psi_actual = ?,
                        km_actual_vehiculo = ?,
                        km_acumulados_total = MAX(km_acumulados_total, ?),
                        fecha_ultimo_movimiento = ?
                    WHERE id = ? AND estado_actual = 'Montada'
                """, (p_min, pe, pc, pi, psi, km_act, km_act, fecha_i, row_m[0]))

            # Novedades si existen
            if nov and nov.upper() not in ('OK', 'NORMAL', 'NINGUNA', 'NAN', ''):
                c.execute("""
                    INSERT INTO llantas_novedades_registro (
                        fecha_deteccion, numero_interno, cliente_propietario, tipo_novedad,
                        categoria_severidad, estado_novedad, placa, posicion, observacion
                    ) VALUES (?, ?, ?, ?, 'Operativa', 'Activa', ?, ?, ?)
                """, (
                    fecha_i, serial, cli, nov, placa, pos, f"Detectado en inspección fecha {fecha_i}"
                ))

    if conn is not None:
        _ejecutar(conn)
    else:
        with database.get_connection() as c:
            _ejecutar(c)
            c.commit()


# =============================================================================
# FLUJOS OPERATIVOS (1 a 9)
# =============================================================================

def crear_llantas_stock(datos: dict) -> dict:
    """
    Flujo 1 — Ingreso de Llantas Nuevas Individual o en Lote.
    """
    import database
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    subcliente = str(datos.get('subcliente_sede') or datos.get('subcliente', 'Principal')).strip()
    modo = str(datos.get('modo', 'individual')).strip().lower()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    if not cliente:
        return {"ok": False, "status": "error", "mensaje": "El cliente propietario es obligatorio"}

    marca = str(datos.get('marca_origen') or datos.get('marca', '')).strip().upper()
    diseno = str(datos.get('diseno_origen') or datos.get('diseno', '')).strip().upper()
    dimension = str(datos.get('dimension', '295/80R22.5')).strip().upper()
    tipo_construccion = str(datos.get('tipo_construccion', 'Radial')).strip()
    precio_compra = database.to_float(datos.get('precio_compra_inicial') or datos.get('precio_compra', 1450000.0), 1450000.0)
    prof_ini = database.to_float(datos.get('prof_inicial_nueva') or datos.get('prof_inicial', 16.0), 16.0)
    proveedor = str(datos.get('proveedor_factura') or datos.get('proveedor', '')).strip()
    dot_base = str(datos.get('numero_serie_dot') or datos.get('dot', '')).strip().upper()

    numeros_a_crear = []
    if modo == 'lote':
        prefijo = str(datos.get('prefijo', 'LL-')).strip()
        num_ini = database.to_int(datos.get('numero_inicial', 1000))
        cantidad = database.to_int(datos.get('cantidad', 1))
        if cantidad <= 0 or cantidad > 200:
            return {"ok": False, "status": "error", "mensaje": "La cantidad de llantas en lote debe ser entre 1 y 200"}
        for i in range(cantidad):
            numeros_a_crear.append(f"{prefijo}{num_ini + i}")
    else:
        num = str(datos.get('numero_interno', '')).strip().upper()
        if not num:
            return {"ok": False, "status": "error", "mensaje": "El número interno es obligatorio en modo individual"}
        numeros_a_crear.append(num)

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    with database.get_connection() as conn:
        cursor = conn.cursor()
        # Validar existencia previa de cualquiera
        for n in numeros_a_crear:
            cursor.execute("""
                SELECT id FROM llantas_maestro 
                WHERE (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ?) AND UPPER(numero_interno) = ?
            """, (cliente, cliente, n))
            if cursor.fetchone():
                return {"ok": False, "status": "error", "mensaje": f"La llanta {n} ya existe en el inventario de {cliente}"}

        creadas = []
        for n in numeros_a_crear:
            cursor.execute("""
                INSERT INTO llantas_maestro (
                    numero_interno, numero_serie_dot, marca_origen, diseno_origen, dimension,
                    tipo_construccion, precio_compra_inicial, prof_inicial_nueva, proveedor_factura,
                    estado_actual, prof_actual_min, psi_actual, ciclo_actual, km_acumulados_total,
                    costo_reencauches_total, costo_reparaciones_total, cpk_acumulado_global,
                    cliente_propietario, subcliente_sede, fecha_alta, fecha_ultimo_movimiento,
                    cliente, subcliente, marca, diseno, prof_inicial, prof_ext, prof_cent, prof_int,
                    ubicacion_bodega, vida_actual, costo_compra_original, costo_ciclo_actual, costo_acumulado_total,
                    proveedor_actual
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    'Bodega_1_Nuevas', ?, 100.0, 1, 0.0,
                    0.0, 0.0, 0.0,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    'BODEGA_1_NUEVAS', 'Original', ?, ?, ?,
                    ?
                )
            """, (
                n, dot_base, marca, diseno, dimension,
                tipo_construccion, precio_compra, prof_ini, proveedor,
                prof_ini,
                cliente, subcliente, hoy_str, hoy_str,
                cliente, subcliente, marca, diseno, prof_ini, prof_ini, prof_ini, prof_ini,
                precio_compra, precio_compra, precio_compra,
                proveedor
            ))
            # Ciclo 1 Original
            cursor.execute("""
                INSERT INTO llantas_ciclos (
                    numero_interno, cliente_propietario, numero_ciclo, tipo_ciclo,
                    proveedor_banda, diseno_banda, prof_inicial_ciclo, prof_final_ciclo,
                    km_inicial_ciclo, km_recorridos_ciclo, costo_ciclo, cpk_ciclo,
                    fecha_inicio_ciclo, estado_ciclo
                ) VALUES (?, ?, 1, 'Original', 'Fábrica Original', 'Banda Original Fábrica', ?, NULL, 0.0, 0.0, ?, 0.0, ?, 'En_Servicio')
            """, (n, cliente, prof_ini, precio_compra, hoy_str))

            # Movimiento COMPRA_INGRESO
            cursor.execute("""
                INSERT INTO llantas_movimientos (
                    fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                    bodega_origen, bodega_destino, profundidad_momento, psi_momento, costo_asociado,
                    motivo, usuario_responsable
                ) VALUES (?, ?, ?, 'COMPRA_INGRESO', 'EXTERNO', 'Bodega_1_Nuevas', ?, 100.0, ?, 'Ingreso de llantas nuevas al inventario', ?)
            """, (hoy_ts, n, cliente, prof_ini, precio_compra, user))

            # Kardex compatible
            cursor.execute("""
                INSERT INTO kardex_movimientos_llanta (
                    fecha_movimiento, cliente, subcliente, numero_interno, bodega_origen, bodega_destino,
                    tipo_movimiento, vida_ciclo, prof_min_mm, costo_asociado, proveedor, causal_o_motivo, usuario_registro
                ) VALUES (?, ?, ?, ?, 'EXTERNO', 'BODEGA_1_NUEVAS', 'ALTA_NUEVA', 'Original', ?, ?, ?, 'Ingreso al inventario', ?)
            """, (hoy_str, cliente, subcliente, n, prof_ini, precio_compra, proveedor, user))

            creadas.append(n)

        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "message": f"{len(creadas)} llantas ingresadas exitosamente en Bodega 1 Nuevas",
        "cantidad": len(creadas),
        "llantas": creadas
    }


def desmontar_llanta_taller(datos: dict) -> dict:
    """
    Flujo 2 — Desmonte Directo desde Inspección de Patio o Taller hacia Bodega.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    raw_destino = str(datos.get('bodega_destino', 'reutilizable')).strip()
    bodega_destino = normalizar_estado_bodega(raw_destino)
    odometro = database.to_float(datos.get('odometro_vehiculo') or datos.get('kilometraje', 0.0))
    user = str(datos.get('usuario_responsable', 'admin')).strip()
    motivo = str(datos.get('motivo', 'Desmonte en taller / patio')).strip()

    if not numero_interno:
        return {"ok": False, "status": "error", "message": "El número interno es obligatorio"}

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, estado_actual, placa_actual, posicion_actual, km_montaje_actual,
                   km_acumulados_total, prof_actual_min, ciclo_actual, cliente_propietario, cliente,
                   costo_ciclo_actual, prof_inicial_nueva, valor_reconocido_garantia
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"La llanta {numero_interno} no se encuentra en el inventario"}

        ll_id, est_act, placa_act, pos_act, km_mont, km_acum, prof_min_act, ciclo_act, cli_prop, cli_old, c_ciclo, p_ini, val_gar = row
        cli_efectivo = cli_prop or cli_old or cliente

        # Profundidad suministrada o actual
        prof_momento = database.to_float(datos.get('profundidad') or datos.get('prof_min_mm', prof_min_act), prof_min_act)
        psi_momento = database.to_float(datos.get('psi', 100.0), 100.0)

        delta_km = 0.0
        if est_act == 'Montada' and odometro > 0 and km_mont > 0:
            delta_km = max(0.0, odometro - km_mont)

        nuevo_km_acum = (km_acum or 0.0) + delta_km

        # Actualizar ciclo activo de llantas_ciclos
        cursor.execute("""
            UPDATE llantas_ciclos SET
                km_recorridos_ciclo = km_recorridos_ciclo + ?,
                prof_final_ciclo = ?
            WHERE numero_interno = ? AND numero_ciclo = ?
        """, (delta_km, prof_momento, numero_interno, ciclo_act))

        # Variables FVU
        mm_desp = 0.0
        dinero_perd = 0.0
        if bodega_destino == 'Bodega_7_FVU':
            cfg = database.obtener_configuracion_avanzada_cliente(cli_efectivo)
            lim_ret = database.to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
            if prof_momento > lim_ret:
                mm_desp = max(0.0, prof_momento - lim_ret)
                denominador = max(1.0, (p_ini or 16.0) - lim_ret)
                costo_base = c_ciclo or 1450000.0
                dinero_perd = max(0.0, (mm_desp * (costo_base / denominador)) - (val_gar or 0.0))

            cursor.execute("""
                UPDATE llantas_ciclos SET
                    estado_ciclo = 'Desechado',
                    fecha_fin_ciclo = CURRENT_DATE,
                    prof_final_ciclo = ?
                WHERE numero_interno = ? AND numero_ciclo = ?
            """, (prof_momento, numero_interno, ciclo_act))

        hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
        hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

        # Mapeo a ubicacion_bodega para compatibilidad
        map_ubi = {
            'Bodega_1_Nuevas': 'BODEGA_1_NUEVAS',
            'Bodega_2_Reutilizable': 'BODEGA_2_RECAMBIO',
            'Bodega_3_Reencauche': 'BODEGA_3_REENCAUCHE',
            'Bodega_4_EnPlanta': 'BODEGA_3_REENCAUCHE',
            'Bodega_5_Reparacion': 'BODEGA_5_REPARACION',
            'Bodega_6_Garantia': 'BODEGA_6_FVU',
            'Bodega_7_FVU': 'BODEGA_6_FVU',
            'Montada': 'MONTADA_OPERACION'
        }
        ubi_compat = map_ubi.get(bodega_destino, 'BODEGA_2_RECAMBIO')

        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = ?,
                ubicacion_bodega = ?,
                placa_actual = NULL,
                posicion_actual = 0,
                prof_actual_min = ?,
                prof_ext = ?,
                prof_cent = ?,
                prof_int = ?,
                psi_actual = ?,
                km_acumulados_total = ?,
                fecha_ultimo_movimiento = ?,
                mm_desperdiciados_fvu = CASE WHEN ? = 'Bodega_7_FVU' THEN ? ELSE mm_desperdiciados_fvu END,
                dinero_perdido_fvu = CASE WHEN ? = 'Bodega_7_FVU' THEN ? ELSE dinero_perdido_fvu END,
                fecha_baja = CASE WHEN ? = 'Bodega_7_FVU' THEN ? ELSE fecha_baja END,
                motivo_baja = CASE WHEN ? = 'Bodega_7_FVU' THEN ? ELSE motivo_baja END
            WHERE id = ?
        """, (
            bodega_destino, ubi_compat, prof_momento, prof_momento, prof_momento, prof_momento, psi_momento,
            nuevo_km_acum, hoy_str,
            bodega_destino, mm_desp,
            bodega_destino, dinero_perd,
            bodega_destino, hoy_str,
            bodega_destino, motivo,
            ll_id
        ))

        # Insertar movimiento DESMONTE
        cursor.execute("""
            INSERT INTO llantas_movimientos (
                fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                bodega_origen, bodega_destino, placa_origen, posicion_origen,
                odometro_vehiculo, profundidad_momento, psi_momento, motivo, usuario_responsable
            ) VALUES (?, ?, ?, 'DESMONTE', 'Montada', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hoy_ts, numero_interno, cli_efectivo, bodega_destino,
            placa_act, pos_act, odometro, prof_momento, psi_momento, motivo, user
        ))

        # Kardex compatible
        cursor.execute("""
            INSERT INTO kardex_movimientos_llanta (
                fecha_movimiento, cliente, subcliente, numero_interno,
                bodega_origen, bodega_destino, tipo_movimiento,
                placa, posicion, prof_min_mm, km_vehiculo, causal_o_motivo, usuario_registro
            ) VALUES (?, ?, 'Principal', ?, 'MONTADA_OPERACION', ?, 'DESMONTE_RECAMBIO', ?, ?, ?, ?, ?, ?)
        """, (
            hoy_str, cli_efectivo, numero_interno, ubi_compat, placa_act, pos_act, prof_momento, odometro, motivo, user
        ))

        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "message": f"Llanta {numero_interno} desmontada hacia {bodega_destino}",
        "bodega_nombre": bodega_destino,
        "delta_km": delta_km
    }


def montar_llanta_taller(datos: dict) -> dict:
    """
    Flujo 3 — Montaje Directo en Patio desde Stock o Nueva Directa.
    """
    import database
    placa = str(datos.get('placa', '')).strip().upper()
    posicion = database.to_int(datos.get('posicion', 0))
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    odometro = database.to_float(datos.get('odometro_vehiculo') or datos.get('kilometraje', 0.0))
    user = str(datos.get('usuario_responsable', 'admin')).strip()
    motivo = str(datos.get('motivo', 'Montaje en patio')).strip()

    if not placa or posicion <= 0:
        return {"ok": False, "status": "error", "message": "Placa y posición válida (>= 1) son obligatorias para montaje"}

    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    es_nueva_directa = bool(datos.get('nueva_directa', False))

    with database.get_connection() as conn:
        cursor = conn.cursor()

        # Si es nueva directa o no existe en llantas_maestro, dar de alta primero
        cursor.execute("SELECT id FROM llantas_maestro WHERE UPPER(numero_interno) = ?", (numero_interno,))
        row_check = cursor.fetchone()
        if not row_check or es_nueva_directa:
            if not row_check:
                res_alta = crear_llantas_stock({
                    "cliente_propietario": cliente or "CLIENTE GENERAL",
                    "modo": "individual",
                    "numero_interno": numero_interno,
                    "marca_origen": str(datos.get('marca', 'MICHELIN')).strip().upper(),
                    "diseno_origen": str(datos.get('diseno', 'X-LINE')).strip().upper(),
                    "dimension": str(datos.get('dimension', '295/80R22.5')).strip().upper(),
                    "precio_compra_inicial": database.to_float(datos.get('precio_compra', 1450000.0), 1450000.0),
                    "prof_inicial_nueva": database.to_float(datos.get('prof_inicial', 16.0), 16.0),
                    "usuario_responsable": user
                })
                if not res_alta.get('ok'):
                    return res_alta

        cursor.execute("""
            SELECT id, estado_actual, ciclo_actual, marca_origen, diseno_origen, dimension,
                   prof_inicial_nueva, prof_actual_min, vida_actual, cliente_propietario, cliente
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ?
        """, (numero_interno,))
        row_ll = cursor.fetchone()
        if not row_ll:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}

        ll_id, est_act, ciclo_act, marca_o, diseno_o, dim, p_ini, p_act, vida_act, cli_prop, cli_old = row_ll
        cli_efectivo = cli_prop or cli_old or cliente or "CLIENTE GENERAL"

        # Candado Direccional: Si es eje direccional y ciclo_actual > 1 (o reencauche), rechazar
        perfil_v = database.obtener_perfil_vehiculo(placa)
        tipologia_v = perfil_v.get('tipologia', '') if perfil_v else ''
        if database.es_posicion_direccional(tipologia_v, posicion):
            if (ciclo_act and ciclo_act > 1) or (vida_act and vida_act.upper() != 'ORIGINAL'):
                return {
                    "ok": False,
                    "status": "error",
                    "message": "⛔ CANDADO VIAL: En eje direccional solo se permite condición Original (prohibido llantas reencauchadas)."
                }

        # Desmonte automático de ocupante previa en la misma posición
        cursor.execute("""
            SELECT id, numero_interno, prof_actual_min, km_montaje_actual, km_acumulados_total, ciclo_actual
            FROM llantas_maestro
            WHERE UPPER(placa_actual) = ? AND posicion_actual = ? AND UPPER(numero_interno) != ?
              AND estado_actual = 'Montada'
        """, (placa, posicion, numero_interno))
        ocupantes = cursor.fetchall()

        hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
        hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

        for oc_id, oc_serial, oc_prof, oc_km_mont, oc_km_acum, oc_ciclo in ocupantes:
            delta_oc = max(0.0, odometro - (oc_km_mont or 0.0)) if odometro > 0 and oc_km_mont else 0.0
            cursor.execute("""
                UPDATE llantas_maestro SET
                    estado_actual = 'Bodega_2_Reutilizable',
                    ubicacion_bodega = 'BODEGA_2_RECAMBIO',
                    placa_actual = NULL,
                    posicion_actual = 0,
                    km_acumulados_total = km_acumulados_total + ?,
                    fecha_ultimo_movimiento = ?
                WHERE id = ?
            """, (delta_oc, hoy_str, oc_id))
            cursor.execute("""
                UPDATE llantas_ciclos SET km_recorridos_ciclo = km_recorridos_ciclo + ?
                WHERE numero_interno = ? AND numero_ciclo = ?
            """, (delta_oc, oc_serial, oc_ciclo))
            cursor.execute("""
                INSERT INTO llantas_movimientos (
                    fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                    bodega_origen, bodega_destino, placa_origen, posicion_origen,
                    odometro_vehiculo, profundidad_momento, motivo, usuario_responsable
                ) VALUES (?, ?, ?, 'DESMONTE', 'Montada', 'Bodega_2_Reutilizable', ?, ?, ?, ?, ?, ?)
            """, (hoy_ts, oc_serial, cli_efectivo, placa, posicion, odometro, oc_prof, f"Desmonte automático por montaje de {numero_interno}", user))

        # Montar llanta entrante
        bodega_previa = est_act or 'Bodega_1_Nuevas'
        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = 'Montada',
                ubicacion_bodega = 'MONTADA_OPERACION',
                placa_actual = ?,
                posicion_actual = ?,
                km_montaje_actual = ?,
                km_actual_vehiculo = ?,
                cliente_propietario = ?,
                cliente = ?,
                fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (placa, posicion, odometro, odometro, cli_efectivo, cli_efectivo, hoy_str, ll_id))

        cursor.execute("""
            INSERT INTO llantas_movimientos (
                fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                bodega_origen, bodega_destino, placa_destino, posicion_destino,
                odometro_vehiculo, profundidad_momento, motivo, usuario_responsable
            ) VALUES (?, ?, ?, 'MONTAJE', ?, 'Montada', ?, ?, ?, ?, ?, ?)
        """, (hoy_ts, numero_interno, cli_efectivo, bodega_previa, placa, posicion, odometro, p_act, motivo, user))

        # Kardex
        cursor.execute("""
            INSERT INTO kardex_movimientos_llanta (
                fecha_movimiento, cliente, subcliente, numero_interno,
                bodega_origen, bodega_destino, tipo_movimiento,
                placa, posicion, prof_min_mm, km_vehiculo, causal_o_motivo, usuario_registro
            ) VALUES (?, ?, 'Principal', ?, 'BODEGA_1_NUEVAS', 'MONTADA_OPERACION', 'MONTAJE', ?, ?, ?, ?, ?, ?)
        """, (hoy_str, cli_efectivo, numero_interno, placa, posicion, p_act, odometro, motivo, user))

        conn.commit()

    vida_desc = "ORIGINAL" if (ciclo_act == 1) else f"R{ciclo_act - 1}"
    return {
        "ok": True,
        "status": "ok",
        "message": f"Llanta {numero_interno} montada en {placa} posición {posicion}",
        "llanta": {
            "numero_interno": numero_interno,
            "marca": marca_o,
            "diseno": diseno_o,
            "dimension": dim,
            "vida": vida_desc,
            "prof_inicial": p_ini,
            "profundidad_actual": p_act
        }
    }


def despachar_lote_planta_reencauche(datos: dict) -> dict:
    """
    Flujo 4 — Despacho en Lote a Planta de Reencauche (Bodega 3 -> Bodega 4).
    """
    import database
    numeros = datos.get('numeros_internos') or datos.get('llantas_ids') or datos.get('llantas') or datos.get('numero_interno') or []
    if isinstance(numeros, (str, int)):
        numeros = [n.strip().upper() for n in str(numeros).split(',') if n.strip()]
    numeros = [str(n).strip().upper() for n in numeros if str(n).strip()]

    if not numeros:
        return {"ok": False, "status": "error", "mensaje": "Debe especificar al menos un número interno para despachar"}

    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    proveedor = str(datos.get('proveedor_planta', 'Renovadora Autorizada')).strip()
    guia = str(datos.get('guia_remision', f"GUIA-{datetime.now(BOGOTA_TZ).strftime('%Y%m%d%H%M')}")).strip()
    transportador = str(datos.get('transportador', '')).strip()
    compromiso = str(datos.get('fecha_compromiso', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    despachadas = []
    with database.get_connection() as conn:
        cursor = conn.cursor()
        for num in numeros:
            cursor.execute("""
                UPDATE llantas_maestro SET
                    estado_actual = 'Bodega_4_EnPlanta',
                    ubicacion_bodega = 'BODEGA_3_REENCAUCHE',
                    proveedor_planta = ?,
                    guia_remision_planta = ?,
                    transportador_planta = ?,
                    fecha_envio_planta = ?,
                    fecha_compromiso_planta = ?,
                    fecha_ultimo_movimiento = ?
                WHERE UPPER(numero_interno) = ?
            """, (proveedor, guia, transportador, hoy_str, compromiso, hoy_str, num))

            cursor.execute("""
                INSERT INTO llantas_movimientos (
                    fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                    bodega_origen, bodega_destino, motivo, usuario_responsable
                ) VALUES (?, ?, ?, 'ENVIO_REENCAUCHE', 'Bodega_3_Reencauche', 'Bodega_4_EnPlanta', ?, ?)
            """, (hoy_ts, num, cliente, f"Despacho con Guía {guia} a {proveedor}", user))

            cursor.execute("""
                INSERT INTO kardex_movimientos_llanta (
                    fecha_movimiento, cliente, subcliente, numero_interno,
                    bodega_origen, bodega_destino, tipo_movimiento,
                    causal_o_motivo, documento_soporte, proveedor, usuario_registro
                ) VALUES (?, ?, 'Principal', ?, 'BODEGA_2_RECAMBIO', 'BODEGA_3_REENCAUCHE', 'ENVIO_REENCAUCHE', ?, ?, ?, ?)
            """, (hoy_str, cliente, num, f"Despacho con Guía {guia}", guia, proveedor, user))

            despachadas.append(num)
        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "despachadas": len(despachadas),
        "guia": guia,
        "message": f"{len(despachadas)} carcasas despachadas a planta con guía {guia}"
    }


def recepcionar_llanta_reencauchada(datos: dict) -> dict:
    """
    Flujo 5 — Recepción desde Planta y Apertura de Nuevo Ciclo (Bodega 4 -> Bodega 2).
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    banda_prov = str(datos.get('proveedor_banda', 'Bandag')).strip()
    banda_diseno = str(datos.get('diseno_banda', 'BDL')).strip().upper()
    prof_nueva = database.to_float(datos.get('prof_banda_nueva', 17.0), 17.0)
    costo_renovado = database.to_float(datos.get('costo_factura_renovado', 720000.0), 720000.0)
    factura = str(datos.get('factura_renovado', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ciclo_actual, costo_reencauches_total, costo_acumulado_total, cliente_propietario, cliente
            FROM llantas_maestro WHERE UPPER(numero_interno) = ?
        """, (numero_interno,))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}

        ll_id, ciclo_ant, costo_reen_tot, costo_acum, cli_prop, cli_old = row
        cli_efectivo = cli_prop or cli_old or cliente
        ciclo_ant = ciclo_ant or 1
        ciclo_nuevo = ciclo_ant + 1

        # Cerrar ciclo anterior en llantas_ciclos
        cursor.execute("""
            UPDATE llantas_ciclos SET
                estado_ciclo = 'Cerrado_Por_Retiro',
                fecha_fin_ciclo = ?,
                cpk_ciclo = costo_ciclo / MAX(1.0, km_recorridos_ciclo)
            WHERE numero_interno = ? AND numero_ciclo = ?
        """, (hoy_str, numero_interno, ciclo_ant))

        # Crear nuevo ciclo
        cursor.execute("""
            INSERT INTO llantas_ciclos (
                numero_interno, cliente_propietario, numero_ciclo, tipo_ciclo,
                proveedor_banda, diseno_banda, prof_inicial_ciclo, prof_final_ciclo,
                km_inicial_ciclo, km_recorridos_ciclo, costo_ciclo, cpk_ciclo,
                factura_renovado, fecha_inicio_ciclo, estado_ciclo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0.0, 0.0, ?, 0.0, ?, ?, 'En_Servicio')
        """, (
            numero_interno, cli_efectivo, ciclo_nuevo, f"Reencauche {ciclo_ant}",
            banda_prov, banda_diseno, prof_nueva, costo_renovado, factura, hoy_str
        ))

        # Actualizar llantas_maestro
        nuevo_costo_reen = (costo_reen_tot or 0.0) + costo_renovado
        nuevo_costo_acum = (costo_acum or 0.0) + costo_renovado
        cursor.execute("""
            UPDATE llantas_maestro SET
                ciclo_actual = ?,
                vida_actual = ?,
                banda_reen = ?,
                num_reencauches = ?,
                prof_inicial = ?,
                prof_ext = ?,
                prof_cent = ?,
                prof_int = ?,
                prof_actual_min = ?,
                costo_ciclo_actual = ?,
                costo_reencauches_total = ?,
                costo_acumulado_total = ?,
                estado_actual = 'Bodega_2_Reutilizable',
                ubicacion_bodega = 'BODEGA_4_REENCAUCHADAS',
                fecha_envio_planta = NULL,
                fecha_compromiso_planta = NULL,
                fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (
            ciclo_nuevo, f"R{ciclo_ant}", banda_diseno, ciclo_ant,
            prof_nueva, prof_nueva, prof_nueva, prof_nueva, prof_nueva,
            costo_renovado, nuevo_costo_reen, nuevo_costo_acum,
            hoy_str, ll_id
        ))

        # Movimiento RETORNO_REENCAUCHE
        cursor.execute("""
            INSERT INTO llantas_movimientos (
                fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                bodega_origen, bodega_destino, profundidad_momento, costo_asociado,
                motivo, usuario_responsable
            ) VALUES (?, ?, ?, 'RETORNO_REENCAUCHE', 'Bodega_4_EnPlanta', 'Bodega_2_Reutilizable', ?, ?, ?, ?)
        """, (
            hoy_ts, numero_interno, cli_efectivo, prof_nueva, costo_renovado,
            f"Retorno de planta reencauche ciclo {ciclo_nuevo} banda {banda_diseno}", user
        ))

        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "ciclo_actual": ciclo_nuevo,
        "mensaje": f"Llanta {numero_interno} recibida en Bodega 2 con ciclo {ciclo_nuevo}"
    }


def finalizar_reparacion_bodega5(datos: dict) -> dict:
    """
    Flujo 6 — Finalizar Reparación / Vulcanizado (Bodega 5 -> Bodega 2).
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    trabajo = str(datos.get('tipo_trabajo', 'Parche radial')).strip()
    costo_rep = database.to_float(datos.get('costo_reparacion', 0.0), 0.0)
    proveedor = str(datos.get('proveedor', 'Vulcanizadora')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ciclo_actual, costo_reparaciones_total, costo_acumulado_total, cliente_propietario, cliente
            FROM llantas_maestro WHERE UPPER(numero_interno) = ?
        """, (numero_interno,))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}

        ll_id, ciclo_act, cost_rep_tot, cost_acum_tot, cli_prop, cli_old = row
        cli_efectivo = cli_prop or cli_old or cliente

        # Reparar novedades
        cursor.execute("""
            UPDATE llantas_novedades_registro
            SET estado_novedad = 'Reparada'
            WHERE UPPER(numero_interno) = ? AND estado_novedad = 'Activa'
        """, (numero_interno,))

        # Sumar costo a ciclo activo
        cursor.execute("""
            UPDATE llantas_ciclos
            SET costo_ciclo = costo_ciclo + ?
            WHERE numero_interno = ? AND numero_ciclo = ?
        """, (costo_rep, numero_interno, ciclo_act or 1))

        # Actualizar llantas_maestro
        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = 'Bodega_2_Reutilizable',
                ubicacion_bodega = 'BODEGA_2_RECAMBIO',
                costo_reparaciones_total = costo_reparaciones_total + ?,
                costo_acumulado_total = costo_acumulado_total + ?,
                fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (costo_rep, costo_rep, hoy_str, ll_id))

        cursor.execute("""
            INSERT INTO llantas_movimientos (
                fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                bodega_origen, bodega_destino, costo_asociado, motivo, usuario_responsable
            ) VALUES (?, ?, ?, 'RETORNO_REPARACION', 'Bodega_5_Reparacion', 'Bodega_2_Reutilizable', ?, ?, ?)
        """, (hoy_ts, numero_interno, cli_efectivo, costo_rep, f"Reparación {trabajo} por {proveedor}", user))

        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "mensaje": f"Reparación finalizada para {numero_interno}, trasladada a Bodega 2"
    }


def procesar_dictamen_garantia_bodega6(datos: dict) -> dict:
    """
    Flujo 7 — Dictamen Técnico de Garantía (Bodega 6 -> Bodega 7).
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    dictamen = str(datos.get('dictamen', 'Aprobada')).strip()
    pct_rec = database.to_float(datos.get('pct_reconocido', 0.0), 0.0)
    valor_nc = database.to_float(datos.get('valor_nota_credito', 0.0), 0.0)
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, dinero_perdido_fvu, cliente_propietario, cliente, ciclo_actual
            FROM llantas_maestro WHERE UPPER(numero_interno) = ?
        """, (numero_interno,))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}

        ll_id, din_perd, cli_prop, cli_old, ciclo_act = row
        cli_efectivo = cli_prop or cli_old or cliente
        nuevo_dinero_perd = max(0.0, (din_perd or 0.0) - valor_nc)

        cursor.execute("""
            UPDATE llantas_maestro SET
                dictamen_garantia = ?,
                pct_reconocido_garantia = ?,
                valor_reconocido_garantia = ?,
                dinero_perdido_fvu = ?,
                estado_actual = 'Bodega_7_FVU',
                ubicacion_bodega = 'BODEGA_7_CHATARRIZADA',
                fecha_baja = ?,
                motivo_baja = ?,
                fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (
            dictamen, pct_rec, valor_nc, nuevo_dinero_perd,
            hoy_str, f"Garantía {dictamen} (NC: ${valor_nc:,.0f})", hoy_str, ll_id
        ))

        cursor.execute("""
            UPDATE llantas_ciclos SET estado_ciclo = 'Desechado', fecha_fin_ciclo = ?
            WHERE numero_interno = ? AND numero_ciclo = ?
        """, (hoy_str, numero_interno, ciclo_act or 1))

        cursor.execute("""
            INSERT INTO llantas_movimientos (
                fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                bodega_origen, bodega_destino, costo_asociado, motivo, usuario_responsable
            ) VALUES (?, ?, ?, 'RECLAMO_GARANTIA', 'Bodega_6_Garantia', 'Bodega_7_FVU', ?, ?, ?)
        """, (hoy_ts, numero_interno, cli_efectivo, valor_nc, f"Garantía {dictamen} ({pct_rec}%)", user))

        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "mensaje": f"Dictamen de garantía procesado para {numero_interno}"
    }


def dar_baja_fvu_bodega7(datos: dict) -> dict:
    """
    Flujo 8 — Chatarrización y Cálculo Financiero FVU.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    motivo = str(datos.get('motivo_baja', 'Fin de Vida Útil')).strip()
    prof_retiro_in = datos.get('prof_retiro')
    foto = str(datos.get('foto_baja', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    hoy_ts = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, prof_actual_min, prof_inicial_nueva, costo_ciclo_actual,
                   valor_reconocido_garantia, ciclo_actual, cliente_propietario, cliente
            FROM llantas_maestro WHERE UPPER(numero_interno) = ?
        """, (numero_interno,))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}

        ll_id, p_act, p_ini, c_ciclo, val_gar, ciclo_act, cli_prop, cli_old = row
        cli_efectivo = cli_prop or cli_old or cliente

        p_ret = database.to_float(prof_retiro_in, p_act or 0.0)
        p_ini = database.to_float(p_ini, 16.0)
        c_ciclo = database.to_float(c_ciclo, 1450000.0)
        val_gar = database.to_float(val_gar, 0.0)

        cfg = database.obtener_configuracion_avanzada_cliente(cli_efectivo)
        lim_ret = database.to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)

        mm_desperdiciados = max(0.0, p_ret - lim_ret)
        denominador = max(1.0, p_ini - lim_ret)
        dinero_perdido = max(0.0, (mm_desperdiciados * (c_ciclo / denominador)) - val_gar)

        cursor.execute("""
            UPDATE llantas_ciclos SET
                estado_ciclo = 'Desechado',
                fecha_fin_ciclo = ?,
                prof_final_ciclo = ?
            WHERE numero_interno = ? AND numero_ciclo = ?
        """, (hoy_str, p_ret, numero_interno, ciclo_act or 1))

        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = 'Bodega_7_FVU',
                ubicacion_bodega = 'BODEGA_7_CHATARRIZADA',
                fecha_baja = ?,
                motivo_baja = ?,
                foto_baja = ?,
                mm_desperdiciados_fvu = ?,
                dinero_perdido_fvu = ?,
                fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (hoy_str, motivo, foto, mm_desperdiciados, dinero_perdido, hoy_str, ll_id))

        cursor.execute("""
            INSERT INTO llantas_movimientos (
                fecha_movimiento, numero_interno, cliente_propietario, tipo_movimiento,
                bodega_origen, bodega_destino, profundidad_momento, motivo, usuario_responsable
            ) VALUES (?, ?, ?, 'BAJA_FVU', 'Bodega_6_FVU', 'Bodega_7_FVU', ?, ?, ?)
        """, (hoy_ts, numero_interno, cli_efectivo, p_ret, motivo, user))

        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "mm_desperdiciados": mm_desperdiciados,
        "dinero_perdido": dinero_perdido
    }


def obtener_hoja_vida_llanta(numero_interno: str, cliente: str = "") -> dict:
    """
    Flujo 9 — Hoja de Vida Completa (Life Sheet).
    """
    import database
    numero_interno = str(numero_interno or '').strip().upper()
    cliente = str(cliente or '').strip().upper()

    with database.get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT * FROM llantas_maestro 
            WHERE UPPER(numero_interno) = ?
        """
        params = [numero_interno]
        if cliente and cliente != "TODOS":
            query += " AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ?)"
            params.extend([cliente, cliente])

        cursor.execute(query, params)
        cols_m = [d[0] for d in cursor.description]
        row_m = cursor.fetchone()

        if not row_m:
            # Intentar sincronizar backfill si existe en inspecciones
            sincronizar_hoja_vida_desde_inspecciones(conn)
            cursor.execute(query, params)
            row_m = cursor.fetchone()
            if not row_m:
                return {"ok": False, "status": "error", "mensaje": f"No se encontró hoja de vida para {numero_interno}"}

        ll = dict(zip(cols_m, row_m))

        # Ciclos de vida
        cursor.execute("""
            SELECT numero_ciclo, tipo_ciclo, prof_inicial_ciclo, prof_final_ciclo,
                   km_recorridos_ciclo, costo_ciclo, cpk_ciclo, diseno_banda, estado_ciclo,
                   fecha_inicio_ciclo, fecha_fin_ciclo
            FROM llantas_ciclos
            WHERE UPPER(numero_interno) = ?
            ORDER BY numero_ciclo ASC
        """, (numero_interno,))
        cols_c = [d[0] for d in cursor.description]
        ciclos_raw = [dict(zip(cols_c, r)) for r in cursor.fetchall()]

        # Movimientos
        cursor.execute("""
            SELECT fecha_movimiento, tipo_movimiento, bodega_origen, bodega_destino,
                   placa_origen, posicion_origen, placa_destino, posicion_destino,
                   odometro_vehiculo, profundidad_momento, psi_momento, costo_asociado,
                   motivo, usuario_responsable
            FROM llantas_movimientos
            WHERE UPPER(numero_interno) = ?
            ORDER BY fecha_movimiento DESC, id DESC
        """, (numero_interno,))
        cols_mov = [d[0] for d in cursor.description]
        movs_raw = [dict(zip(cols_mov, r)) for r in cursor.fetchall()]

        # Novedades
        cursor.execute("""
            SELECT fecha_deteccion, tipo_novedad, categoria_severidad, estado_novedad,
                   placa, posicion, observacion, foto_url
            FROM llantas_novedades_registro
            WHERE UPPER(numero_interno) = ?
            ORDER BY fecha_deteccion DESC, id DESC
        """, (numero_interno,))
        cols_nov = [d[0] for d in cursor.description]
        novedades_raw = [dict(zip(cols_nov, r)) for r in cursor.fetchall()]

        # Inspecciones históricas de esta llanta
        cursor.execute("""
            SELECT fecha, placa, posicion, kilometraje, prof_ext, prof_cent, prof_int, psi, novedades
            FROM inspecciones
            WHERE UPPER(numero_interno) = ?
            ORDER BY fecha ASC, id ASC
        """, (numero_interno,))
        insps = cursor.fetchall()

    # Consolidar métricas
    km_totales = database.to_float(ll.get('km_acumulados_total', 0.0))
    if not km_totales and ciclos_raw:
        km_totales = sum(database.to_float(c.get('km_recorridos_ciclo', 0.0)) for c in ciclos_raw)

    costo_total = database.to_float(ll.get('costo_acumulado_total', 0.0))
    if not costo_total and ciclos_raw:
        costo_total = sum(database.to_float(c.get('costo_ciclo', 0.0)) for c in ciclos_raw)

    if not costo_total:
        costo_total = database.to_float(ll.get('precio_compra_inicial', 1450000.0), 1450000.0)

    cpk_global = round(costo_total / max(1.0, km_totales), 4)

    # Calcular mm gastados para rendimiento km/mm
    mm_gastados_tot = 0.0
    for c in ciclos_raw:
        p_i = database.to_float(c.get('prof_inicial_ciclo', 16.0), 16.0)
        p_f = database.to_float(c.get('prof_final_ciclo', ll.get('prof_actual_min', 3.0)), 3.0)
        mm_gastados_tot += max(0.0, p_i - p_f)

    rendimiento_km_mm = round(km_totales / max(1.0, mm_gastados_tot), 1)

    # Ahorro vs Llanta Nueva
    p_compra_ini = database.to_float(ll.get('precio_compra_inicial', 1450000.0), 1450000.0)
    ciclo_1_km = ciclos_raw[0].get('km_recorridos_ciclo', 0.0) if ciclos_raw else km_totales
    cpk_nueva_estimado = p_compra_ini / max(1.0, ciclo_1_km)
    costo_proyectado_solo_nuevas = km_totales * cpk_nueva_estimado
    ahorro_generado = max(0.0, round(costo_proyectado_solo_nuevas - costo_total, 2))

    # Curva de Desgaste (mm vs km) con trazabilidad de ciclos (diente de sierra) e inspecciones
    curva_desgaste = []
    p_ini_nueva = database.to_float(ll.get('prof_inicial_nueva', 16.0), 16.0)

    km_cursor = 0.0
    for idx_c, c in enumerate(ciclos_raw):
        n_c = c.get('numero_ciclo', idx_c + 1)
        p_ini_c = database.to_float(c.get('prof_inicial_ciclo', p_ini_nueva), p_ini_nueva)
        p_fin_c = c.get('prof_final_ciclo')
        km_rec = database.to_float(c.get('km_recorridos_ciclo', 0.0))
        f_ini = str(c.get('fecha_inicio_ciclo', '') or ll.get('fecha_alta', ''))[:10]
        f_fin = str(c.get('fecha_fin_ciclo', '') or ll.get('fecha_ultimo_movimiento', ''))[:10]
        tipo_c = c.get('tipo_ciclo', 'Original')

        if n_c == 1:
            curva_desgaste.append({
                "fecha": f_ini or "Inicial",
                "km": 0.0,
                "prof_mm": p_ini_c,
                "evento": "Alta Inicial (0 km)"
            })
        else:
            curva_desgaste.append({
                "fecha": f_ini or "Reencauche",
                "km": km_cursor,
                "prof_mm": p_ini_c,
                "evento": f"Reencauche {tipo_c} (+{p_ini_c} mm)"
            })

        km_cursor += km_rec
        if p_fin_c is not None or km_rec > 0:
            prof_fin_val = database.to_float(p_fin_c, database.to_float(ll.get('prof_actual_min', 3.0), 3.0))
            curva_desgaste.append({
                "fecha": f_fin or f_ini,
                "km": km_cursor,
                "prof_mm": prof_fin_val,
                "evento": f"Cierre Ciclo {n_c} ({tipo_c})"
            })

    if not curva_desgaste:
        curva_desgaste.append({
            "fecha": str(ll.get('fecha_alta', '') or 'Inicial')[:10],
            "km": 0.0,
            "prof_mm": p_ini_nueva,
            "evento": "Alta Inicial (0 km)"
        })

    for insp in insps:
        f_i, pl_i, pos_i, km_i, pe_i, pc_i, pi_i, psi_i, nov_i = insp
        pos_vals = [x for x in (database.to_float(pe_i), database.to_float(pc_i), database.to_float(pi_i)) if x > 0]
        p_min_i = min(pos_vals) if pos_vals else p_ini_nueva
        curva_desgaste.append({
            "fecha": str(f_i)[:10],
            "km": database.to_float(km_i),
            "prof_mm": p_min_i,
            "evento": f"Inspección {pl_i} Pos {pos_i}"
        })

    curva_desgaste.sort(key=lambda x: (x.get("km", 0.0), x.get("fecha", "")))

    # Formato desglose ciclos
    desglose_formateado = []
    for c in ciclos_raw:
        n_ciclo = c.get('numero_ciclo', 1)
        tipo = c.get('tipo_ciclo', 'Original')
        p_ini_c = database.to_float(c.get('prof_inicial_ciclo', 16.0), 16.0)
        p_fin_c = database.to_float(c.get('prof_final_ciclo', ll.get('prof_actual_min', 3.0)), 3.0)
        km_rec_c = database.to_float(c.get('km_recorridos_ciclo', 0.0))
        costo_c = database.to_float(c.get('costo_ciclo', 0.0))
        cpk_c = round(costo_c / max(1.0, km_rec_c), 4) if km_rec_c > 0 else 0.0
        desglose_formateado.append({
            "ciclo": n_ciclo,
            "tipo": tipo,
            "prof_inicial": p_ini_c,
            "prof_final": p_fin_c,
            "km_recorridos": km_rec_c,
            "costo": costo_c,
            "cpk": cpk_c,
            "banda": c.get('diseno_banda', 'Original')
        })

    # Timeline formateado
    historial_formateado = []
    for m in movs_raw:
        historial_formateado.append({
            "fecha": str(m.get('fecha_movimiento', ''))[:19],
            "evento": m.get('tipo_movimiento', ''),
            "bodega_origen": m.get('bodega_origen', ''),
            "bodega_destino": m.get('bodega_destino', ''),
            "placa": m.get('placa_destino') or m.get('placa_origen', ''),
            "posicion": m.get('posicion_destino') or m.get('posicion_origen', 0),
            "profundidad_mm": m.get('profundidad_momento', 0.0),
            "detalle": m.get('motivo', ''),
            "responsable": m.get('usuario_responsable', 'admin')
        })

    ciclo_num = ll.get('ciclo_actual', 1) or 1
    vida_nombre = "Original" if ciclo_num == 1 else f"R{ciclo_num - 1}"

    return {
        "ok": True,
        "status": "ok",
        "numero_interno": numero_interno,
        "dot": ll.get('numero_serie_dot', ''),
        "numero_serie_dot": ll.get('numero_serie_dot', ''),
        "ficha_tecnica": {
            "marca": ll.get('marca_origen') or ll.get('marca', ''),
            "diseno": ll.get('diseno_origen') or ll.get('diseno', ''),
            "dimension": ll.get('dimension', '295/80R22.5'),
            "tipo_construccion": ll.get('tipo_construccion', 'Radial'),
            "precio_compra": p_compra_ini,
            "fecha_alta": str(ll.get('fecha_alta', ''))[:10],
            "cliente": ll.get('cliente_propietario') or ll.get('cliente', '')
        },
        "estado_actual": {
            "estado": ll.get('estado_actual', 'Bodega_1_Nuevas'),
            "placa": ll.get('placa_actual', ''),
            "posicion": ll.get('posicion_actual', 0),
            "tipo_eje": ll.get('tipo_eje_actual', ''),
            "prof_min_actual": database.to_float(ll.get('prof_actual_min', 0.0)),
            "psi_actual": database.to_float(ll.get('psi_actual', 100.0)),
            "ciclo_vida": vida_nombre
        },
        "metricas_consolidadas": {
            "km_totales": km_totales,
            "costo_total_invertido": costo_total,
            "cpk_global": cpk_global,
            "rendimiento_km_mm": rendimiento_km_mm,
            "ahorro_generado_vs_nueva": ahorro_generado
        },
        "desglose_por_ciclos": desglose_formateado,
        "historial_movimientos": historial_formateado,
        "curva_desgaste": curva_desgaste,
        "novedades_carcasa": novedades_raw
    }


def obtener_posicion_taller_info(placa: str, posicion: int, cliente: str = "") -> dict:
    """
    Retorna información de la rueda instalada en (placa, posicion) y el stock disponible
    para montar desde Bodega 1 y Bodega 2, aplicando el filtro de candado direccional.
    """
    import database
    placa = str(placa or '').strip().upper()
    posicion = database.to_int(posicion, 0)
    cliente = str(cliente or '').strip().upper()

    llanta_instalada = None
    with database.get_connection() as conn:
        cursor = conn.cursor()

        # Buscar llanta instalada en llantas_maestro
        cursor.execute("""
            SELECT id, numero_interno, numero_serie_dot, marca_origen, diseno_origen, marca, diseno,
                   dimension, prof_inicial_nueva, prof_actual_min, psi_actual, ciclo_actual,
                   vida_actual, banda_reen
            FROM llantas_maestro
            WHERE UPPER(placa_actual) = ? AND posicion_actual = ? AND estado_actual = 'Montada'
        """, (placa, posicion))
        r_inst = cursor.fetchone()
        if r_inst:
            llanta_instalada = {
                "id": r_inst[0],
                "numero_interno": r_inst[1],
                "dot": r_inst[2],
                "marca": r_inst[3] or r_inst[5],
                "diseno": r_inst[4] or r_inst[6],
                "dimension": r_inst[7],
                "prof_inicial": r_inst[8],
                "profundidad_actual": r_inst[9],
                "psi_actual": r_inst[10],
                "ciclo_actual": r_inst[11],
                "vida": "ORIGINAL" if r_inst[11] == 1 else f"R{r_inst[11] - 1}",
                "banda": r_inst[13]
            }
        else:
            # Buscar última inspección de patio en esa posición
            cursor.execute("""
                SELECT numero_interno, marca, diseno, dimension, prof_inicial,
                       prof_ext, prof_cent, prof_int, psi, vida, banda_reen
                FROM inspecciones
                WHERE UPPER(placa) = ? AND posicion = ?
                ORDER BY fecha DESC, id DESC LIMIT 1
            """, (placa, posicion))
            r_insp = cursor.fetchone()
            if r_insp and r_insp[0] and r_insp[0].upper() != 'SN':
                p_vals = [x for x in (database.to_float(r_insp[5]), database.to_float(r_insp[6]), database.to_float(r_insp[7])) if x > 0]
                p_min = min(p_vals) if p_vals else database.to_float(r_insp[4])
                llanta_instalada = {
                    "numero_interno": r_insp[0],
                    "marca": r_insp[1],
                    "diseno": r_insp[2],
                    "dimension": r_insp[3],
                    "prof_inicial": r_insp[4],
                    "profundidad_actual": p_min,
                    "psi_actual": r_insp[8],
                    "vida": r_insp[9] or "ORIGINAL",
                    "banda": r_insp[10]
                }

        # Tipología y candado direccional
        perfil_v = database.obtener_perfil_vehiculo(placa)
        tipologia = perfil_v.get('tipologia', '') if perfil_v else ''
        es_direccional = database.es_posicion_direccional(tipologia, posicion)

        # Buscar stock disponible en Bodega 1 y Bodega 2
        query_stock = """
            SELECT id, numero_interno, estado_actual, marca_origen, diseno_origen, marca, diseno,
                   dimension, prof_inicial_nueva, prof_actual_min, ciclo_actual, vida_actual
            FROM llantas_maestro
            WHERE estado_actual IN ('Bodega_1_Nuevas', 'Bodega_2_Reutilizable', 'BODEGA_1_NUEVAS', 'BODEGA_2_RECAMBIO', 'BODEGA_4_REENCAUCHADAS')
        """
        params_s = []
        if cliente and cliente != "TODOS":
            query_stock += " AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ?)"
            params_s.extend([cliente, cliente])

        query_stock += " ORDER BY estado_actual ASC, prof_actual_min DESC"
        cursor.execute(query_stock, params_s)
        stock_raw = cursor.fetchall()

        stock_disponible = []
        for r_s in stock_raw:
            c_num = r_s[10] or 1
            v_act = str(r_s[11] or 'Original')
            # Si la posición es direccional, excluir reencauches
            if es_direccional and (c_num > 1 or v_act.upper() != 'ORIGINAL'):
                continue

            stock_disponible.append({
                "id": r_s[0],
                "numero_interno": r_s[1],
                "bodega": r_s[2],
                "marca": r_s[3] or r_s[5],
                "diseno": r_s[4] or r_s[6],
                "dimension": r_s[7],
                "prof_inicial": r_s[8],
                "profundidad_actual": r_s[9],
                "ciclo_actual": c_num,
                "vida": "ORIGINAL" if c_num == 1 else f"R{c_num - 1}"
            })

    return {
        "placa": placa,
        "posicion": posicion,
        "es_direccional": es_direccional,
        "llanta_instalada": llanta_instalada,
        "stock_disponible": stock_disponible
    }


def listar_inventario_bodegas_con_kpis(filtros: dict = None) -> dict:
    """
    Lista el inventario con cálculo de dias_en_bodega y consolidado de KPIs para las 8 tarjetas.
    """
    import database
    filtros = filtros or {}
    cliente = str(filtros.get('cliente', '')).strip().upper()
    subcliente = str(filtros.get('subcliente', '')).strip().upper()
    ubicacion = str(filtros.get('ubicacion_bodega') or filtros.get('estado_actual', '')).strip()
    dimension = str(filtros.get('dimension', '')).strip().upper()
    q = str(filtros.get('q', '')).strip().upper()

    query = "SELECT * FROM llantas_maestro WHERE 1=1"
    params = []

    if cliente and cliente != "TODOS":
        query += " AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ?)"
        params.extend([cliente, cliente])
    if subcliente and subcliente != "TODOS":
        query += " AND (UPPER(subcliente_sede) = ? OR UPPER(subcliente) = ?)"
        params.extend([subcliente, subcliente])
    if ubicacion and ubicacion != "TODAS":
        canonica = normalizar_estado_bodega(ubicacion)
        query += " AND (UPPER(estado_actual) = ? OR UPPER(ubicacion_bodega) = ?)"
        params.extend([canonica.upper(), ubicacion.upper()])
    if dimension and dimension != "TODAS":
        query += " AND UPPER(dimension) = ?"
        params.append(dimension)
    if q:
        query += " AND (UPPER(numero_interno) LIKE ? OR UPPER(marca_origen) LIKE ? OR UPPER(marca) LIKE ? OR UPPER(placa_actual) LIKE ?)"
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q, like_q])

    query += " ORDER BY fecha_ultimo_movimiento DESC, id DESC"

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        cols = [d[0] for d in cursor.description]
        llantas = [dict(zip(cols, r)) for r in cursor.fetchall()]

        hoy = date.today()
        # Inicializar conteos y valorización para las 8 tarjetas
        kpis = {
            "total_llantas": {"cantidad": 0, "valor_cop": 0.0},
            "b1_nuevas": {"cantidad": 0, "valor_cop": 0.0},
            "b2_reutilizable": {"cantidad": 0, "valor_cop": 0.0},
            "b3_reencauche": {"cantidad": 0, "valor_cop": 0.0},
            "b4_enplanta": {"cantidad": 0, "valor_cop": 0.0},
            "b5_reparacion": {"cantidad": 0, "valor_cop": 0.0},
            "b6_garantia": {"cantidad": 0, "valor_cop": 0.0},
            "b7_chatarra": {"cantidad": 0, "valor_cop": 0.0},
            "montadas": {"cantidad": 0, "valor_cop": 0.0}
        }

        # Calcular totales para todas las llantas de este cliente
        query_all = "SELECT estado_actual, ubicacion_bodega, costo_ciclo_actual, costo_acumulado_total, fecha_ultimo_movimiento, fecha_alta FROM llantas_maestro WHERE 1=1"
        params_all = []
        if cliente and cliente != "TODOS":
            query_all += " AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ?)"
            params_all.extend([cliente, cliente])
        cursor.execute(query_all, params_all)
        for r_all in cursor.fetchall():
            est = normalizar_estado_bodega(r_all[0] or r_all[1])
            costo = database.to_float(r_all[2] or r_all[3], 0.0)
            kpis["total_llantas"]["cantidad"] += 1
            kpis["total_llantas"]["valor_cop"] += costo

            if est == 'Bodega_1_Nuevas':
                kpis["b1_nuevas"]["cantidad"] += 1
                kpis["b1_nuevas"]["valor_cop"] += costo
            elif est == 'Bodega_2_Reutilizable':
                kpis["b2_reutilizable"]["cantidad"] += 1
                kpis["b2_reutilizable"]["valor_cop"] += costo
            elif est == 'Bodega_3_Reencauche':
                kpis["b3_reencauche"]["cantidad"] += 1
                kpis["b3_reencauche"]["valor_cop"] += costo
            elif est == 'Bodega_4_EnPlanta':
                kpis["b4_enplanta"]["cantidad"] += 1
                kpis["b4_enplanta"]["valor_cop"] += costo
            elif est == 'Bodega_5_Reparacion':
                kpis["b5_reparacion"]["cantidad"] += 1
                kpis["b5_reparacion"]["valor_cop"] += costo
            elif est == 'Bodega_6_Garantia':
                kpis["b6_garantia"]["cantidad"] += 1
                kpis["b6_garantia"]["valor_cop"] += costo
            elif est == 'Bodega_7_FVU':
                kpis["b7_chatarra"]["cantidad"] += 1
                kpis["b7_chatarra"]["valor_cop"] += costo
            elif est == 'Montada':
                kpis["montadas"]["cantidad"] += 1
                kpis["montadas"]["valor_cop"] += costo

        for item in llantas:
            f_mov = item.get("fecha_ultimo_movimiento") or item.get("fecha_alta")
            item["dias_en_bodega"] = 0
            if f_mov:
                try:
                    f_d = datetime.strptime(str(f_mov)[:10], '%Y-%m-%d').date()
                    item["dias_en_bodega"] = max(0, (hoy - f_d).days)
                except Exception:
                    pass
            item["marca_display"] = item.get("marca_origen") or item.get("marca") or ""
            item["diseno_display"] = item.get("diseno_origen") or item.get("diseno") or ""
            item["estado_display"] = normalizar_estado_bodega(item.get("estado_actual") or item.get("ubicacion_bodega"))
            item["reservada_para_dual"] = bool(item.get("reservada_para_placa"))

    return {
        "total": len(llantas),
        "llantas": llantas,
        "kpis": kpis,
        "resumen_kpis": kpis
    }
