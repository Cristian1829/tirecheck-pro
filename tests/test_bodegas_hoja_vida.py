# -*- coding: utf-8 -*-
"""
Suite de pruebas automatizadas para las 7 Bodegas, Taller en Patio y Hoja de Vida (Life Sheet).
Implementación según sección 6 del prompt.
"""

import pytest
import database

def test_ingreso_lote_bodega1_y_montaje_desmonte_patio(auth_client, test_db):
    cliente = "TRANSPORTES DEL SUR"
    database.guardar_licencia_cliente(cliente, "PRO")
    database.sincronizar_vehiculo_catalogo("TPX067", "Tractocamión (6x4)", cliente, "Principal")

    # 1. Ingreso lote de 3 llantas (LL-1050 a LL-1052)
    resp_lote = auth_client.post("/api/llantas-crear-stock", json={
        "modo": "lote",
        "prefijo": "LL-",
        "numero_inicial": 1050,
        "cantidad": 3,
        "cliente_propietario": cliente,
        "marca_origen": "MICHELIN",
        "diseno_origen": "X-MULTI",
        "dimension": "295/80R22.5",
        "prof_inicial_nueva": 16.0,
        "precio_compra_inicial": 1500000.0
    })
    assert resp_lote.status_code == 200, resp_lote.text
    d_lote = resp_lote.json()
    assert d_lote["ok"] is True
    assert d_lote["cantidad"] == 3
    assert "LL-1050" in d_lote["llantas"]
    assert "LL-1052" in d_lote["llantas"]

    # 2. Consultar posición info en patio para TPX067 Posición 3 (Tracción)
    resp_pos = auth_client.get(f"/api/taller/posicion-info?placa=TPX067&posicion=3&cliente={cliente}")
    assert resp_pos.status_code == 200, resp_pos.text
    d_pos = resp_pos.json()
    assert d_pos["placa"] == "TPX067"
    assert d_pos["posicion"] == 3
    seriales_disp = [ll["numero_interno"] for ll in d_pos["stock_disponible"]]
    assert "LL-1050" in seriales_disp

    # 3. Montar LL-1050 en TPX067 Posición 3
    resp_mont = auth_client.post("/api/taller/montar", json={
        "placa": "TPX067",
        "posicion": 3,
        "numero_interno": "LL-1050",
        "cliente_propietario": cliente,
        "odometro_vehiculo": 45000.0
    })
    assert resp_mont.status_code == 200, resp_mont.text
    d_mont = resp_mont.json()
    assert d_mont["status"] == "ok"
    assert d_mont["llanta"]["numero_interno"] == "LL-1050"
    assert d_mont["llanta"]["marca"] == "MICHELIN"
    assert d_mont["llanta"]["profundidad_actual"] == 16.0

    # 4. Desmontar hacia 'reencauche' con 3.2 mm
    resp_desm = auth_client.post("/api/taller/desmontar", json={
        "numero_interno": "LL-1050",
        "cliente_propietario": cliente,
        "bodega_destino": "reencauche",
        "odometro_vehiculo": 95000.0,
        "profundidad": 3.2,
        "motivo": "Llegó a milímetros de retiro"
    })
    assert resp_desm.status_code == 200, resp_desm.text
    d_desm = resp_desm.json()
    assert d_desm["status"] == "ok"
    assert d_desm["bodega_nombre"] == "Bodega_3_Reencauche"

    # Verificar inventario en Bodega 3
    hv = database.obtener_hoja_vida_llanta("LL-1050", cliente)
    assert hv["ok"] is True
    assert hv["estado_actual"]["estado"] == "Bodega_3_Reencauche"
    assert hv["estado_actual"]["prof_min_actual"] == 3.2
    assert hv["metricas_consolidadas"]["km_totales"] == 50000.0  # 95000 - 45000


