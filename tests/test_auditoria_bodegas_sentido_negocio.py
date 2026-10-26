"""
Suite de Pruebas de Estrés y Sentido de Negocio
Módulo de Las 7 Bodegas, Kardex, Garantías y Balance MRP (KPI 20)
Auditoría Senior de Operaciones de Flota y Control de Calidad QA
"""

import pytest
import database
import server
import pandas as pd


def test_bloqueo_reencauche_en_eje_direccional_desde_bodega(test_db, auth_client):
    """
    Regla 2: Candado de Seguridad Vial al Montar desde Bodega hacia un Vehículo.
    Crea una llanta en BODEGA_4_REENCAUCHADAS (vida_actual = 'R1') e intenta moverla
    a MONTADA_OPERACION en un Cabezote (6x4) en posicion = 1.
    Verifica que el backend responda HTTP 400 bloqueando el montaje por seguridad vial,
    pero que sí permita montarla en posicion = 3 (tracción).
    """
    cliente = "FLOTA TRANSPORTE SEGURO"
    placa = "CAB-604"
    numero_interno = "LL-REEN-DIR-01"

    # Registrar vehículo en catálogo como CABEZOTE 6X4
    database.sincronizar_vehiculo_catalogo(placa, "CABEZOTE 6X4", cliente, "BOGOTA", "Troncal", 120000.0)

    # 1. Crear llanta reencauchada en Bodega 4
    res_alta = auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "ubicacion_bodega": "BODEGA_4_REENCAUCHADAS",
        "marca": "BRIDGESTONE",
        "dimension": "295/80R22.5",
        "vida_actual": "R1",
        "prof_inicial": 20.0,
        "prof_actual_min": 20.0,
        "costo_compra": 650000.0
    })
    assert res_alta.status_code == 200, res_alta.text

    # 2. Intentar montarla en Posición 1 (Direccional) -> Debe ser rechazada con HTTP 400
    res_mont_dir = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": placa,
        "posicion": 1,
        "km_vehiculo": 120000.0
    })
    assert res_mont_dir.status_code == 400
    assert "CANDADO VIAL" in res_mont_dir.text or "direccional" in res_mont_dir.text

    # 3. Montarla en Posición 3 (Tracción) -> Debe permitirse exitosamente
    res_mont_trac = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": placa,
        "posicion": 3,
        "km_vehiculo": 120000.0
    })
    assert res_mont_trac.status_code == 200
    assert res_mont_trac.json()["ok"] is True

    # Verificar en inventario
    inv = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={numero_interno}").json()["llantas"][0]
    assert inv["ubicacion_bodega"] == "MONTADA_OPERACION"
    assert inv["placa_actual"] == placa
    assert inv["posicion_actual"] == 3


def test_bloqueo_transiciones_invalidas_y_chatarrizada_inmutable(test_db, auth_client):
    """
    Regla 3: Máquina de Estados Estricta.
    Lleva una llanta hasta BODEGA_7_CHATARRIZADA con acta ambiental e intenta moverla
    de nuevo a BODEGA_2_RECAMBIO o MONTADA_OPERACION.
    Verifica que devuelva HTTP 400 impidiendo revivir una llanta chatarrizada.
    También valida que una llanta nueva no se envíe directo a reencauche,
    ni se mueva a la misma bodega de manera redundante.
    """
    cliente = "FLOTA CICLO LIMPIO"
    serial_chatarra = "LL-CHATARRA-01"
    serial_nueva = "LL-NUEVA-01"

    # 1. Crear y llevar llanta hasta Bodega 7 Chatarrizada
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial_chatarra,
        "ubicacion_bodega": "BODEGA_6_FVU",
        "marca": "GOODYEAR",
        "dimension": "295/80R22.5",
        "prof_actual_min": 2.0
    }).raise_for_status()

    res_chat = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial_chatarra,
        "bodega_destino": "BODEGA_7_CHATARRIZADA",
        "documento_soporte": "ACTA-AMB-999"
    })
    assert res_chat.status_code == 200

    # Intentar revivir llanta chatarrizada hacia Bodega 2 -> HTTP 400
    res_revivir_b2 = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial_chatarra,
        "bodega_destino": "BODEGA_2_RECAMBIO"
    })
    assert res_revivir_b2.status_code == 400
    assert "chatarrizada" in res_revivir_b2.json()["detail"].lower()

    # Intentar montar llanta chatarrizada en un camión -> HTTP 400
    res_revivir_mont = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial_chatarra,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": "TRK-001",
        "posicion": 3
    })
    # Solo puede volver a montarse dejando trazabilidad del reingreso (motivo, responsable y foto)
    assert res_revivir_mont.status_code == 400
    assert "foto" in res_revivir_mont.json()["detail"].lower()

    # 2. Alta de llanta nueva y probar enviar directo a reencauche (Bodega 3) -> HTTP 400
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial_nueva,
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "MICHELIN",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "prof_actual_min": 18.0
    })

    res_nueva_a_reen = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial_nueva,
        "bodega_destino": "BODEGA_3_REENCAUCHE"
    })
    assert res_nueva_a_reen.status_code == 400
    assert "nueva" in res_nueva_a_reen.json()["detail"].lower()

    # 3. Mover a la misma bodega redundante -> HTTP 400
    res_redundante = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial_nueva,
        "bodega_destino": "BODEGA_1_NUEVAS"
    })
    assert res_redundante.status_code == 400


