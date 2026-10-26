"""Auditoría de seguridad (bloque 1): licencias, permisos y usuarios por defecto."""
from fastapi.testclient import TestClient

import database
import server


def _cliente_http(username, rol):
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(username, rol)}"})
    return c


def _crear_usuario(username, rol, clientes="", vistas=None):
    with database.get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE username = ?", (username,))
        conn.execute(
            "INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas) VALUES (?, ?, ?, ?, ?, ?)",
            (username, database.hash_password("x"), username, rol, clientes, vistas))
        conn.commit()


def _licencia(cliente, tipo):
    with database.get_connection() as conn:
        conn.execute("INSERT INTO configuracion_avanzada_cliente (cliente, tipo_licencia) VALUES (?, ?) "
                     "ON CONFLICT(cliente) DO UPDATE SET tipo_licencia = excluded.tipo_licencia", (cliente, tipo))
        conn.commit()


# --- #1: la licencia sale siempre de la configuración del cliente --------------------------
def test_1_parametro_licencia_no_sube_a_full(test_db):
    _licencia("CLI LIGHT", "LIGHT")
    _crear_usuario("insp_light", "inspector", "CLI LIGHT")
    c = _cliente_http("insp_light", "inspector")
    d = c.get("/api/kpis/suite-20?cliente=CLI LIGHT&licencia=FULL").json()
    assert d["licencia"] == "LIGHT"
    assert d["kpi_12"]["disponible"] is False


def test_1_full_puede_previsualizar_light(test_db):
    _licencia("CLI FULL", "PRO")
    d = _cliente_http("admin", "admin").get("/api/kpis/suite-20?cliente=CLI FULL&licencia=LIGHT").json()
    assert d["licencia"] == "LIGHT"


# --- #2: sin licencia configurada el cliente queda LIGHT -----------------------------------
def test_2_cliente_sin_configuracion_es_light(test_db):
    assert database.obtener_licencia_cliente("CLIENTE NUEVO SIN CONFIG") == "LIGHT"


def test_2_guardar_limites_no_regala_full(test_db):
    database.guardar_limite_retiro_cliente("CLI SOLO LIMITES", 3.0, eje="DIRECCIONAL")
    assert database.obtener_licencia_cliente("CLI SOLO LIMITES") == "LIGHT"
    with database.get_connection() as conn:
        conn.execute("INSERT INTO inspecciones (fecha, cliente, placa, posicion, vida) VALUES ('2026-10-01', 'CLI DESDE INSPECCION', 'AAA111', 1, 'ORIGINAL')")
        conn.commit()
    database.inicializar_bd()  # al arrancar se crean las configuraciones de los clientes nuevos
    assert database.obtener_licencia_cliente("CLI DESDE INSPECCION") == "LIGHT"


# --- #7: un usuario borrado no reaparece al reiniciar con clave conocida -------------------
def test_7_usuarios_borrados_no_reaparecen(test_db):
    with database.get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE username IN ('jefe1', 'gerencia1')")
        conn.commit()
    database.inicializar_bd()
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM usuarios WHERE username IN ('jefe1', 'gerencia1')").fetchone()[0] == 0


# --- #8: las migraciones de datos no se pueden relanzar desde una URL ----------------------
def test_8_migraciones_no_expuestas(test_db):
    c = _cliente_http("jefe1", "jefatura")
    for ruta in ("migrar-pepsico-tellantas", "migrar-restar-pext-ciudad-limpia?forzar=true",
                 "migrar-normalizar-cliente-ciudad-limpia?forzar=true", "migrar-limite-ciudad-limpia-4mm?forzar=true"):
        assert c.get(f"/api/admin/{ruta}").status_code in (404, 405), ruta
        assert c.post(f"/api/admin/{ruta}").status_code in (404, 405), ruta