def test_ciclo_completo_planta_reencauche_reparacion_y_garantia(auth_client, test_db):
    cliente = "FLOTA OPERATIVA PRO"
    database.guardar_licencia_cliente(cliente, "PRO")

    # Crear llanta LL-2001 en Bodega 3 lista para despacho
    auth_client.post("/api/llantas-crear-stock", json={
        "modo": "individual",
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "marca_origen": "BRIDGESTONE",
        "diseno_origen": "M729",
        "dimension": "295/80R22.5",
        "prof_inicial_nueva": 16.0,
        "precio_compra_inicial": 1600000.0
    })
    database.desmontar_llanta_taller({
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "bodega_destino": "Bodega_3_Reencauche",
        "profundidad": 3.0
    })

    # 1. Despachar a planta (Bodega 3 -> Bodega 4)
    resp_desp = auth_client.post("/api/bodegas/despacho-planta", json={
        "numeros_internos": ["LL-2001"],
        "cliente_propietario": cliente,
        "proveedor_planta": "Renovadora Bandag",
        "guia_remision": "GUIA-7788",
        "fecha_compromiso": "2026-11-15"
    })
    assert resp_desp.status_code == 200
    assert resp_desp.json()["despachadas"] == 1

    hv4 = database.obtener_hoja_vida_llanta("LL-2001", cliente)
    assert hv4["estado_actual"]["estado"] == "Bodega_4_EnPlanta"

    # 2. Retorno de planta (Bodega 4 -> Bodega 2) con nuevo ciclo
    resp_ret = auth_client.post("/api/bodegas/retorno-reencauche", json={
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "proveedor_banda": "Bandag",
        "diseno_banda": "Bandag BDL",
        "prof_banda_nueva": 17.0,
        "costo_factura_renovado": 720000.0,
        "factura_renovado": "FACT-9921"
    })
    assert resp_ret.status_code == 200
    d_ret = resp_ret.json()
    assert d_ret["ciclo_actual"] == 2

    hv2 = database.obtener_hoja_vida_llanta("LL-2001", cliente)
    assert hv2["estado_actual"]["estado"] == "Bodega_2_Reutilizable"
    assert hv2["estado_actual"]["ciclo_vida"] == "R1"
    assert hv2["estado_actual"]["prof_min_actual"] == 17.0
    assert len(hv2["desglose_por_ciclos"]) == 2

    # 3. Reparación en Bodega 5
    # Trasladar a Bodega 5 y finalizar reparación
    database.desmontar_llanta_taller({
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "bodega_destino": "Bodega_5_Reparacion",
        "profundidad": 16.5
    })
    resp_rep = auth_client.post("/api/bodegas/finalizar-reparacion", json={
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "tipo_trabajo": "Parche radial por penetración",
        "costo_reparacion": 120000.0,
        "proveedor": "Taller Especializado"
    })
    assert resp_rep.status_code == 200
    hv_rep = database.obtener_hoja_vida_llanta("LL-2001", cliente)
    assert hv_rep["estado_actual"]["estado"] == "Bodega_2_Reutilizable"

    # 4. Dictamen de garantía hacia Bodega 7
    database.desmontar_llanta_taller({
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "bodega_destino": "Bodega_6_Garantia",
        "profundidad": 15.0
    })
    resp_gar = auth_client.post("/api/bodegas/dictamen-garantia", json={
        "numero_interno": "LL-2001",
        "cliente_propietario": cliente,
        "dictamen": "Aprobada",
        "pct_reconocido": 80.0,
        "valor_nota_credito": 500000.0
    })
    assert resp_gar.status_code == 200
    hv_gar = database.obtener_hoja_vida_llanta("LL-2001", cliente)
    assert hv_gar["estado_actual"]["estado"] == "Bodega_7_FVU"


def test_endpoint_hoja_vida_json_exacto(auth_client, test_db):
    cliente = "TRANS-CARGA LOGISTICA"
    database.guardar_licencia_cliente(cliente, "PRO")

    # 1. Crear LL-1045 con ciclo 1 Original (122.000 km, costo $1.850.000)
    auth_client.post("/api/llantas-crear-stock", json={
        "modo": "individual",
        "numero_interno": "LL-1045",
        "cliente_propietario": cliente,
        "marca_origen": "GOODYEAR",
        "diseno_origen": "KMAX D",
        "dimension": "295/80R22.5",
        "precio_compra_inicial": 1850000.0,
        "prof_inicial_nueva": 18.0
    })
    # Simular montaje a km 100.000 y desmonte a km 222.000 (122.000 km recorridos)
    database.montar_llanta_taller({
        "placa": "TRK-900",
        "posicion": 3,
        "numero_interno": "LL-1045",
        "cliente_propietario": cliente,
        "odometro_vehiculo": 100000.0
    })
    database.desmontar_llanta_taller({
        "numero_interno": "LL-1045",
        "cliente_propietario": cliente,
        "bodega_destino": "Bodega_3_Reencauche",
        "odometro_vehiculo": 222000.0,
        "profundidad": 3.5
    })

    # 2. Reencauche Ciclo 2 (72.500 km, costo $720.000)
    database.recepcionar_llanta_reencauchada({
        "numero_interno": "LL-1045",
        "cliente_propietario": cliente,
        "proveedor_banda": "Bandag",
        "diseno_banda": "BDL 18",
        "prof_banda_nueva": 18.0,
        "costo_factura_renovado": 720000.0
    })
    database.montar_llanta_taller({
        "placa": "TRK-900",
        "posicion": 4,
        "numero_interno": "LL-1045",
        "cliente_propietario": cliente,
        "odometro_vehiculo": 230000.0
    })
    database.desmontar_llanta_taller({
        "numero_interno": "LL-1045",
        "cliente_propietario": cliente,
        "bodega_destino": "Bodega_2_Reutilizable",
        "odometro_vehiculo": 302500.0,
        "profundidad": 7.0
    })

    # Consultar endpoint REST de Hoja de Vida
    resp = auth_client.get(f"/api/llanta/hoja-vida/LL-1045?cliente={cliente}")
    assert resp.status_code == 200, resp.text
    hv = resp.json()

    assert hv["numero_interno"] == "LL-1045"
    assert hv["ficha_tecnica"]["marca"] == "GOODYEAR"
    assert hv["ficha_tecnica"]["diseno"] == "KMAX D"
    assert hv["ficha_tecnica"]["precio_compra"] == 1850000.0

    met = hv["metricas_consolidadas"]
    assert met["km_totales"] == 194500.0  # 122.000 + 72.500
    assert met["costo_total_invertido"] == 2570000.0  # 1.850.000 + 720.000
    assert met["cpk_global"] > 0

    assert len(hv["desglose_por_ciclos"]) == 2
    assert hv["desglose_por_ciclos"][0]["ciclo"] == 1
    assert hv["desglose_por_ciclos"][0]["km_recorridos"] == 122000.0
    assert hv["desglose_por_ciclos"][1]["ciclo"] == 2
    assert hv["desglose_por_ciclos"][1]["km_recorridos"] == 72500.0

    assert len(hv["curva_desgaste"]) >= 3
    assert any(pt["km"] == 0.0 for pt in hv["curva_desgaste"])