def test_mrp_no_cubre_demanda_direccional_con_reencauches(test_db, auth_client):
    """
    Regla 1: Prohibido cubrir Demanda Direccional con Llantas Reencauchadas en el MRP (KPI 20).
    Configura un cliente con 2 llantas direccionales en retiro (Pos 1 y Pos 2 <= 3.0 mm),
    0 llantas en BODEGA_1_NUEVAS y 10 llantas listas en BODEGA_4_REENCAUCHADAS.
    Consulta GET /api/bodegas/resumen-mrp y verifica que compra_nuevas_direccional == 2
    y compra_neta_sugerida >= 2.
    """
    cliente = "FLOTA LOGISTICA MRP DIRECCIONAL"
    dim = "295/80R22.5"

    with database.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO configuracion_avanzada_cliente (
                cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion,
                porcentaje_aprobacion_reencauche, stock_seguridad_default
            ) VALUES (?, 'PRO', 3.0, 3.0, 85.0, 0)
        """, (cliente,))

        # Vehículo con Pos 1 y Pos 2 en límite de retiro (2.5 mm)
        conn.execute("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, placa, posicion, tipologia, marca, dimension,
                prof_ext, prof_cent, prof_int, prof_inicial, numero_interno
            ) VALUES
            ('2026-10-18', ?, 'BOGOTA', 'DIR-101', 1, 'CABEZOTE 6X4', 'MICHELIN', ?, 2.5, 2.5, 2.5, 18.0, 'LL-DIR-01'),
            ('2026-10-18', ?, 'BOGOTA', 'DIR-101', 2, 'CABEZOTE 6X4', 'MICHELIN', ?, 2.5, 2.5, 2.5, 18.0, 'LL-DIR-02')
        """, (cliente, dim, cliente, dim))
        conn.commit()

    # Dar de alta 10 llantas en BODEGA_4_REENCAUCHADAS (Stock abundante de reencauches)
    for i in range(1, 11):
        auth_client.post("/api/bodegas/alta", json={
            "cliente": cliente,
            "numero_interno": f"LL-REENC-STOCK-{i}",
            "ubicacion_bodega": "BODEGA_4_REENCAUCHADAS",
            "marca": "BANDAG",
            "dimension": dim,
            "vida_actual": "R1",
            "prof_inicial": 20.0,
            "costo_compra": 650000.0
        })

    # Consultar balance MRP
    res_mrp = auth_client.get(f"/api/bodegas/resumen-mrp?cliente={cliente}&dimension={dim}")
    assert res_mrp.status_code == 200
    data = res_mrp.json()

    assert len(data["matriz_mrp"]) >= 1
    mrp_item = data["matriz_mrp"][0]

    # Demanda direccional = 2
    assert mrp_item["demanda_direccional"] == 2
    # Bodega 1 Nuevas = 0
    assert mrp_item["b1_nuevas"] == 0
    # Bodega 4 Reencauchadas = 10
    assert mrp_item["b4_reenc_listas"] == 10

    # REGLA DE ORO: Las 10 llantas reencauchadas NO pueden cubrir las 2 direccionales requeridas
    assert mrp_item["compra_nuevas_direccional"] == 2
    assert mrp_item["compra_neta_sugerida"] >= 2


