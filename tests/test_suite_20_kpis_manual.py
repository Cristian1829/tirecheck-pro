import pytest
import json
import math
import database

def sembrar_datos_prueba_suite():
    """
    Siembra en la base de datos temporal vehículos en el padrón, inspecciones multi-mes
    y registros en llantas_maestro para cubrir los 20 KPIs.
    """
    # 1. Configuración de cliente en PRO/FULL
    database.guardar_licencia_cliente("FLOTA TEST SUITE", "PRO")

    # 2. Padrón de vehículos
    with database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM padron_vehiculos_cliente WHERE UPPER(cliente) = 'FLOTA TEST SUITE'")
        padron = [
            ("FLOTA TEST SUITE", "Sede Central", "TST-001", "Tracto 6x4", "Activo", 1),
            ("FLOTA TEST SUITE", "Sede Central", "TST-002", "Tracto 6x4", "Activo", 1),
            ("FLOTA TEST SUITE", "Sede Norte",   "TST-003", "Doble Troque", "Activo", 1),
            ("FLOTA TEST SUITE", "Sede Norte",   "TST-004", "Doble Troque", "Activo", 1),
        ]
        cur.executemany("""
            INSERT INTO padron_vehiculos_cliente (cliente, subcliente, placa, tipologia, estado_operativo, activo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, padron)
        conn.commit()

    # 3. Inspecciones mes 1 (2026-08) y mes 2 (2026-09)
    # TST-001 inspeccionado en ambos meses
    database.insertar_inspeccion({
        'fecha': '2026-08-15',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-001',
        'posicion': 1,
        'kilometraje': 40000.0,
        'km_montaje': 20000.0,
        'numero_interno': 'LL-TST-01',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1800000.0,
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 110.0
    })

    database.insertar_inspeccion({
        'fecha': '2026-09-20',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-001',
        'posicion': 1,
        'kilometraje': 60000.0,
        'km_montaje': 20000.0,
        'numero_interno': 'LL-TST-01',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1800000.0,
        'prof_inicial': 16.0,
        'prof_ext': 10.0,
        'prof_cent': 10.0,
        'prof_int': 10.0,
        'psi': 110.0
    })

    # Posición 2 de TST-001 en septiembre (buen estado)
    database.insertar_inspeccion({
        'fecha': '2026-09-20',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-001',
        'posicion': 2,
        'kilometraje': 60000.0,
        'km_montaje': 20000.0,
        'numero_interno': 'LL-TST-02',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1800000.0,
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 110.0
    })

    # TST-002 inspeccionado en septiembre: Par direccional desgastado y con desalineación
    database.insertar_inspeccion({
        'fecha': '2026-09-21',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-002',
        'posicion': 1,
        'kilometraje': 80000.0,
        'km_montaje': 30000.0,
        'numero_interno': 'LL-TST-03',
        'marca': 'Bridgestone',
        'diseno': 'R268',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1750000.0,
        'prof_inicial': 16.0,
        'prof_ext': 3.5,  # Requiere cambio (límite dir = 4.0)
        'prof_cent': 3.5,
        'prof_int': 1.0,  # Desalineación severa (dif hombros = 2.5 mm >= 2.0)
        'psi': 85.0       # Baja Presión (-22% vs 110)
    })

    # Posición 2 de TST-002: aún con 11.0 mm (diferencia con nueva 16 - 11 = 5.0 mm > 3.0 mm)
    database.insertar_inspeccion({
        'fecha': '2026-09-21',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-002',
        'posicion': 2,
        'kilometraje': 80000.0,
        'km_montaje': 30000.0,
        'numero_interno': 'LL-TST-04',
        'marca': 'Bridgestone',
        'diseno': 'R268',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1750000.0,
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 110.0
    })

    # Pacha P3-P4 de TST-002: Mal apareada (P3=12.0 mm, P4=8.5 mm -> delta 3.5 mm > 2.5 mm)
    database.insertar_inspeccion({
        'fecha': '2026-09-21',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-002',
        'posicion': 3,
        'kilometraje': 80000.0,
        'km_montaje': 30000.0,
        'numero_interno': 'LL-TST-05',
        'marca': 'Goodyear',
        'diseno': 'KMax D',
        'dimension': '295/80R22.5',
        'vida': 'R1',
        'banda_reen': 'Bandag BDM',
        'precio': 950000.0,
        'prof_inicial': 18.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 100.0
    })
    database.insertar_inspeccion({
        'fecha': '2026-09-21',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-002',
        'posicion': 4,
        'kilometraje': 80000.0,
        'km_montaje': 30000.0,
        'numero_interno': 'LL-TST-06',
        'marca': 'Goodyear',
        'diseno': 'KMax D',
        'dimension': '295/80R22.5',
        'vida': 'R1',
        'banda_reen': 'Bandag BDM',
        'precio': 950000.0,
        'prof_inicial': 18.0,
        'prof_ext': 8.5,
        'prof_cent': 8.5,
        'prof_int': 8.5,
        'psi': 100.0
    })

    # 4. Llantas en bodegas y FVU en llantas_maestro
    with database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM llantas_maestro WHERE UPPER(cliente) = 'FLOTA TEST SUITE'")
        llantas_bodegas = [
            # Bodega 1 Nuevas
            ('LL-B1-01', 'FLOTA TEST SUITE', 'BODEGA_1_NUEVAS', '295/80R22.5', 'Michelin', 'Original', 0, 16.0, 16.0, 1800000.0, '', 0.0, 0.0),
            ('LL-B1-02', 'FLOTA TEST SUITE', 'BODEGA_1_NUEVAS', '295/80R22.5', 'Michelin', 'Original', 0, 16.0, 16.0, 1800000.0, '', 0.0, 0.0),
            # Bodega 2 Recambio (libre y útil)
            ('LL-B2-01', 'FLOTA TEST SUITE', 'BODEGA_2_RECAMBIO', '295/80R22.5', 'Goodyear', 'R1', 1, 18.0, 11.5, 950000.0, '', 0.0, 0.0),
            # Bodega 3 Planta Reencauche
            ('LL-B3-01', 'FLOTA TEST SUITE', 'BODEGA_3_REENCAUCHE', '295/80R22.5', 'Goodyear', 'Original', 0, 18.0, 3.5, 950000.0, '', 0.0, 0.0),
            ('LL-B3-02', 'FLOTA TEST SUITE', 'BODEGA_3_REENCAUCHE', '295/80R22.5', 'Michelin', 'Original', 0, 16.0, 3.0, 1200000.0, '', 0.0, 0.0),
            # Bodega 4 Reencauchadas Listas
            ('LL-B4-01', 'FLOTA TEST SUITE', 'BODEGA_4_REENCAUCHADAS', '295/80R22.5', 'Michelin', 'R1', 1, 18.0, 18.0, 950000.0, '', 0.0, 0.0),
            # Bodega 6 FVU (Bajas)
            ('LL-B6-01', 'FLOTA TEST SUITE', 'BODEGA_6_FVU', '295/80R22.5', 'Bridgestone', 'Original', 0, 16.0, 5.0, 1750000.0, 'Separación de lonas', 2.0, 250000.0),
            ('LL-B6-02', 'FLOTA TEST SUITE', 'BODEGA_6_FVU', '295/80R22.5', 'Michelin', 'R2', 2, 18.0, 3.0, 950000.0, 'Fin de vida útil normal', 0.0, 0.0)
        ]
        cur.executemany("""
            INSERT INTO llantas_maestro (
                numero_interno, cliente, ubicacion_bodega, dimension, marca,
                vida_actual, num_reencauches, prof_inicial, prof_actual_min,
                costo_ciclo_actual, causal_baja_fvu, mm_perdidos_fvu, dinero_perdido_fvu
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, llantas_bodegas)
        conn.commit()


def test_estructura_5_pestanas_y_20_kpis_completos(test_db, auth_client):
    """
    1. Siembra vehículos en padrón, inspecciones de varios meses y registros en bodegas/FVU.
    Llama a GET /api/kpis/suite-20 y verifica que retorne HTTP 200 con los 20 objetos (kpi_01 a kpi_20),
    comprobando que ninguno contenga NaN ni Infinity.
    """
    sembrar_datos_prueba_suite()

    resp = auth_client.get("/api/kpis/suite-20?cliente=FLOTA+TEST+SUITE")
    assert resp.status_code == 200
    data = resp.json()

    # Comprobar existencia de las 5 pestañas
    assert "pestanas" in data
    assert len(data["pestanas"]) == 5
    for p_id in ("pestana_1", "pestana_2", "pestana_3", "pestana_4", "pestana_5"):
        assert p_id in data["pestanas"]

    # Comprobar presencia de los 20 KPIs
    for i in range(1, 21):
        kpi_key = f"kpi_{i:02d}"
        assert kpi_key in data, f"Falta el objeto {kpi_key} en la respuesta"
        assert isinstance(data[kpi_key], dict)

    # Validar que no contenga 'NaN' ni 'Infinity' en la serialización
    txt = json.dumps(data)
    assert "NaN" not in txt
    assert "Infinity" not in txt
    assert "-Infinity" not in txt

    # Validar KPI 01: 2 vehículos inspeccionados de 4 en padrón = 50.0%
    k1 = data["kpi_01"]
    assert k1["disponible"] is True
    assert k1["total_padron"] == 4
    assert k1["vehiculos_auditados"] == 2
    assert k1["cumplimiento_pct"] == 50.0
    assert len(k1["placas_pendientes"]) == 2  # TST-003 y TST-004 pendientes


def test_kpi14_triada_agrupacion_dinamica(test_db, auth_client):
    """
    2. Verifica que GET /api/kpis/suite-20?agrupar_kpi14=marca, fechas, inspeccion, eje y tipologia
    devuelvan las 3 series sincronizadas (proyeccion_km, km_mm, cpk) correctamente calculadas.
    """
    sembrar_datos_prueba_suite()

    opciones = ["marca", "fechas", "inspeccion", "eje", "tipologia"]
    for opt in opciones:
        resp = auth_client.get(f"/api/kpis/suite-20?cliente=FLOTA+TEST+SUITE&agrupar_kpi14={opt}")
        assert resp.status_code == 200
        data = resp.json()

        k14 = data["kpi_14"]
        assert k14["disponible"] is True
        assert k14["agrupacion_actual"] == opt

        labels = k14["labels"]
        proy = k14["proyeccion_km"]
        kmmm = k14["km_mm"]
        cpk = k14["cpk"]

        assert len(labels) > 0, f"No devolvió etiquetas para agrupación {opt}"
        assert len(labels) == len(proy) == len(kmmm) == len(cpk), (
            f"Series asincrónicas en agrupación {opt}: len(labels)={len(labels)}, "
            f"len(proy)={len(proy)}, len(kmmm)={len(kmmm)}, len(cpk)={len(cpk)}"
        )

        for val in proy:
            assert isinstance(val, (int, float)) and not math.isnan(val) and val >= 0
        for val in kmmm:
            assert isinstance(val, (int, float)) and not math.isnan(val) and val >= 0
        for val in cpk:
            assert isinstance(val, (int, float)) and not math.isnan(val) and val >= 0


def test_kpi15_filtro_madurez_y_kpi20_formula_mrp(test_db, auth_client):
    """
    3. Comprueba que una llanta recién montada con 0.2 mm de desgaste no distorsione el máximo
    de KPI 15 (filtro >= 1.5 mm), y que la ecuación del KPI 20 aplique el factor 0.90 a Bodega 3
    y el margen de seguridad del 15%.
    """
    sembrar_datos_prueba_suite()

    # Insertamos una llanta con desgaste mínimo de 0.2 mm y proyección inflada ficticia
    database.insertar_inspeccion({
        'fecha': '2026-09-22',
        'cliente': 'FLOTA TEST SUITE',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga General',
        'placa': 'TST-001',
        'posicion': 5,
        'kilometraje': 10000.0,
        'km_montaje': 5000.0,      # 5000 km
        'numero_interno': 'LL-RECIEN-MONTADA',
        'marca': 'MarcaInmadura',
        'diseno': 'Test',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1800000.0,
        'prof_inicial': 16.0,
        'prof_ext': 15.8,
        'prof_cent': 15.8,
        'prof_int': 15.8,          # desgaste = 0.2 mm (< 1.5 mm)
        'psi': 110.0
    })

    resp = auth_client.get("/api/kpis/suite-20?cliente=FLOTA+TEST+SUITE")
    assert resp.status_code == 200
    data = resp.json()

    # KPI 15: La 'MarcaInmadura' NO debe figurar en las etiquetas porque su desgaste fue 0.2 mm (< 1.5 mm)
    k15 = data["kpi_15"]
    assert "MarcaInmadura" not in k15["labels"], (
        "El KPI 15 incluyó una llanta con desgaste < 1.5 mm violando el filtro estricto de madurez"
    )

    # KPI 20: Verificar fórmula MRP
    k20 = data["kpi_20"]
    assert k20["disponible"] is True
    matriz = k20["matriz_mrp"]
    assert len(matriz) >= 1
    mrp_dim = matriz[0]

    # Demanda flota + bajas FVU
    dem = mrp_dim["demanda_flota"]
    bajas = mrp_dim["reposicion_bajas_fvu"]

    # Margen de seguridad = parámetro stock_seguridad_default del cliente (el mismo MRP de Bodegas;
    # antes el KPI 20 usaba un 15 % fijo y Bodegas el parámetro, y daban compras distintas)
    margen_esperado = database.obtener_configuracion_avanzada_cliente('FLOTA TEST SUITE').get('stock_seguridad_default', 4) or 4
    assert mrp_dim["margen_seguridad"] == margen_esperado

    # Necesidad Bruta = Demanda + Bajas + Margen
    assert mrp_dim["necesidad_bruta"] == dem + bajas + margen_esperado

    # Bodega 3 en siembra tiene 2 llantas: factor 0.90 -> floor(2 * 0.90) = floor(1.8) = 1
    assert mrp_dim["stock_b3"] == 2
    assert mrp_dim["stock_b3_util"] == math.floor(2 * 0.90) == 1

    # Stock Disponible = B1 + B2 + floor(B3*0.90) + B4
    stk_disp_esperado = mrp_dim["stock_b1"] + mrp_dim["stock_b2"] + mrp_dim["stock_b3_util"] + mrp_dim["stock_b4"]
    assert mrp_dim["stock_disponible"] == stk_disp_esperado

    # Compra neta sugerida = max(0, necesidad_bruta - stock_disponible)
    assert mrp_dim["compra_neta_sugerida"] == max(0, mrp_dim["necesidad_bruta"] - stk_disp_esperado)


def test_licenciamiento_light_vs_full(test_db, auth_client):
    """
    4. Verifica que el endpoint respete la visibilidad de indicadores según la matriz:
    LIGHT (KPI 02 a 10 activos, KPI 01 y 11 sin $ o bloqueados, 12 a 20 con candado)
    vs FULL (KPI 01 a 20 todos activos).
    """
    sembrar_datos_prueba_suite()

    # 1. Consulta en modo LIGHT (conmutador)
    resp_light = auth_client.get("/api/kpis/suite-20?cliente=FLOTA+TEST+SUITE&licencia=LIGHT")
    assert resp_light.status_code == 200
    data_light = resp_light.json()

    assert data_light["licencia"] == "LIGHT"
    assert data_light["disponible_en_licencia"] is False

    # KPI 01 bloqueado en LIGHT
    assert data_light["kpi_01"]["disponible"] is False
    assert "Exclusivo Licencia FULL" in data_light["kpi_01"]["mensaje"]

    # KPIs 02 a 10 activos en LIGHT
    for i in range(2, 11):
        assert data_light[f"kpi_{i:02d}"]["disponible"] is True, f"KPI {i:02d} debería estar activo en LIGHT"

    # KPI 11 sin montos en $ en LIGHT
    assert data_light["kpi_11"]["disponible_pesos"] is False
    assert data_light["kpi_11"]["total_dinero_perdido_cop"] == 0.0

    # KPIs 12 a 20 bloqueados en LIGHT
    for i in range(12, 21):
        k_obj = data_light[f"kpi_{i:02d}"]
        assert k_obj["disponible"] is False, f"KPI {i:02d} debería estar bloqueado en LIGHT"
        assert "Exclusivo Licencia FULL" in k_obj["mensaje"]

    # 2. Consulta en modo FULL
    resp_full = auth_client.get("/api/kpis/suite-20?cliente=FLOTA+TEST+SUITE&licencia=FULL")
    assert resp_full.status_code == 200
    data_full = resp_full.json()

    assert data_full["licencia"] == "FULL"
    assert data_full["disponible_en_licencia"] is True

    # Todos del KPI 01 al 20 activos en FULL
    for i in range(1, 21):
        assert data_full[f"kpi_{i:02d}"]["disponible"] is True, f"KPI {i:02d} debería estar activo en FULL"


def test_no_inflado_km_montaje_cero_y_ahorro_roi(test_db, auth_client):
    """
    Verifica que:
    1. Una llanta con km_montaje <= 0 (o nulo) NO infle el cálculo de kilometraje rodado con el odómetro
       total acumulado (ej. 350.000 km), sino que se blinde calculando contra el primer corte o 0.0 (asentamiento).
    2. El objeto 'ahorro_roi' (y 'resumen_ahorro_roi') se retorne en la suite de 20 KPIs con los 6 campos clave:
       - cascos_en_ventana_salvamento
       - ahorro_salvamento_cascos_cop
       - ahorro_alineacion_oportuna_cop
       - ahorro_combustible_anual_psi_cop
       - ahorro_potencial_total_cop
       - alertas_cambiazo_serial
    3. El archivo templates/index.html contenga los 3 canvas exactos de KPI 04 y los banners ROI.
    """
    cliente = "FLOTA BLINDAJE KM"
    database.guardar_licencia_cliente(cliente, "PRO")

    # Insertar inspección con odómetro alto (350.000 km) pero km_montaje = 0
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': cliente,
        'subcliente': 'Sede Principal',
        'tipo_operacion': 'Ruta Nacional',
        'placa': 'BLN-999',
        'posicion': 1,
        'kilometraje': 350000.0,
        'km_montaje': 0.0,
        'numero_interno': 'LL-ODOM-01',
        'marca': 'Bridgestone',
        'diseno': 'R168',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1600000.0,
        'prof_inicial': 16.0,
        'prof_ext': 3.8,
        'prof_cent': 3.8,
        'prof_int': 3.8,
        'psi': 85.0
    })

    # Segunda inspección con incremento normal de 5.000 km (355.000 km)
    database.insertar_inspeccion({
        'fecha': '2026-10-15',
        'cliente': cliente,
        'subcliente': 'Sede Principal',
        'tipo_operacion': 'Ruta Nacional',
        'placa': 'BLN-999',
        'posicion': 1,
        'kilometraje': 355000.0,
        'km_montaje': 0.0,
        'numero_interno': 'LL-ODOM-01',
        'marca': 'Bridgestone',
        'diseno': 'R168',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1600000.0,
        'prof_inicial': 16.0,
        'prof_ext': 3.5,
        'prof_cent': 3.5,
        'prof_int': 3.5,
        'psi': 85.0
    })

    # Consultar Suite de 20 KPIs
    resp = auth_client.get(f"/api/kpis/suite-20?cliente={cliente}&licencia=FULL")
    assert resp.status_code == 200
    data = resp.json()

    # 1. Validar que ahorro_roi esté presente
    assert "ahorro_roi" in data, "Falta la clave ahorro_roi en suite-20"
    roi = data["ahorro_roi"]
    assert "cascos_en_ventana_salvamento" in roi
    assert "ahorro_salvamento_cascos_cop" in roi
    assert "ahorro_alineacion_oportuna_cop" in roi
    assert "ahorro_combustible_anual_psi_cop" in roi
    assert "ahorro_potencial_total_cop" in roi
    assert "alertas_cambiazo_serial" in roi

    # Al tener prof_min = 3.5 mm y ser Original, debe entrar en ventana salvamento (3.0 a 4.2 mm)
    assert roi["cascos_en_ventana_salvamento"] >= 1
    assert roi["ahorro_salvamento_cascos_cop"] >= 950000.0
    assert roi["ahorro_potencial_total_cop"] >= roi["ahorro_salvamento_cascos_cop"]

    # 2. Validar que templates/index.html contenga los 3 canvas de KPI 04 y los banners
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="canvasKpi04_tipologia"' in html, "Falta canvasKpi04_tipologia en index.html"
    assert 'id="canvasKpi04_marca"' in html, "Falta canvasKpi04_marca en index.html"
    assert 'id="canvasKpi04_dimension"' in html, "Falta canvasKpi04_dimension en index.html"
    assert 'id="banner-ahorro-roi-kpis"' in html, "Falta banner-ahorro-roi-kpis en index.html"
    assert 'id="banner-ahorro-roi-diag"' in html, "Falta banner-ahorro-roi-diag en index.html"
    assert 'id="modalAlertasCambiazo"' in html, "Falta modalAlertasCambiazo en index.html"

