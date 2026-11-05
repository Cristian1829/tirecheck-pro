"""
App de Motores: login propio (mismo nivel que el de TireAnalyze y separado de él) y los módulos del documento:
ingreso, despacho parcial y total, certificado, clientes, trazabilidad y archivos con sesión.
"""
import base64
import io
import os
import re
import secrets

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import database
import server
from motores import base, rutas, seguridad
from motores.modelos import Usuario

CLAVE = "Motores-Seguros-26"
CLAVE_NUEVA = "Taller-Brentwood-77"


def _png():
    b = io.BytesIO()
    Image.new("RGB", (60, 30), "white").save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


IMG = _png()


@pytest.fixture(autouse=True)
def motores_temporal(tmp_path):
    seguridad.intentos_ip.clear()
    base.configurar(str(tmp_path / "motores"))
    yield
    seguridad.intentos_ip.clear()
    base.configurar(str(tmp_path / "motores_fin"))


def _usuario(username="admin1", rol="admin", clave=CLAVE, cambiar=False):
    db = base.nueva_sesion()
    db.add(Usuario(username=username, nombre=username, rol=rol, password_hash=database.hash_password(clave),
                   activo=True, debe_cambiar_clave=cambiar))
    db.commit()
    db.close()


def _cliente_http():
    return TestClient(server.app)


def _login(c, username="admin1", clave=CLAVE, **cabeceras):
    return c.post("/api/motores/login", json={"username": username, "password": clave}, headers=cabeceras)


@pytest.fixture
def c():
    _usuario()
    cliente = _cliente_http()
    assert _login(cliente).status_code == 200
    return cliente


def _orden(c, n=2, **extra):
    datos = {
        "company_name": "skyline scaffolding",
        "date_in": "2026-11-05T09:30:00",
        "dropoff_name": "john miller",
        "firma_dropoff": IMG,
        "received_name": "marino trejos",
        "firma_received": IMG,
        "motores": [
            {"make": "tirak", "model": "tirak xe 500p", "serial_number": f"s-{i}", "observaciones": "A & B <x>", "foto_ingreso_url": IMG}
            for i in range(n)
        ],
    }
    datos.update(extra)
    return c.post("/api/motores/orders/", json=datos)


def _despacho(c, orden, motores, **extra):
    datos = {
        "orden_id": orden["id"],
        "fecha_salida": "2026-11-06T15:00:00",
        "firma_entrega_empresa": IMG,
        "firma_recibe_cliente": IMG,
        "motores_despacho": [{"motor_id": m["id"], "foto_salida_url": IMG} for m in motores],
    }
    datos.update(extra)
    return c.post("/api/motores/dispatches/", json=datos)


def _certificado(c, motor_id, **extra):
    datos = dict(motor_id=motor_id, rectifier=True, brake_release_lever=True, brake_function=True, normal_noise=True,
                 emergency_pin_descend=True, brake_disc=True, stirrup_adapter=True, rated_load_test=True)
    datos.update(extra)
    return c.post("/api/motores/certificates/", json=datos)


# ================= HOME Y PÁGINA =================
def test_el_home_tiene_el_boton_login_motores():
    r = _cliente_http().get("/")
    assert r.status_code == 200
    assert 'href="/motores"' in r.text and "Login Motores" in r.text


def test_la_pagina_de_motores_abre_el_login_sin_sesion():
    r = _cliente_http().get("/motores")
    assert r.status_code == 200
    assert 'id="vista-login"' in r.text


# ================= LOGIN =================
def test_todo_exige_sesion():
    c = _cliente_http()
    for ruta in ["orders/", "motors/", "clients/", "certificates/", "dispatches/", "motors/dashboard/stats",
                 "motors/common/presets", "usuarios", "archivos/x.pdf", "network-qr", "me"]:
        assert c.get(f"/api/motores/{ruta}").status_code == 401, ruta


