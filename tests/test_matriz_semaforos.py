import pytest
import pandas as pd
from fastapi.testclient import TestClient
import database
import pdf_generator
from server import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    database.inicializar_bd()

def test_calculo_profundidad_minima_pb():
    """
    Regla A:
    PB = min({p in {prof_ext, prof_cent, prof_int} | p > 0})
    Si todas son <= 0, PB = 0.0 (Sin datos / Casco).
    """
    df = pd.DataFrame([
        {
            'placa': 'TEST-PB1',
            'posicion': 1,
            'prof_ext': 7.5,
            'prof_cent': 6.2,
            'prof_int': 8.0,
            'cliente': 'Flota Test',
            'tipologia': 'Camión Sencillo (4x2)'
        },
        {
            'placa': 'TEST-PB2',
            'posicion': 1,
            'prof_ext': 0.0,
            'prof_cent': 0.0,
            'prof_int': 0.0,
            'cliente': 'Flota Test',
            'tipologia': 'Camión Sencillo (4x2)'
        },
        {
            'placa': 'TEST-PB3',
            'posicion': 1,
            'prof_ext': -1.0,
            'prof_cent': 4.5,
            'prof_int': 0.0,
            'cliente': 'Flota Test',
            'tipologia': 'Camión Sencillo (4x2)'
        }
    ])
    matriz = database.calcular_matriz_semaforos_posicion(df)
    filas_map = {f['placa']: f for f in matriz['filas']}

    # Caso 1: min(7.5, 6.2, 8.0) = 6.2
    assert filas_map['TEST-PB1']['posiciones'][1]['pb'] == 6.2

    # Caso 2: todos <= 0 -> pb = 0.0, color gris
    assert filas_map['TEST-PB2']['posiciones'][1]['pb'] == 0.0
    assert filas_map['TEST-PB2']['posiciones'][1]['color'] == 'gris'
    assert filas_map['TEST-PB2']['posiciones'][1]['icono'] == '⚪'

    # Caso 3: solo 4.5 > 0 -> min({4.5}) = 4.5
    assert filas_map['TEST-PB3']['posiciones'][1]['pb'] == 4.5

def test_jerarquia_dinamica_limite_retiro():
    """
    Regla B: Jerarquía dinámica de límite en cascada:
    1. Cliente + Sede + Eje (ej: Metrollantas + Teusaca + DIRECCIONAL -> 4.0 mm)
    2. Cliente + Sede (ej: Metrollantas + Teusaca -> 3.5 mm)
    3. Cliente + Eje (ej: Metrollantas + DIRECCIONAL -> 3.0 mm)
    4. Cliente general (ej: Metrollantas general -> 3.0 mm)
    5. Fallback por defecto (3.0 mm)
    """
    cli = 'CLIENTE_JERNUEVA'
    database.guardar_limite_retiro_cliente(cli, 3.0, subcliente='TODOS', eje='TODOS')
    database.guardar_limite_retiro_cliente(cli, 3.2, subcliente='TODOS', eje='DIRECCIONAL')
    database.guardar_limite_retiro_cliente(cli, 3.5, subcliente='SEDE SUR', eje='TODOS')
    database.guardar_limite_retiro_cliente(cli, 4.0, subcliente='SEDE NORTE', eje='DIRECCIONAL')

    resolver = database._construir_cache_limites_retiro()

    # 1. Exacto: Cliente + Sede Norte + DIRECCIONAL -> 4.0 mm
    assert resolver(cli, 'SEDE NORTE', 'DIRECCIONAL') == 4.0

    # 2. Cliente + Sede Sur (todos los ejes de esa sede) -> 3.5 mm (incluso en TRACCIÓN)
    assert resolver(cli, 'SEDE SUR', 'TRACCIÓN') == 3.5

    # 3. Cliente + Eje DIRECCIONAL en sede sin regla de sede (ej: SEDE CALI) -> 3.2 mm
    assert resolver(cli, 'SEDE CALI', 'DIRECCIONAL') == 3.2

    # 4. Cliente en eje y sede sin regla (ej: SEDE CALI + TRACCIÓN) -> Fallback cliente (3.0 mm)
    assert resolver(cli, 'SEDE CALI', 'TRACCIÓN') == 3.0

    # 5. Cliente desconocido -> Fallback sistema 3.0 mm
    assert resolver('CLIENTE_TOTALMENTE_DESCONOCIDO', 'X', 'Y') == 3.0

