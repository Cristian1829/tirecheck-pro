import pytest
import database
import server

def test_asociacion_fija_placa_esquema(test_db, auth_client):
    # 1. Registrar inspección inicial con tipología Trailer (3 Ejes - 12 Llantas)
    datos = {
        'fecha': '2026-10-10',
        'cliente': 'Transportes del Caribe',
        'subcliente': 'Barranquilla',
        'tipo_operacion': 'Refrigerada',
        'placa': 'TRL-999',
        'posicion': 1,
        'kilometraje': 85400,
        'tipologia': 'Trailer (3 Ejes - 12 Llantas)',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'prof_ext': 14.0,
        'prof_cent': 14.0,
        'prof_int': 14.0,
        'prof_inicial': 16.5,
        'numero_interno': 'LL-TRL-01'
    }
    database.insertar_inspeccion(datos)

    # 2. Consultar endpoint /api/vehiculo-perfil
    resp = auth_client.get('/api/vehiculo-perfil?placa=TRL-999')
    assert resp.status_code == 200
    data = resp.json()
    assert data['encontrado'] is True
    assert data['placa'] == 'TRL-999'
    assert data['tipologia'] == 'TRAILER (3 EJES - 12 LLANTAS)'
    assert data['cliente'] == 'TRANSPORTES DEL CARIBE'
    assert data['subcliente'] == 'BARRANQUILLA'
    assert data['tipo_operacion'] == 'REFRIGERADA'
    assert data['ultimo_km'] == 85400.0
    assert data['cant_llantas'] == 12
    assert len(data['posiciones']) == 12
    assert 12 in data['posiciones']

def test_autocompletado_llanta_dependiente_cliente(test_db, auth_client):
    # 1. Registrar llanta '1010' en 'Cliente A' como Michelin
    datos_a = {
        'fecha': '2026-10-01',
        'cliente': 'Cliente A',
        'subcliente': 'Sede Centro',
        'tipo_operacion': 'Carga Seca',
        'placa': 'AAA111',
        'posicion': 1,
        'kilometraje': 10000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'prof_inicial': 16.5,
        'precio': 1850000,
        'prof_ext': 13.0,
        'prof_cent': 13.0,
        'prof_int': 13.0,
        'numero_interno': '1010'
    }
    database.insertar_inspeccion(datos_a)

    # 2. Registrar la misma numeración '1010' en 'Cliente B' como Bridgestone
    datos_b = {
        'fecha': '2026-10-02',
        'cliente': 'Cliente B',
        'subcliente': 'Sede Norte',
        'tipo_operacion': 'Líquidos',
        'placa': 'BBB222',
        'posicion': 3,
        'kilometraje': 20000,
        'tipologia': 'Camión Sencillo (4x2)',
        'marca': 'Bridgestone',
        'diseno': 'M726 EL',
        'dimension': '11R22.5',
        'vida': 'Original',
        'prof_inicial': 24.5,
        'precio': 1950000,
        'prof_ext': 20.0,
        'prof_cent': 20.0,
        'prof_int': 20.0,
        'numero_interno': '1010'
    }
    database.insertar_inspeccion(datos_b)

    # 3. Consultar /api/llanta-por-cliente para Cliente A
    resp_a = auth_client.get('/api/llanta-por-cliente?cliente=Cliente A&numero_interno=1010')
    assert resp_a.status_code == 200
    res_data_a = resp_a.json()
    assert res_data_a['encontrado'] is True
    assert res_data_a['datos']['marca'] == 'MICHELIN'
    assert res_data_a['datos']['diseno'] == 'X MULTI Z'
    assert res_data_a['datos']['dimension'] == '295/80R22.5'
    assert res_data_a['datos']['prof_inicial'] == 16.5

    # 4. Consultar /api/llanta-por-cliente para Cliente B
    resp_b = auth_client.get('/api/llanta-por-cliente?cliente=Cliente B&numero_interno=1010')
    assert resp_b.status_code == 200
    res_data_b = resp_b.json()
    assert res_data_b['encontrado'] is True
    assert res_data_b['datos']['marca'] == 'BRIDGESTONE'
    assert res_data_b['datos']['diseno'] == 'M726 EL'
    assert res_data_b['datos']['dimension'] == '11R22.5'
    assert res_data_b['datos']['prof_inicial'] == 24.5

def test_candado_rotacion_intermensual(test_db):
    # 1. Registrar llanta 'ROT-01' en Pos 1 en Octubre 2026
    datos_oct = {
        'fecha': '2026-10-05',
        'cliente': 'Flota Andina',
        'subcliente': 'Bogota',
        'tipo_operacion': 'Paqueteo',
        'placa': 'AND-100',
        'posicion': 1,
        'kilometraje': 50000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Goodyear',
        'diseno': 'KMax S',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'numero_interno': 'ROT-01'
    }
    database.insertar_inspeccion(datos_oct)

    # 2. Intentar registrar la misma llanta en Pos 5 en el MISMO mes de Octubre -> DEBE BLOQUEARSE
    datos_oct_dup = {
        'fecha': '2026-10-20',
        'cliente': 'Flota Andina',
        'subcliente': 'Bogota',
        'tipo_operacion': 'Paqueteo',
        'placa': 'AND-100',
        'posicion': 5,
        'kilometraje': 52000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Goodyear',
        'diseno': 'KMax S',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 11.5,
        'prof_cent': 11.5,
        'prof_int': 11.5,
        'numero_interno': 'ROT-01'
    }
    val_dup = database.validar_inspeccion_candados(datos_oct_dup)
    assert not val_dup['valido']
    assert 'CANDADO DE NÚMERO INTERNO' in val_dup['mensaje']

    # 3. Intentar registrar la llanta rotada a Pos 5 en NOVIEMBRE (mes siguiente + 20 días) -> DEBE PERMITIRSE
    datos_nov_rot = {
        'fecha': '2026-11-25',
        'cliente': 'Flota Andina',
        'subcliente': 'Bogota',
        'tipo_operacion': 'Paqueteo',
        'placa': 'AND-100',
        'posicion': 5,
        'kilometraje': 55000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Goodyear',
        'diseno': 'KMax S',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'numero_interno': 'ROT-01'
    }
    val_rot = database.validar_inspeccion_candados(datos_nov_rot)
    assert val_rot['valido'] is True

