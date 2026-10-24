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
    assert "modalInformePdf" in html
    assert "modalEditarUsuario" in html
    assert "modalResetPassword" in html
    assert "modalAsociarMarcaCliente" in html
    assert "cat-seccion-marcas_cliente" in html
    assert "badgeMarcasModo" in html
    # Verificar filtros clave de base de datos
    assert "filtroBDSede" in html
    assert "filtroBDCliente" in html
    # Verificar filtros de diagnóstico al inicio y eliminación de Re-animar
    assert "filtroDiagCliente" in html
    assert "filtroDiagSede" in html
    assert "filtroDiagOperacion" in html
    assert "filtroDiagAlerta" in html
    assert "filtroDiagPlaca" in html
    assert "Re-animar" not in html

def test_servicios_landing_page_loads():
    res = client.get("/servicios")
    assert res.status_code == 200
    html = res.text
    assert "TireAnalyze Pro" in html
    assert "Las 7 Bodegas (MRP)" in html
    assert "https://www.tireanalizepro.com" in html
    assert "lblAhorroEstimado" in html
    assert "actualizarCalculadora" in html
    # Verificación de logos emblemáticos y textura de huellas de neumáticos
    assert "srvTireTreadGrad" in html # Llanta 3D con gráfico
    assert "srvCupBodyGrad" in html   # Taza de café con vapor analítico
    assert "CONFIANZA EN TU INFORMACIÓN" in html
    assert "tire-treads-bg" in html   # Textura de huellas de neumático
    assert "Los 4 Candados Viales de Seguridad" in html
    
    # También probar el alias /landing
    res_alias = client.get("/landing")
    assert res_alias.status_code == 200
    assert "TireAnalyze Pro" in res_alias.text

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

    # Exportar Diagnóstico (Sin filtros y con filtros)
    res_diag = auth_client.get("/api/diagnostico/exportar-excel")
    assert res_diag.status_code == 200
    assert len(res_diag.content) > 1000

    # Exportar Diagnóstico con Filtro de Cliente y Alerta
    res_diag_filt = auth_client.get("/api/diagnostico/exportar-excel?cliente=LA%20SIERRA&alerta=Cambio")
    assert res_diag_filt.status_code == 200
    assert "attachment; filename=Diagnostico" in res_diag_filt.headers.get("content-disposition", "")
    assert len(res_diag_filt.content) > 1000

    # Exportar Diagnóstico con Filtro de Placa
    res_diag_placa = auth_client.get("/api/diagnostico/exportar-excel?placa=AAA123")
    assert res_diag_placa.status_code == 200
    assert len(res_diag_placa.content) > 1000

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
    assert res_login1.json()["usuario"]["cliente_asignado"] == "FLOTA NORTE"

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
    assert res_login_new.json()["usuario"]["cliente_asignado"] == "FLOTA SUR"

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

