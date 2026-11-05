"""Matriz de semáforos por posición: profundidad base, límite de retiro en cascada, colores, API, PDF y permisos."""
import io

import pandas as pd
import pypdf
import pytest
from fastapi.testclient import TestClient

import database
import pdf_generator
import server

client = TestClient(server.app)

# Cada prueba arranca con su propia base vacía: ninguna depende de lo que dejó otra
pytestmark = pytest.mark.usefixtures("test_db")


@pytest.fixture
def tres_flotas():
    """ALPHA y BETA asignadas al inspector multiflota; GAMMA es ajena. Un vehículo por flota en tres colores."""
    database.crear_usuario(
        username="inspector_multiflotas",
        password="password123",
        nombre_completo="Inspector Multi Flotas",
        rol="inspector",
        cliente_asignado="FLOTA ALPHA, FLOTA BETA",
        vistas_permitidas="patio,diagnostico"
    )
    for cliente, sede, operacion, placa, prof in (("FLOTA ALPHA", "SEDE A", "URBANO", "ALP101", 4.0),     # amarillo
                                                  ("FLOTA BETA", "SEDE B", "NACIONAL", "BET202", 7.0),    # verde
                                                  ("FLOTA GAMMA", "SEDE G", "RURAL", "GAM303", 2.5)):     # rojo
        database.insertar_inspeccion({
            'fecha': '2026-10-15', 'cliente': cliente, 'subcliente': sede, 'tipo_operacion': operacion,
            'placa': placa, 'posicion': 1, 'tipologia': 'Camión Sencillo (4x2)',
            'prof_ext': prof, 'prof_cent': prof, 'prof_int': prof
        })
    return {"Authorization": f"Bearer {server.crear_token_acceso('inspector_multiflotas', 'inspector')}"}


def _placas(res):
    assert res.status_code == 200
    return sorted(f['placa'] for f in res.json()['filas'])


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

def test_api_matriz_semaforos(auth_client, tres_flotas):
    """El endpoint devuelve cada vehículo con su color y los totales por posición (límite por defecto 3,0 mm)."""
    data = auth_client.get("/api/diagnostico/matriz-semaforos").json()
    colores = {f['placa']: f['posiciones']['1']['color'] for f in data['filas']}
    assert colores == {'ALP101': 'amarillo', 'BET202': 'verde', 'GAM303': 'rojo'}
    assert data['posiciones'] == [1]
    totales = data['totales_posicion']['1']
    assert (totales['rojo'], totales['amarillo'], totales['verde']) == (1, 1, 1)


def test_pdf_consolidado_incluye_matriz_semaforos():
    """Verifica que el PDF consolidado se genere con la matriz de semáforos por posición"""
    database.insertar_inspeccion({
        'fecha': '2026-10-14', 'cliente': 'FLOTA PDF', 'subcliente': 'SEDE A', 'tipo_operacion': 'CARGA',
        'placa': 'PDF101', 'posicion': 1, 'kilometraje': 50000, 'tipologia': 'Camión Sencillo (4x2)',
        'marca': 'MICHELIN', 'diseno': 'XZE', 'dimension': '295/80R22.5', 'vida': 'Original',
        'prof_ext': 8.0, 'prof_cent': 8.0, 'prof_int': 8.0, 'psi': 100, 'numero_interno': 'PDF-1'
    })
    pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada()
    assert pdf_bytes.startswith(b'%PDF-')
    texto = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)
    assert "Matriz de Semáforos por Posición" in texto
    assert "PDF101" in texto

def test_matriz_semaforos_inspector_multiples_flotas(tres_flotas):
    """Un inspector con varias flotas ve las suyas, puede filtrar por cada una y no entra a una ajena."""
    url = "/api/diagnostico/matriz-semaforos"
    assert _placas(client.get(url, headers=tres_flotas)) == ['ALP101', 'BET202']
    assert _placas(client.get(url + "?cliente=FLOTA ALPHA", headers=tres_flotas)) == ['ALP101']
    assert _placas(client.get(url + "?cliente=FLOTA BETA", headers=tres_flotas)) == ['BET202']

    res_gamma = client.get(url + "?cliente=FLOTA GAMMA", headers=tres_flotas)
    assert res_gamma.status_code == 403
    assert "No tiene permisos" in res_gamma.json().get("detail", "")


def test_matriz_semaforos_inspector_flota_unica(tres_flotas):
    """Un inspector con una sola flota asignada solo ve esa flota."""
    database.crear_usuario(
        username="inspector_uniflota",
        password="password123",
        nombre_completo="Inspector Flota Única",
        rol="inspector",
        cliente_asignado="FLOTA ALPHA",
        vistas_permitidas="patio,diagnostico"
    )
    headers = {"Authorization": f"Bearer {server.crear_token_acceso('inspector_uniflota', 'inspector')}"}

    assert _placas(client.get("/api/diagnostico/matriz-semaforos", headers=headers)) == ['ALP101']
    assert client.get("/api/diagnostico/matriz-semaforos?cliente=FLOTA BETA", headers=headers).status_code == 403


def test_pdf_consolidado_inspector_permisos(tres_flotas):
    """El informe PDF consolidado respeta las flotas asignadas del inspector."""
    res_ok = client.get("/api/informe-pdf-consolidado?cliente=FLOTA ALPHA", headers=tres_flotas)
    assert res_ok.status_code == 200
    assert res_ok.headers.get("content-type") == "application/pdf"
    texto = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(res_ok.content)).pages)
    assert "ALP101" in texto and "GAM303" not in texto and "BET202" not in texto

    res_denied = client.get("/api/informe-pdf-consolidado?cliente=FLOTA GAMMA", headers=tres_flotas)
    assert res_denied.status_code == 403
