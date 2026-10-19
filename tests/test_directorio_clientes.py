import pytest
from fastapi.testclient import TestClient
import database
import server

def test_directorio_clientes_crud_y_seguridad(auth_client, inspector_token):
    # 1. Obtener listado de directorio inicial
    resp = auth_client.get("/api/clientes-directorio")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    
    # 2. Inspector no puede crear clientes (solo admin / jefatura)
    insp_client = TestClient(server.app)
    insp_client.headers.update({"Authorization": f"Bearer {inspector_token}"})
    
    payload_nuevo = {
        "cliente": "transportes alfa sas",
        "tipo_licencia": "PRO",
        "limite_retiro_mm": 3.5,
        "subclientes": "BOGOTA, MEDELLIN",
        "observaciones": "Cliente VIP de prueba"
    }
    resp_insp = insp_client.post("/api/clientes-directorio", json=payload_nuevo)
    assert resp_insp.status_code == 403

    # 3. Admin crea cliente exitosamente
    resp_crear = auth_client.post("/api/clientes-directorio", json=payload_nuevo)
    assert resp_crear.status_code == 200
    res_json = resp_crear.json()
    assert res_json["status"] == "ok"
    assert res_json["cliente"] == "TRANSPORTES ALFA SAS"

    # 4. Verificar que aparece en el directorio con mayúsculas y datos consolidados
    resp_list = auth_client.get("/api/clientes-directorio")
    assert resp_list.status_code == 200
    clientes = resp_list.json()
    alfa = next((c for c in clientes if c["cliente"] == "TRANSPORTES ALFA SAS"), None)
    assert alfa is not None
    assert alfa["tipo_licencia"] == "PRO"
    assert alfa["limite_retiro_mm"] == 3.5
    assert "BOGOTA" in alfa["subclientes"]
    assert "MEDELLIN" in alfa["subclientes"]

    # 5. Modificar cliente existente
    payload_editar = {
        "cliente": "TRANSPORTES ALFA SAS",
        "tipo_licencia": "LIGHT",
        "limite_retiro_mm": 2.8,
        "subclientes": "BOGOTA, CALI",
        "observaciones": "Actualizado a plan Light"
    }
    resp_edit = auth_client.post("/api/clientes-directorio", json=payload_editar)
    assert resp_edit.status_code == 200

    resp_list2 = auth_client.get("/api/clientes-directorio")
    alfa_edit = next((c for c in resp_list2.json() if c["cliente"] == "TRANSPORTES ALFA SAS"), None)
    assert alfa_edit["tipo_licencia"] == "LIGHT"
    assert alfa_edit["limite_retiro_mm"] == 2.8
    assert "CALI" in alfa_edit["subclientes"]

    # 6. Eliminar cliente que no tiene historial operativo
    resp_del = auth_client.delete("/api/clientes-directorio/TRANSPORTES ALFA SAS")
    assert resp_del.status_code == 200
    assert resp_del.json()["status"] == "ok"

    # 7. Verificar que ya no existe
    resp_list3 = auth_client.get("/api/clientes-directorio")
    alfa_deleted = next((c for c in resp_list3.json() if c["cliente"] == "TRANSPORTES ALFA SAS"), None)
    assert alfa_deleted is None

def test_candado_eliminacion_cliente_con_historial(auth_client):
    # Crear cliente
    auth_client.post("/api/clientes-directorio", json={
        "cliente": "FLOTA OPERATIVA DEMO",
        "tipo_licencia": "PRO",
        "limite_retiro_mm": 3.0,
        "subclientes": "SEDE NORTE",
        "observaciones": "Flota con registros"
    })

    # Simular inspección para la flota
    with database.get_connection() as conn:
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, subcliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi)
            VALUES ('2026-10-18', 'FLOTA OPERATIVA DEMO', 'SEDE NORTE', 'ZZZ999', 1, 'Cabezote (6x4)', 10, 10, 10, 100)
        """)

    # Intentar eliminar debe ser rechazado con 400 por candado de seguridad
    resp_del = auth_client.delete("/api/clientes-directorio/FLOTA OPERATIVA DEMO")
    assert resp_del.status_code == 400
    assert "inspecciones registradas" in resp_del.json()["detail"]
