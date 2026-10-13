import io
import pytest
from fastapi.testclient import TestClient
from server import app
import database

client = TestClient(app)

def test_api_info_servidor():
    res = client.get("/api/servidor/info")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["app"] == "TireCheck Pro"

def test_api_crud_inspeccion(test_db):
    # 1. Crear inspección
    payload = {
        "fecha": "2026-10-01",
        "cliente": "API Cliente",
        "subcliente": "Sede 1",
        "tipo_operacion": "Carga Seca",
        "placa": "API-123",
        "posicion": 1,
        "kilometraje": 50000.0,
        "tipologia": "Cabezote (6x4)",
        "marca": "Michelin",
        "diseno": "X Multi Z",
        "dimension": "295/80R22.5",
        "prof_inicial": 16.0,
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0,
        "psi": 110.0,
        "numero_interno": "LL-API-01"
    }
    res_crear = client.post("/api/inspecciones", json=payload)
    assert res_crear.status_code == 200
    reg_id = res_crear.json()["id"]
    assert reg_id > 0

    # 2. Consultar por ID
    res_get = client.get(f"/api/inspecciones/{reg_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["placa"] == "API-123"
    assert data["numero_interno"] == "LL-API-01"

    # 3. Actualizar inspección (PUT)
    payload["kilometraje"] = 55000.0
    payload["novedades"] = "Corte superficial en banda"
    payload["foto_novedad"] = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    res_put = client.put(f"/api/inspecciones/{reg_id}", json=payload)
    assert res_put.status_code == 200
    assert res_put.json()["status"] == "ok"

    # Verificar actualización
    res_get2 = client.get(f"/api/inspecciones/{reg_id}")
    assert res_get2.json()["kilometraje"] == 55000.0
    assert res_get2.json()["novedades"] == "Corte superficial en banda"
    assert res_get2.json()["foto_novedad"] == "data:image/jpeg;base64,/9j/4AAQSkZJRg=="

    # 4. Eliminar inspección (DELETE)
    res_del = client.delete(f"/api/inspecciones/{reg_id}")
    assert res_del.status_code == 200

    # Verificar que ya no existe
    res_get3 = client.get(f"/api/inspecciones/{reg_id}")
    assert res_get3.status_code == 404

def test_api_descargar_plantilla_excel():
    res = client.get("/api/inspecciones/plantilla-excel")
    assert res.status_code == 200
    assert "spreadsheet" in res.headers["content-type"]
    assert len(res.content) > 1000

def test_api_exportar_excel(test_db):
    # Insertar un registro
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'placa': 'EXP-01',
        'posicion': 1,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    })

    # Exportar Base de datos
    res_bd = client.get("/api/inspecciones/exportar-excel")
    assert res_bd.status_code == 200
    assert len(res_bd.content) > 1000

    # Exportar Diagnóstico
    res_diag = client.get("/api/diagnostico/exportar-excel")
    assert res_diag.status_code == 200
    assert len(res_diag.content) > 1000

    # Exportar KPIs
    res_kpis = client.get("/api/kpis-llantas/exportar-excel")
    assert res_kpis.status_code == 200
    assert len(res_kpis.content) > 1000

def test_api_usuarios_gestion(test_db):
    # Crear usuario
    res_crear = client.post("/api/usuarios", json={
        "username": "auditor_test",
        "password": "pass123",
        "nombre_completo": "Auditor Test",
        "rol": "auditor",
        "cliente_asignado": ""
    })
    assert res_crear.status_code == 200

    # Actualizar usuario
    res_put = client.put("/api/usuarios/auditor_test", json={
        "nombre_completo": "Auditor Test Modificado",
        "rol": "inspector"
    })
    assert res_put.status_code == 200

    # Eliminar usuario
    res_del = client.delete("/api/usuarios/auditor_test")
    assert res_del.status_code == 200

def test_index_page_loads_all_views():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    # Verificar que el HTML contiene las 5 vistas principales integradas
    assert "vista-patio" in html
    assert "vista-basedatos" in html
    assert "vista-diagnostico" in html
    assert "vista-kpis" in html
    assert "vista-catalogos" in html
    assert "vista-remoto" not in html
    # Verificar modales esenciales
    assert "modalEditarInspeccion" in html
    assert "modalImportarExcel" in html
    assert "modalInformePdf" in html

def test_api_importar_excel(test_db):
    import pandas as pd
    # Crear un excel temporal en memoria con formato válido
    df = pd.DataFrame([{
        'fecha': '2026-10-01',
        'cliente': 'Cliente Import',
        'subcliente': 'Sede Import',
        'tipo_operacion': 'Carga',
        'placa': 'IMP-001',
        'numero_interno': 'LL-IMP-1',
        'posicion': 1,
        'kilometraje': 80000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 105,
        'prof_inicial': 16.0
    }])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    files = {'file': ('test_cargue.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    res = client.post("/api/inspecciones/importar-excel", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["registros_importados"] >= 1