def test_clave_incorrecta_y_cookie_segura():
    _usuario()
    c = _cliente_http()
    assert _login(c, clave="otra-cosa-99").status_code == 401
    r = _login(c, **{"X-Forwarded-Proto": "https"})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "motores_token=" in cookie and "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert "token" not in r.json()  # el token no queda al alcance de JavaScript
    assert "password_hash" not in str(r.json())


def test_usuario_inexistente_gasta_lo_mismo(monkeypatch):
    llamadas = []
    monkeypatch.setattr(database, "verificar_clave_ficticia", lambda clave: llamadas.append(1))
    assert _login(_cliente_http(), username="nadie").status_code == 401
    assert llamadas == [1]


def test_bloqueo_por_ip():
    _usuario()
    c = _cliente_http()
    for _ in range(seguridad.MAX_FALLOS_IP):
        assert _login(c, clave="mala-clave-1", **{"X-Real-IP": "9.9.9.9"}).status_code == 401
    assert _login(c, **{"X-Real-IP": "9.9.9.9"}).status_code == 429
    assert _login(c, **{"X-Real-IP": "8.8.8.8"}).status_code == 200


def test_bloqueo_por_usuario_aunque_cambie_la_ip():
    _usuario()
    c = _cliente_http()
    for i in range(seguridad.MAX_FALLOS_USUARIO):
        assert _login(c, clave="mala-clave-1", **{"X-Real-IP": f"7.7.7.{i}"}).status_code == 401
    assert _login(c, **{"X-Real-IP": "6.6.6.6"}).status_code == 429


def test_salir_revoca_la_sesion_aunque_se_haya_copiado_el_token(c):
    copia = c.cookies.get(seguridad.COOKIE)
    assert c.post("/api/motores/logout").status_code == 200
    otro = _cliente_http()
    otro.cookies.set(seguridad.COOKIE, copia)
    assert otro.get("/api/motores/me").status_code == 401


