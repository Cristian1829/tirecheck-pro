import pytest
import database

def test_api_kpis_llantas_incluye_tipo_eje_heuristico_y_esquema(test_db, auth_client):
    """
    Prueba 1: Verifica que /api/kpis-llantas retorne el campo calculado 'tipo_eje'
    tanto por esquema de tipología como por resolución heurística:
    - Cabezote (6x4) pos 1 -> direccional
    - Cabezote (6x4) pos 3 -> traccion
    - Trailer (3 Ejes - 12 Llantas) pos 5 -> libre
    - Trailer (2 Ejes - 8 Llantas + Repuesto) pos 9 -> repuesto
    """
    inspecciones_test = [
        {
            'fecha': '2026-10-10',
            'cliente': 'TRANSPORTES DEL VALLE',
            'subcliente': 'BOGOTÁ',
            'tipo_operacion': 'CARGA',
            'placa': 'TRK-001',
            'tipologia': 'Cabezote (6x4)',
            'posicion': 1,
            'kilometraje': 50000.0,
            'km_montaje': 10000.0,
            'numero_interno': 'LL-DIR-01',
            'marca': 'MICHELIN',
            'diseno': 'X MULTI Z',
            'dimension': '295/80R22.5',
            'vida': 'ORIGINAL',
            'precio': 1800000.0,
            'prof_inicial': 16.0,
            'prof_ext': 13.0,
            'prof_cent': 13.0,
            'prof_int': 13.0,
            'psi': 110.0
        },
        {
            'fecha': '2026-10-10',
            'cliente': 'TRANSPORTES DEL VALLE',
            'subcliente': 'BOGOTÁ',
            'tipo_operacion': 'CARGA',
            'placa': 'TRK-001',
            'tipologia': 'Cabezote (6x4)',
            'posicion': 3,
            'kilometraje': 50000.0,
            'km_montaje': 10000.0,
            'numero_interno': 'LL-TRAC-01',
            'marca': 'GOODYEAR',
            'diseno': 'KMAX D',
            'dimension': '295/80R22.5',
            'vida': 'REENCAUCHE',
            'precio': 900000.0,
            'prof_inicial': 20.0,
            'prof_ext': 15.0,
            'prof_cent': 15.0,
            'prof_int': 15.0,
            'psi': 105.0
        },
        {
            'fecha': '2026-10-10',
            'cliente': 'TRANSPORTES DEL VALLE',
            'subcliente': 'BOGOTÁ',
            'tipo_operacion': 'CARGA',
            'placa': 'TRL-002',
            'tipologia': 'Trailer (3 Ejes - 12 Llantas)',
            'posicion': 5,
            'kilometraje': 80000.0,
            'km_montaje': 20000.0,
            'numero_interno': 'LL-LIB-01',
            'marca': 'BRIDGESTONE',
            'diseno': 'R168',
            'dimension': '295/80R22.5',
            'vida': 'ORIGINAL',
            'precio': 1750000.0,
            'prof_inicial': 15.0,
            'prof_ext': 11.0,
            'prof_cent': 11.0,
            'prof_int': 11.0,
            'psi': 115.0
        },
        {
            'fecha': '2026-10-10',
            'cliente': 'TRANSPORTES DEL VALLE',
            'subcliente': 'BOGOTÁ',
            'tipo_operacion': 'CARGA',
            'placa': 'TRL-003',
            'tipologia': 'Trailer (2 Ejes - 8 Llantas + Repuesto)',
            'posicion': 9,
            'kilometraje': 40000.0,
            'km_montaje': 0.0,
            'numero_interno': 'LL-REP-01',
            'marca': 'CONTINENTAL',
            'diseno': 'CONTI HYBRID HT3',
            'dimension': '295/80R22.5',
            'vida': 'REENCAUCHE',
            'precio': 850000.0,
            'prof_inicial': 14.0,
            'prof_ext': 12.0,
            'prof_cent': 12.0,
            'prof_int': 12.0,
            'psi': 110.0
        }
    ]

    for insp in inspecciones_test:
        database.insertar_inspeccion(insp)

    res = auth_client.get("/api/kpis-llantas")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 4

    mapa_por_llanta = {item['numero_interno']: item for item in data}

    assert 'LL-DIR-01' in mapa_por_llanta
    assert mapa_por_llanta['LL-DIR-01']['tipo_eje'] == 'direccional'

    assert 'LL-TRAC-01' in mapa_por_llanta
    assert mapa_por_llanta['LL-TRAC-01']['tipo_eje'] == 'traccion'

    assert 'LL-LIB-01' in mapa_por_llanta
    assert mapa_por_llanta['LL-LIB-01']['tipo_eje'] == 'libre'

    assert 'LL-REP-01' in mapa_por_llanta
    assert mapa_por_llanta['LL-REP-01']['tipo_eje'] == 'repuesto'


