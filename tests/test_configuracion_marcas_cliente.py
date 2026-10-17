import pytest
import database
import server
from fastapi.testclient import TestClient

def test_bd_tabla_marcas_cliente_y_crud(test_db):
    # 1. Guardar marcas para clientes distintos
    assert database.guardar_marca_cliente('TransCarga', 'Michelin') is True
    assert database.guardar_marca_cliente('TRANSCARGA', 'Goodyear') is True
    assert database.guardar_marca_cliente('Axxom', 'Bridgestone') is True

    # 2. Consultar marcas por cliente (insensible a mayúsculas/minúsculas)
    marcas_trans = database.obtener_marcas_por_cliente('transcarga')
    assert len(marcas_trans) == 2
    assert 'Goodyear' in marcas_trans
    assert 'Michelin' in marcas_trans

    marcas_axxom = database.obtener_marcas_por_cliente('AXXOM')
    assert marcas_axxom == ['Bridgestone']

    # 3. Consultar todas las configuraciones
    todas = database.obtener_todas_configuraciones_marcas()
    assert len(todas) >= 3
    assert any(t['cliente'] == 'TRANSCARGA' and t['marca'] == 'Michelin' for t in todas)

    # 4. Eliminar por cliente y marca
    assert database.eliminar_marca_cliente('TRANSCARGA', 'Goodyear') is True
    marcas_post_del = database.obtener_marcas_por_cliente('TRANSCARGA')
    assert 'Goodyear' not in marcas_post_del
    assert 'Michelin' in marcas_post_del

    # 5. Eliminar por ID
    item_michelin = next(t for t in database.obtener_todas_configuraciones_marcas() if t['cliente'] == 'TRANSCARGA')
    assert database.eliminar_marca_cliente_por_id(item_michelin['id']) is True
    assert database.obtener_marcas_por_cliente('TRANSCARGA') == []

def test_obtener_valores_unicos_campo_marcas_filtrado(test_db):
    # Parametrizar marcas específicas para una flota
    database.guardar_marca_cliente('LOGISTICA_CENTRO', 'Pirelli')
    database.guardar_marca_cliente('LOGISTICA_CENTRO', 'Hankook')

    # Al filtrar por ese cliente sin 'todas', solo debe retornar las marcas parametrizadas
    marcas_filtradas = database.obtener_valores_unicos_campo('marca', filtro_cliente='LOGISTICA_CENTRO')
    assert marcas_filtradas == ['Hankook', 'Pirelli']

    # Al solicitar todas=True, debe retornar el catálogo general amplio
    marcas_todas = database.obtener_valores_unicos_campo('marca', filtro_cliente='LOGISTICA_CENTRO', todas=True)
    assert len(marcas_todas) > 2
    assert 'Michelin' in marcas_todas or 'MICHELIN' in [m.upper() for m in marcas_todas]
    assert 'Hankook' in marcas_todas or 'HANKOOK' in [m.upper() for m in marcas_todas]

def test_auto_sincronizacion_marca_al_insertar_inspeccion(test_db):
    # Registrar inspección para cliente con una marca
    datos = {
        'fecha': '2026-10-15',
        'cliente': 'Flota Continental',
        'subcliente': 'Cali',
        'tipo_operacion': 'Urbana',
        'placa': 'CAL-100',
        'posicion': 1,
        'kilometraje': 12000,
        'tipologia': 'Camión Sencillo (4x2)',
        'marca': 'Double Coin',
        'diseno': 'RR9',
        'dimension': '11R22.5',
        'vida': 'Original',
        'prof_inicial': 15.0,
        'prof_ext': 14.0,
        'prof_cent': 14.0,
        'prof_int': 14.0,
        'numero_interno': 'DC-01'
    }
    database.insertar_inspeccion(datos)

    # La marca 'DOUBLE COIN' debe sincronizarse como marca habitual para 'FLOTA CONTINENTAL'
    marcas_flota = database.obtener_marcas_por_cliente('FLOTA CONTINENTAL')
    assert any('DOUBLE COIN' in m.upper() for m in marcas_flota)

def test_api_endpoints_marcas_cliente(test_db, auth_client):
    # 1. Asociar marca mediante POST /api/configuracion-marcas-cliente
    resp_post = auth_client.post('/api/configuracion-marcas-cliente', json={
        'cliente': 'Transportes Rapidos',
        'marca': 'Toyo'
    })
    assert resp_post.status_code == 200
    assert resp_post.json()['status'] == 'ok'

    # 2. Consultar marcas del cliente vía GET /api/configuracion-marcas-cliente?cliente=...
    resp_get = auth_client.get('/api/configuracion-marcas-cliente?cliente=Transportes Rapidos')
    assert resp_get.status_code == 200
    datos_get = resp_get.json()
    assert datos_get['cliente'] == 'TRANSPORTES RAPIDOS'
    assert 'Toyo' in datos_get['marcas']

    # 3. Consultar vía /api/valores-campo?campo=marca&cliente=...
    resp_campo = auth_client.get('/api/valores-campo?campo=marca&cliente=Transportes Rapidos')
    assert resp_campo.status_code == 200
    marcas_campo = resp_campo.json()
    assert marcas_campo == ['Toyo']

    # 4. Consultar todas las marcas del catálogo vía /api/valores-campo?campo=marca&cliente=...&todas=true
    resp_campo_todas = auth_client.get('/api/valores-campo?campo=marca&cliente=Transportes Rapidos&todas=true')
    assert resp_campo_todas.status_code == 200
    assert len(resp_campo_todas.json()) > 1

    # 5. Listar todas las configuraciones
    resp_todas = auth_client.get('/api/configuracion-marcas-cliente')
    assert resp_todas.status_code == 200
    lista_todas = resp_todas.json()
    assert any(x['cliente'] == 'TRANSPORTES RAPIDOS' and x['marca'] == 'Toyo' for x in lista_todas)

    # 6. Eliminar asociación vía DELETE /api/configuracion-marcas-cliente
    resp_del = auth_client.delete('/api/configuracion-marcas-cliente?cliente=TRANSPORTES RAPIDOS&marca=Toyo')
    assert resp_del.status_code == 200
    assert resp_del.json()['status'] == 'ok'

    # Verificar que ya no aparece
    resp_get_after = auth_client.get('/api/configuracion-marcas-cliente?cliente=Transportes Rapidos')
    assert resp_get_after.json()['marcas'] == []

def test_api_seguridad_marcas_cliente(test_db):
    client_anon = TestClient(server.app)

    # Petición no autenticada a GET /api/configuracion-marcas-cliente debe fallar con 401
    resp_anon = client_anon.get('/api/configuracion-marcas-cliente')
    assert resp_anon.status_code == 401

    # Petición no autenticada a POST /api/configuracion-marcas-cliente debe fallar con 401
    resp_post_anon = client_anon.post('/api/configuracion-marcas-cliente', json={'cliente': 'A', 'marca': 'B'})
    assert resp_post_anon.status_code == 401