def test_cruce_bodega_2_excluye_llantas_gastadas_y_no_repite_serial(test_db, auth_client):
    """
    Regla 6: Filtro de Calidad en Cruce de Duales con BODEGA_2_RECAMBIO (KPI 08).
    Inserta en BODEGA_2_RECAMBIO dos llantas: LL-GASTADA (2.8 mm) y LL-BUENA (11.5 mm).
    Inserta dos camiones distintos (CAM-01 y CAM-02) que necesitan aparear un dual
    con una llanta compañera de 12.0 mm.
    Ejecuta GET /api/diagnostico y verifica que LL-GASTADA jamás sea recomendada,
    y que LL-BUENA se asigne únicamente al primer camión sin duplicarse en el segundo.
    """
    cliente = "FLOTA DUALES INTELIGENTES"
    dim = "295/80R22.5"

    with database.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO configuracion_avanzada_cliente (
                cliente, tipo_licencia, mm_retiro_traccion, mm_retiro_direccional
            ) VALUES (?, 'PRO', 3.0, 3.0)
        """, (cliente,))

        # Insertar llanta gastada en Bodega 2 (2.8 mm <= 3.0 + 1.5 = 4.5 mm)
        conn.execute("""
            INSERT INTO llantas_maestro (
                numero_interno, cliente, ubicacion_bodega, estado_actual,
                marca, dimension, prof_actual_min, costo_ciclo_actual
            ) VALUES ('LL-GASTADA', ?, 'BODEGA_2_RECAMBIO', 'En Stock - Reutilizable', 'MICHELIN', ?, 2.8, 1500000.0)
        """, (cliente, dim))

        # Insertar llanta buena en Bodega 2 (11.5 mm, apta para pacha de 12.0 mm)
        conn.execute("""
            INSERT INTO llantas_maestro (
                numero_interno, cliente, ubicacion_bodega, estado_actual,
                marca, dimension, prof_actual_min, costo_ciclo_actual
            ) VALUES ('LL-BUENA', ?, 'BODEGA_2_RECAMBIO', 'En Stock - Reutilizable', 'MICHELIN', ?, 11.5, 1500000.0)
        """, (cliente, dim))

        # Camión 1: Pacha Pos 3 (12.0 mm) y Pos 4 (5.0 mm) -> Desapareo severo 7.0 mm > 2.0 mm
        conn.execute("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, placa, posicion, tipologia, marca, dimension,
                prof_ext, prof_cent, prof_int, prof_inicial, numero_interno
            ) VALUES
            ('2026-10-18', ?, 'CALI', 'CAM-01', 3, 'CABEZOTE 6X4', 'MICHELIN', ?, 12.0, 12.0, 12.0, 18.0, 'LL-C1-P3'),
            ('2026-10-18', ?, 'CALI', 'CAM-01', 4, 'CABEZOTE 6X4', 'MICHELIN', ?, 5.0, 5.0, 5.0, 18.0, 'LL-C1-P4')
        """, (cliente, dim, cliente, dim))

        # Camión 2: Pacha Pos 3 (12.0 mm) y Pos 4 (5.0 mm) -> Idéntica necesidad
        conn.execute("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, placa, posicion, tipologia, marca, dimension,
                prof_ext, prof_cent, prof_int, prof_inicial, numero_interno
            ) VALUES
            ('2026-10-18', ?, 'CALI', 'CAM-02', 3, 'CABEZOTE 6X4', 'MICHELIN', ?, 12.0, 12.0, 12.0, 18.0, 'LL-C2-P3'),
            ('2026-10-18', ?, 'CALI', 'CAM-02', 4, 'CABEZOTE 6X4', 'MICHELIN', ?, 5.0, 5.0, 5.0, 18.0, 'LL-C2-P4')
        """, (cliente, dim, cliente, dim))
        conn.commit()

    # Ejecutar diagnóstico
    res_diag = auth_client.get(f"/api/diagnostico?cliente={cliente}")
    assert res_diag.status_code == 200
    filas = res_diag.json()

    # Encontrar las recomendaciones de ambos camiones
    def obtener_rec_dual(fila):
        return fila.get("Recomendaciones_Dual") or fila.get("recomendacion_dual") or fila.get("recomendaciones_dual") or ""

    def coincide_placa(fila, target):
        for k in ["Vehículo/Placa", "Vehiculo/Placa", "Placa", "placa"]:
            if fila.get(k) == target:
                return True
        for k, v in fila.items():
            if "placa" in k.lower() and v == target:
                return True
        return False

    recs_cam01 = [f for f in filas if coincide_placa(f, "CAM-01")]
    recs_cam02 = [f for f in filas if coincide_placa(f, "CAM-02")]

    texto_cam01 = " ".join([obtener_rec_dual(f) for f in recs_cam01])
    texto_cam02 = " ".join([obtener_rec_dual(f) for f in recs_cam02])
    todos_textos = texto_cam01 + " " + texto_cam02

    # 1. LL-GASTADA jamás debe ser recomendada
    assert "LL-GASTADA" not in todos_textos, "Error: Se recomendó una llanta gastada de Bodega 2"

    # 2. LL-BUENA debe estar en CAM-01 pero NO repetirse en CAM-02
    assert "LL-BUENA" in texto_cam01
    assert "LL-BUENA" not in texto_cam02, "Error: LL-BUENA se recomendó para dos camiones simultáneamente"


def test_contabilidad_exacta_bodega_5_y_reinicio_en_reencauche_bodega_4(test_db, auth_client):
    """
    Regla 5: No Duplicar el Costo de Reparación en BODEGA_5_REPARACION y Reinicio en Reencauche.
    Verifica que una llanta de $1.500.000 que pasa por BODEGA_5_REPARACION ($150.000)
    y rueda 33.000 km tenga CPK = 1.650.000 / 33.000 = $50,0/km.
    Luego se envía a BODEGA_3_REENCAUCHE -> BODEGA_4_REENCAUCHADAS con costo de $700.000.
    Comprueba que en su nueva vida (R1) su costo_ciclo_actual == 700000,
    costo_reparaciones_ciclo_actual == 0 y costo_acumulado_total == 2350000.
    """
    cliente = "FLOTA CONTABILIDAD EXACTA"
    serial = "LL-CPK-01"

    # 1. Alta nueva por $1.500.000
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial,
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "GOODYEAR",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "costo_compra": 1500000.0
    })

    # 2. Montar en camión y rodar 33.000 km
    auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": "TRK-888",
        "posicion": 3,
        "km_vehiculo": 33000.0
    })

    # Actualizar kilometraje rodado del ciclo
    with database.get_connection() as conn:
        conn.execute("UPDATE llantas_maestro SET km_recorridos_ciclo = 33000.0 WHERE numero_interno = ?", (serial,))
        conn.commit()

    # 3. Envío a Reparación Bodega 5
    res_env_rep = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_5_REPARACION",
        "proveedor": "VULCANIZADORA MASTER"
    })
    assert res_env_rep.status_code == 200

    # Retorno de reparación a Bodega 2 con costo de $150.000
    res_ret_rep = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_2_RECAMBIO",
        "costo_asociado": 150000.0,
        "causal_o_motivo": "Reparación sección lateral"
    })
    assert res_ret_rep.status_code == 200

    # Comprobar contabilidad del primer ciclo
    ll_rep = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert ll_rep["costo_ciclo_actual"] == 1500000.0
    assert ll_rep["costo_reparaciones_ciclo_actual"] == 150000.0
    assert ll_rep["costo_acumulado_total"] == 1650000.0

    costo_total_primer_ciclo = ll_rep["costo_ciclo_actual"] + ll_rep["costo_reparaciones_ciclo_actual"]
    cpk_primer_ciclo = costo_total_primer_ciclo / 33000.0
    assert round(cpk_primer_ciclo, 2) == 50.0

    # 4. Enviar a Bodega 3 (Reencauche)
    res_reen_env = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_3_REENCAUCHE",
        "proveedor": "PLANTA BANDAG"
    })
    assert res_reen_env.status_code == 200

    # Retornar de reencauche a Bodega 4 con costo de $700.000 y prof 20.0 mm
    res_reen_ret = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_4_REENCAUCHADAS",
        "costo_asociado": 700000.0,
        "nueva_prof_inicial": 20.0,
        "banda_reen": "BDM"
    })
    assert res_reen_ret.status_code == 200

    # 5. Comprobar reinicio de contabilidad en nueva vida R1
    ll_r1 = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert ll_r1["vida_actual"] == "R1"
    assert ll_r1["costo_ciclo_actual"] == 700000.0
    assert ll_r1["costo_reparaciones_ciclo_actual"] == 0.0
    assert ll_r1["costo_acumulado_total"] == 2350000.0  # 1.650.000 + 700.000


def test_bodega_6_fvu_garantia_automatica_y_tope_nota_credito(test_db, auth_client):
    """
    Regla 7: Cálculo Realista de Pérdida Financiera y Garantías en BODEGA_6_FVU (KPI 17, 18, 19).
    Envía una llanta casi nueva (Pini = 18.0 mm, Pmin = 15.0 mm, desgaste 20% < 30%) a BODEGA_6_FVU.
    Verifica que se active estado_garantia == 'Posible Garantía'.
    Aplica una nota de crédito y verifica el descuento exacto en dinero_perdido_fvu
    sin permitir saldos negativos.
    """
    cliente = "FLOTA GARANTIAS QA"
    serial = "LL-GARANTIA-01"

    with database.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_traccion)
            VALUES (?, 'PRO', 3.0)
        """, (cliente,))
        conn.commit()

    # 1. Alta nueva con 18.0 mm y costo $1.500.000
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial,
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "MICHELIN",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "prof_actual_min": 15.0,
        "costo_compra": 1500000.0
    })

    # 2. Desecho prematuro a Bodega 6 por daño de fábrica
    # Desgaste: (18 - 15) / (18 - 3) = 3 / 15 = 20% < 30% -> Debe marcar 'Posible Garantía'
    res_baja = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_6_FVU",
        "prof_min_mm": 15.0,
        "causal_o_motivo": "Separación de banda por defecto de vulcanización"
    })
    assert res_baja.status_code == 200

    inv_fvu = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_fvu["ubicacion_bodega"] == "BODEGA_6_FVU"
    assert inv_fvu["estado_garantia"] == "Posible Garantía"

    # mm_perdidos_fvu = 15.0 - 3.0 = 12.0 mm
    assert inv_fvu["mm_perdidos_fvu"] == 12.0
    dinero_perdido_original = inv_fvu["dinero_perdido_fvu"]
    assert dinero_perdido_original > 0

    # 3. Aplicar Nota de Crédito por valor parcial (ej. $500.000)
    res_nc = auth_client.post("/api/bodegas/garantia", json={
        "cliente": cliente,
        "numero_interno": serial,
        "estado_garantia": "Nota Crédito Reconocida",
        "valor_reconocido_garantia": 500000.0
    })
    assert res_nc.status_code == 200
    nuevo_dinero_perdido = res_nc.json()["dinero_perdido_fvu"]
    assert round(nuevo_dinero_perdido, 2) == round(dinero_perdido_original - 500000.0, 2)

    # 4. Probar que una nota de crédito astronómica no genera saldos negativos
    res_nc_max = auth_client.post("/api/bodegas/garantia", json={
        "cliente": cliente,
        "numero_interno": serial,
        "estado_garantia": "Nota Crédito Reconocida",
        "valor_reconocido_garantia": 3000000.0
    })
    assert res_nc_max.status_code == 200
    assert res_nc_max.json()["dinero_perdido_fvu"] == 0.0