def test_token_alterado_no_sirve(c):
    otro = _cliente_http()
    token = c.cookies.get(seguridad.COOKIE)
    otro.cookies.set(seguridad.COOKIE, token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert otro.get("/api/motores/me").status_code == 401


def test_cambio_de_clave_obligatorio_y_politica():
    _usuario(cambiar=True)
    c = _cliente_http()
    assert _login(c).status_code == 200
    r = c.get("/api/motores/orders/")
    assert r.status_code == 403 and r.headers.get("X-Requiere-Cambio-Clave") == "1"
    assert c.get("/api/motores/me").status_code == 200

    malas = [("incorrecta-1", CLAVE_NUEVA, 400), (CLAVE, "12345678", 400), (CLAVE, "corta", 400), (CLAVE, CLAVE, 400)]
    for actual, nueva, codigo in malas:
        assert c.post("/api/motores/mi-cuenta/cambiar-clave", json={"clave_actual": actual, "clave_nueva": nueva}).status_code == codigo

    otra_sesion = _cliente_http()
    assert _login(otra_sesion).status_code == 200
    r = c.post("/api/motores/mi-cuenta/cambiar-clave", json={"clave_actual": CLAVE, "clave_nueva": CLAVE_NUEVA})
    assert r.status_code == 200
    assert c.get("/api/motores/orders/").status_code == 200
    assert otra_sesion.get("/api/motores/me").status_code == 401  # las demás sesiones quedan cerradas
    assert _login(_cliente_http(), clave=CLAVE).status_code == 401
    assert _login(_cliente_http(), clave=CLAVE_NUEVA).status_code == 200


def test_primer_admin_sale_de_variables_y_nunca_de_una_clave_fija(monkeypatch):
    monkeypatch.delenv("MOTORES_ADMIN_USUARIO", raising=False)
    monkeypatch.delenv("MOTORES_ADMIN_CLAVE", raising=False)
    seguridad.crear_admin_inicial()
    db = base.nueva_sesion()
    assert db.query(Usuario).count() == 0

    monkeypatch.setenv("MOTORES_ADMIN_USUARIO", "dueno")
    monkeypatch.setenv("MOTORES_ADMIN_CLAVE", "12345678")  # débil: no se crea
    seguridad.crear_admin_inicial()
    assert db.query(Usuario).count() == 0

    clave = secrets.token_urlsafe(12)
    monkeypatch.setenv("MOTORES_ADMIN_CLAVE", clave)
    seguridad.crear_admin_inicial()
    u = db.query(Usuario).one()
    assert (u.username, u.rol, u.debe_cambiar_clave) == ("dueno", "admin", True)
    assert clave not in u.password_hash
    db.close()


def test_solo_el_admin_gestiona_usuarios(c):
    r = c.post("/api/motores/usuarios", json={"username": "tecnico1", "rol": "tecnico", "clave_nueva": CLAVE})
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is True
    assert c.post("/api/motores/usuarios", json={"username": "tecnico1", "clave_nueva": CLAVE}).status_code == 400
    assert c.post("/api/motores/usuarios", json={"username": "t2", "clave_nueva": "12345678"}).status_code == 400

    _usuario("tec2", rol="tecnico")
    tec = _cliente_http()
    assert _login(tec, "tec2").status_code == 200
    assert tec.get("/api/motores/usuarios").status_code == 403
    assert tec.post("/api/motores/usuarios", json={"username": "otro1", "clave_nueva": CLAVE}).status_code == 403
    assert tec.get("/api/motores/orders/").status_code == 200

    # Desactivar cierra su sesión
    id_tec = next(u["id"] for u in c.get("/api/motores/usuarios").json() if u["username"] == "tec2")
    assert c.put(f"/api/motores/usuarios/{id_tec}", json={"activo": False}).status_code == 200
    assert tec.get("/api/motores/me").status_code == 401
    assert _login(_cliente_http(), "tec2").status_code == 401

    # Un admin no se deja a sí mismo sin acceso
    id_yo = c.get("/api/motores/me").json()["usuario"]["id"]
    assert c.put(f"/api/motores/usuarios/{id_yo}", json={"activo": False}).status_code == 400


# ================= SEPARACIÓN DE TIREANALYZE =================
def test_token_de_llantas_no_entra_a_motores_ni_al_reves(c, test_db):
    assert database.crear_usuario("llantas_x", CLAVE, "Llantas", "inspector", "FLOTA X", "patio")
    token_llantas = server.crear_token_acceso("admin1", "admin", 0)
    otro = _cliente_http()
    otro.cookies.set(seguridad.COOKIE, token_llantas)
    assert otro.get("/api/motores/me").status_code == 401

    # El usuario de llantas no existe en Motores
    assert _login(_cliente_http(), "llantas_x").status_code == 401

    # La sesión de Motores no abre TireAnalyze
    token_motores = c.cookies.get(seguridad.COOKIE)
    r = _cliente_http().get("/api/usuario-actual", headers={"Authorization": f"Bearer {token_motores}"})
    assert r.status_code == 401


def test_motores_no_usa_la_base_de_llantas(c):
    assert os.path.dirname(os.path.abspath(database.DB_PATH)) != base.dir_datos()
    assert os.path.exists(os.path.join(base.dir_datos(), "motores_control.db"))


# ================= MÓDULO A: INGRESO =================
def test_ingreso_varios_motores_mayusculas_y_pdf(c):
    r = _orden(c)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["numero_orden"].startswith("ORD-") and o["company_name"] == "SKYLINE SCAFFOLDING"
    assert o["estado_orden"] == "En Taller" and o["date_in"] == "2026-11-05T09:30:00"
    assert [m["serial_number"] for m in o["motores"]] == ["S-0", "S-1"]
    assert o["motores"][0]["make"] == "TIRAK"
    assert o["pdf_ingreso_url"].endswith(".pdf")
    pdf = c.get(o["pdf_ingreso_url"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert pdf.headers["content-disposition"].startswith("inline")
    # Ni rutas de disco en la respuesta
    assert base.dir_datos() not in r.text
    assert _orden(c).json()["numero_orden"] != o["numero_orden"]


def test_ingreso_exige_motor_foto_y_firmas(c):
    assert _orden(c, n=0).status_code == 400
    assert _orden(c, firma_dropoff=None).status_code == 400
    assert _orden(c, firma_received=None).status_code == 400
    r = _orden(c, motores=[{"make": "T", "model": "M", "serial_number": "1"}])
    assert r.status_code == 400 and "foto" in r.json()["detail"]
    assert _orden(c, motores=[{"make": " ", "model": "M", "serial_number": "1", "foto_ingreso_url": IMG}]).status_code == 400


@pytest.mark.parametrize("malo", [
    "C:/Windows/win.ini",
    "../../data/.secret_key",
    "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
    "data:image/png;base64,bm8tZXMtaW1hZ2Vu",
    "data:image/png;base64,###",
])
def test_no_acepta_rutas_ni_archivos_que_no_sean_imagen(c, malo):
    r = _orden(c, firma_dropoff=malo)
    assert r.status_code == 400
    r = _orden(c, motores=[{"make": "T", "model": "M", "serial_number": "1", "foto_ingreso_url": malo}])
    assert r.status_code == 400


def test_la_foto_guardada_no_conserva_metadatos(c):
    b = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "CAMARA-SECRETA"
    Image.new("RGB", (40, 40), "red").save(b, "JPEG", exif=exif)
    foto = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    o = _orden(c, motores=[{"make": "T", "model": "M", "serial_number": "1", "foto_ingreso_url": foto}]).json()
    assert b"CAMARA-SECRETA" not in c.get(o["motores"][0]["foto_ingreso_url"]).content


def test_texto_con_marcas_no_rompe_el_pdf(c):
    """ReportLab interpreta etiquetas: un & o una etiqueta en los datos no debe dejar la orden sin PDF."""
    o = _orden(c, company_name="A & B SCAFFOLD").json()
    assert o["pdf_ingreso_url"]
    assert o["company_name"] == "A & B SCAFFOLD"
    # Directo al generador, sin pasar por el filtro de entrada
    from motores import pdf
    assert pdf.esc("<b>x & y") == "&lt;b&gt;x &amp; y"


# ================= MÓDULO B: DESPACHOS =================
def test_despacho_parcial_y_luego_total(c):
    o = _orden(c, n=2).json()
    r = _despacho(c, o, o["motores"][:1])
    assert r.status_code == 200, r.text
    assert r.json()["tipo_entrega"] == "Parcial" and r.json()["pdf_salida_url"]
    d = c.get(f"/api/motores/orders/{o['id']}").json()
    assert d["estado_orden"] == "Entregado Parcial" and d["date_out"] is None
    assert [m["estado_motor"] for m in d["motores"]] == ["Entregado", "En Taller"]
    assert d["motores"][0]["foto_salida_url"]

    r = _despacho(c, o, o["motores"][1:])
    assert r.json()["tipo_entrega"] == "Total"
    d = c.get(f"/api/motores/orders/{o['id']}").json()
    assert d["estado_orden"] == "Entregado Total" and d["date_out"] == "2026-11-06T15:00:00"
    # El PDF de la orden es el unificado de ingreso y salida
    assert d["pdf_ingreso_url"] == r.json()["pdf_salida_url"]
    assert c.get(d["pdf_ingreso_url"]).content[:4] == b"%PDF"
    assert len(c.get(f"/api/motores/dispatches/order/{o['id']}").json()) == 2


def test_despacho_rechaza_lo_que_no_corresponde(c):
    o = _orden(c, n=1).json()
    otra = _orden(c, n=1).json()
    assert _despacho(c, o, []).status_code == 400
    assert _despacho(c, o, otra["motores"]).status_code == 400  # motor de otra orden
    assert _despacho(c, o, o["motores"] * 2).status_code == 400  # repetido
    assert _despacho(c, o, o["motores"], firma_recibe_cliente=None).status_code == 400
    sin_foto = {"orden_id": o["id"], "firma_entrega_empresa": IMG, "firma_recibe_cliente": IMG,
                "motores_despacho": [{"motor_id": o["motores"][0]["id"]}]}
    assert c.post("/api/motores/dispatches/", json=sin_foto).status_code == 400
    assert c.get(f"/api/motores/orders/{o['id']}").json()["estado_orden"] == "En Taller"
    assert c.get("/api/motores/dispatches/").json() == []  # los rechazos no dejan despachos vacíos

    assert _despacho(c, o, o["motores"]).status_code == 200
    assert _despacho(c, o, o["motores"]).status_code == 400  # ya entregado


# ================= MÓDULO C: CERTIFICADOS =================
def test_certificado_consecutivo_y_proximo_servicio(c):
    m = _orden(c, n=1).json()["motores"][0]
    r = _certificado(c, m["id"], test_date="2026-11-05T00:00:00")
    assert r.status_code == 200, r.text
    cert = r.json()
    assert cert["test_certificate_no"] == "10010001"
    assert cert["next_service"].startswith("2027-11-05")
    assert cert["blocstop_serial"] == f"BS-{m['serial_number']}"
    assert c.get(cert["pdf_certificado_url"]).content[:4] == b"%PDF"
    assert _certificado(c, m["id"]).json()["test_certificate_no"] == "10010002"
    assert _certificado(c, 999999).status_code == 404


def _texto_pdf(c, url):
    from pypdf import PdfReader
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(c.get(url).content)).pages)


def test_los_pdf_llevan_los_dos_logos_y_caben_en_una_hoja(c):
    pytest.importorskip("pypdf")
    from pypdf import PdfReader
    o = _orden(c, n=1).json()
    cert = _certificado(c, o["motores"][0]["id"]).json()
    for url, minimo in [(o["pdf_ingreso_url"], 2), (cert["pdf_certificado_url"], 2)]:
        paginas = PdfReader(io.BytesIO(c.get(url).content)).pages
        assert len(paginas) == 1
        assert len(paginas[0].images) >= minimo


def test_la_pagina_muestra_los_logos():
    c = _cliente_http()
    html = c.get("/motores").text
    for logo in ("logo_marino_horizontal.png", "logo_motor_service_nyc.png"):
        assert logo in html
        assert c.get(f"/static/img/motores/{logo}").status_code == 200


def test_el_certificado_no_dice_passed_si_el_punto_no_paso(c):
    """Son equipos de izaje: el documento imprimía PASSED aunque el técnico no marcara el punto."""
    pytest.importorskip("pypdf")
    m = _orden(c, n=1).json()["motores"][0]

    aprobado = _certificado(c, m["id"]).json()
    t = _texto_pdf(c, aprobado["pdf_certificado_url"])
    assert "NOT PASSED" not in t and "PASSED" in t

    con_falla = _certificado(c, m["id"], brake_function=False, blocstop_trigger_speed="Testing Fail").json()
    t = _texto_pdf(c, con_falla["pdf_certificado_url"])
    assert "NOT PASSED" in t and "ONE OR MORE ITEMS NOT PASSED" in t
    assert con_falla["test_certificate_no"] in t


PALABRAS_EN_ESPANOL = re.compile(
    r"\b(ENTREGADO|ENTREGA|ENTREGAS|PENDIENTE|TALLER|FOTO|INGRESO|SALIDA|OBSERVACIONES|CLIENTE|FIRMA|FIRMAS|FECHA|MOTORES|"
    r"DESPACHADOS|PARCIAL|RECIBE|RECEPCI\u00d3N|DESCRIPCI\u00d3N|MANTENIMIENTO|INSPECCIONADO|ESTADO|TRANSPORTISTA|DOCUMENTO|AUN|A\u00daN)\b",
    re.I,
)


def test_todo_el_texto_fijo_de_los_pdf_esta_en_ingles(c):
    pytest.importorskip("pypdf")
    assert PALABRAS_EN_ESPANOL.search("ENTREGADO TOTAL") and not PALABRAS_EN_ESPANOL.search("DELIVERED")
    datos = dict(company_name="acme", dropoff_name="john miller", received_name="marino trejos")
    o = _orden(c, n=3, motores=[{"make": "tirak", "model": "xe 500p", "serial_number": f"s{i}", "foto_ingreso_url": IMG} for i in range(3)], **datos).json()
    # En taller, parcial y total
    assert not PALABRAS_EN_ESPANOL.search(_texto_pdf(c, o["pdf_ingreso_url"]))
    r = _despacho(c, o, o["motores"][:1], recibe_cliente_name="ann lee").json()
    texto = _texto_pdf(c, r["pdf_salida_url"])
    assert not PALABRAS_EN_ESPANOL.search(texto) and "PARTIALLY DELIVERED" in texto and "PENDING IN SHOP" in texto
    r = _despacho(c, o, o["motores"][1:], recibe_cliente_name="ann lee").json()
    texto = _texto_pdf(c, r["pdf_salida_url"])
    assert not PALABRAS_EN_ESPANOL.search(texto) and "FULLY DELIVERED" in texto
    cert = _certificado(c, o["motores"][0]["id"]).json()
    assert not PALABRAS_EN_ESPANOL.search(_texto_pdf(c, cert["pdf_certificado_url"]))


def test_el_pdf_conserva_las_firmas_de_cada_entrega(c):
    pytest.importorskip("pypdf")
    o = _orden(c, n=2).json()
    _despacho(c, o, o["motores"][:1], recibe_cliente_name="primero", fecha_salida="2026-11-06T10:00:00")
    r = _despacho(c, o, o["motores"][1:], recibe_cliente_name="segundo", fecha_salida="2026-11-07T11:00:00").json()
    texto = _texto_pdf(c, r["pdf_salida_url"])
    assert "DISPATCH 1 OF 2" in texto and "DISPATCH 2 OF 2" in texto
    assert "PRIMERO" in texto and "SEGUNDO" in texto
    assert "2026-11-06 10:00" in texto and "2026-11-07 11:00" in texto


def test_el_certificado_imprime_el_tecnico_registrado(c):
    pytest.importorskip("pypdf")
    m = _orden(c, n=1).json()["motores"][0]
    cert = _certificado(c, m["id"], certified_by="Ana Perez | Cert#ABC123").json()
    texto = _texto_pdf(c, cert["pdf_certificado_url"])
    assert "Ana Perez" in texto and "CERT#ABC123" in texto
    assert "Marino Trejos\n" not in texto and "061821" not in texto


def test_fechas_y_numeros_coherentes(c):
    o = _orden(c, n=1).json()
    m = o["motores"][0]
    # Certificado: el próximo servicio va después de la prueba
    assert _certificado(c, m["id"], test_date="2026-11-05T00:00:00", next_service="2026-11-05T00:00:00").status_code == 400
    # Salida antes del ingreso
    assert _despacho(c, o, o["motores"], fecha_salida="2026-11-01T08:00:00").status_code == 400
    assert c.get(f"/api/motores/orders/{o['id']}").json()["estado_orden"] == "En Taller"
    # Número oficial repetido: se rechaza; el automático salta los ocupados
    assert _certificado(c, m["id"], test_certificate_no="10010002").status_code == 200
    assert _certificado(c, m["id"], test_certificate_no="10010002").status_code == 400
    assert _certificado(c, m["id"]).json()["test_certificate_no"] == "10010003"
    # Un número manual no deja hueco en el consecutivo
    assert _certificado(c, m["id"], test_certificate_no="QA-500").status_code == 200
    assert _certificado(c, m["id"]).json()["test_certificate_no"] == "10010004"


def test_sin_enviar_un_punto_de_seguridad_no_queda_aprobado(c):
    m = _orden(c, n=1).json()["motores"][0]
    cert = c.post("/api/motores/certificates/", json={"motor_id": m["id"]}).json()
    assert cert["brake_function"] is False and cert["rated_load_test"] is False


def test_numero_de_certificado_no_escribe_fuera_de_su_carpeta(c):
    m = _orden(c, n=1).json()["motores"][0]
    r = _certificado(c, m["id"], test_certificate_no="../../../evil")
    assert r.status_code == 200
    url = r.json()["pdf_certificado_url"]
    assert ".." not in url and "/" not in url.rsplit("/archivos/", 1)[1]
    assert c.get(url).status_code == 200


# ================= MÓDULO D: CLIENTES =================
def test_clientes_crud_sin_duplicados(c):
    r = c.post("/api/motores/clients/", json={"company_name": " acme hoist ", "contacto_principal": "sunny", "email": "a@b.co"})
    assert r.status_code == 200
    cli = r.json()
    assert cli["company_name"] == "ACME HOIST" and cli["contacto_principal"] == "SUNNY"
    assert c.post("/api/motores/clients/", json={"company_name": "Acme Hoist"}).status_code == 400

    otro = c.post("/api/motores/clients/", json={"company_name": "otra", "id": "21"}).json()
    assert otro["id"] == "21"
    assert c.post("/api/motores/clients/", json={"company_name": "mala", "id": "x');alert(1)//"}).status_code == 400
    assert c.put("/api/motores/clients/21", json={"company_name": "ACME HOIST"}).status_code == 400  # renombrar tampoco duplica
    assert c.put("/api/motores/clients/21", json={"phone": "631"}).json()["phone"] == "631"

    assert [x["id"] for x in c.get("/api/motores/clients/", params={"search": "acme"}).json()] == [cli["id"]]
    assert "ACME HOIST" in c.get("/api/motores/motors/common/presets").json()["customers"]
    assert c.delete(f"/api/motores/clients/{cli['id']}").status_code == 200
    assert c.get(f"/api/motores/clients/{cli['id']}").status_code == 404


# ================= MÓDULO E: TRAZABILIDAD =================
def test_presets_con_los_13_modelos(c):
    p = c.get("/api/motores/motors/common/presets").json()
    assert len(p["models"]) == 13 and len(p["model_to_make"]) == 13
    assert p["model_to_make"]["TIRAK XE 500P"] == "Tirak"


def test_buscador_ficha_y_metricas(c):
    o = _orden(c, n=2).json()
    m = o["motores"][0]
    _certificado(c, m["id"])
    _despacho(c, o, [m])

    assert len(c.get("/api/motores/motors/", params={"search": "s-1"}).json()) == 1
    assert len(c.get("/api/motores/motors/", params={"search": o["numero_orden"]}).json()) == 2
    assert len(c.get("/api/motores/motors/", params={"search": "skyline"}).json()) == 2
    assert len(c.get("/api/motores/motors/", params={"estado": "Entregado"}).json()) == 1

    ficha = c.get(f"/api/motores/motors/{m['id']}").json()
    assert ficha["numero_orden"] == o["numero_orden"] and ficha["company_name"] == "SKYLINE SCAFFOLDING"
    assert len(ficha["certificados"]) == 1 and ficha["certificados"][0]["pdf_certificado_url"]

    s = c.get("/api/motores/motors/dashboard/stats").json()
    assert s == {"total_ordenes": 1, "ordenes_en_taller": 1, "ordenes_entregadas": 0,
                 "motores_en_taller": 1, "motores_entregados": 1, "certificados_emitidos": 1}


# ================= ARCHIVOS =================
def test_los_archivos_exigen_sesion_y_no_salen_de_su_carpeta(c):
    o = _orden(c, n=1).json()
    url = o["pdf_ingreso_url"]
    assert c.get(url).status_code == 200
    assert _cliente_http().get(url).status_code == 401
    # No quedan en /static, que es público
    assert _cliente_http().get("/static/generated_pdfs/" + url.rsplit("/", 1)[1]).status_code == 404

    secreto = os.path.join(base.dir_datos(), ".secret_key")
    assert os.path.exists(secreto)
    for malo in ["..%2F.secret_key", ".secret_key", "..%5C.secret_key", "motores_control.db", "..%2Fmotores_control.db"]:
        assert c.get(f"/api/motores/archivos/{malo}").status_code in (404, 405), malo


def test_el_service_worker_no_guarda_datos_de_motores():
    sw = _cliente_http().get("/sw.js").text
    assert "/api/motores/" in sw
    assert sw.index("/api/motores/") < sw.index("Network-First")


def test_qr_de_acceso_movil(c):
    r = c.get("/api/motores/network-qr")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