def test_normalizacion_marcas_y_calculos_matriz_composicion(test_db, auth_client):
    """
    Prueba 2: Verifica que /api/kpis-llantas unifique marcas con espacios y distinta
    capitalización ('Michelin', 'MICHELIN ', 'michelin') bajo 'MICHELIN' y que
    prof_actual_min excluya valores <= 0.
    """
    variantes = [
        ('LL-NORM-1', 'Michelin', 'X Multi Z', '295/80R22.5', 'Original', 12.0),
        ('LL-NORM-2', 'MICHELIN ', 'X MULTI Z', '295/80R22.5', 'Reencauche', 10.0),
        ('LL-NORM-3', 'michelin', 'x multi z', '295/80R22.5', 'Original', 11.5)
    ]

    for num, mar, dis, dim, vid, prof in variantes:
        database.insertar_inspeccion({
            'fecha': '2026-10-15',
            'cliente': 'LOGÍSTICA INTEGRAL',
            'subcliente': 'CALI',
            'tipo_operacion': 'URBANO',
            'placa': 'V-NORM-01',
            'tipologia': 'Cabezote (6x4)',
            'posicion': 1,
            'kilometraje': 30000.0,
            'km_montaje': 0.0,
            'numero_interno': num,
            'marca': mar,
            'diseno': dis,
            'dimension': dim,
            'vida': vid,
            'precio': 1900000.0,
            'prof_inicial': 16.0,
            'prof_ext': prof,
            'prof_cent': 0.0,  # 0.0 debe ser excluido al calcular prof_actual_min
            'prof_int': prof + 1.0,
            'psi': 110.0
        })

    res = auth_client.get("/api/kpis-llantas?cliente=LOGÍSTICA+INTEGRAL")
    assert res.status_code == 200
    llantas = res.json()
    assert len(llantas) == 3

    for ll in llantas:
        assert ll['marca'] == 'MICHELIN'
        assert ll['diseno'] == 'X MULTI Z'
        assert ll['dimension'] == '295/80R22.5'
        assert ll['prof_actual_min'] > 0.0


def test_regla_de_oro_1_direccion_sin_reencauches(test_db, auth_client):
    """
    Prueba 3: Verifica que el candado y filtro de tipo_eje == 'direccional'
    identifiquen 0.0% de reencauche en dirección en una flota saludable.
    """
    flota_saludable = [
        {
            'fecha': '2026-10-18',
            'cliente': 'FLOTA SALUDABLE',
            'subcliente': 'MEDELLÍN',
            'tipo_operacion': 'TRONCAL',
            'placa': 'SAL-101',
            'tipologia': 'Cabezote (6x4)',
            'posicion': 1,  # Direccional
            'kilometraje': 20000.0,
            'km_montaje': 0.0,
            'numero_interno': 'SAL-DIR-1',
            'marca': 'MICHELIN',
            'diseno': 'X MULTI ENERGY Z',
            'dimension': '295/80R22.5',
            'vida': 'ORIGINAL',
            'precio': 2100000.0,
            'prof_inicial': 16.0,
            'prof_ext': 14.0,
            'prof_cent': 14.0,
            'prof_int': 14.0,
            'psi': 110.0
        },
        {
            'fecha': '2026-10-18',
            'cliente': 'FLOTA SALUDABLE',
            'subcliente': 'MEDELLÍN',
            'tipo_operacion': 'TRONCAL',
            'placa': 'SAL-101',
            'tipologia': 'Cabezote (6x4)',
            'posicion': 2,  # Direccional
            'kilometraje': 20000.0,
            'km_montaje': 0.0,
            'numero_interno': 'SAL-DIR-2',
            'marca': 'MICHELIN',
            'diseno': 'X MULTI ENERGY Z',
            'dimension': '295/80R22.5',
            'vida': 'ORIGINAL',
            'precio': 2100000.0,
            'prof_inicial': 16.0,
            'prof_ext': 14.0,
            'prof_cent': 14.0,
            'prof_int': 14.0,
            'psi': 110.0
        },
        {
            'fecha': '2026-10-18',
            'cliente': 'FLOTA SALUDABLE',
            'subcliente': 'MEDELLÍN',
            'tipo_operacion': 'TRONCAL',
            'placa': 'SAL-101',
            'tipologia': 'Cabezote (6x4)',
            'posicion': 3,  # Tracción
            'kilometraje': 20000.0,
            'km_montaje': 0.0,
            'numero_interno': 'SAL-TRAC-1',
            'marca': 'BANDAG',
            'diseno': 'BDR-HT',
            'dimension': '295/80R22.5',
            'vida': 'REENCAUCHE',
            'precio': 950000.0,
            'prof_inicial': 18.0,
            'prof_ext': 12.0,
            'prof_cent': 12.0,
            'prof_int': 12.0,
            'psi': 105.0
        }
    ]

    for insp in flota_saludable:
        database.insertar_inspeccion(insp)

    res = auth_client.get("/api/kpis-llantas?cliente=FLOTA+SALUDABLE")
    assert res.status_code == 200
    llantas = res.json()

    direccionales = [ll for ll in llantas if ll['tipo_eje'] == 'direccional']
    assert len(direccionales) == 2

    reencauches_direccion = [ll for ll in direccionales if 'reenc' in str(ll.get('vida', '')).lower()]
    assert len(reencauches_direccion) == 0

    pct_reenc_dir = (len(reencauches_direccion) / len(direccionales)) * 100.0
    assert pct_reenc_dir == 0.0


