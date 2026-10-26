# -*- coding: utf-8 -*-
"""
Módulo de Gestión de las 7 Bodegas, Taller en Patio y Hoja de Vida de Neumáticos (Life Sheet).
Implementación según especificación: docs/prompt_antigravity_ide_implementaci_n_de_las_7_bodegas_y_hoja_de_vida_de_neum_ticos.md
"""

import os
import math
from datetime import datetime, date, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    BOGOTA_TZ = ZoneInfo("America/Bogota")
except Exception:
    BOGOTA_TZ = timezone(timedelta(hours=-5))

def normalizar_estado_bodega(valor: str) -> str:
    """Ubicación oficial (database.UBICACIONES_LLANTA) a partir de cualquier nombre de bodega o estado."""
    import database
    return database.ubicacion_canonica(valor)


def _ubicacion_actual(ubicacion, estado, acta='', fecha_disp=''):
    import database
    return database.ubicacion_canonica(ubicacion, estado, acta, fecha_disp)


def sincronizar_hoja_vida_desde_inspecciones(conn=None):
    """
    Backfill desde inspecciones: el maestro lo crea la sincronización única de database (antes había dos
    con reglas distintas) y aquí solo se registran las novedades de carcasa que aún no estén.
    """
    import database

    def _ejecutar(c):
        database.sincronizar_maestro_desde_inspecciones(c)
        c.execute("""
            SELECT cliente, numero_interno, placa, posicion, novedades, fecha
            FROM inspecciones
            WHERE numero_interno IS NOT NULL AND TRIM(numero_interno) != '' AND UPPER(TRIM(numero_interno)) != 'SN'
              AND cliente IS NOT NULL AND TRIM(cliente) != ''
              AND novedades IS NOT NULL AND UPPER(TRIM(novedades)) NOT IN ('', 'OK', 'NORMAL', 'NINGUNA', 'NAN')
        """)
        for cli, serial, placa, pos, nov, fecha in c.fetchall():
            cli, serial, fecha_i = str(cli).strip().upper(), str(serial).strip().upper(), str(fecha or '')[:10]
            existe = c.execute("""SELECT 1 FROM llantas_novedades_registro WHERE UPPER(numero_interno) = ?
                                  AND UPPER(cliente_propietario) = ? AND fecha_deteccion = ? AND tipo_novedad = ?""",
                               (serial, cli, fecha_i, str(nov).strip())).fetchone()
            if not existe:
                c.execute("""
                    INSERT INTO llantas_novedades_registro (
                        fecha_deteccion, numero_interno, cliente_propietario, tipo_novedad,
                        categoria_severidad, estado_novedad, placa, posicion, observacion
                    ) VALUES (?, ?, ?, ?, 'Operativa', 'Activa', ?, ?, ?)
                """, (fecha_i, serial, cli, str(nov).strip(), str(placa or '').upper(), database.to_int(pos),
                      f"Detectado en inspección fecha {fecha_i}"))

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
    dimension = str(datos.get('dimension', '')).strip().upper()
    tipo_construccion = str(datos.get('tipo_construccion', 'Radial')).strip()
    precio_compra = database.to_float(datos.get('precio_compra_inicial') or datos.get('precio_compra'), 0.0)  # sin precio = 0: la llanta queda fuera de los cálculos en pesos (no se inventa un valor)
    prof_ini = database.to_float(datos.get('prof_inicial_nueva') or datos.get('prof_inicial'), 0.0)
    if prof_ini <= 0 and marca and diseno:
        prof_ini = database.to_float(database.buscar_profundidad_inicial(marca, diseno, dimension, 'Original'), 0.0)
    proveedor = str(datos.get('proveedor_factura') or datos.get('proveedor', '')).strip()
    dot_base = str(datos.get('numero_serie_dot') or datos.get('dot', '')).strip().upper()

    # Sin marca, diseño, dimensión y profundidad inicial no se da de alta (antes 295/80R22.5 y 16 mm por defecto)
    if not (marca and diseno and dimension and prof_ini > 0):
        return {"ok": False, "status": "error", "mensaje": "Indique marca, diseño, dimensión y profundidad inicial de la llanta"}

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
                    'En Stock - Nueva', ?, 0.0, 1, 0.0,
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

            database.registrar_kardex(cursor, n, cliente, 'EXTERNO', 'BODEGA_1_NUEVAS', 'ALTA_NUEVA', fecha=hoy_str,
                                      subcliente=subcliente, vida='Original', prof=prof_ini, costo=precio_compra,
                                      proveedor=proveedor, motivo='Ingreso al inventario', usuario=user)

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
    Flujo 2 — Desmonte desde patio o taller hacia una bodega. Solo se desmonta una llanta montada.
    Fin de vida útil y reclamación de garantía van a Bodega 6 (primera fase del FVU); la disposición
    final (Bodega 7) se registra cuando la empresa ambiental la retira, con su acta.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    raw_destino = str(datos.get('bodega_destino', 'BODEGA_2_RECAMBIO')).strip()
    bodega_destino = normalizar_estado_bodega(raw_destino)
    reclamar_garantia = database._clave_estado(raw_destino) in database._ALIAS_GARANTIA
    odometro = database.to_float(datos.get('odometro_vehiculo') or datos.get('kilometraje', 0.0))
    user = str(datos.get('usuario_responsable', 'admin')).strip()
    motivo = str(datos.get('motivo', 'Desmonte en taller / patio')).strip()

    if not numero_interno:
        return {"ok": False, "status": "error", "message": "El número interno es obligatorio"}
    if bodega_destino == 'BODEGA_7_CHATARRIZADA':
        bodega_destino = 'BODEGA_6_FVU'  # al desmontar es la primera fase del FVU

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ubicacion_bodega, estado_actual, placa_actual, posicion_actual, km_montaje_actual,
                   km_acumulados_total, prof_actual_min, ciclo_actual, cliente_propietario, cliente,
                   costo_ciclo_actual, prof_inicial, prof_inicial_nueva, valor_reconocido_garantia, subcliente, vida_actual
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"La llanta {numero_interno} no se encuentra en el inventario"}

        (ll_id, ubi, est, placa_act, pos_act, km_mont, km_acum, prof_min_act, ciclo_act, cli_prop, cli_old,
         c_ciclo, p_ini_m, p_ini_n, val_gar, subc, vida_act) = row
        cli_efectivo = cli_old or cli_prop or cliente
        origen = _ubicacion_actual(ubi, est)
        if origen != database.MONTADA:
            return {"ok": False, "status": "error", "message": f"La llanta {numero_interno} no está montada ({database.nombre_ubicacion(origen) or est}): no se puede desmontar"}
        error = database.validar_transicion_llanta(origen, bodega_destino)
        if error:
            return {"ok": False, "status": "error", "message": error}
        p_ini = database.to_float(p_ini_m) or database.to_float(p_ini_n)

        # Profundidad suministrada o la última conocida; presión solo si se midió
        prof_momento = database.to_float(datos.get('profundidad') or datos.get('prof_min_mm', prof_min_act), prof_min_act)
        psi_momento = database.to_float(datos.get('psi'), 0.0)

        delta_km = max(0.0, odometro - km_mont) if (odometro > 0 and km_mont and km_mont > 0) else 0.0
        nuevo_km_acum = (km_acum or 0.0) + delta_km

        cursor.execute("""
            UPDATE llantas_ciclos SET
                km_recorridos_ciclo = km_recorridos_ciclo + ?,
                prof_final_ciclo = ?
            WHERE UPPER(numero_interno) = ? AND numero_ciclo = ?
              AND (UPPER(cliente_propietario) = ? OR ? = '')
        """, (delta_km, prof_momento, numero_interno, ciclo_act, cli_efectivo, cli_efectivo))

        es_fvu = bodega_destino == 'BODEGA_6_FVU'
        mm_desp, dinero_perd = 0.0, 0.0
        if es_fvu:
            cfg = database.obtener_configuracion_avanzada_cliente(cli_efectivo)
            lim_ret = database.to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
            if prof_momento > lim_ret:
                mm_desp = max(0.0, prof_momento - lim_ret)
                denominador = max(1.0, (p_ini or 0.0) - lim_ret)
                # Sin costo o sin profundidad inicial registrados, la pérdida en pesos queda sin dato
                dinero_perd = max(0.0, (mm_desp * (c_ciclo / denominador)) - (val_gar or 0.0)) if (c_ciclo and p_ini) else None
            cursor.execute("""
                UPDATE llantas_ciclos SET estado_ciclo = 'Desechado', fecha_fin_ciclo = CURRENT_DATE, prof_final_ciclo = ?
                WHERE UPPER(numero_interno) = ? AND numero_ciclo = ?
                  AND (UPPER(cliente_propietario) = ? OR ? = '')
            """, (prof_momento, numero_interno, ciclo_act, cli_efectivo, cli_efectivo))

        hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = ?, ubicacion_bodega = ?, placa_actual = '', posicion_actual = 0,
                prof_actual_min = ?, prof_ext = ?, prof_cent = ?, prof_int = ?,
                psi_actual = CASE WHEN ? > 0 THEN ? ELSE psi_actual END,
                km_acumulados_total = ?, fecha_ultimo_movimiento = ?,
                mm_desperdiciados_fvu = CASE WHEN ? THEN ? ELSE mm_desperdiciados_fvu END,
                mm_perdidos_fvu = CASE WHEN ? THEN ? ELSE mm_perdidos_fvu END,
                dinero_perdido_fvu = CASE WHEN ? THEN ? ELSE dinero_perdido_fvu END,
                fecha_baja = CASE WHEN ? THEN ? ELSE fecha_baja END,
                motivo_baja = CASE WHEN ? THEN ? ELSE motivo_baja END,
                causal_baja_fvu = CASE WHEN ? THEN ? ELSE causal_baja_fvu END,
                estado_garantia = CASE WHEN ? THEN 'En Reclamación' ELSE estado_garantia END
            WHERE id = ?
        """, (
            database.nombre_ubicacion(bodega_destino), bodega_destino,
            prof_momento, prof_momento, prof_momento, prof_momento, psi_momento, psi_momento,
            nuevo_km_acum, hoy_str,
            es_fvu, mm_desp, es_fvu, mm_desp, es_fvu, dinero_perd, es_fvu, hoy_str, es_fvu, motivo, es_fvu, motivo,
            reclamar_garantia, ll_id
        ))

        tipo = {'BODEGA_2_RECAMBIO': 'DESMONTE_RECAMBIO', 'BODEGA_3_REENCAUCHE': 'DESMONTE_REENCAUCHE',
                'BODEGA_5_REPARACION': 'ENVIO_REPARACION', 'BODEGA_6_FVU': 'BAJA_FVU'}.get(bodega_destino, 'DESMONTE')
        database.registrar_kardex(cursor, numero_interno, cli_efectivo, database.MONTADA, bodega_destino, tipo,
                                  fecha=hoy_str, subcliente=subc or '', placa=placa_act, posicion=pos_act,
                                  vida=vida_act, prof=prof_momento, km=odometro, motivo=motivo, usuario=user)
        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "message": f"Llanta {numero_interno} desmontada hacia {database.nombre_ubicacion(bodega_destino)}",
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
        cursor.execute("""
            SELECT id FROM llantas_maestro 
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente))
        row_check = cursor.fetchone()
        if not row_check or es_nueva_directa:
            if not row_check:
                marca_n = str(datos.get('marca') or '').strip().upper()
                diseno_n = str(datos.get('diseno') or '').strip().upper()
                dim_n = str(datos.get('dimension') or '').strip().upper()
                prof_n = database.to_float(datos.get('prof_inicial'), 0.0)
                if prof_n <= 0 and marca_n and diseno_n:
                    prof_n = database.to_float(database.buscar_profundidad_inicial(marca_n, diseno_n, dim_n, 'Original'), 0.0)
                if not (marca_n and diseno_n and dim_n and prof_n > 0):
                    return {"ok": False, "status": "error", "message": f"La llanta {numero_interno} no existe en el inventario: indique marca, diseño, dimensión y profundidad inicial para darla de alta"}
                res_alta = crear_llantas_stock({
                    "cliente_propietario": cliente or "CLIENTE GENERAL",
                    "modo": "individual",
                    "numero_interno": numero_interno,
                    "marca_origen": marca_n,
                    "diseno_origen": diseno_n,
                    "dimension": dim_n,
                    "precio_compra_inicial": database.to_float(datos.get('precio_compra'), 0.0),
                    "prof_inicial_nueva": prof_n,
                    "usuario_responsable": user
                })
                if not res_alta.get('ok'):
                    return res_alta

        cursor.execute("""
            SELECT id, estado_actual, ciclo_actual, marca, diseno, dimension,
                   prof_inicial, prof_actual_min, vida_actual, cliente_propietario, cliente,
                   ubicacion_bodega, numero_acta_ambiental, fecha_disposicion, subcliente, placa_actual, posicion_actual
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente))
        row_ll = cursor.fetchone()
        if not row_ll:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}

        (ll_id, est_act, ciclo_act, marca_o, diseno_o, dim, p_ini, p_act, vida_act, cli_prop, cli_old,
         ubi_act, acta, f_disp, subc, placa_prev, pos_prev) = row_ll
        cli_efectivo = cli_old or cli_prop or cliente

        # Solo se monta desde una bodega permitida; una llanta dada de baja exige trazabilidad del reingreso
        origen = _ubicacion_actual(ubi_act, est_act, acta, f_disp)
        reingreso = {"motivo": datos.get('motivo_reingreso'), "responsable": datos.get('responsable_reingreso') or user,
                     "foto": datos.get('foto_reingreso')}
        error = database.validar_transicion_llanta(origen, database.MONTADA, reingreso=reingreso)
        if error:
            return {"ok": False, "status": "error", "message": error}
        es_reingreso = origen in ('BODEGA_6_FVU', 'BODEGA_7_CHATARRIZADA')

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
              AND ubicacion_bodega = 'MONTADA_OPERACION'
              AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
        """, (placa, posicion, numero_interno, cliente, cliente, cliente))
        ocupantes = cursor.fetchall()

        hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')

        for oc_id, oc_serial, oc_prof, oc_km_mont, oc_km_acum, oc_ciclo in ocupantes:
            delta_oc = max(0.0, odometro - (oc_km_mont or 0.0)) if odometro > 0 and oc_km_mont else 0.0
            cursor.execute("""
                UPDATE llantas_maestro SET
                    estado_actual = ?,
                    ubicacion_bodega = 'BODEGA_2_RECAMBIO',
                    placa_actual = '',
                    posicion_actual = 0,
                    km_acumulados_total = km_acumulados_total + ?,
                    fecha_ultimo_movimiento = ?
                WHERE id = ? AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
            """, (database.nombre_ubicacion('BODEGA_2_RECAMBIO'), delta_oc, hoy_str, oc_id, cliente, cliente, cliente))
            cursor.execute("""
                UPDATE llantas_ciclos SET km_recorridos_ciclo = km_recorridos_ciclo + ?
                WHERE UPPER(numero_interno) = ? AND numero_ciclo = ?
                  AND (UPPER(cliente_propietario) = ? OR ? = '')
            """, (delta_oc, oc_serial, oc_ciclo, cli_efectivo, cli_efectivo))
            database.registrar_kardex(cursor, oc_serial, cli_efectivo, database.MONTADA, 'BODEGA_2_RECAMBIO',
                                      'DESMONTE_RECAMBIO', fecha=hoy_str, subcliente=subc or '', placa=placa,
                                      posicion=posicion, prof=oc_prof, km=odometro,
                                      motivo=f"Desmonte automático por montaje de {numero_interno}", usuario=user)

        # Montar llanta entrante
        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = ?,
                ubicacion_bodega = 'MONTADA_OPERACION',
                placa_actual = ?,
                posicion_actual = ?,
                km_montaje_actual = ?,
                km_actual_vehiculo = ?,
                cliente_propietario = ?,
                cliente = ?,
                fecha_ultimo_movimiento = ?
            WHERE id = ? AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ? OR ? = '')
        """, (database.nombre_ubicacion(database.MONTADA), placa, posicion, odometro, odometro, cli_efectivo, cli_efectivo,
              hoy_str, ll_id, cliente, cliente, cliente))

        # Kardex con el origen real (antes siempre decía Bodega 1)
        if es_reingreso:
            motivo_k = f"Reingreso desde {database.nombre_ubicacion(origen)}: {reingreso['motivo']}"
        elif origen == database.MONTADA:
            motivo_k = f"Rotación desde {placa_prev} posición {pos_prev}. {motivo}".strip()
        else:
            motivo_k = motivo
        tipo_k = 'REINGRESO_MONTAJE' if es_reingreso else ('ROTACION' if origen == database.MONTADA else 'MONTAJE')
        database.registrar_kardex(cursor, numero_interno, cli_efectivo, origen, database.MONTADA, tipo_k,
                                  fecha=hoy_str, subcliente=subc or '', placa=placa, posicion=posicion, vida=vida_act,
                                  prof=p_act, km=odometro, motivo=motivo_k,
                                  usuario=(reingreso['responsable'] if es_reingreso else user),
                                  foto=(reingreso['foto'] if es_reingreso else ''))

        conn.commit()

    vida_desc = database.vida_llanta(vida_act, ciclo=ciclo_act)
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
    Flujo 4 — Despacho en lote a la planta de reencauche. Solo cascos en Bodega 2 o en Bodega 3 sin
    despachar; se respeta el máximo de reencauches configurado para el cliente y la marca.
    """
    import database
    numeros = datos.get('numeros_internos') or datos.get('llantas_ids') or datos.get('llantas') or datos.get('numero_interno') or []
    if isinstance(numeros, (str, int)):
        numeros = [n.strip().upper() for n in str(numeros).split(',') if n.strip()]
    numeros = [str(n).strip().upper() for n in numeros if str(n).strip()]

    if not numeros:
        return {"ok": False, "status": "error", "mensaje": "Debe especificar al menos un número interno para despachar"}

    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    proveedor = str(datos.get('proveedor_planta', '')).strip()
    guia = str(datos.get('guia_remision') or datos.get('guia_remision_planta') or '').strip()
    transportador = str(datos.get('transportador', '')).strip()
    compromiso = str(datos.get('fecha_compromiso', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()
    if not proveedor or not guia:
        return {"ok": False, "status": "error", "mensaje": "Indique la planta reencauchadora y el número de guía del despacho"}

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    despachadas, rechazadas = [], []
    with database.get_connection() as conn:
        cursor = conn.cursor()
        for num in numeros:
            row = cursor.execute("""
                SELECT id, ubicacion_bodega, estado_actual, fecha_envio_planta, cliente, cliente_propietario,
                       subcliente, vida_actual, prof_actual_min, num_reencauches, marca
                FROM llantas_maestro
                WHERE UPPER(numero_interno) = ? AND (UPPER(cliente) = ? OR UPPER(cliente_propietario) = ? OR ? = '')
            """, (num, cliente, cliente, cliente)).fetchone()
            if not row:
                rechazadas.append(f"{num}: no existe en el inventario")
                continue
            ll_id, ubi, est, f_envio, cli_m, cli_p, subc, vida, prof, n_reen, marca = row
            origen = _ubicacion_actual(ubi, est)
            if origen == 'BODEGA_3_REENCAUCHE' and f_envio:
                rechazadas.append(f"{num}: ya fue despachada a planta el {f_envio}")
                continue
            if origen not in ('BODEGA_2_RECAMBIO', 'BODEGA_3_REENCAUCHE'):
                rechazadas.append(f"{num}: está en {database.nombre_ubicacion(origen) or est}, no en bodega de cascos")
                continue
            cli_ef = cli_m or cli_p or cliente
            tope = database.maximo_reencauches(cli_ef, marca)
            if tope is not None and database.to_int(n_reen) >= tope:
                rechazadas.append(f"{num}: ya tiene {database.to_int(n_reen)} reencauche(s), el máximo para {marca or 'esta marca'} es {tope}")
                continue
            cursor.execute("""
                UPDATE llantas_maestro SET
                    estado_actual = ?, ubicacion_bodega = 'BODEGA_3_REENCAUCHE',
                    proveedor_planta = ?, guia_remision_planta = ?, transportador_planta = ?,
                    fecha_envio_planta = ?, fecha_compromiso_planta = ?, fecha_ultimo_movimiento = ?
                WHERE id = ?
            """, (database.nombre_ubicacion('BODEGA_3_REENCAUCHE'), proveedor, guia, transportador, hoy_str, compromiso, hoy_str, ll_id))
            database.registrar_kardex(cursor, num, cli_ef, origen, 'BODEGA_3_REENCAUCHE', 'ENVIO_REENCAUCHE',
                                      fecha=hoy_str, subcliente=subc or '', vida=vida, prof=prof,
                                      proveedor=proveedor, motivo=f"Despacho con guía {guia}", documento=guia, usuario=user)
            despachadas.append(num)
        conn.commit()

    return {
        "ok": bool(despachadas),
        "status": "ok" if despachadas else "error",
        "despachadas": len(despachadas),
        "rechazadas": rechazadas,
        "guia": guia,
        "mensaje": f"{len(despachadas)} carcasas despachadas a planta con guía {guia}" + (f". No despachadas: {'; '.join(rechazadas)}" if rechazadas else ""),
        "message": f"{len(despachadas)} carcasas despachadas a planta con guía {guia}" + (f". No despachadas: {'; '.join(rechazadas)}" if rechazadas else "")
    }


def recepcionar_llanta_reencauchada(datos: dict) -> dict:
    """
    Flujo 5 — Recepción desde la planta y apertura de la nueva vida (R1, R2…). Solo se recibe una llanta
    que fue despachada a la planta; la profundidad y el diseño de la banda son obligatorios.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    banda_prov = str(datos.get('proveedor_banda', '')).strip()
    banda_diseno = str(datos.get('diseno_banda', '')).strip().upper()
    prof_nueva = database.to_float(datos.get('prof_banda_nueva'), 0.0)
    costo_renovado = database.to_float(datos.get('costo_factura_renovado'), 0.0)  # sin precio = 0: fuera de cálculos en pesos
    factura = str(datos.get('factura_renovado', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()
    if not banda_diseno or prof_nueva <= 0:
        return {"ok": False, "status": "error", "message": "Indique el diseño de la banda y su profundidad inicial (mm)"}

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    with database.get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT id, ubicacion_bodega, estado_actual, fecha_envio_planta, num_reencauches, ciclo_actual,
                   costo_reencauches_total, costo_acumulado_total, cliente, cliente_propietario, subcliente, marca
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ? AND (UPPER(cliente) = ? OR UPPER(cliente_propietario) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente)).fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}
        ll_id, ubi, est, f_envio, n_reen, ciclo, costo_reen_tot, costo_acum, cli_m, cli_p, subc, marca = row
        cli_efectivo = cli_m or cli_p or cliente
        origen = _ubicacion_actual(ubi, est)
        error = database.validar_transicion_llanta(origen, 'BODEGA_4_REENCAUCHADAS', enviada_planta=bool(f_envio))
        if error:
            return {"ok": False, "status": "error", "message": error}

        # La vida sale del número de reencauches (no de un ciclo que cada módulo contaba distinto)
        reen_ant = max(database.to_int(n_reen), database.to_int(ciclo, 1) - 1, 0)
        reen_nuevo = reen_ant + 1
        ciclo_ant, ciclo_nuevo = reen_ant + 1, reen_nuevo + 1

        cursor.execute("""
            UPDATE llantas_ciclos SET estado_ciclo = 'Cerrado_Por_Retiro', fecha_fin_ciclo = ?,
                   cpk_ciclo = CASE WHEN costo_ciclo > 0 THEN costo_ciclo / MAX(1.0, km_recorridos_ciclo) ELSE NULL END
            WHERE UPPER(numero_interno) = ? AND numero_ciclo = ? AND (UPPER(cliente_propietario) = ? OR ? = '')
        """, (hoy_str, numero_interno, ciclo_ant, cli_efectivo, cli_efectivo))
        cursor.execute("""
            INSERT INTO llantas_ciclos (
                numero_interno, cliente_propietario, numero_ciclo, tipo_ciclo, proveedor_banda, diseno_banda,
                prof_inicial_ciclo, prof_final_ciclo, km_inicial_ciclo, km_recorridos_ciclo, costo_ciclo, cpk_ciclo,
                factura_renovado, fecha_inicio_ciclo, estado_ciclo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0.0, 0.0, ?, NULL, ?, ?, 'En_Servicio')
        """, (numero_interno, cli_efectivo, ciclo_nuevo, f"R{reen_nuevo}", banda_prov, banda_diseno,
              prof_nueva, costo_renovado, factura, hoy_str))

        cursor.execute("""
            UPDATE llantas_maestro SET
                ciclo_actual = ?, vida_actual = ?, num_reencauches = ?, banda_reen = ?,
                prof_inicial = ?, prof_ext = ?, prof_cent = ?, prof_int = ?, prof_actual_min = ?,
                costo_ciclo_actual = ?, costo_reparaciones_ciclo_actual = 0, km_recorridos_ciclo = 0,
                costo_reencauches_total = ?, costo_acumulado_total = ?,
                estado_actual = ?, ubicacion_bodega = 'BODEGA_4_REENCAUCHADAS',
                fecha_envio_planta = NULL, fecha_compromiso_planta = NULL, fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (ciclo_nuevo, f"R{reen_nuevo}", reen_nuevo, banda_diseno,
              prof_nueva, prof_nueva, prof_nueva, prof_nueva, prof_nueva,
              costo_renovado, (costo_reen_tot or 0.0) + costo_renovado, (costo_acum or 0.0) + costo_renovado,
              database.nombre_ubicacion('BODEGA_4_REENCAUCHADAS'), hoy_str, ll_id))

        database.registrar_kardex(cursor, numero_interno, cli_efectivo, 'BODEGA_3_REENCAUCHE', 'BODEGA_4_REENCAUCHADAS',
                                  'RETORNO_REENCAUCHE', fecha=hoy_str, subcliente=subc or '', vida=f"R{reen_nuevo}",
                                  prof=prof_nueva, costo=costo_renovado, proveedor=banda_prov,
                                  motivo=f"Retorno de planta: vida R{reen_nuevo}, banda {banda_diseno}", documento=factura, usuario=user)
        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "ciclo_actual": ciclo_nuevo,
        "vida": f"R{reen_nuevo}",
        "mensaje": f"Llanta {numero_interno} recibida en Bodega 4 (Reencauchadas) como R{reen_nuevo}"
    }