def test_candado_direccional_y_desmonte_automatico_en_montaje(auth_client, test_db):
    cliente = "LOGISTICA ANDINA"
    database.guardar_licencia_cliente(cliente, "PRO")
    database.sincronizar_vehiculo_catalogo("DIR-101", "Tractocamión (6x4)", cliente, "Principal")

    # 1. Crear llanta reencauchada (ciclo 2)
    auth_client.post("/api/llantas-crear-stock", json={
        "modo": "individual",
        "numero_interno": "REEN-01",
        "cliente_propietario": cliente,
        "marca_origen": "CONTINENTAL",
        "diseno_origen": "HDR2",
        "dimension": "295/80R22.5",
        "precio_compra_inicial": 1400000.0
    })
    database.recepcionar_llanta_reencauchada({
        "numero_interno": "REEN-01",
        "cliente_propietario": cliente,
        "proveedor_banda": "Bandag",
        "diseno_banda": "B1",
        "prof_banda_nueva": 16.0,
        "costo_factura_renovado": 650000.0
    })

    # Intentar montarla en Posición 1 (Direccional) debe ser rechazada
    resp_dir = auth_client.post("/api/taller/montar", json={
        "placa": "DIR-101",
        "posicion": 1,
        "numero_interno": "REEN-01",
        "cliente_propietario": cliente
    })
    assert resp_dir.status_code == 400
    assert "direccional" in resp_dir.json()["detail"].lower()
    assert "reencauchadas" in resp_dir.json()["detail"].lower()

    # 2. Desmonte automático de ocupante previa:
    # Montar primero LL-ORIG1 en Posición 3 (Tracción)
    auth_client.post("/api/llantas-crear-stock", json={
        "modo": "individual",
        "numero_interno": "LL-ORIG1",
        "cliente_propietario": cliente,
        "marca_origen": "MICHELIN",
        "diseno_origen": "X-LINE",
        "dimension": "295/80R22.5"
    })
    auth_client.post("/api/taller/montar", json={
        "placa": "DIR-101",
        "posicion": 3,
        "numero_interno": "LL-ORIG1",
        "cliente_propietario": cliente,
        "odometro_vehiculo": 50000.0
    })

    # Ahora montar REEN-01 en Posición 3 (permitida para tracción)
    resp_trac = auth_client.post("/api/taller/montar", json={
        "placa": "DIR-101",
        "posicion": 3,
        "numero_interno": "REEN-01",
        "cliente_propietario": cliente,
        "odometro_vehiculo": 60000.0
    })
    assert resp_trac.status_code == 200, resp_trac.text

    # Verificar que REEN-01 quedó Montada en Posición 3
    hv_reen = database.obtener_hoja_vida_llanta("REEN-01", cliente)
    assert hv_reen["estado_actual"]["estado"] == "Montada"
    assert hv_reen["estado_actual"]["posicion"] == 3

    # Y verificar que LL-ORIG1 fue desmontada automáticamente hacia Bodega 2 Reutilizable
    hv_orig = database.obtener_hoja_vida_llanta("LL-ORIG1", cliente)
    assert hv_orig["estado_actual"]["estado"] == "Bodega_2_Reutilizable"
    assert hv_orig["estado_actual"]["posicion"] == 0
    assert hv_orig["metricas_consolidadas"]["km_totales"] == 10000.0  # 60000 - 50000