def test_umbrales_semaforo_rojo_amarillo_verde_gris():
    """
    Regla C:
    🔴 Rojo: PB <= L (Retiro inmediato)
    🟡 Amarillo: L < PB <= L + 2.0 mm (Próxima a cambio)
    🟢 Verde: PB > L + 2.0 mm (Óptimo)
    ⚪ Gris: PB <= 0 (Sin datos / casco)
    """
    cli = 'FLOTA_UMBRALES'
    database.guardar_limite_retiro_cliente(cli, 4.0, subcliente='TODOS', eje='TODOS')

    df = pd.DataFrame([
        # Llanta en Pos 1: PB = 3.5 <= 4.0 -> ROJO
        {
            'placa': 'V-ROJO',
            'posicion': 1,
            'prof_ext': 3.5,
            'prof_cent': 3.8,
            'prof_int': 4.0,
            'cliente': cli,
            'subcliente': 'TODOS',
            'tipologia': 'Camión Sencillo (4x2)'
        },
        # Llanta en Pos 1: PB = 5.5 (4.0 < 5.5 <= 6.0) -> AMARILLO
        {
            'placa': 'V-AMARILLO',
            'posicion': 1,
            'prof_ext': 5.5,
            'prof_cent': 6.0,
            'prof_int': 5.8,
            'cliente': cli,
            'subcliente': 'TODOS',
            'tipologia': 'Camión Sencillo (4x2)'
        },
        # Llanta en Pos 1: PB = 8.0 (> 6.0) -> VERDE
        {
            'placa': 'V-VERDE',
            'posicion': 1,
            'prof_ext': 8.0,
            'prof_cent': 8.2,
            'prof_int': 8.5,
            'cliente': cli,
            'subcliente': 'TODOS',
            'tipologia': 'Camión Sencillo (4x2)'
        },
        # Llanta en Pos 1: PB <= 0 -> GRIS
        {
            'placa': 'V-GRIS',
            'posicion': 1,
            'prof_ext': 0.0,
            'prof_cent': 0.0,
            'prof_int': 0.0,
            'cliente': cli,
            'subcliente': 'TODOS',
            'tipologia': 'Camión Sencillo (4x2)'
        }
    ])

    matriz = database.calcular_matriz_semaforos_posicion(df)
    filas = {f['placa']: f for f in matriz['filas']}

    assert filas['V-ROJO']['posiciones'][1]['color'] == 'rojo'
    assert filas['V-ROJO']['posiciones'][1]['estado'] == 'Retiro Inmediato'

    assert filas['V-AMARILLO']['posiciones'][1]['color'] == 'amarillo'
    assert filas['V-AMARILLO']['posiciones'][1]['estado'] == 'Próxima a Cambio'

    assert filas['V-VERDE']['posiciones'][1]['color'] == 'verde'
    assert filas['V-VERDE']['posiciones'][1]['estado'] == 'Estado Óptimo'

    assert filas['V-GRIS']['posiciones'][1]['color'] == 'gris'
    assert filas['V-GRIS']['posiciones'][1]['estado'] == 'Sin Datos / Casco'

    # Verificar conteos de columna y totales
    assert matriz['totales_posicion'][1]['rojo'] == 1
    assert matriz['totales_posicion'][1]['amarillo'] == 1
    assert matriz['totales_posicion'][1]['verde'] == 1
    assert matriz['totales_posicion'][1]['gris'] == 1