# --- #4: un usuario que no es administrador y no tiene cliente asignado no ve ni toca datos ---
def _inspeccion(cliente, placa="SEG001"):
    return database.insertar_inspeccion({
        "fecha": "2026-10-10", "cliente": cliente, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": placa,
        "posicion": 1, "kilometraje": 1000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
        "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "psi": 110,
        "prof_inicial": 18, "numero_interno": f"N-{placa}", "usuario_registro": "otro"})


def test_4_usuario_sin_cliente_no_borra_ni_consulta(test_db):
    _inspeccion("CLIENTE AJENO")
    with database.get_connection() as conn:
        insp_id = conn.execute("SELECT id FROM inspecciones WHERE placa = 'SEG001'").fetchone()[0]
    _crear_usuario("insp_sin_cliente", "inspector", "")
    c = _cliente_http("insp_sin_cliente", "inspector")
    assert c.get("/api/inspecciones").status_code == 403
    assert c.delete(f"/api/inspecciones/{insp_id}").status_code == 403
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM inspecciones WHERE id = ?", (insp_id,)).fetchone()[0] == 1
    # puede consultar su sesión para que la app le explique por qué no ve datos
    assert c.get("/api/usuario-actual").status_code == 200


def test_4_no_se_crea_usuario_sin_cliente(test_db):
    c = _cliente_http("admin", "admin")
    r = c.post("/api/usuarios", json={"username": "nuevo_sin_cli", "password": "12345", "nombre_completo": "X",
                                      "rol": "inspector", "cliente_asignado": ""})
    assert r.status_code == 400


# --- #5: los datos se ven por cliente asignado, y editar no cambia quién registró -----------
def test_5_jefe_ve_inspecciones_de_otros_usuarios_de_su_cliente(test_db):
    _inspeccion("CLI JEFE", "JEF001")  # registrada por "otro"
    _crear_usuario("jefe_cli", "jefatura", "CLI JEFE")
    c = _cliente_http("jefe_cli", "jefatura")
    placas = {r["placa"] for r in c.get("/api/inspecciones").json()}
    assert "JEF001" in placas


def test_5_editar_conserva_el_autor(test_db):
    _inspeccion("CLI JEFE", "JEF002")
    with database.get_connection() as conn:
        insp_id = conn.execute("SELECT id FROM inspecciones WHERE placa = 'JEF002'").fetchone()[0]
    _crear_usuario("jefe_cli", "jefatura", "CLI JEFE")
    c = _cliente_http("jefe_cli", "jefatura")
    r = c.put(f"/api/inspecciones/{insp_id}", json={
        "fecha": "2026-10-10", "cliente": "CLI JEFE", "subcliente": "SEDE", "placa": "JEF002", "posicion": 1,
        "kilometraje": 1000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
        "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 9.5, "prof_cent": 10, "prof_int": 10,
        "psi": 110, "prof_inicial": 18, "numero_interno": "N-JEF002"})
    assert r.status_code == 200, r.text
    with database.get_connection() as conn:
        assert conn.execute("SELECT usuario_registro FROM inspecciones WHERE id = ?", (insp_id,)).fetchone()[0].lower() == "otro"


# --- #6: el servidor respeta las vistas permitidas de cada usuario --------------------------
def test_6_vistas_no_permitidas_se_rechazan_en_el_servidor(test_db):
    _crear_usuario("insp_solo_patio", "inspector", "CLI V", "patio")
    c = _cliente_http("insp_solo_patio", "inspector")
    for ruta in ("/api/kpis/suite-20", "/api/diagnostico", "/api/kpis-llantas", "/api/bodegas/inventario",
                 "/api/inspecciones/exportar-excel"):
        assert c.get(ruta).status_code == 403, ruta
    # lo que usa el patio sigue disponible (informe al finalizar la inspección)
    assert c.get("/api/informe-resumen/SINPLACA").status_code != 403


def test_6_vista_permitida_funciona(test_db):
    _crear_usuario("insp_kpis", "inspector", "CLI V", "patio,kpis")
    assert _cliente_http("insp_kpis", "inspector").get("/api/kpis/suite-20").status_code == 200