def test_sincronizacion_inspecciones_no_sobreescribe_bajas_fvu(test_db, auth_client):
    """
    Regla 4: Respeto de Estado en sincronizar_maestro_desde_inspecciones().
    Da de baja una llanta en BODEGA_6_FVU, ejecuta database.sincronizar_maestro_desde_inspecciones()
    y comprueba que la llanta permanezca en BODEGA_6_FVU y no regrese a MONTADA_OPERACION.
    """
    cliente = "FLOTA PERSISTENCIA FVU"
    serial = "LL-BAJA-PERSISTENTE"
    placa = "VEH-999"

    # 1. Registrar inspección en patio con fecha de hace 15 días (2026-10-01)
    database.insertar_inspeccion({
        "cliente": cliente,
        "subcliente": "CALI",
        "placa": placa,
        "posicion": 3,
        "tipologia": "CABEZOTE 6X4",
        "marca": "GOODYEAR",
        "diseno": "KMAX D",
        "dimension": "295/80R22.5",
        "vida": "ORIGINAL",
        "prof_ext": 10.0,
        "prof_cent": 10.0,
        "prof_int": 10.0,
        "prof_inicial": 18.0,
        "numero_interno": serial,
        "kilometraje": 60000.0,
        "fecha": "2026-10-01"
    })

    # Verificar que tras la inspección quedó MONTADA_OPERACION
    inv1 = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv1["ubicacion_bodega"] == "MONTADA_OPERACION"

    # 2. El 2026-10-18 la llanta sufre daño catastrófico y se traslada a BODEGA_6_FVU
    res_baja = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_6_FVU",
        "fecha_movimiento": "2026-10-18",
        "prof_min_mm": 9.0,
        "causal_o_motivo": "Corte en costado no reparable"
    })
    assert res_baja.status_code == 200

    inv_baja = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_baja["ubicacion_bodega"] == "BODEGA_6_FVU"
    assert inv_baja["placa_actual"] == ""
    assert inv_baja["posicion_actual"] == 0

    # 3. Se ejecuta la sincronización masiva desde el historial de inspecciones
    database.sincronizar_maestro_desde_inspecciones()

    # 4. Comprobar que la llanta NO revivió como MONTADA_OPERACION
    inv_post_sync = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_post_sync["ubicacion_bodega"] == "BODEGA_6_FVU", "Fallo: Inspección vieja revivió una llanta de baja FVU"
    assert inv_post_sync["placa_actual"] == ""
    assert inv_post_sync["posicion_actual"] == 0