def test_api_matriz_semaforos(inspector_token):
    """Verifica que el endpoint /api/diagnostico/matriz-semaforos responda correctamente"""
    res = client.get("/api/diagnostico/matriz-semaforos", headers={"Authorization": f"Bearer {inspector_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "posiciones" in data
    assert "filas" in data
    assert "totales_posicion" in data
    assert "resumen_global" in data
    assert isinstance(data["posiciones"], list)
    assert isinstance(data["filas"], list)

def test_pdf_consolidado_incluye_matriz_semaforos():
    """Verifica que el PDF consolidado se genere con la matriz de semáforos por posición"""
    pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada()
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b'%PDF-')

def test_matriz_semaforos_inspector_multiples_flotas():
    """
    Verifica que un usuario inspector con múltiples flotas asignadas (separadas por coma)
    pueda ver las inspecciones de todas sus flotas asignadas, filtrar por cada una de ellas
    y no pueda acceder a flotas no asignadas.
    """
    import server

    # 1. Crear usuarios inspectores
    database.crear_usuario(
        username="inspector_multiflotas",
        password="password123",
        nombre_completo="Inspector Multi Flotas",
        rol="inspector",
        cliente_asignado="FLOTA ALPHA, FLOTA BETA",
        vistas_permitidas="patio,diagnostico"
    )
    token_multi = server.crear_token_acceso("inspector_multiflotas", "inspector")

    # 2. Insertar inspecciones para FLOTA ALPHA, FLOTA BETA y FLOTA GAMMA (ajena)
    database.insertar_inspeccion({
        'fecha': '2026-10-15',
        'cliente': 'FLOTA ALPHA',
        'subcliente': 'SEDE A',
        'tipo_operacion': 'URBANO',
        'placa': 'ALP101',
        'posicion': 1,
        'tipologia': 'Camión Sencillo (4x2)',
        'prof_ext': 6.0, 'prof_cent': 6.0, 'prof_int': 6.0
    })
    database.insertar_inspeccion({
        'fecha': '2026-10-15',
        'cliente': 'FLOTA BETA',
        'subcliente': 'SEDE B',
        'tipo_operacion': 'NACIONAL',
        'placa': 'BET202',
        'posicion': 1,
        'tipologia': 'Camión Sencillo (4x2)',
        'prof_ext': 7.0, 'prof_cent': 7.0, 'prof_int': 7.0
    })
    database.insertar_inspeccion({
        'fecha': '2026-10-15',
        'cliente': 'FLOTA GAMMA',
        'subcliente': 'SEDE G',
        'tipo_operacion': 'RURAL',
        'placa': 'GAM303',
        'posicion': 1,
        'tipologia': 'Camión Sencillo (4x2)',
        'prof_ext': 8.0, 'prof_cent': 8.0, 'prof_int': 8.0
    })

    # Caso A: Consulta sin parámetro cliente (o 'Todos') -> Debe incluir ALP101 y BET202, NUNCA GAM303
    res_todos = client.get("/api/diagnostico/matriz-semaforos", headers={"Authorization": f"Bearer {token_multi}"})
    assert res_todos.status_code == 200
    data_todos = res_todos.json()
    placas_todos = [f['placa'] for f in data_todos.get('filas', [])]
    assert 'ALP101' in placas_todos
    assert 'BET202' in placas_todos
    assert 'GAM303' not in placas_todos
    assert len(placas_todos) == 2

    # Caso B: Filtrar por una flota permitida (FLOTA ALPHA)
    res_alpha = client.get("/api/diagnostico/matriz-semaforos?cliente=FLOTA ALPHA", headers={"Authorization": f"Bearer {token_multi}"})
    assert res_alpha.status_code == 200
    data_alpha = res_alpha.json()
    placas_alpha = [f['placa'] for f in data_alpha.get('filas', [])]
    assert 'ALP101' in placas_alpha
    assert 'BET202' not in placas_alpha
    assert 'GAM303' not in placas_alpha

    # Caso C: Filtrar por otra flota permitida (FLOTA BETA)
    res_beta = client.get("/api/diagnostico/matriz-semaforos?cliente=FLOTA BETA", headers={"Authorization": f"Bearer {token_multi}"})
    assert res_beta.status_code == 200
    data_beta = res_beta.json()
    placas_beta = [f['placa'] for f in data_beta.get('filas', [])]
    assert 'BET202' in placas_beta
    assert 'ALP101' not in placas_beta

    # Caso D: Intentar consultar flota no asignada (FLOTA GAMMA) -> 403 Forbidden
    res_gamma = client.get("/api/diagnostico/matriz-semaforos?cliente=FLOTA GAMMA", headers={"Authorization": f"Bearer {token_multi}"})
    assert res_gamma.status_code == 403
    assert "No tiene permisos" in res_gamma.json().get("detail", "")

def test_matriz_semaforos_inspector_flota_unica():
    """Verifica que un inspector con una sola flota asignada solo acceda a su flota"""
    import server

    database.crear_usuario(
        username="inspector_uniflota",
        password="password123",
        nombre_completo="Inspector Flota Única",
        rol="inspector",
        cliente_asignado="FLOTA ALPHA",
        vistas_permitidas="patio,diagnostico"
    )
    token_single = server.crear_token_acceso("inspector_uniflota", "inspector")

    # Consulta general solo debe ver FLOTA ALPHA
    res = client.get("/api/diagnostico/matriz-semaforos", headers={"Authorization": f"Bearer {token_single}"})
    assert res.status_code == 200
    placas = [f['placa'] for f in res.json().get('filas', [])]
    assert 'ALP101' in placas
    assert 'BET202' not in placas
    assert 'GAM303' not in placas

    # Consulta a FLOTA BETA debe retornar 403
    res_beta = client.get("/api/diagnostico/matriz-semaforos?cliente=FLOTA BETA", headers={"Authorization": f"Bearer {token_single}"})
    assert res_beta.status_code == 403

def test_pdf_consolidado_inspector_permisos():
    """Verifica que el informe PDF consolidado respete las flotas asignadas del inspector"""
    import server

    token_multi = server.crear_token_acceso("inspector_multiflotas", "inspector")

    # Flota permitida -> 200 OK
    res_ok = client.get("/api/informe-pdf-consolidado?cliente=FLOTA ALPHA", headers={"Authorization": f"Bearer {token_multi}"})
    assert res_ok.status_code == 200
    assert res_ok.headers.get("content-type") == "application/pdf"

    # Flota no permitida -> 403 Forbidden
    res_denied = client.get("/api/informe-pdf-consolidado?cliente=FLOTA GAMMA", headers={"Authorization": f"Bearer {token_multi}"})
    assert res_denied.status_code == 403