def finalizar_reparacion_bodega5(datos: dict) -> dict:
    """
    Flujo 6 — Finalizar reparación (Bodega 5). Vuelve a Bodega 4 si es reencauchada y a Bodega 2 si es original.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    trabajo = str(datos.get('tipo_trabajo', '')).strip() or 'Reparación'
    costo_rep = database.to_float(datos.get('costo_reparacion', 0.0), 0.0)
    proveedor = str(datos.get('proveedor', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    with database.get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT id, ubicacion_bodega, estado_actual, ciclo_actual, cliente, cliente_propietario, subcliente,
                   vida_actual, prof_actual_min, num_reencauches
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ? AND (UPPER(cliente) = ? OR UPPER(cliente_propietario) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente)).fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}
        ll_id, ubi, est, ciclo_act, cli_m, cli_p, subc, vida, prof, n_reen = row
        cli_efectivo = cli_m or cli_p or cliente
        origen = _ubicacion_actual(ubi, est)
        if origen != 'BODEGA_5_REPARACION':
            return {"ok": False, "status": "error", "message": f"La llanta {numero_interno} no está en reparación ({database.nombre_ubicacion(origen) or est})"}
        destino = 'BODEGA_4_REENCAUCHADAS' if database.to_int(n_reen) > 0 or str(vida or '').upper().startswith('R') else 'BODEGA_2_RECAMBIO'

        cursor.execute("""
            UPDATE llantas_novedades_registro SET estado_novedad = 'Reparada'
            WHERE UPPER(numero_interno) = ? AND estado_novedad = 'Activa' AND (UPPER(cliente_propietario) = ? OR ? = '')
        """, (numero_interno, cli_efectivo, cli_efectivo))
        cursor.execute("""
            UPDATE llantas_ciclos SET costo_ciclo = costo_ciclo + ?
            WHERE UPPER(numero_interno) = ? AND numero_ciclo = ? AND (UPPER(cliente_propietario) = ? OR ? = '')
        """, (costo_rep, numero_interno, ciclo_act or 1, cli_efectivo, cli_efectivo))
        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = ?, ubicacion_bodega = ?,
                costo_reparaciones_total = IFNULL(costo_reparaciones_total, 0) + ?,
                costo_reparaciones_ciclo_actual = IFNULL(costo_reparaciones_ciclo_actual, 0) + ?,
                costo_acumulado_total = IFNULL(costo_acumulado_total, 0) + ?,
                fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (database.nombre_ubicacion(destino), destino, costo_rep, costo_rep, costo_rep, hoy_str, ll_id))
        database.registrar_kardex(cursor, numero_interno, cli_efectivo, 'BODEGA_5_REPARACION', destino, 'RETORNO_REPARACION',
                                  fecha=hoy_str, subcliente=subc or '', vida=vida, prof=prof, costo=costo_rep,
                                  proveedor=proveedor, motivo=f"{trabajo}" + (f" por {proveedor}" if proveedor else ""), usuario=user)
        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "mensaje": f"Reparación finalizada para {numero_interno}, trasladada a {database.nombre_ubicacion(destino)}"
    }


def procesar_dictamen_garantia_bodega6(datos: dict) -> dict:
    """
    Flujo 7 — Dictamen técnico de garantía de una llanta en FVU (Bodega 6). El dictamen no la saca del
    FVU: la disposición final (Bodega 7) se registra cuando la empresa ambiental la retira, con su acta.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    dictamen = str(datos.get('dictamen', '')).strip()
    pct_rec = database.to_float(datos.get('pct_reconocido', 0.0), 0.0)
    # La pantalla envía valor_reconocido (antes se leía valor_nota_credito y quedaba siempre en $0)
    valor_nc = database.to_float(datos.get('valor_reconocido', datos.get('valor_nota_credito', 0.0)), 0.0)
    user = str(datos.get('usuario_responsable', 'admin')).strip()
    if dictamen not in ('Aprobada', 'Rechazada'):
        return {"ok": False, "status": "error", "message": "Indique el dictamen: Aprobada o Rechazada"}

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    with database.get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT id, ubicacion_bodega, estado_actual, dinero_perdido_fvu, cliente, cliente_propietario, subcliente, vida_actual
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ? AND (UPPER(cliente) = ? OR UPPER(cliente_propietario) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente)).fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}
        ll_id, ubi, est, din_perd, cli_m, cli_p, subc, vida = row
        cli_efectivo = cli_m or cli_p or cliente
        if _ubicacion_actual(ubi, est) != 'BODEGA_6_FVU':
            return {"ok": False, "status": "error", "message": f"El dictamen de garantía aplica a llantas en FVU (Bodega 6); {numero_interno} está en {database.nombre_ubicacion(_ubicacion_actual(ubi, est)) or est}"}
        nuevo_dinero_perd = max(0.0, din_perd - valor_nc) if din_perd is not None else None
        estado_gar = 'Nota Crédito Reconocida' if dictamen == 'Aprobada' else 'Rechazada'

        cursor.execute("""
            UPDATE llantas_maestro SET
                dictamen_garantia = ?, estado_garantia = ?, pct_reconocido_garantia = ?,
                valor_reconocido_garantia = ?, dinero_perdido_fvu = ?, fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (dictamen, estado_gar, pct_rec, valor_nc, nuevo_dinero_perd, hoy_str, ll_id))
        database.registrar_kardex(cursor, numero_interno, cli_efectivo, 'BODEGA_6_FVU', 'BODEGA_6_FVU', 'AJUSTE_GARANTIA',
                                  fecha=hoy_str, subcliente=subc or '', vida=vida, costo=valor_nc,
                                  motivo=f"Garantía {dictamen} ({pct_rec}%)", usuario=user)
        conn.commit()

    return {
        "ok": True,
        "status": "ok",
        "mensaje": f"Dictamen de garantía procesado para {numero_interno}"
    }


def dar_baja_fvu_bodega7(datos: dict) -> dict:
    """
    Flujo 8 — Baja por fin de vida útil (primera fase del FVU, Bodega 6) y cálculo de la pérdida.
    La disposición final (Bodega 7) se registra después, con el acta de la empresa ambiental.
    """
    import database
    numero_interno = str(datos.get('numero_interno', '')).strip().upper()
    cliente = str(datos.get('cliente_propietario') or datos.get('cliente', '')).strip().upper()
    motivo = str(datos.get('motivo_baja', 'Fin de Vida Útil')).strip()
    prof_retiro_in = datos.get('prof_retiro')
    foto = str(datos.get('foto_baja', '')).strip()
    user = str(datos.get('usuario_responsable', 'admin')).strip()

    hoy_str = datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d')
    with database.get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT id, ubicacion_bodega, estado_actual, prof_actual_min, prof_inicial, prof_inicial_nueva,
                   costo_ciclo_actual, valor_reconocido_garantia, ciclo_actual, cliente, cliente_propietario,
                   subcliente, vida_actual, placa_actual, posicion_actual
            FROM llantas_maestro
            WHERE UPPER(numero_interno) = ? AND (UPPER(cliente) = ? OR UPPER(cliente_propietario) = ? OR ? = '')
        """, (numero_interno, cliente, cliente, cliente)).fetchone()
        if not row:
            return {"ok": False, "status": "error", "message": f"No se encontró la llanta {numero_interno}"}
        (ll_id, ubi, est, p_act, p_ini_m, p_ini_n, c_ciclo, val_gar, ciclo_act, cli_m, cli_p,
         subc, vida, placa_act, pos_act) = row
        cli_efectivo = cli_m or cli_p or cliente
        origen = _ubicacion_actual(ubi, est)
        error = database.validar_transicion_llanta(origen, 'BODEGA_6_FVU')
        if error:
            return {"ok": False, "status": "error", "message": error}

        p_ret = database.to_float(prof_retiro_in, p_act or 0.0)
        p_ini = database.to_float(p_ini_m) or database.to_float(p_ini_n)
        c_ciclo = database.to_float(c_ciclo, 0.0)
        val_gar = database.to_float(val_gar, 0.0)
        cfg = database.obtener_configuracion_avanzada_cliente(cli_efectivo)
        lim_ret = database.to_float(cfg.get('mm_retiro_traccion', 3.0), 3.0)
        mm_desperdiciados = max(0.0, p_ret - lim_ret)
        denominador = max(1.0, p_ini - lim_ret)
        dinero_perdido = max(0.0, (mm_desperdiciados * (c_ciclo / denominador)) - val_gar) if (c_ciclo > 0 and p_ini > 0) else None

        cursor.execute("""
            UPDATE llantas_ciclos SET estado_ciclo = 'Desechado', fecha_fin_ciclo = ?, prof_final_ciclo = ?
            WHERE UPPER(numero_interno) = ? AND numero_ciclo = ? AND (UPPER(cliente_propietario) = ? OR ? = '')
        """, (hoy_str, p_ret, numero_interno, ciclo_act or 1, cli_efectivo, cli_efectivo))
        cursor.execute("""
            UPDATE llantas_maestro SET
                estado_actual = ?, ubicacion_bodega = 'BODEGA_6_FVU', placa_actual = '', posicion_actual = 0,
                fecha_baja = ?, motivo_baja = ?, causal_baja_fvu = ?, foto_baja = ?,
                mm_desperdiciados_fvu = ?, mm_perdidos_fvu = ?, dinero_perdido_fvu = ?, fecha_ultimo_movimiento = ?
            WHERE id = ?
        """, (database.nombre_ubicacion('BODEGA_6_FVU'), hoy_str, motivo, motivo, foto,
              mm_desperdiciados, mm_desperdiciados, dinero_perdido, hoy_str, ll_id))
        database.registrar_kardex(cursor, numero_interno, cli_efectivo, origen, 'BODEGA_6_FVU', 'BAJA_FVU',
                                  fecha=hoy_str, subcliente=subc or '', placa=placa_act, posicion=pos_act, vida=vida,
                                  prof=p_ret, motivo=motivo, usuario=user, foto=foto)
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
        cli_filtro = str(ll.get('cliente') or ll.get('cliente_propietario') or cliente or '').strip().upper()

        # Ciclos de vida
        cursor.execute("""
            SELECT numero_ciclo, tipo_ciclo, prof_inicial_ciclo, prof_final_ciclo,
                   km_recorridos_ciclo, costo_ciclo, cpk_ciclo, diseno_banda, estado_ciclo,
                   fecha_inicio_ciclo, fecha_fin_ciclo
            FROM llantas_ciclos
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente_propietario) = ? OR ? = '')
            ORDER BY numero_ciclo ASC
        """, (numero_interno, cli_filtro, cli_filtro))
        cols_c = [d[0] for d in cursor.description]
        ciclos_raw = [dict(zip(cols_c, r)) for r in cursor.fetchall()]

        # Movimientos: el kardex es la fuente oficial (Bodegas y Taller registran ahí)
        cursor.execute("""
            SELECT fecha_movimiento, tipo_movimiento, bodega_origen, bodega_destino,
                   placa, posicion, km_vehiculo AS odometro_vehiculo, prof_min_mm AS profundidad_momento,
                   costo_asociado, causal_o_motivo AS motivo, usuario_registro AS usuario_responsable,
                   vida_ciclo, documento_soporte, foto_soporte
            FROM kardex_movimientos_llanta
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente) = ? OR ? = '')
            ORDER BY fecha_movimiento DESC, id DESC
        """, (numero_interno, cli_filtro, cli_filtro))
        cols_mov = [d[0] for d in cursor.description]
        movs_raw = [dict(zip(cols_mov, r)) for r in cursor.fetchall()]

        # Novedades
        cursor.execute("""
            SELECT fecha_deteccion, tipo_novedad, categoria_severidad, estado_novedad,
                   placa, posicion, observacion, foto_url
            FROM llantas_novedades_registro
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente_propietario) = ? OR ? = '')
            ORDER BY fecha_deteccion DESC, id DESC
        """, (numero_interno, cli_filtro, cli_filtro))
        cols_nov = [d[0] for d in cursor.description]
        novedades_raw = [dict(zip(cols_nov, r)) for r in cursor.fetchall()]

        # Inspecciones históricas de esta llanta
        cursor.execute("""
            SELECT fecha, placa, posicion, kilometraje, prof_ext, prof_cent, prof_int, psi, novedades
            FROM inspecciones
            WHERE UPPER(numero_interno) = ?
              AND (UPPER(cliente) = ? OR ? = '')
            ORDER BY fecha ASC, id ASC
        """, (numero_interno, cli_filtro, cli_filtro))
        insps = cursor.fetchall()

    # Consolidar métricas
    km_totales = database.to_float(ll.get('km_acumulados_total', 0.0))
    if not km_totales and ciclos_raw:
        km_totales = sum(database.to_float(c.get('km_recorridos_ciclo', 0.0)) for c in ciclos_raw)

    costo_total = database.to_float(ll.get('costo_acumulado_total', 0.0))
    if not costo_total and ciclos_raw:
        costo_total = sum(database.to_float(c.get('costo_ciclo', 0.0)) for c in ciclos_raw)

    if not costo_total:
        costo_total = database.to_float(ll.get('precio_compra_inicial'), 0.0)

    # Sin costo registrado no hay CPK (antes se usaba $1.450.000)
    cpk_global = round(costo_total / max(1.0, km_totales), 4) if costo_total > 0 else None

    # Calcular mm gastados para rendimiento km/mm
    mm_gastados_tot = 0.0
    for c in ciclos_raw:
        p_i = database.to_float(c.get('prof_inicial_ciclo', 16.0), 16.0)
        p_f = database.to_float(c.get('prof_final_ciclo', ll.get('prof_actual_min', 3.0)), 3.0)
        mm_gastados_tot += max(0.0, p_i - p_f)

    rendimiento_km_mm = round(km_totales / max(1.0, mm_gastados_tot), 1)

    # Ahorro vs Llanta Nueva
    p_compra_ini = database.to_float(ll.get('precio_compra_inicial'), 0.0)
    ciclo_1_km = ciclos_raw[0].get('km_recorridos_ciclo', 0.0) if ciclos_raw else km_totales
    if p_compra_ini > 0 and costo_total > 0:
        cpk_nueva_estimado = p_compra_ini / max(1.0, ciclo_1_km)
        costo_proyectado_solo_nuevas = km_totales * cpk_nueva_estimado
        ahorro_generado = max(0.0, round(costo_proyectado_solo_nuevas - costo_total, 2))
    else:
        ahorro_generado = None

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
        b_o, b_d = m.get('bodega_origen', ''), m.get('bodega_destino', '')
        historial_formateado.append({
            # La pantalla lee estos nombres (antes recibía evento/fecha/detalle y mostraba "undefined")
            "fecha_movimiento": str(m.get('fecha_movimiento', ''))[:19],
            "tipo_movimiento": m.get('tipo_movimiento', ''),
            "bodega_origen": database.nombre_ubicacion(b_o) if b_o in database.UBICACIONES_LLANTA else b_o,
            "bodega_destino": database.nombre_ubicacion(b_d) if b_d in database.UBICACIONES_LLANTA else b_d,
            "placa": m.get('placa', ''),
            "posicion": m.get('posicion', 0),
            "odometro_vehiculo": m.get('odometro_vehiculo', 0.0),
            "profundidad_momento": m.get('profundidad_momento', 0.0),
            "costo_asociado": m.get('costo_asociado', 0.0),
            "vida": m.get('vida_ciclo', ''),
            "motivo": m.get('motivo', ''),
            "responsable": m.get('usuario_responsable', ''),
            "documento_soporte": m.get('documento_soporte', ''),
            "foto_soporte": m.get('foto_soporte', ''),
            # nombres anteriores, por compatibilidad
            "fecha": str(m.get('fecha_movimiento', ''))[:19],
            "evento": m.get('tipo_movimiento', ''),
            "detalle": m.get('motivo', ''),
            "profundidad_mm": m.get('profundidad_momento', 0.0)
        })

    vida_nombre = database.vida_llanta(ll.get('vida_actual'), ll.get('num_reencauches'), ll.get('ciclo_actual'))

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
            "estado": database.nombre_ubicacion(_ubicacion_actual(ll.get('ubicacion_bodega'), ll.get('estado_actual'))),
            "ubicacion_bodega": _ubicacion_actual(ll.get('ubicacion_bodega'), ll.get('estado_actual')),
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
            WHERE UPPER(placa_actual) = ? AND posicion_actual = ? AND ubicacion_bodega = 'MONTADA_OPERACION'
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
                "vida": database.vida_llanta(r_inst[12], ciclo=r_inst[11]),
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
            SELECT id, numero_interno, ubicacion_bodega, marca_origen, diseno_origen, marca, diseno,
                   dimension, prof_inicial, prof_actual_min, ciclo_actual, vida_actual, num_reencauches
            FROM llantas_maestro
            WHERE ubicacion_bodega IN ('BODEGA_1_NUEVAS', 'BODEGA_2_RECAMBIO', 'BODEGA_4_REENCAUCHADAS')
        """
        params_s = []
        if cliente and cliente != "TODOS":
            query_stock += " AND (UPPER(cliente_propietario) = ? OR UPPER(cliente) = ?)"
            params_s.extend([cliente, cliente])

        query_stock += " ORDER BY ubicacion_bodega ASC, prof_actual_min DESC"
        cursor.execute(query_stock, params_s)
        stock_raw = cursor.fetchall()

        stock_disponible = []
        for r_s in stock_raw:
            c_num = r_s[10] or 1
            v_act = database.vida_llanta(r_s[11], r_s[12], c_num)
            # Si la posición es direccional, excluir reencauches
            if es_direccional and v_act != 'Original':
                continue

            stock_disponible.append({
                "id": r_s[0],
                "numero_interno": r_s[1],
                "bodega": database.nombre_ubicacion(r_s[2]),
                "marca": r_s[3] or r_s[5],
                "diseno": r_s[4] or r_s[6],
                "dimension": r_s[7],
                "prof_inicial": r_s[8],
                "profundidad_actual": r_s[9],
                "ciclo_actual": c_num,
                "vida": v_act
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
    sedes_f = [str(x).strip().upper() for x in (filtros.get('sedes') or []) if str(x).strip()]
    if sedes_f:  # usuario limitado a ciertas sedes
        query += f" AND UPPER(IFNULL(subcliente, '')) IN ({', '.join(['?'] * len(sedes_f))})"
        params.extend(sedes_f)
    if ubicacion and ubicacion != "TODAS":
        query += " AND ubicacion_bodega = ?"
        params.append(normalizar_estado_bodega(ubicacion) or ubicacion.upper())
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
            est = _ubicacion_actual(r_all[1], r_all[0])
            costo = database.to_float(r_all[2] or r_all[3], 0.0)
            kpis["total_llantas"]["cantidad"] += 1
            kpis["total_llantas"]["valor_cop"] += costo

            if est == 'BODEGA_1_NUEVAS':
                kpis["b1_nuevas"]["cantidad"] += 1
                kpis["b1_nuevas"]["valor_cop"] += costo
            elif est == 'BODEGA_2_RECAMBIO':
                kpis["b2_reutilizable"]["cantidad"] += 1
                kpis["b2_reutilizable"]["valor_cop"] += costo
            elif est == 'BODEGA_3_REENCAUCHE':
                kpis["b3_reencauche"]["cantidad"] += 1
                kpis["b3_reencauche"]["valor_cop"] += costo
            elif est == 'BODEGA_4_REENCAUCHADAS':
                kpis["b4_enplanta"]["cantidad"] += 1
                kpis["b4_enplanta"]["valor_cop"] += costo
            elif est == 'BODEGA_5_REPARACION':
                kpis["b5_reparacion"]["cantidad"] += 1
                kpis["b5_reparacion"]["valor_cop"] += costo
            elif est == 'BODEGA_6_FVU':
                kpis["b6_garantia"]["cantidad"] += 1
                kpis["b6_garantia"]["valor_cop"] += costo
            elif est == 'BODEGA_7_CHATARRIZADA':
                kpis["b7_chatarra"]["cantidad"] += 1
                kpis["b7_chatarra"]["valor_cop"] += costo
            elif est == database.MONTADA:
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
            item["estado_display"] = database.nombre_ubicacion(_ubicacion_actual(item.get("ubicacion_bodega"), item.get("estado_actual")))
            item["reservada_para_dual"] = bool(item.get("reservada_para_placa"))

    return {
        "total": len(llantas),
        "llantas": llantas,
        "kpis": kpis,
        "resumen_kpis": kpis
    }
