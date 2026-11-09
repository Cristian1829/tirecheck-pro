"""Auditoría 2026-11-09, lote 1: aislamiento entre clientes y credenciales (H-01, H-03, H-04, H-15, H-36, H-44)."""
import os

from fastapi.testclient import TestClient

import database
import server

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cliente_http(username, rol):
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(username, rol)}"})
    return c


VISTAS_POR_ROL = {"jefatura": "patio,basedatos,diagnostico,kpis,composicion,catalogos",
                  "gerencia": "basedatos,diagnostico,kpis,composicion", "admin": "patio,basedatos,diagnostico,kpis,composicion,catalogos",
                  "inspector": "patio,diagnostico,kpis,composicion"}


def _usuario(username, rol, clientes="", vistas=None, sedes="", clave="Clave-Segura-2026"):
    vistas = vistas or VISTAS_POR_ROL[rol]  # las que asigna la pantalla de Usuarios a cada rol
    with database.get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE username = ?", (username,))
        conn.execute("INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas,"
                     " sedes_asignadas) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (username, database.hash_password(clave), username, rol, clientes, vistas, sedes))
        conn.commit()


def _inspeccion(cliente, placa, sede="SEDE A", marca="MICHELIN"):
    with database.get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO inspecciones (fecha, cliente, subcliente, placa, posicion, marca, diseno, dimension, vida,"
            " prof_ext, prof_cent, prof_int) VALUES ('2026-10-01', ?, ?, ?, 1, ?, 'XZE', '295/80R22.5', 'ORIGINAL', 10, 10, 10)",
            (cliente, sede, placa, marca))
        conn.commit()
        return cur.lastrowid


# --- H-01: ?usuario= solo lo usa el administrador -------------------------------------------
def test_h01_jefatura_con_usuario_admin_no_ve_otras_flotas(test_db):
    _inspeccion("CLI PROPIO", "PRO001")
    _inspeccion("CLI AJENO", "AJE001")
    for rol in ("jefatura", "gerencia"):
        _usuario(f"{rol}_uno", rol, "CLI PROPIO")
        c = _cliente_http(f"{rol}_uno", rol)
        for url in ("/api/inspecciones?usuario=admin", "/api/inspecciones"):
            placas = {r["placa"] for r in c.get(url).json()}
            assert placas == {"PRO001"}, (rol, url, placas)
        # Las otras rutas que aceptaban ?usuario= tampoco abren otras flotas
        llantas = c.get("/api/kpis-llantas?usuario=admin").json()
        assert all(str(l.get("cliente", "")).upper() == "CLI PROPIO" for l in llantas)


def test_h01_admin_conserva_el_filtro_por_usuario(test_db):
    _inspeccion("CLI PROPIO", "PRO001")
    _inspeccion("CLI AJENO", "AJE001")
    _usuario("jefe_filtro", "jefatura", "CLI PROPIO")
    admin = _cliente_http("admin", "admin")
    assert {"PRO001", "AJE001"} <= {r["placa"] for r in admin.get("/api/inspecciones").json()}
    assert {r["placa"] for r in admin.get("/api/inspecciones?usuario=jefe_filtro").json()} == {"PRO001"}


def test_h01_jefatura_sin_clientes_asignados_ve_todo(test_db):
    """Sin clientes asignados el perfil es de todas las flotas (como antes)."""
    _inspeccion("CLI PROPIO", "PRO001")
    _inspeccion("CLI AJENO", "AJE001")
    _usuario("jefe_global", "jefatura", "")
    assert server.resolver_filtro_usuario_inspecciones({"username": "jefe_global", "rol": "jefatura"}, "admin") is None


# --- H-04: marca/diseño por placa y límite por cliente solo de flotas propias ----------------
def test_h04_ultima_marca_diseno_de_otra_flota_es_403(test_db):
    _inspeccion("CLI AJENO", "AJE777", marca="BRIDGESTONE")
    _inspeccion("CLI PROPIO", "PRO777")
    _usuario("insp_propio", "inspector", "CLI PROPIO")
    c = _cliente_http("insp_propio", "inspector")
    r = c.get("/api/inspecciones/ultima-marca-diseno?placa=AJE777")
    assert r.status_code == 403 and "BRIDGESTONE" not in r.text
    assert c.get("/api/inspecciones/ultima-marca-diseno?placa=PRO777").status_code == 200


def test_h04_limite_cliente_de_otra_flota_es_403(test_db):
    _usuario("insp_propio", "inspector", "CLI PROPIO", sedes="CLI PROPIO|SEDE A")
    c = _cliente_http("insp_propio", "inspector")
    assert c.get("/api/limite-cliente?cliente=CLI AJENO").status_code == 403
    assert c.get("/api/limite-cliente?cliente=CLI PROPIO&subcliente=SEDE B").status_code == 403
    ok = c.get("/api/limite-cliente?cliente=CLI PROPIO&subcliente=SEDE A")
    assert ok.status_code == 200 and "limite_retiro_mm" in ok.json()
    assert _cliente_http("admin", "admin").get("/api/limite-cliente?cliente=CLI AJENO").status_code == 200


# --- H-15: listar, ver, editar y borrar exigen la vista basedatos; el detalle valida la sede --
def test_h15_inspector_solo_patio_no_lista_ni_borra(test_db):
    i = _inspeccion("CLI PROPIO", "PRO001")
    _usuario("insp_patio", "inspector", "CLI PROPIO", vistas="patio")
    c = _cliente_http("insp_patio", "inspector")
    assert c.get("/api/inspecciones").status_code == 403
    assert c.get(f"/api/inspecciones/{i}").status_code == 403
    assert c.delete(f"/api/inspecciones/{i}").status_code == 403
    assert c.put(f"/api/inspecciones/{i}", json={"placa": "PRO001", "posicion": 1}).status_code == 403
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM inspecciones WHERE id = ?", (i,)).fetchone()[0] == 1


def test_h15_detalle_de_otra_sede_es_403(test_db):
    propia = _inspeccion("CLI PROPIO", "PRO001", sede="SEDE A")
    otra = _inspeccion("CLI PROPIO", "PRO002", sede="SEDE B")
    _usuario("jefe_sede", "jefatura", "CLI PROPIO", sedes="CLI PROPIO|SEDE A")
    c = _cliente_http("jefe_sede", "jefatura")
    assert c.get(f"/api/inspecciones/{propia}").status_code == 200
    assert c.get(f"/api/inspecciones/{otra}").status_code == 403


def test_h15_la_base_avisa_si_el_perfil_no_tiene_la_vista():
    js = open(os.path.join(RAIZ, "static", "js", "modulo_basedatos.js"), encoding="utf-8").read()
    cuerpo = js[js.index("async function cargarBaseInspecciones"):js.index("function poblarSelectoresFiltroBD")]
    assert "res.status === 403" in cuerpo


# --- H-03: claves de ejemplo publicadas -----------------------------------------------------
def test_h03_clave_1234_publicada_no_da_acceso(test_db):
    server._login_attempts.clear()
    _usuario("insp_demo", "inspector", "CLI PROPIO", clave="1234")
    assert database.autenticar_usuario("insp_demo", "1234") is None
    r = TestClient(server.app).post("/api/login", json={"username": "insp_demo", "password": "1234"})
    assert r.status_code == 401
    server._login_attempts.clear()


def test_h03_admin_con_clave_publicada_entra_pero_debe_cambiarla(test_db):
    """El administrador no queda bloqueado (no habría cómo entrar), pero se le exige cambiar la clave."""
    _usuario("admin_demo", "admin", "", clave="admin123")
    u = database.autenticar_usuario("admin_demo", "admin123")
    assert u is not None and u["debe_cambiar_clave"] is True


def test_h03_base_nueva_sin_claves_conocidas(tmp_path, monkeypatch):
    anterior = database.DB_PATH
    monkeypatch.delenv("TIREANALYZE_CLAVE_INICIAL_ADMIN", raising=False)
    database.DB_PATH = str(tmp_path / "nueva.db")
    try:
        database.inicializar_bd()
        for usr in ("admin", "jefe1", "gerencia1", "inspector1"):
            for clave in ("admin123", "1234"):
                with database.get_connection() as conn:
                    guardada = conn.execute("SELECT password FROM usuarios WHERE username = ?", (usr,)).fetchone()[0]
                assert not database.verify_password(clave, guardada), (usr, clave)
        monkeypatch.setenv("TIREANALYZE_CLAVE_INICIAL_ADMIN", "Inicial-Conocida-26")
        database.DB_PATH = str(tmp_path / "otra.db")
        database.inicializar_bd()
        assert database.autenticar_usuario("admin", "Inicial-Conocida-26") is not None
    finally:
        database.DB_PATH = anterior


def test_h03_documentacion_sin_claves_de_ejemplo():
    for rel in ("README.md", "docs/AGENTS.md", "docs/GUIA_DESPLIEGUE_RENDER.md", "docs/API_REFERENCE.md",
                "docs/DOCUMENTACION_MIGRACION.md"):
        texto = open(os.path.join(RAIZ, rel), encoding="utf-8").read()
        assert "admin123" not in texto and "`1234`" not in texto, rel


# --- H-44: restaurar la semilla exige frase y clave -----------------------------------------
def test_h44_restaurar_semilla_exige_frase_y_clave(test_db, monkeypatch):
    copias = []
    monkeypatch.setattr("shutil.copy2", lambda *a, **k: copias.append(a))
    admin = _cliente_http("admin", "admin")
    assert admin.post("/api/admin/restaurar-seed", json={}).status_code == 400
    assert admin.post("/api/admin/restaurar-seed",
                      json={"confirmacion": "RESTAURAR BASE", "clave": "incorrecta"}).status_code == 403
    assert copias == []  # nada se copió sobre la base
    _usuario("jefe_x", "jefatura", "CLI PROPIO")
    assert _cliente_http("jefe_x", "jefatura").post(
        "/api/admin/restaurar-seed", json={"confirmacion": "RESTAURAR BASE", "clave": "x"}).status_code == 403


# --- H-36 (parte): textos de la base que se pintaban sin escapar ----------------------------
def test_h36_motivo_y_cliente_se_escapan():
    bodegas = open(os.path.join(RAIZ, "static", "js", "modulo_bodegas.js"), encoding="utf-8").read()
    patio = open(os.path.join(RAIZ, "static", "js", "modulo_patio.js"), encoding="utf-8").read()
    assert "Motivo: ${m.motivo}" not in bodegas and "Motivo: ${escapeHtml(m.motivo)}" in bodegas
    assert "Llanta de ${lt.cliente" not in patio and "Llanta de ${escapeHtml(lt.cliente" in patio
