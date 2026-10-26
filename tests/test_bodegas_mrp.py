"""
Suite de Pruebas Automatizadas para el Módulo de Las 7 Bodegas, Kardex, Garantías y Balance MRP (KPI 20)
TireAnalyze Pro / TireCheck Pro
"""

import pytest
from datetime import datetime
import database
import server

def test_ciclo_completo_7_bodegas_y_kardex(test_db, auth_client):
    """
    Valida el ciclo de vida completo de una carcasa a través de las 7 bodegas:
    1. Alta nueva en Bodega 1.
    2. Montaje en vehículo rodante.
    3. Reparación mayor en Bodega 5 y retorno a Bodega 2.
    4. Envío a Bodega 3 y retorno como R1 a Bodega 4.
    5. Baja por daño a Bodega 6 FVU con detección de garantía.
    6. Aplicación de nota de crédito por garantía.
    7. Disposición final y chatarrización en Bodega 7 con acta ambiental.
    8. Consulta de trazabilidad histórica en Kardex.
    """
    cliente = "TRANSPORTES DEL VALLE"
    numero_interno = "LL-BOD-01"

    # Configuración del cliente con límite de retiro en 3.0 mm
    with database.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_traccion, mm_retiro_direccional)
            VALUES (?, 'PRO', 3.0, 3.0)
        """, (cliente,))
        conn.commit()

    # 1. Alta nueva en BODEGA_1_NUEVAS
    res_alta = auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "subcliente": "CALI",
        "numero_interno": numero_interno,
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "GOODYEAR",
        "diseno": "KMAX S",
        "dimension": "295/80R22.5",
        "vida_actual": "Original",
        "prof_inicial": 18.0,
        "prof_actual_min": 18.0,
        "costo_compra": 1600000.0,
        "proveedor_actual": "DISTRIBUIDORA NACIONAL"
    })
    assert res_alta.status_code == 200, res_alta.text
    assert res_alta.json()["ok"] is True

    # 2. Montaje en vehículo TRK-900 Posición 3
    res_mont = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": "TRK-900",
        "posicion": 3,
        "km_vehiculo": 50000.0
    })
    assert res_mont.status_code == 200
    assert res_mont.json()["ok"] is True

    # 3. Envío a BODEGA_5_REPARACION y retorno a BODEGA_2_RECAMBIO con costo de $120.000
    res_rep = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "BODEGA_5_REPARACION",
        "proveedor": "VULCANIZADORA EL SOL"
    })
    assert res_rep.status_code == 200

    res_ret_rep = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "BODEGA_2_RECAMBIO",
        "costo_asociado": 120000.0,
        "causal_o_motivo": "Reparación sección corona"
    })
    assert res_ret_rep.status_code == 200

    # Verificar que el costo de reparación se sumó al ciclo actual y al acumulado total
    inv_post_rep = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={numero_interno}").json()
    ll_rep = inv_post_rep["llantas"][0]
    assert ll_rep["costo_reparaciones_ciclo_actual"] == 120000.0
    assert ll_rep["costo_acumulado_total"] == 1600000.0 + 120000.0  # 1.720.000

    # 4. Envío a BODEGA_3_REENCAUCHE y retorno a BODEGA_4_REENCAUCHADAS con costo $650.000 y prof 20.0 mm
    res_env_reen = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "BODEGA_3_REENCAUCHE",
        "proveedor": "BANDAG COLOMBIA"
    })
    assert res_env_reen.status_code == 200

    res_ret_reen = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "BODEGA_4_REENCAUCHADAS",
        "costo_asociado": 650000.0,
        "nueva_prof_inicial": 20.0,
        "banda_reen": "BDR-HG",
        "causal_o_motivo": "Primer reencauche cumplido"
    })
    assert res_ret_reen.status_code == 200

    # Verificar nuevo ciclo: vida R1, costo_ciclo 650.000, costo_reparaciones reiniciado a 0, costo_acumulado suma histórica
    inv_post_reen = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={numero_interno}").json()
    ll_reen = inv_post_reen["llantas"][0]
    assert ll_reen["vida_actual"] == "R1"
    assert ll_reen["prof_inicial"] == 20.0
    assert ll_reen["prof_actual_min"] == 20.0
    assert ll_reen["costo_ciclo_actual"] == 650000.0
    assert ll_reen["costo_reparaciones_ciclo_actual"] == 0.0
    assert ll_reen["costo_acumulado_total"] == 1720000.0 + 650000.0  # 2.370.000

    # 5. Envío a BODEGA_6_FVU con prof_min = 7.0 mm (pérdida de 4.0 mm sobre límite 3.0 mm)
    res_fvu = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "BODEGA_6_FVU",
        "prof_min_mm": 7.0,
        "causal_o_motivo": "Corte profundo en costado"
    })
    assert res_fvu.status_code == 200

    inv_post_fvu = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={numero_interno}").json()
    ll_fvu = inv_post_fvu["llantas"][0]
    assert ll_fvu["ubicacion_bodega"] == "BODEGA_6_FVU"
    assert ll_fvu["mm_perdidos_fvu"] == 4.0  # 7.0 - 3.0
    assert ll_fvu["dinero_perdido_fvu"] > 0
    # Con prof_ini=20, prof_act=7 -> mm_ut = 17, desg = 13/17 = 76%, si desgaste fuera <30% se marcaría 'Posible Garantía'
    
    # Probar actualización explícita de Garantía y Nota Crédito de $100.000
    dinero_perdido_prev = ll_fvu["dinero_perdido_fvu"]
    res_gar = auth_client.post("/api/bodegas/garantia", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "estado_garantia": "Nota Crédito Reconocida",
        "valor_reconocido_garantia": 100000.0,
        "observaciones": "Aprobada por fabricante tras peritaje técnico"
    })
    assert res_gar.status_code == 200
    assert res_gar.json()["ok"] is True
    # El dinero perdido debe haberse reducido en exactamente $100.000
    assert round(res_gar.json()["dinero_perdido_fvu"], 2) == round(max(0.0, dinero_perdido_prev - 100000.0), 2)

    # 6. Chatarrización en BODEGA_7_CHATARRIZADA con Acta Ambiental
    res_chat = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": numero_interno,
        "bodega_destino": "BODEGA_7_CHATARRIZADA",
        "documento_soporte": "ACTA-AMB-2026-01",
        "proveedor": "ECO-LLANTAS RECICLAJE SAS",
        "causal_o_motivo": "Disposición final autorizada"
    })
    assert res_chat.status_code == 200

    # 7. Verificación de Kardex completo
    res_kardex = auth_client.get(f"/api/bodegas/kardex?cliente={cliente}&numero_interno={numero_interno}")
    assert res_kardex.status_code == 200
    kardex_data = res_kardex.json()
    assert kardex_data["total_eventos"] >= 6
    movs = kardex_data["movimientos"]
    tipos_mov = [m["tipo_movimiento"] for m in movs]
    assert "ALTA_NUEVA" in tipos_mov
    assert "MONTAJE" in tipos_mov
    assert "RETORNO_REPARACION" in tipos_mov
    assert "RETORNO_REENCAUCHE" in tipos_mov
    assert "BAJA_FVU" in tipos_mov
    assert "AJUSTE_GARANTIA" in tipos_mov
    assert "CHATARRIZACION" in tipos_mov


def test_calculo_mrp_kpi20_y_par_direccional(test_db, auth_client):
    """
    Valida el cálculo algorítmico del Balance MRP (KPI 20) y la regla de ajuste de par direccional (KPI 05):
    - 1 llanta direccional en retiro + compañera con diferencia > 3.0 mm frente a nueva = Demanda direccional de 2 llantas.
    - Bodega 1 con 1 llanta nueva.
    - Bodega 3 con 10 llantas al 85% de aprobación = 8 llantas útiles estimadas.
    - Verifica Necesidad Bruta, Stock Disponible Útil y Compra Neta Sugerida.
    """
    cliente = "FLOTA LOGISTICA MRP"
    dim = "295/80R22.5"

    with database.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO configuracion_avanzada_cliente (
                cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion,
                porcentaje_aprobacion_reencauche, stock_seguridad_default, diferencia_minima_par_direccional_mm
            ) VALUES (?, 'PRO', 3.0, 3.0, 85.0, 4, 3.0)
        """, (cliente,))

        # Insertar vehículo con par direccional disparejo: Pos 1 en 2.5 mm (retiro) y Pos 2 en 11.0 mm (desgaste 7.0 mm > 3.0)
        conn.execute("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, placa, posicion, tipologia, marca, dimension,
                prof_ext, prof_cent, prof_int, prof_inicial, numero_interno
            ) VALUES
            ('2026-10-15', ?, 'SEDE NORTE', 'VEH-101', 1, 'CABEZOTE 6X4', 'MICHELIN', ?, 2.5, 2.5, 2.5, 18.0, 'LL-P1'),
            ('2026-10-15', ?, 'SEDE NORTE', 'VEH-101', 2, 'CABEZOTE 6X4', 'MICHELIN', ?, 11.0, 11.0, 11.0, 18.0, 'LL-P2')
        """, (cliente, dim, cliente, dim))

        conn.commit()

    # Dar de alta 1 llanta nueva en Bodega 1
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": "LL-NUEVA-01",
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "MICHELIN",
        "dimension": dim,
        "prof_inicial": 18.0,
        "costo_compra": 1500000.0
    })

    # Dar de alta 10 llantas en Bodega 3 (Planta Reencauche)
    for i in range(1, 11):
        auth_client.post("/api/bodegas/alta", json={
            "cliente": cliente,
            "numero_interno": f"LL-REEN-PL_{i}",
            "ubicacion_bodega": "BODEGA_3_REENCAUCHE",
            "marca": "MICHELIN",
            "dimension": dim,
            "costo_compra": 600000.0
        })

    # Consultar Balance MRP
    res_mrp = auth_client.get(f"/api/bodegas/resumen-mrp?cliente={cliente}&dimension={dim}")
    assert res_mrp.status_code == 200
    datos_mrp = res_mrp.json()

    assert datos_mrp["licencia"] == "PRO"
    assert datos_mrp["disponible_en_licencia"] is True
    assert len(datos_mrp["matriz_mrp"]) >= 1

    item_mrp = datos_mrp["matriz_mrp"][0]
    assert item_mrp["dimension"] == dim

    # Demanda direccional: 1 por Pos 1 retirada + 1 por ajuste par direccional de Pos 2 = 2 llantas
    assert item_mrp["demanda_direccional"] == 2
    assert item_mrp["demanda_flota"] == 2

    # Stock de seguridad = 4
    assert item_mrp["stock_seguridad"] == 4

    # Necesidad Bruta = Demanda Flota (2) + Bajas FVU (0) + Stock Seguridad (4) = 6
    assert item_mrp["necesidad_bruta"] == 6

    # Bodega 1 = 1 llanta
    assert item_mrp["b1_nuevas"] == 1
    # Bodega 3 = 10 llantas -> Retorno estimado con 85% = floor(10 * 0.85) = 8
    assert item_mrp["b3_planta"] == 10
    assert item_mrp["retorno_planta_estimado"] == 8

    # Stock disponible útil = B1 (1) + Retorno planta (8) = 9
    assert item_mrp["stock_disponible_util"] == 9

    # Compra neta sugerida (KPI 20): compra_nuevas_direccional (1) + compra_adicional_reencauche (0) = 1
    assert item_mrp["compra_neta_sugerida"] == 1

    # Compra nuevas direccional = max(0, Demanda Dir (2) - B1 Nuevas (1)) = 1
    assert item_mrp["compra_nuevas_direccional"] == 1


def test_montaje_desmonte_automatico_conflicto_posicion(test_db, auth_client):
    """
    Valida la regla de integridad de flota:
    Si una llanta A está en TRK-100 Posición 1 y se monta una llanta B en esa misma posición,
    la llanta A debe desmontarse automáticamente hacia Bodega 2 (Recambio) con su evento en el Kardex.
    """
    cliente = "FLOTA COHERENCIA AUTOMATICA"
    placa = "TRK-100"
    pos = 1

    # 1. Dar de alta y montar la llanta A
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": "LL-A-ORIGINAL",
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "BRIDGESTONE",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0
    })
    auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": "LL-A-ORIGINAL",
        "bodega_destino": "MONTADA_OPERACION",
        "placa": placa,
        "posicion": pos,
        "prof_min_mm": 12.0
    })

    # Verificar que Llanta A está montada
    inv_a = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q=LL-A-ORIGINAL").json()["llantas"][0]
    assert inv_a["ubicacion_bodega"] == "MONTADA_OPERACION"
    assert inv_a["placa_actual"] == placa
    assert inv_a["posicion_actual"] == pos

    # 2. Dar de alta la llanta B y montarla en la MISMA placa y posición
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": "LL-B-REEMPLAZO",
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "MICHELIN",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0
    })
    res_b = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": "LL-B-REEMPLAZO",
        "bodega_destino": "MONTADA_OPERACION",
        "placa": placa,
        "posicion": pos,
        "prof_min_mm": 18.0
    })
    assert res_b.status_code == 200

    # 3. Comprobar que Llanta B es ahora la que está montada
    inv_b = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q=LL-B-REEMPLAZO").json()["llantas"][0]
    assert inv_b["ubicacion_bodega"] == "MONTADA_OPERACION"
    assert inv_b["placa_actual"] == placa
    assert inv_b["posicion_actual"] == pos

    # 4. Comprobar que Llanta A fue automáticamente desmontada a Bodega 2
    inv_a_post = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q=LL-A-ORIGINAL").json()["llantas"][0]
    assert inv_a_post["ubicacion_bodega"] == "BODEGA_2_RECAMBIO"
    assert inv_a_post["placa_actual"] == ""
    assert inv_a_post["posicion_actual"] == 0

    # 5. Comprobar que el Kardex de Llanta A tiene el evento DESMONTE_RECAMBIO
    kardex_a = auth_client.get(f"/api/bodegas/kardex?cliente={cliente}&numero_interno=LL-A-ORIGINAL").json()
    tipos_a = [m["tipo_movimiento"] for m in kardex_a["movimientos"]]
    assert "DESMONTE_RECAMBIO" in tipos_a


def test_inspeccion_patio_sincroniza_llanta_desde_bodega(test_db, auth_client):
    """
    Valida que si una llanta fue registrada en Bodega (ej. B1 Nuevas o B4 Reencauchadas)
    y luego el inspector en patio la inspecciona en un vehículo, llantas_maestro
    transicione atómicamente a MONTADA_OPERACION y registre el MONTAJE en el Kardex.
    """
    cliente = "FLOTA PATIO SINCRONIZADA"
    serial = "LL-PATIO-SYNC-01"

    # 1. Crear llanta en Bodega 4 Reencauchadas
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial,
        "ubicacion_bodega": "BODEGA_4_REENCAUCHADAS",
        "marca": "BANDAG",
        "dimension": "295/80R22.5",
        "vida_actual": "R1",
        "prof_inicial": 21.0
    })

    inv_antes = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_antes["ubicacion_bodega"] == "BODEGA_4_REENCAUCHADAS"

    # 2. Registrar inspección en patio con esa llanta
    database.insertar_inspeccion({
        "cliente": cliente,
        "subcliente": "BOGOTA",
        "placa": "TRK-777",
        "posicion": 4,
        "tipologia": "CABEZOTE 6X4",
        "marca": "BANDAG",
        "diseno": "BDM",
        "dimension": "295/80R22.5",
        "vida": "REENCAUCHE",
        "prof_ext": 19.0,
        "prof_cent": 19.5,
        "prof_int": 19.0,
        "prof_inicial": 21.0,
        "numero_interno": serial,
        "kilometraje": 45000.0,
        "fecha": "2026-10-27"
    })

    # 3. Verificar que llantas_maestro se actualizó a MONTADA_OPERACION
    inv_despues = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_despues["ubicacion_bodega"] == "MONTADA_OPERACION"
    assert inv_despues["placa_actual"] == "TRK-777"
    assert inv_despues["posicion_actual"] == 4
    assert inv_despues["prof_actual_min"] == 19.0

    # 4. Verificar que se registró el evento MONTAJE en Kardex
    kardex_sync = auth_client.get(f"/api/bodegas/kardex?cliente={cliente}&numero_interno={serial}").json()
    tipos_sync = [m["tipo_movimiento"] for m in kardex_sync["movimientos"]]
    assert "MONTAJE" in tipos_sync


def test_reserva_apareo_dual_kpi08_y_liberacion_al_montar(test_db, auth_client):
    """
    Valida el ciclo de una llanta en Bodega 2 reservada para apareo dual:
    - Estado de reserva para dual.
    - El resumen MRP contabiliza llantas libres vs reservadas.
    - Al montarse en el camión, la reserva se limpia automáticamente.
    """
    cliente = "FLOTA DUALES KPI08"
    serial = "LL-DUAL-09"

    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial,
        "ubicacion_bodega": "BODEGA_2_RECAMBIO",
        "marca": "MICHELIN",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "prof_actual_min": 10.0
    })

    # Simular asignación de reserva para dual por parte del algoritmo KPI 08
    with database.get_connection() as conn:
        conn.execute("""
            UPDATE llantas_maestro SET
                reservada_para_placa = 'TRK-222',
                reservada_posicion = 5
            WHERE UPPER(cliente) = ? AND UPPER(numero_interno) = ?
        """, (cliente, serial))
        conn.commit()

    inv_res = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_res["reservada_para_dual"] is True

    # Montar la llanta en el vehículo
    res_mont = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": "TRK-222",
        "posicion": 5
    })
    assert res_mont.status_code == 200

    inv_post_mont = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv_post_mont["ubicacion_bodega"] == "MONTADA_OPERACION"
    assert inv_post_mont["reservada_para_dual"] is False
    assert inv_post_mont["placa_actual"] == "TRK-222"
    assert inv_post_mont["posicion_actual"] == 5


def test_deteccion_automatica_garantia_desgaste_bajo_y_busqueda(test_db, auth_client):
    """
    Valida:
    1. Si una llanta es enviada a BODEGA_6_FVU con desgaste < 30% (ej. prof_act 16.5 mm vs prof_ini 18.0 mm),
       el sistema marca automáticamente estado_garantia = 'Posible Garantía'.
    2. El buscador de inventario `q` encuentra llantas por serie, marca o placa.
    """
    cliente = "FLOTA GARANTIAS QA"
    serial = "LL-GAR-PREMATURA-01"

    # Configuración de límite de retiro 3.0 mm (mm útiles = 18 - 3 = 15 mm)
    with database.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO configuracion_avanzada_cliente (cliente, tipo_licencia, mm_retiro_traccion)
            VALUES (?, 'PRO', 3.0)
        """, (cliente,))
        conn.commit()

    # Alta en Bodega 1
    auth_client.post("/api/bodegas/alta", json={
        "cliente": cliente,
        "numero_interno": serial,
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "CONTINENTAL",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "costo_compra": 1800000.0
    })

    # Montaje en TRK-333
    auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "MONTADA_OPERACION",
        "placa": "TRK-333",
        "posicion": 2,
        "prof_min_mm": 18.0
    })

    # Daño severo a los pocos kilómetros: desecho a Bodega 6 con 17.0 mm (desgaste = 1 mm de 15 mm = 6.6% < 30%)
    res_baja = auth_client.post("/api/bodegas/movimiento", json={
        "cliente": cliente,
        "numero_interno": serial,
        "bodega_destino": "BODEGA_6_FVU",
        "prof_min_mm": 17.0,
        "causal_o_motivo": "Separación de lonas en hombro"
    })
    assert res_baja.status_code == 200

    inv = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q={serial}").json()["llantas"][0]
    assert inv["ubicacion_bodega"] == "BODEGA_6_FVU"
    assert inv["estado_garantia"] == "Posible Garantía"
    assert inv["mm_perdidos_fvu"] == 14.0  # 17.0 - 3.0
    assert inv["dinero_perdido_fvu"] > 1000000.0  # Gran pérdida por daño prematuro

    # Comprobar búsqueda por placa (debe encontrar llanta que estuvo o está asociada)
    res_q_marca = auth_client.get(f"/api/bodegas/inventario?cliente={cliente}&q=CONTINENTAL").json()
    assert res_q_marca["total"] >= 1
    assert any(l["numero_interno"] == serial for l in res_q_marca["llantas"])

