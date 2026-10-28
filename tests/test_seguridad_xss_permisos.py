"""Correcciones de la revisión de seguridad: textos sin HTML al guardarse (XSS almacenado), jefatura limitada a sus
clientes, catálogos compartidos editables solo por el administrador y cabeceras de seguridad."""
import json

import pandas as pd
from fastapi.testclient import TestClient

import database
import server

A, B = "CLIENTE ALFA", "CLIENTE BRAVO"
CARGA = '<img src=x onerror="alert(1)">'


def _cliente(usuario, rol, cliente=A):
    database.crear_usuario(usuario, "Clave-Prueba-123", usuario, rol, cliente,
                           vistas_permitidas="patio,basedatos,diagnostico,kpis,composicion,catalogos,bodegas")
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(usuario, rol)}"})
    return c


def _inspeccion(**extra):
    d = {"fecha": "2026-10-08", "cliente": A, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": "XSS001", "posicion": 1,
         "kilometraje": 50000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
         "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "psi": 100,
         "numero_interno": "SN-1"}
    d.update(extra)
    return d


def test_textos_de_la_api_se_guardan_sin_html(test_db, auth_client):
    foto = json.dumps(["data:image/jpeg;base64,AAAA"])
    r = auth_client.post("/api/inspecciones", json=_inspeccion(marca=CARGA, diseno="it's \"X\" `y`", novedades="corte <b>grave</b>",
                                                               foto_novedad=foto))
    assert r.status_code == 200, r.text
    with database.get_connection() as conn:
        marca, diseno, novedades, f = conn.execute("SELECT marca, diseno, novedades, foto_novedad FROM inspecciones").fetchone()
    for texto in (marca, diseno, novedades):
        assert not any(ch in texto for ch in '<>"\'`'), texto
    assert "IMG SRC=X ONERROR=ALERT(1)" in marca  # el texto queda, sin los caracteres que lo vuelven HTML
    assert f == foto  # las fotos no se tocan


def test_contrasena_con_comillas_sigue_funcionando(test_db, auth_client):
    clave = 'Cl"ave<con>\'raros`1'
    r = auth_client.post("/api/usuarios", json={"username": "usuario_raro", "password": clave, "nombre_completo": "Usuario <Raro>",
                                                "rol": "inspector", "cliente_asignado": A, "vistas_permitidas": "patio"})
    assert r.status_code == 200, r.text
    assert TestClient(server.app).post("/api/login", json={"username": "usuario_raro", "password": clave}).status_code == 200
    assert "<" not in database.obtener_usuario_por_username("usuario_raro")["nombre_completo"]


def test_excel_de_inspecciones_se_guarda_sin_html(test_db, tmp_path):
    ruta = tmp_path / "insp.xlsx"
    pd.DataFrame([{"Fecha": "2026-10-08", "Cliente": A, "Sede": "SEDE", "Placa": "XLS001", "Posicion": 1,
                   "Tipologia": "Cabezote (6x4)", "Marca": CARGA, "Dimension": "295/80R22.5", "Prof Ext": 10,
                   "Prof Cent": 10, "Prof Int": 10, "PSI": 100, "Kilometraje": 1000, "Novedades": "<script>x</script>"}]).to_excel(ruta, index=False)
    database.cargar_excel_a_bd(str(ruta))
    with database.get_connection() as conn:
        marca, nov = conn.execute("SELECT marca, novedades FROM inspecciones WHERE placa = 'XLS001'").fetchone()
    assert "<" not in marca and "<" not in nov


def test_jefatura_solo_cambia_la_configuracion_de_sus_clientes(test_db):
    jefe = _cliente("jefe_alfa", "jefatura")
    database.guardar_limite_retiro_cliente(cliente=B, limite_retiro_mm=3.0, observaciones="", subcliente="TODOS", eje="TODOS")
    database.guardar_marca_cliente(B, "MICHELIN")
    with database.get_connection() as conn:
        lim_b = conn.execute("SELECT id FROM configuracion_limites_retiro WHERE cliente = ?", (B,)).fetchone()[0]
        marca_b = conn.execute("SELECT id FROM configuracion_marcas_cliente WHERE cliente = ?", (B,)).fetchone()[0]

    limite = {"limite_retiro_mm": 9, "observaciones": "", "subcliente": "TODOS", "eje": "TODOS"}
    assert jefe.post("/api/configuraciones-clientes", json={"cliente": B, **limite}).status_code == 403
    assert jefe.put(f"/api/configuraciones-clientes/{lim_b}", json={"cliente": A, **limite}).status_code == 403
    assert jefe.delete(f"/api/configuraciones-clientes/{lim_b}").status_code == 403
    assert jefe.post("/api/configuracion-marcas-cliente", json={"cliente": B, "marca": "PIRELLI"}).status_code == 403
    assert jefe.delete(f"/api/configuracion-marcas-cliente/{marca_b}").status_code == 403
    assert jefe.delete("/api/configuracion-marcas-cliente", params={"cliente": B, "marca": "MICHELIN"}).status_code == 403
    assert jefe.post("/api/clientes-directorio", json={"cliente": B, "limite_retiro_mm": 3, "observaciones": "x"}).status_code == 403
    assert jefe.delete(f"/api/clientes-directorio/{B}").status_code == 403
    with database.get_connection() as conn:
        assert conn.execute("SELECT limite_retiro_mm FROM configuracion_limites_retiro WHERE id = ?", (lim_b,)).fetchone()[0] == 3.0
        assert conn.execute("SELECT COUNT(*) FROM configuracion_marcas_cliente WHERE cliente = ?", (B,)).fetchone()[0] == 1

    # Con su propio cliente sí puede
    assert jefe.post("/api/configuraciones-clientes", json={"cliente": A, **limite}).status_code == 200
    assert jefe.post("/api/configuracion-marcas-cliente", json={"cliente": A, "marca": "PIRELLI"}).status_code == 200


def test_catalogos_compartidos_solo_los_cambia_el_administrador(test_db, auth_client):
    jefe = _cliente("jefe_cat", "jefatura")
    tip = auth_client.get("/api/tipologias").json()[0]["nombre"]
    assert jefe.delete("/api/tipologias", params={"nombre": tip}).status_code == 403
    assert jefe.delete("/api/operaciones", params={"nombre": "CARGA"}).status_code == 403
    assert any(t["nombre"] == tip for t in auth_client.get("/api/tipologias").json())


def test_cabeceras_de_seguridad(test_db):
    r = TestClient(server.app).get("/login")
    for cabecera in ("Content-Security-Policy", "Strict-Transport-Security", "X-Frame-Options", "X-Content-Type-Options",
                     "Referrer-Policy", "Permissions-Policy"):
        assert cabecera in r.headers, cabecera
    assert "frame-ancestors 'self'" in r.headers["Content-Security-Policy"]
    assert "object-src 'none'" in r.headers["Content-Security-Policy"]
