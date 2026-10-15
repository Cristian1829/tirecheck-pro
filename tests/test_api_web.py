import io
import pytest
from fastapi.testclient import TestClient
from server import app
import database
import server

client = TestClient(app)

def test_api_info_servidor():
    res = client.get("/api/servidor/info")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["app"] == "TireAnalyze Pro"

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
    assert "modalEditarUsuario" in html
    assert "modalResetPassword" in html

def test_seguridad_rechazo_sin_autenticacion(test_db):
    # 1. Petición sin token a /api/inspecciones debe dar 401
    res_insp = client.get("/api/inspecciones")
    assert res_insp.status_code == 401
    assert "Sesión no válida" in res_insp.json()["detail"]

    # 2. Petición sin token a /api/usuarios debe dar 401
    res_usr = client.get("/api/usuarios")
    assert res_usr.status_code == 401

    # 3. Petición sin token a creación de usuario debe dar 401
    res_crear = client.post("/api/usuarios", json={
        "username": "hacker",
        "password": "hackpassword",
        "nombre_completo": "Intruso"
    })
    assert res_crear.status_code == 401

def test_seguridad_control_roles_inspector_vs_admin(test_db, inspector_token):
    # Cliente autenticado como inspector
    client_insp = TestClient(app)
    client_insp.headers.update({"Authorization": f"Bearer {inspector_token}"})

    # Un inspector tiene acceso a lectura de inspecciones
    res_insp = client_insp.get("/api/inspecciones")
    assert res_insp.status_code == 200

    # Pero un inspector NO tiene permisos de administrador (debe dar 403 Forbidden)
    res_admin_usr = client_insp.get("/api/usuarios")
    assert res_admin_usr.status_code == 403
    assert "administrador" in res_admin_usr.json()["detail"].lower()

    # Intentar resetear password de admin siendo inspector da 403
    res_reset = client_insp.post("/api/usuarios/admin/reset-password", json={"nueva_password": "nuevaclave123"})
    assert res_reset.status_code == 403

def test_contrasenas_hasheadas_pbkdf2(test_db):
    # Verificar directamente en la base de datos que las contraseñas están hasheadas
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, password FROM usuarios")
        rows = cursor.fetchall()
        assert len(rows) >= 2
        for username, stored_pwd in rows:
            assert stored_pwd.startswith("pbkdf2_sha256$"), f"La contraseña de {username} no usa formato PBKDF2"
            parts = stored_pwd.split('$')
            assert len(parts) == 3
            salt, hash_hex = parts[1], parts[2]
            assert len(salt) == 32
            assert len(hash_hex) == 64

def test_api_crud_inspeccion(test_db, auth_client):
    # 1. Crear inspección autenticado
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
    res_crear = auth_client.post("/api/inspecciones", json=payload)
    assert res_crear.status_code == 200
    reg_id = res_crear.json()["id"]
    assert reg_id > 0

    # 2. Consultar por ID
    res_get = auth_client.get(f"/api/inspecciones/{reg_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["placa"] == "API-123"
    assert data["numero_interno"] == "LL-API-01"

    # 3. Actualizar inspección (PUT)
    payload["kilometraje"] = 55000.0
    payload["novedades"] = "Corte superficial en banda"
    payload["foto_novedad"] = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    res_put = auth_client.put(f"/api/inspecciones/{reg_id}", json=payload)
    assert res_put.status_code == 200
    assert res_put.json()["status"] == "ok"

    # Verificar actualización
    res_get2 = auth_client.get(f"/api/inspecciones/{reg_id}")
    assert res_get2.json()["kilometraje"] == 55000.0
    assert res_get2.json()["novedades"] == "CORTE SUPERFICIAL EN BANDA"

    # 4. Eliminar inspección (DELETE)
    res_del = auth_client.delete(f"/api/inspecciones/{reg_id}")
    assert res_del.status_code == 200

    # Verificar que ya no existe
    res_get3 = auth_client.get(f"/api/inspecciones/{reg_id}")
    assert res_get3.status_code == 404

def test_api_descargar_plantilla_excel(auth_client):
    res = auth_client.get("/api/inspecciones/plantilla-excel")
    assert res.status_code == 200
    assert "spreadsheet" in res.headers["content-type"]
    assert len(res.content) > 1000

def test_api_exportar_excel(test_db, auth_client):
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
    res_bd = auth_client.get("/api/inspecciones/exportar-excel")
    assert res_bd.status_code == 200
    assert len(res_bd.content) > 1000

    # Exportar Diagnóstico
    res_diag = auth_client.get("/api/diagnostico/exportar-excel")
    assert res_diag.status_code == 200
    assert len(res_diag.content) > 1000

    # Exportar KPIs
    res_kpis = auth_client.get("/api/kpis-llantas/exportar-excel")
    assert res_kpis.status_code == 200
    assert len(res_kpis.content) > 1000

def test_flujo_completo_gestion_usuarios_y_reset_password(test_db, auth_client):
    # 1. Admin crea un nuevo usuario
    res_crear = auth_client.post("/api/usuarios", json={
        "username": "operario_test",
        "password": "claveInicial123",
        "nombre_completo": "Operario de Pruebas",
        "rol": "inspector",
        "cliente_asignado": "Flota Norte"
    })
    assert res_crear.status_code == 200
    assert res_crear.json()["username"] == "operario_test"

    # 2. Login con credenciales iniciales
    res_login1 = client.post("/api/login", json={
        "username": "operario_test",
        "password": "claveInicial123"
    })
    assert res_login1.status_code == 200
    assert "token" in res_login1.json()
    assert res_login1.json()["usuario"]["cliente_asignado"] == "Flota Norte"

    # 3. Admin actualiza datos del usuario
    res_put = auth_client.put("/api/usuarios/operario_test", json={
        "nombre_completo": "Operario Senior",
        "cliente_asignado": "Flota Sur"
    })
    assert res_put.status_code == 200

    # 4. Admin restablece contraseña mediante endpoint reset-password
    res_reset = auth_client.post("/api/usuarios/operario_test/reset-password", json={
        "nueva_password": "nuevaClaveSegura2026"
    })
    assert res_reset.status_code == 200
    assert "restablecida" in res_reset.json()["message"]

    # 5. La contraseña antigua ya NO debe funcionar
    res_login_old = client.post("/api/login", json={
        "username": "operario_test",
        "password": "claveInicial123"
    })
    assert res_login_old.status_code == 401

    # 6. La nueva contraseña funciona inmediatamente
    res_login_new = client.post("/api/login", json={
        "username": "operario_test",
        "password": "nuevaClaveSegura2026"
    })
    assert res_login_new.status_code == 200
    assert res_login_new.json()["usuario"]["nombre_completo"] == "Operario Senior"
    assert res_login_new.json()["usuario"]["cliente_asignado"] == "Flota Sur"

    # 7. Admin elimina el usuario de prueba
    res_del = auth_client.delete("/api/usuarios/operario_test")
    assert res_del.status_code == 200

def test_api_importar_excel(test_db, auth_client):
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
    res = auth_client.post("/api/inspecciones/importar-excel", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["registros_importados"] >= 1