def test_recuperacion_datos_inspeccion_previa_vehiculo_y_posicion(test_db, auth_client):
    # 1. Registrar inspección previa para PREV-01 en Posición 1 y Posición 2
    insp_pos1 = {
        'fecha': '2026-10-01',
        'cliente': 'Logística del Norte',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Granel',
        'placa': 'PREV-01',
        'posicion': 1,
        'kilometraje': 120000,
        'tipologia': 'Camión Sencillo (4x2)',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'prof_inicial': 16.5,
        'precio': 1500000,
        'km_montaje': 45000,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'numero_interno': 'INT-01'
    }
    insp_pos2 = {
        'fecha': '2026-10-01',
        'cliente': 'Logística del Norte',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Granel',
        'placa': 'PREV-01',
        'posicion': 2,
        'kilometraje': 120000,
        'tipologia': 'Camión Sencillo (4x2)',
        'marca': 'Bridgestone',
        'diseno': 'M726 EL',
        'dimension': '295/80R22.5',
        'vida': 'Reencauche',
        'banda_reen': 'BDM Bandag',
        'prof_inicial': 18.0,
        'precio': 980000,
        'km_montaje': 50000,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'numero_interno': 'INT-02'
    }
    database.insertar_inspeccion(insp_pos1)
    database.insertar_inspeccion(insp_pos2)

    # 2. Consultar perfil del vehículo: debe traer Cliente, Subcliente, Operación y Tipología previa
    perfil = database.obtener_perfil_vehiculo('PREV-01')
    assert perfil['encontrado'] is True
    assert perfil['placa'] == 'PREV-01'
    assert perfil['cliente'] == 'LOGÍSTICA DEL NORTE'
    assert perfil['subcliente'] == 'SEDE CENTRAL'
    assert perfil['tipo_operacion'] == 'GRANEL'
    assert perfil['tipologia'] == 'CAMIÓN SENCILLO (4X2)'
    assert perfil['ultimo_km'] == 120000.0

    # Vía API
    resp_perfil = auth_client.get('/api/vehiculo-perfil?placa=PREV-01')
    assert resp_perfil.status_code == 200
    data_p = resp_perfil.json()
    assert data_p['encontrado'] is True
    assert data_p['cliente'] == 'LOGÍSTICA DEL NORTE'
    assert data_p['subcliente'] == 'SEDE CENTRAL'
    assert data_p['tipo_operacion'] == 'GRANEL'
    assert data_p['tipologia'] == 'CAMIÓN SENCILLO (4X2)'

    # 3. Consultar especificaciones de Posición 1
    llanta_pos1 = database.obtener_ultima_inspeccion_posicion('PREV-01', 1)
    assert llanta_pos1 is not None
    assert llanta_pos1['numero_interno'] == 'INT-01'
    assert llanta_pos1['marca'] == 'MICHELIN'
    assert llanta_pos1['diseno'] == 'X MULTI Z'
    assert llanta_pos1['dimension'] == '295/80R22.5'
    assert llanta_pos1['vida'] == 'ORIGINAL'
    assert llanta_pos1['prof_inicial'] == 16.5
    assert llanta_pos1['precio'] == 1500000
    assert llanta_pos1['km_montaje'] == 45000

    # Vía API para Posición 1
    resp_pos1 = auth_client.get('/api/inspeccion-anterior?placa=PREV-01&posicion=1')
    assert resp_pos1.status_code == 200
    data_pos1 = resp_pos1.json()
    assert data_pos1['encontrado'] is True
    assert data_pos1['datos']['numero_interno'] == 'INT-01'
    assert data_pos1['datos']['marca'] == 'MICHELIN'
    assert data_pos1['datos']['diseno'] == 'X MULTI Z'

    # 4. Consultar especificaciones de Posición 2 (Reencauche)
    llanta_pos2 = database.obtener_ultima_inspeccion_posicion('PREV-01', 2)
    assert llanta_pos2 is not None
    assert llanta_pos2['numero_interno'] == 'INT-02'
    assert llanta_pos2['marca'] == 'BRIDGESTONE'
    assert llanta_pos2['vida'] == 'REENCAUCHE'
    assert llanta_pos2['banda_reen'] == 'BDM BANDAG'

    # 5. Posición sin registro previo (por ej. Posición 4)
    llanta_pos4 = database.obtener_ultima_inspeccion_posicion('PREV-01', 4)
    assert llanta_pos4 is None
    resp_pos4 = auth_client.get('/api/inspeccion-anterior?placa=PREV-01&posicion=4')
    assert resp_pos4.status_code == 200
    assert resp_pos4.json()['encontrado'] is False