def test_api_importar_excel_rechazo_profundidad_invalida(test_db, auth_client):
    import pandas as pd
    # Crear un excel con profundidad exterior 35.0 mm (> 27.0 mm permitidos en R22.5)
    df = pd.DataFrame([{
        'fecha': '2026-10-01',
        'cliente': 'Cliente Import',
        'subcliente': 'Sede Import',
        'tipo_operacion': 'Carga',
        'placa': 'IMP-ERR',
        'numero_interno': 'LL-ERR-1',
        'posicion': 1,
        'kilometraje': 80000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'prof_ext': 35.0,  # Inválido: supera 27.0 mm
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 105,
        'prof_inicial': 16.0
    }])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    files = {'file': ('test_cargue_err.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    res = auth_client.post("/api/inspecciones/importar-excel", files=files)
    assert res.status_code == 400
    data = res.json()
    assert "detail" in data
    assert "CANDADO DE SEGURIDAD" in data["detail"] or "27.0 mm" in data["detail"] or "Fila 2" in data["detail"]

def test_api_crear_y_editar_usuario_vistas_y_clientes(test_db, auth_client):
    # Crear usuario con vistas y múltiples clientes
    payload = {
        "username": "inspector_test",
        "password": "password123",
        "nombre_completo": "Inspector de Prueba",
        "rol": "inspector",
        "cliente_asignado": "TransCarga, Flota Norte",
        "vistas_permitidas": "patio,diagnostico"
    }
    res = auth_client.post("/api/usuarios", json=payload)
    assert res.status_code == 200

    # Listar usuarios y verificar persistencia
    res_list = auth_client.get("/api/usuarios")
    assert res_list.status_code == 200
    users = res_list.json()
    u = next(x for x in users if x["username"] == "inspector_test")
    assert u["rol"] == "inspector"
    assert "patio" in u["vistas_permitidas"]
    assert "diagnostico" in u["vistas_permitidas"]
    # Verificar que basedatos queda estrictamente excluido para inspectores (solo admin)
    assert "basedatos" not in u["vistas_permitidas"]
    assert len(u["clientes_asignados"]) == 2
    assert "TRANSCARGA" in u["clientes_asignados"]
    assert "FLOTA NORTE" in u["clientes_asignados"]

    # Editar usuario a un solo cliente asignado
    res_edit = auth_client.put("/api/usuarios/inspector_test", json={
        "nombre_completo": "Inspector Modificado",
        "rol": "inspector",
        "cliente_asignado": "TransCarga",
        "vistas_permitidas": "patio,kpis,catalogos",
        "activo": True
    })
    assert res_edit.status_code == 200

    res_list2 = auth_client.get("/api/usuarios")
    u2 = next(x for x in res_list2.json() if x["username"] == "inspector_test")
    assert u2["nombre_completo"] == "Inspector Modificado"
    assert u2["cliente_asignado"] == "TRANSCARGA"
    assert u2["clientes_asignados"] == ["TRANSCARGA"]
    assert "kpis" in u2["vistas_permitidas"]
    assert "catalogos" in u2["vistas_permitidas"]
    assert "basedatos" not in u2["vistas_permitidas"]

def test_api_inspector_cliente_predeterminado_y_restricciones(test_db):
    # Crear usuario inspector con un único cliente asignado
    database.crear_usuario("inspector_mono", "12345", "Inspector Mono", "inspector", "TransCarga", "patio,diagnostico")
    token = server.crear_token_acceso("inspector_mono", "inspector")
    client = TestClient(server.app)
    client.headers.update({"Authorization": f"Bearer {token}"})

    # Consulta de valores de campo: solo debe retornar su cliente asignado
    res_val = client.get("/api/valores-campo?campo=cliente")
    assert res_val.status_code == 200
    assert res_val.json() == ["TRANSCARGA"]

    # Registro de inspección: si no manda cliente, el servidor predetermina automáticamente TransCarga
    insp_payload = {
        "fecha": "2026-10-15",
        "subcliente": "Sede Norte",
        "tipo_operacion": "Urbano",
        "placa": "TRC-001",
        "numero_interno": "LL-100",
        "posicion": 1,
        "kilometraje": 50000,
        "tipologia": "Camión 2 Ejes (4x2)",
        "marca": "Michelin",
        "diseno": "X Multi Z",
        "dimension": "295/80R22.5",
        "vida": "Original",
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0,
        "psi": 110,
        "prof_inicial": 16.0
    }
    res_insp = client.post("/api/inspecciones", json=insp_payload)
    assert res_insp.status_code == 200
    insp_id = res_insp.json()["id"]

    # Verificar que quedó registrado como TRANSCARGA (estandarizado en mayúsculas)
    res_get = client.get(f"/api/inspecciones/{insp_id}")
    assert res_get.status_code == 200
    assert res_get.json()["cliente"] == "TRANSCARGA"

    # Intento de registrar para un cliente no autorizado -> 403 Forbidden
    insp_payload_ajeno = dict(insp_payload)
    insp_payload_ajeno["cliente"] = "Flota Ajena SAS"
    insp_payload_ajeno["placa"] = "TRC-002"
    insp_payload_ajeno["numero_interno"] = "LL-101"
    res_prohibido = client.post("/api/inspecciones", json=insp_payload_ajeno)
    assert res_prohibido.status_code == 403

def test_api_permisos_catalogos_y_usuarios_inspector(test_db):
    # Crear inspector
    database.crear_usuario("inspector_cat", "12345", "Inspector Cat", "inspector", "TransCarga", "patio,catalogos")
    token = server.crear_token_acceso("inspector_cat", "inspector")
    client = TestClient(server.app)
    client.headers.update({"Authorization": f"Bearer {token}"})

    # 1. Inspector PUEDE ver operaciones, tipologias y modelos
    assert client.get("/api/operaciones").status_code == 200
    assert client.get("/api/tipologias").status_code == 200
    assert client.get("/api/modelos-llanta").status_code == 200

    # 2. Inspector NO PUEDE ver límites por cliente (solo admin)
    res_lim = client.get("/api/configuraciones-clientes")
    assert res_lim.status_code == 403

    # 3. Inspector NO PUEDE crear operaciones, tipologías, modelos ni límites
    assert client.post("/api/operaciones", json={"nombre": "Operacion Ilegal"}).status_code == 403
    assert client.post("/api/tipologias", json={"nombre": "Tipologia Ilegal", "cant_llantas": 6, "esquema_custom": "2-4"}).status_code == 403
    assert client.post("/api/modelos-llanta", json={"tipo_llanta": "Nueva", "marca": "X", "diseno": "Y", "dimension": "295/80R22.5", "prof_inicial": 15.0}).status_code == 403
    assert client.post("/api/configuraciones-clientes", json={"cliente": "CLIX", "limite_retiro_mm": 3.0}).status_code == 403

    # 4. Inspector NO PUEDE crear usuarios ni ver lista de usuarios
    assert client.get("/api/usuarios").status_code == 403
    assert client.post("/api/usuarios", json={
        "username": "hacker", "password": "123", "nombre_completo": "Hacker", "rol": "admin"
    }).status_code == 403

def test_admin_editar_y_eliminar_tipologia_con_candado_uso(test_db):
    token = server.crear_token_acceso("admin", "admin")
    admin_client = TestClient(server.app)
    admin_client.headers.update({"Authorization": f"Bearer {token}"})

    # 1. Crear tipología de prueba
    res_crear = admin_client.post("/api/tipologias", json={
        "nombre": "Volqueta 10x4 Pro",
        "descripcion": "Volqueta especial",
        "cant_llantas": 14,
        "ejes_dir": 2,
        "ejes_trac": 2,
        "ejes_libres": 1
    })
    assert res_crear.status_code == 200

    # 2. Editar la tipología
    res_edit = admin_client.put("/api/tipologias", json={
        "nombre_antiguo": "VOLQUETA 10X4 PRO",
        "nombre_nuevo": "VOLQUETA 10X4 ULTRA",
        "descripcion": "Volqueta ultra pesada",
        "cant_llantas": 14,
        "ejes_dir": 2,
        "ejes_trac": 2,
        "ejes_libres": 1
    })
    assert res_edit.status_code == 200

    # Verificar que el nombre nuevo está en el catálogo
    tips = admin_client.get("/api/tipologias").json()
    assert any(t["nombre"] == "VOLQUETA 10X4 ULTRA" for t in tips)

    # 3. Vincular una inspección a esta tipología para probar el candado de no eliminación
    database.insertar_inspeccion({
        "fecha": "2026-03-01",
        "cliente": "MINERA DEL SUR",
        "placa": "VOL-101",
        "posicion": 1,
        "kilometraje": 12000,
        "tipologia": "VOLQUETA 10X4 ULTRA",
        "marca": "GOODYEAR",
        "diseno": "KMAX S",
        "dimension": "295/80R22.5",
        "vida": "Original",
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0,
        "psi": 105.0,
        "numero_interno": "LL-V101"
    })

    # 4. Intentar eliminar la tipología en uso -> DEBE FALLAR con 400
    res_del_fail = admin_client.delete("/api/tipologias?nombre=VOLQUETA 10X4 ULTRA")
    assert res_del_fail.status_code == 400
    assert "está siendo utilizada" in res_del_fail.json()["detail"]

    # 5. Crear una tipología no utilizada y eliminarla -> DEBE TENER ÉXITO con 200
    admin_client.post("/api/tipologias", json={
        "nombre": "Tipologia Sin Uso",
        "cant_llantas": 6
    })
    res_del_ok = admin_client.delete("/api/tipologias?nombre=TIPOLOGIA SIN USO")
    assert res_del_ok.status_code == 200

def test_admin_editar_catalogo_modelos_y_sincronizar_prof_inicial(test_db):
    token = server.crear_token_acceso("admin", "admin")
    admin_client = TestClient(server.app)
    admin_client.headers.update({"Authorization": f"Bearer {token}"})

    # 1. Registrar inspección con Goodyear KMax D y profundidad inicial 22.0
    database.insertar_inspeccion({
        "fecha": "2026-03-01",
        "cliente": "LOGISTICA ANDINA",
        "placa": "LOG-555",
        "posicion": 1,
        "kilometraje": 50000,
        "tipologia": "Cabezote (6x4)",
        "marca": "GOODYEAR",
        "diseno": "KMAX D",
        "dimension": "295/80R22.5",
        "prof_inicial": 22.0,
        "prof_ext": 18.0,
        "prof_cent": 18.0,
        "prof_int": 18.0,
        "psi": 100.0,
        "numero_interno": "LL-LOG1"
    })

    # 2. Obtener el modelo del catálogo
    mods = admin_client.get("/api/modelos-llanta").json()
    mod_goodyear = next(m for m in mods if m["marca"].upper() == "GOODYEAR" and "KMAX D" in m["diseno"].upper())
    mod_id = mod_goodyear["id"]

    # 3. Editar el modelo en el catálogo cambiando profundidad inicial a 24.0 mm
    res_edit = admin_client.put("/api/modelos-llanta", json={
        "id": mod_id,
        "tipo_llanta": "Nueva",
        "marca": "Goodyear",
        "diseno": "KMax D",
        "dimension": "295/80R22.5",
        "prof_inicial": 24.0,
        "descripcion": "Tracción Carretera Actualizada",
        "actualizar_bd": True
    })
    assert res_edit.status_code == 200
    data_edit = res_edit.json()
    assert data_edit["status"] == "ok"
    assert data_edit["filas_actualizadas"] >= 1
    assert data_edit["prof_inicial"] == 24.0

    # 4. Verificar que en la base de datos de inspecciones la prof_inicial se actualizó a 24.0
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT prof_inicial FROM inspecciones WHERE placa = 'LOG-555' AND numero_interno = 'LL-LOG1'")
        assert cursor.fetchone()[0] == 24.0

def test_admin_editar_limites_por_cliente(test_db):
    token = server.crear_token_acceso("admin", "admin")
    admin_client = TestClient(server.app)
    admin_client.headers.update({"Authorization": f"Bearer {token}"})

    # 1. Crear un límite
    res_crear = admin_client.post("/api/configuraciones-clientes", json={
        "cliente": "FLOTA PRUEBA EDIT",
        "subcliente": "TODOS",
        "eje": "TODOS",
        "limite_retiro_mm": 3.0,
        "observaciones": "Inicial"
    })
    assert res_crear.status_code == 200

    # Obtener el registro para conocer su ID
    cfgs = admin_client.get("/api/configuraciones-clientes").json()
    cfg = next(c for c in cfgs if c["cliente"] == "FLOTA PRUEBA EDIT")
    cfg_id = cfg["id"]

    # 2. Editar el límite mediante PUT /api/configuraciones-clientes
    res_edit = admin_client.put("/api/configuraciones-clientes", json={
        "id": cfg_id,
        "cliente": "FLOTA PRUEBA EDIT",
        "subcliente": "SEDE BOGOTA",
        "eje": "DIRECCIONAL",
        "limite_retiro_mm": 4.5,
        "observaciones": "Editado por Admin"
    })
    assert res_edit.status_code == 200

    # 3. Verificar en BD que el límite cambió a 4.5 mm
    lim = database.obtener_limite_retiro_cliente("FLOTA PRUEBA EDIT", "SEDE BOGOTA", "DIRECCIONAL")
    assert lim == 4.5

def test_api_usuario_actual_sincroniza_flotas_actualizadas(test_db, auth_client):
    """
    Verifica que el endpoint /api/usuario-actual devuelva la información fresca de la BD,
    y que al actualizar las flotas asignadas de un inspector, el token existente
    reciba inmediatamente las nuevas flotas en mayúsculas sin duplicados.
    """
    # 1. Crear usuario inspector con flotas iniciales
    database.crear_usuario(
        username="inspector_sync",
        password="password123",
        nombre_completo="Inspector Sincronización",
        rol="inspector",
        cliente_asignado="FLOTA INICIAL",
        vistas_permitidas="patio,diagnostico"
    )
    token = server.crear_token_acceso("inspector_sync", "inspector")
    client_insp = TestClient(server.app)
    client_insp.headers.update({"Authorization": f"Bearer {token}"})

    # Consulta inicial
    res1 = client_insp.get("/api/usuario-actual")
    assert res1.status_code == 200
    u1 = res1.json()["usuario"]
    assert u1["cliente_asignado"] == "FLOTA INICIAL"
    assert u1["clientes_asignados"] == ["FLOTA INICIAL"]

    # 2. El administrador actualiza las flotas del inspector a múltiples clientes
    res_put = auth_client.put("/api/usuarios/inspector_sync", json={
        "nombre_completo": "Inspector Sincronización",
        "rol": "inspector",
        "cliente_asignado": "AXXOM, Demo Flota, DEMO FLOTA",  # Caso real con mezcla y duplicados
        "activo": True
    })
    assert res_put.status_code == 200

    # 3. El inspector consulta /api/usuario-actual sin re-loguear (con su token activo)
    res2 = client_insp.get("/api/usuario-actual")
    assert res2.status_code == 200
    u2 = res2.json()["usuario"]
    # Debe recibir las nuevas flotas normalizadas en mayúsculas y deduplicadas
    assert "AXXOM" in u2["clientes_asignados"]
    assert "DEMO FLOTA" in u2["clientes_asignados"]
    # 'DEMO FLOTA' y 'Demo Flota' no deben duplicarse
    assert len(u2["clientes_asignados"]) == 2
    assert u2["clientes_asignados"] == ["AXXOM", "DEMO FLOTA"]


def test_roles_jefatura_y_gerencia(test_db):
    # 1. Login con jefe1 y gerencia1 creados automáticamente
    res_login_jefe = client.post("/api/login", json={"username": "jefe1", "password": "1234"})
    assert res_login_jefe.status_code == 200
    token_jefe = res_login_jefe.json()["token"]
    u_jefe = res_login_jefe.json()["usuario"]
    assert u_jefe["rol"] == "jefatura"
    assert "basedatos" in u_jefe["vistas_permitidas"]
    assert "catalogos" in u_jefe["vistas_permitidas"]

    res_login_gere = client.post("/api/login", json={"username": "gerencia1", "password": "1234"})
    assert res_login_gere.status_code == 200
    token_gere = res_login_gere.json()["token"]
    u_gere = res_login_gere.json()["usuario"]
    assert u_gere["rol"] == "gerencia"
    assert "basedatos" in u_gere["vistas_permitidas"]
    assert "kpis" in u_gere["vistas_permitidas"]

    client_jefe = TestClient(server.app)
    client_jefe.headers.update({"Authorization": f"Bearer {token_jefe}"})

    client_gere = TestClient(server.app)
    client_gere.headers.update({"Authorization": f"Bearer {token_gere}"})

    # 2. Jefatura puede gestionar catálogos (ej: crear tipología)
    res_tipo = client_jefe.post("/api/tipologias", json={"nombre": "C3R2 TEST", "ejes": 5, "esquema": "2-4-4-4-4"})
    assert res_tipo.status_code == 200

    # 3. Gerencia NO puede gestionar catálogos (debe dar 403)
    res_tipo_gere = client_gere.post("/api/tipologias", json={"nombre": "C4 TEST", "ejes": 4, "esquema": "2-4-4-4"})
    assert res_tipo_gere.status_code == 403

    # 4. Ni Jefatura ni Gerencia pueden gestionar usuarios (debe dar 403)
    assert client_jefe.get("/api/usuarios").status_code == 403
    assert client_gere.get("/api/usuarios").status_code == 403

    # 5. Ambos tienen acceso de lectura a /api/inspecciones
    assert client_jefe.get("/api/inspecciones").status_code == 200
    assert client_gere.get("/api/inspecciones").status_code == 200

    # 6. Gerencia NO puede crear ni modificar ni eliminar inspecciones
    insp_payload = {
        "fecha": "2026-10-16",
        "cliente": "FLOTA TEST",
        "placa": "GER001",
        "posicion": 1,
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0,
        "presion_psi": 105.0
    }
    assert client_gere.post("/api/inspecciones", json=insp_payload).status_code == 403
    assert client_gere.put("/api/inspecciones/1", json=insp_payload).status_code == 403
    assert client_gere.delete("/api/inspecciones/1").status_code == 403

    # 7. Jefatura SÍ puede crear inspecciones
    res_insp_jefe = client_jefe.post("/api/inspecciones", json=insp_payload)
    assert res_insp_jefe.status_code == 200
    id_creado = res_insp_jefe.json()["id"]

    # 8. Jefatura SÍ puede editar inspecciones
    insp_payload["prof_ext"] = 11.5
    res_put_jefe = client_jefe.put(f"/api/inspecciones/{id_creado}", json=insp_payload)
    assert res_put_jefe.status_code == 200


def test_api_diagnostico_graficos_estructura_y_blindaje_matematico(test_db, auth_client):
    # 1. Llanta recién montada: Delta mm = 0.0, km_rodados = 0
    database.insertar_inspeccion({
        "fecha": "2026-03-01",
        "cliente": "FLOTA PRUEBA BLINDAJE",
        "subcliente": "BOGOTA",
        "placa": "NEW-001",
        "posicion": 1,
        "kilometraje": 0,
        "km_montaje": 0,
        "tipologia": "Cabezote",
        "marca": "MICHELIN",
        "diseno": "X MULTI Z",
        "dimension": "295/80R22.5",
        "vida": "Original",
        "prof_inicial": 16.0,
        "prof_ext": 16.0,
        "prof_cent": 16.0,
        "prof_int": 16.0,
        "psi": 110.0,
        "precio": 1500000.0
    })

    # 2. Llanta madura: montaje inicial a km 0 el 1 de marzo, e inspección madura a km 36000 el 20 de marzo
    database.insertar_inspeccion({
        "fecha": "2026-03-01",
        "cliente": "FLOTA PRUEBA BLINDAJE",
        "subcliente": "BOGOTA",
        "placa": "MAD-002",
        "posicion": 3,
        "kilometraje": 0,
        "km_montaje": 0,
        "numero_interno": "LL-MAD-02",
        "tipologia": "Cabezote",
        "marca": "GOODYEAR",
        "diseno": "KMAX D",
        "dimension": "295/80R22.5",
        "vida": "Original",
        "prof_inicial": 16.0,
        "prof_ext": 16.0,
        "prof_cent": 16.0,
        "prof_int": 16.0,
        "psi": 100.0,
        "precio": 1450000.0
    })

    # Segunda inspección: prof_inicial = 16.0, p_min = 11.5 (Delta mm = 4.5), km_rodados = 36000,
    # desalineación p_ext = 14.0, p_cent = 13.0, p_int = 11.5 (|14.0 - 11.5| = 2.5 mm >= 2.0 mm),
    # psi = 82 (objetivo tracción 100 psi, 82 < 90 psi -> Baja Presión)
    database.insertar_inspeccion({
        "fecha": "2026-03-20",
        "cliente": "FLOTA PRUEBA BLINDAJE",
        "subcliente": "BOGOTA",
        "placa": "MAD-002",
        "posicion": 3,
        "kilometraje": 36000,
        "km_montaje": 0,
        "numero_interno": "LL-MAD-02",
        "tipologia": "Cabezote",
        "marca": "GOODYEAR",
        "diseno": "KMAX D",
        "dimension": "295/80R22.5",
        "vida": "Original",
        "prof_inicial": 16.0,
        "prof_ext": 14.0,
        "prof_cent": 13.0,
        "prof_int": 11.5,
        "psi": 82.0,
        "precio": 1450000.0
    })

    res = auth_client.get("/api/diagnostico/graficos?cliente=FLOTA PRUEBA BLINDAJE")
    assert res.status_code == 200
    data = res.json()

    # Comprobación de que no existen NaN ni Infinity
    raw_str = res.text
    assert "NaN" not in raw_str
    assert "Infinity" not in raw_str

    # Comprobación de métricas de diagnóstico
    kpis = data["kpis"]
    assert kpis["perdidaMm"] >= 2.5
    assert kpis["impactoPesos"] > 0

    # Comprobación de presiones: 82 PSI debe clasificarse en 'Baja Presión'
    presiones = data["presiones"]
    idx_baja = presiones["labels"].index("Baja Presión")
    assert presiones["valores"][idx_baja] >= 1

    # Comprobación de techos en proyMaxMin sin distorsión por división entre cero
    proy = data["proyMaxMin"]
    assert len(proy["labels"]) >= 1
    assert proy["prom"][0] > 0
    assert proy["max"][0] >= proy["prom"][0]
    assert proy["min"][0] <= proy["prom"][0]


def test_configuracion_licencia_light_vs_pro(test_db, auth_client):
    cliente_test = "CLIENTE LICENCIA TEST"
    
    # 1. Configurar en LIGHT mediante POST /api/configuraciones-clientes/licencia
    res_post = auth_client.post("/api/configuraciones-clientes/licencia", json={
        "cliente": cliente_test,
        "tipo_licencia": "LIGHT",
        "plantilla_kpis_json": "{}"
    })
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "ok"

    # 2. Consultar GET /api/diagnostico/graficos y verificar que retorne LIGHT
    res_get = auth_client.get(f"/api/diagnostico/graficos?cliente={cliente_test}")
    assert res_get.status_code == 200
    assert res_get.json()["licencia"] == "LIGHT"

    # 3. Conmutar a PRO y verificar que retorne PRO
    res_pro = auth_client.post("/api/configuraciones-clientes/licencia", json={
        "cliente": cliente_test,
        "tipo_licencia": "PRO",
        "plantilla_kpis_json": "{}"
    })
    assert res_pro.status_code == 200
    res_get_pro = auth_client.get(f"/api/diagnostico/graficos?cliente={cliente_test}")
    assert res_get_pro.status_code == 200
    assert res_get_pro.json()["licencia"] == "PRO"


def test_api_inspecciones_sn_light_vs_pro(test_db, auth_client):
    cliente_light = "CLIENTE API LIGHT TEST"
    # Configurar licencia LIGHT
    auth_client.post("/api/configuraciones-clientes/licencia", json={
        "cliente": cliente_light,
        "tipo_licencia": "LIGHT"
    })

    # 1. Crear primera inspección con "sn" en minúscula
    payload1 = {
        "fecha": "2026-10-01",
        "cliente": cliente_light,
        "placa": "LGT-001",
        "posicion": 1,
        "kilometraje": 20000.0,
        "numero_interno": "sn",
        "prof_inicial": 16.0,
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0
    }
    r1 = auth_client.post("/api/inspecciones", json=payload1)
    assert r1.status_code == 200
    id1 = r1.json()["id"]

    # Verificar que en la base de datos se guardó como mayúscula "SN"
    insp1 = auth_client.get(f"/api/inspecciones/{id1}").json()
    assert insp1["numero_interno"] == "SN"

    # 2. Crear segunda inspección en el mismo mes con "SN" para otra posición en LIGHT -> Debe ser 200 OK
    payload2 = {
        "fecha": "2026-10-01",
        "cliente": cliente_light,
        "placa": "LGT-001",
        "posicion": 2,
        "kilometraje": 20000.0,
        "numero_interno": "SN",
        "prof_inicial": 16.0,
        "prof_ext": 11.0,
        "prof_cent": 11.0,
        "prof_int": 11.0
    }
    r2 = auth_client.post("/api/inspecciones", json=payload2)
    assert r2.status_code == 200

    # 3. Consultar /api/llanta-por-cliente para "sn" o "SN" -> Debe retornar encontrado: false
    r_llanta = auth_client.get(f"/api/llanta-por-cliente?cliente={cliente_light}&numero_interno=sn")
    assert r_llanta.status_code == 200
    assert r_llanta.json()["encontrado"] is False

    # 4. Probar en cliente PRO: segundo 'sn' duplicado en el mismo mes debe ser rechazado con 400
    cliente_pro = "CLIENTE API PRO TEST"
    auth_client.post("/api/configuraciones-clientes/licencia", json={
        "cliente": cliente_pro,
        "tipo_licencia": "PRO"
    })
    p_pro1 = dict(payload1, cliente=cliente_pro, placa="PRO-001")
    assert auth_client.post("/api/inspecciones", json=p_pro1).status_code == 200

    p_pro2 = dict(payload2, cliente=cliente_pro, placa="PRO-002", posicion=1)
    r_pro2 = auth_client.post("/api/inspecciones", json=p_pro2)
    assert r_pro2.status_code == 400
    assert "CANDADO DE NÚMERO INTERNO" in r_pro2.json()["detail"]