def test_vista_composicion_presente_en_html(auth_client):
    """
    Prueba 4: Verifica que GET / retorne HTTP 200 e incluya la estructura DOM
    completa de Composición de Flota (IDs exactos de filtros, KPIs, gráficos y matriz).
    """
    res = auth_client.get("/")
    assert res.status_code == 200
    html = res.text

    # 1. Pestaña y Navegación
    assert 'id="vista-composicion"' in html or 'id="vista_composicion"' in html
    assert 'id="nav-btn-composicion"' in html

    # 2. Los 7 Filtros Interactivos en Cascada
    filtros_requeridos = [
        'id="filtro_comp_cliente"',
        'id="filtro_comp_subcliente"',
        'id="filtro_comp_tipo_eje"',
        'id="filtro_comp_vida"',
        'id="filtro_comp_marca"',
        'id="filtro_comp_dimension"',
        'id="filtro_comp_diseno"'
    ]
    for filtro in filtros_requeridos:
        assert filtro in html, f"Filtro faltante: {filtro}"

    # 3. Las 6 Tarjetas Resumen de KPIs
    kpis_requeridos = [
        'id="comp_kpi_total_llantas"',
        'id="comp_kpi_total_vehiculos"',
        'id="comp_kpi_pct_reenc"',
        'id="comp_kpi_cnt_reenc"',
        'id="comp_kpi_pct_orig"',
        'id="comp_kpi_cnt_orig"',
        'id="comp_kpi_top_marca"',
        'id="comp_kpi_sub_marca"',
        'id="comp_kpi_top_dim"',
        'id="comp_kpi_sub_dim"',
        'id="comp_kpi_top_diseno"',
        'id="comp_kpi_sub_diseno"'
    ]
    for kpi in kpis_requeridos:
        assert kpi in html, f"Elemento KPI faltante: {kpi}"

    # 4. Los 4 Canvas Gráficos y Botones Píldora
    canvas_requeridos = [
        'id="chartCompVidaEje"',
        'id="chartCompMarcas"',
        'id="chartCompDimensiones"',
        'id="chartCompDisenos"'
    ]
    for canvas in canvas_requeridos:
        assert canvas in html, f"Canvas faltante: {canvas}"

    pildoras_requeridas = [
        'id="btn_eje_comp_TODOS"',
        'id="btn_eje_comp_direccional"',
        'id="btn_eje_comp_traccion"',
        'id="btn_eje_comp_libre"'
    ]
    for pildora in pildoras_requeridas:
        assert pildora in html, f"Botón píldora faltante: {pildora}"

    # 5. Tabla Matriz y Contador de Combinaciones
    assert 'id="badge_comp_combinaciones"' in html
    assert 'id="tbody_composicion_flota"' in html

    # 6. Funciones JavaScript de Composición
    assert 'cargarComposicionFlotaWeb' in html
    assert 'renderizarComposicionFlotaWeb' in html
    assert 'seleccionarEjeRapidoComposicion' in html
    assert 'exportarComposicionExcel' in html
