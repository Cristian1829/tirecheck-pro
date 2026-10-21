import pytest
import uuid
from datetime import date
from fastapi.testclient import TestClient
import database
from server import app, crear_token_acceso

client = TestClient(app)

@pytest.fixture(autouse=True)
def preparar_bd_pruebas():
    database.inicializar_bd()
    yield

def test_candado_frecuencia_ciudad_limpia_dias_corridos():
    """
    Para CIUDAD LIMPIA: debe habilitar la inspección 20 días después de la última inspección,
    sin exigir que haya cambiado el mes calendario.
    """
    token = crear_token_acceso("admin", "admin")
    headers = {"Authorization": f"Bearer {token}"}

    placa = f"CL{uuid.uuid4().hex[:4].upper()}"
    # Asegurar configuración para Ciudad Limpia
    database.crear_o_actualizar_cliente({
        "cliente": "CIUDAD LIMPIA",
        "dias_espera_inspeccion": 20,
        "requiere_mes_siguiente": False
    })

    # 1. Primera inspección: 1 de Octubre de 2026
    insp_1 = {
        "fecha": "2026-10-01",
        "cliente": "CIUDAD LIMPIA",
        "subcliente": "BOGOTA",
        "tipo_operacion": "ASEO",
        "placa": placa,
        "posicion": 1,
        "kilometraje": 10000,
        "tipologia": "COMPACTADOR 4X2",
        "marca": "GOODYEAR",
        "diseno": "G658",
        "dimension": "295/80R22.5",
        "prof_inicial": 16.0,
        "prof_ext": 15.0,
        "prof_cent": 15.0,
        "prof_int": 15.0,
        "psi": 110,
        "vida": "Original"
    }
    res1 = client.post("/api/inspecciones", json=insp_1, headers=headers)
    assert res1.status_code == 200

    # 2. Intentar segunda inspección el 15 de Octubre (solo han pasado 14 días < 20) -> DEBE BLOQUEARSE
    insp_bloqueada = dict(insp_1)
    insp_bloqueada["fecha"] = "2026-10-15"
    insp_bloqueada["kilometraje"] = 10500
    res2 = client.post("/api/inspecciones", json=insp_bloqueada, headers=headers)
    assert res2.status_code == 400
    assert "candado de frecuencia" in res2.json()["detail"].lower()

    # 3. Intentar segunda inspección el 22 de Octubre (21 días después, MISMO MES) -> DEBE PERMITIRSE
    insp_permitida = dict(insp_1)
    insp_permitida["fecha"] = "2026-10-22"
    insp_permitida["kilometraje"] = 11000
    res3 = client.post("/api/inspecciones", json=insp_permitida, headers=headers)
    assert res3.status_code == 200

def test_candado_frecuencia_demas_clientes_mes_siguiente_y_dias():
    """
    Para los demás clientes: primero debe ser el siguiente mes calendario Y haber pasado 20 días
    desde la última inspección.
    """
    token = crear_token_acceso("admin", "admin")
    headers = {"Authorization": f"Bearer {token}"}

    placa = f"GE{uuid.uuid4().hex[:4].upper()}"
    # Asegurar configuración estándar para cliente general
    database.crear_o_actualizar_cliente({
        "cliente": "FLOTA GENERAL ANDINA",
        "dias_espera_inspeccion": 20,
        "requiere_mes_siguiente": True
    })

    # Caso A: Inspección a inicio de mes (1 de Octubre)
    insp_base = {
        "fecha": "2026-10-01",
        "cliente": "FLOTA GENERAL ANDINA",
        "subcliente": "SEDE NORTE",
        "tipo_operacion": "CARGA",
        "placa": placa,
        "posicion": 1,
        "kilometraje": 20000,
        "tipologia": "TRACTOMULA 3S3",
        "marca": "MICHELIN",
        "diseno": "X MULTI",
        "dimension": "295/80R22.5",
        "prof_inicial": 16.0,
        "prof_ext": 14.0,
        "prof_cent": 14.0,
        "prof_int": 14.0,
        "psi": 110,
        "vida": "Original"
    }
    res_base = client.post("/api/inspecciones", json=insp_base, headers=headers)
    assert res_base.status_code == 200

    # Intento el 25 de Octubre (pasaron 24 días > 20, pero NO es el siguiente mes) -> DEBE BLOQUEARSE
    insp_mismo_mes = dict(insp_base)
    insp_mismo_mes["fecha"] = "2026-10-25"
    insp_mismo_mes["kilometraje"] = 20500
    res_bloq1 = client.post("/api/inspecciones", json=insp_mismo_mes, headers=headers)
    assert res_bloq1.status_code == 400
    assert "candado de frecuencia" in res_bloq1.json()["detail"].lower()

    # Intento el 1 de Noviembre (es siguiente mes Y pasaron 31 días > 20) -> DEBE PERMITIRSE
    insp_sig_mes = dict(insp_base)
    insp_sig_mes["fecha"] = "2026-11-01"
    insp_sig_mes["kilometraje"] = 21000
    res_ok1 = client.post("/api/inspecciones", json=insp_sig_mes, headers=headers)
    assert res_ok1.status_code == 200

def test_candado_frecuencia_fin_de_mes_requiere_ambas_condiciones():
    """
    Si la última inspección fue a fin de mes (ej. 25 de Octubre), el 1 de Noviembre ya es
    siguiente mes, pero NO han pasado los 20 días. Debe esperar a que pasen los 20 días (14 de Noviembre).
    """
    token = crear_token_acceso("admin", "admin")
    headers = {"Authorization": f"Bearer {token}"}

    placa = f"FI{uuid.uuid4().hex[:4].upper()}"
    database.crear_o_actualizar_cliente({
        "cliente": "LOGISTICA CARGO",
        "dias_espera_inspeccion": 20,
        "requiere_mes_siguiente": True
    })

    insp_fin_oct = {
        "fecha": "2026-10-25",
        "cliente": "LOGISTICA CARGO",
        "subcliente": "CENTRAL",
        "tipo_operacion": "CARGA",
        "placa": placa,
        "posicion": 1,
        "kilometraje": 30000,
        "tipologia": "CAMION SENCILLO 4X2",
        "marca": "BRIDGESTONE",
        "diseno": "M729",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "prof_ext": 15.0,
        "prof_cent": 15.0,
        "prof_int": 15.0,
        "psi": 105,
        "vida": "Original"
    }
    res_fin = client.post("/api/inspecciones", json=insp_fin_oct, headers=headers)
    assert res_fin.status_code == 200

    # 5 de Noviembre: es el siguiente mes, pero solo pasaron 11 días (< 20) -> DEBE BLOQUEARSE
    insp_nov_temprano = dict(insp_fin_oct)
    insp_nov_temprano["fecha"] = "2026-11-05"
    insp_nov_temprano["kilometraje"] = 30400
    res_nov_bloq = client.post("/api/inspecciones", json=insp_nov_temprano, headers=headers)
    assert res_nov_bloq.status_code == 400
    assert "2026-11-14" in res_nov_bloq.json()["detail"]

    # 15 de Noviembre: es el siguiente mes Y ya pasaron 21 días -> DEBE PERMITIRSE
    insp_nov_ok = dict(insp_fin_oct)
    insp_nov_ok["fecha"] = "2026-11-15"
    insp_nov_ok["kilometraje"] = 31000
    res_nov_ok = client.post("/api/inspecciones", json=insp_nov_ok, headers=headers)
    assert res_nov_ok.status_code == 200
