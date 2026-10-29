"""
Seguridad del ingreso (paquetes 1 y 2 de la revisión del login):
bloqueo por usuario e IP real, sesiones que se pueden cerrar, clave secreta sin valor fijo,
mismo tiempo con usuario inexistente, cookie solo HTTPS, reglas de clave, cifrado más fuerte,
cambio de clave propio (y obligatorio) y registro de ingresos.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import pytest
from fastapi.testclient import TestClient

import database
import server

CLAVE = "Llantas-Seguras-26"


@pytest.fixture(autouse=True)
def sin_intentos_previos():
    server._login_attempts.clear()
    yield
    server._login_attempts.clear()


def _crear(username, clave=CLAVE, rol="inspector", cliente="FLOTA PRUEBAS"):
    assert database.crear_usuario(username, clave, username.title(), rol, cliente, "patio,diagnostico")


def _login(c, username, clave=CLAVE, ip=None, **cabeceras):
    if ip:
        cabeceras["X-Real-IP"] = ip
    return c.post("/api/login", json={"username": username, "password": clave}, headers=cabeceras)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- Paquete 1 -----------------------------------------------------------------------------------

def test_bloqueo_por_usuario_aunque_cambie_la_ip(test_db):
    c = TestClient(server.app)
    _crear("victima")
    for i in range(server.MAX_FALLOS_USUARIO):
        assert _login(c, "victima", f"mala-{i}", ip=f"10.0.0.{i}").status_code == 401
    # Ni con la clave correcta ni desde otra IP: la cuenta queda frenada 15 minutos
    r = _login(c, "victima", ip="10.9.9.9")
    assert r.status_code == 429
    assert "este usuario" in r.json()["detail"]
    # Otra cuenta no se ve afectada
    _crear("otra_cuenta")
    assert _login(c, "otra_cuenta", ip="10.9.9.9").status_code == 200


def test_bloqueo_por_usuario_tambien_para_usuarios_inexistentes(test_db):
    """El bloqueo no revela si el usuario existe: aplica igual a nombres que no están en la base."""
    c = TestClient(server.app)
    for i in range(server.MAX_FALLOS_USUARIO):
        assert _login(c, "no_existe_nadie", f"x-{i}", ip=f"10.1.0.{i}").status_code == 401
    assert _login(c, "no_existe_nadie", "x", ip="10.1.9.9").status_code == 429


def test_un_ingreso_exitoso_reinicia_el_conteo_por_usuario(test_db):
    c = TestClient(server.app)
    _crear("olvidadizo")
    for i in range(server.MAX_FALLOS_USUARIO - 1):
        _login(c, "olvidadizo", f"mala-{i}", ip=f"10.2.0.{i}")
    assert _login(c, "olvidadizo", ip="10.2.1.1").status_code == 200
    assert database.fallos_recientes_usuario("olvidadizo", server.VENTANA_FALLOS_USUARIO) == 0


def test_bloqueo_por_ip_usa_la_ip_real_del_usuario(test_db):
    """Detrás del proxy de Railway, la IP sale de X-Real-IP: un usuario no bloquea a los demás."""
    c = TestClient(server.app)
    for i in range(server.MAX_FALLOS_IP):
        assert _login(c, f"probando{i}", "x", ip="200.1.1.1").status_code == 401
    assert _login(c, "probando_mas", "x", ip="200.1.1.1").status_code == 429
    _crear("vecino")
    assert _login(c, "vecino", ip="200.2.2.2").status_code == 200


def test_ip_desde_x_forwarded_for_toma_la_ultima_entrada(test_db):
    c = TestClient(server.app)
    for i in range(server.MAX_FALLOS_IP):
        _login(c, f"xff{i}", "x", **{"X-Forwarded-For": f"1.2.3.{i}, 190.5.5.5"})
    # Lo que escribe el atacante a la izquierda cambia, pero la IP que puso el proxy (derecha) es la misma
    assert _login(c, "xff_otro", "x", **{"X-Forwarded-For": "9.9.9.9, 190.5.5.5"}).status_code == 429


def test_salir_cierra_la_sesion_aunque_se_haya_copiado_el_token(test_db):
    c = TestClient(server.app)
    _crear("salidor")
    token = _login(c, "salidor").json()["token"]
    assert c.get("/api/usuario-actual", headers=_auth(token)).status_code == 200
    assert c.post("/api/logout", headers=_auth(token)).status_code == 200
    assert TestClient(server.app).get("/api/usuario-actual", headers=_auth(token)).status_code == 401


def test_sesiones_anteriores_al_cambio_siguen_sirviendo(test_db):
    """Los tokens emitidos antes de este cambio (sin 'ver' ni 'jti') siguen válidos: nadie queda afuera al desplegar."""
    _crear("antiguo")
    payload = {"sub": "antiguo", "rol": "inspector", "exp": int(time.time()) + 3600}
    b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    firma = hmac.new(server.SECRET_KEY.encode(), b64.encode(), hashlib.sha256).hexdigest()
    r = TestClient(server.app).get("/api/usuario-actual", headers=_auth(f"{b64}.{firma}"))
    assert r.status_code == 200


def test_clave_secreta_sin_valor_fijo_si_no_se_puede_guardar(monkeypatch):
    monkeypatch.delenv("TIREANALYZE_SECRET_KEY", raising=False)
    monkeypatch.delenv("TIRECHECK_SECRET_KEY", raising=False)
    monkeypatch.setattr(server.os.path, "exists", lambda _: False)

    def falla(*a, **k):
        raise PermissionError("disco de solo lectura")

    monkeypatch.setattr(server.os, "makedirs", falla)
    k1, k2 = server._obtener_o_crear_secret_key(), server._obtener_o_crear_secret_key()
    assert len(k1) == 64 and k1 != k2
    assert "fallback" not in k1


def test_usuario_inexistente_gasta_lo_mismo_que_uno_real(test_db, monkeypatch):
    llamadas = []
    monkeypatch.setattr(database, "verificar_clave_ficticia", lambda p: llamadas.append(p))
    assert database.autenticar_usuario("fantasma_total", "alguna-clave") is None
    assert llamadas == ["alguna-clave"]


def test_cookie_solo_https_cuando_la_conexion_es_https(test_db):
    c = TestClient(server.app)
    _crear("galletas")
    r_https = _login(c, "galletas", ip="10.3.0.1", **{"X-Forwarded-Proto": "https"})
    assert "secure" in r_https.headers["set-cookie"].lower()
    r_http = _login(c, "galletas", ip="10.3.0.2")
    assert "secure" not in r_http.headers["set-cookie"].lower()


def test_pantalla_no_sugiere_usuarios_de_ejemplo():
    with open(os.path.join(os.path.dirname(server.__file__), "templates", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "admin o inspector1" not in html


# --- Paquete 2 -----------------------------------------------------------------------------------

@pytest.mark.parametrize("clave, valida", [
    ("1234", False), ("12345678", False), ("admin123", False), ("Password123", False),
    ("aaaaaaaa", False), ("34567890", False), ("juanperez", False),
    ("Llantas-Seguras-26", True), ("ruta 45 Bogotá", True), ("87h!kq2Z", True),
])
def test_reglas_de_clave_nueva(clave, valida):
    assert (database.validar_clave_nueva(clave, "juanperez") is None) == valida


def test_cifrado_nuevo_formato_e_iteraciones_de_produccion():
    assert database.PBKDF2_ITERACIONES_PRODUCCION >= 600_000
    h = database.hash_password("x")
    _, iteraciones, salt, digest = h.split("$")
    assert int(iteraciones) == database.PBKDF2_ITERACIONES and len(salt) == 32 and len(digest) == 64
    assert database.verify_password("x", h) and not database.verify_password("y", h)


def test_clave_con_formato_antiguo_entra_y_se_vuelve_a_cifrar(test_db, monkeypatch):
    # Como en producción: las iteraciones actuales superan las 100.000 del formato antiguo
    monkeypatch.setattr(database, "PBKDF2_ITERACIONES", 200_000)
    salt = secrets.token_hex(16)
    antiguo = "pbkdf2_sha256${}${}".format(
        salt, hashlib.pbkdf2_hmac("sha256", CLAVE.encode(), salt.encode(), 100_000).hex())
    _crear("veterano")
    with database.get_connection() as conn:
        conn.execute("UPDATE usuarios SET password = ? WHERE username = 'veterano'", (antiguo,))
        conn.commit()
    assert database.autenticar_usuario("veterano", CLAVE) is not None
    with database.get_connection() as conn:
        nuevo = conn.execute("SELECT password FROM usuarios WHERE username = 'veterano'").fetchone()[0]
    assert nuevo.split("$")[1] == str(database.PBKDF2_ITERACIONES)
    assert database.autenticar_usuario("veterano", CLAVE) is not None


def test_clave_debil_actual_obliga_a_cambiarla(test_db):
    c = TestClient(server.app)
    _crear("debil", clave="12345")
    r = _login(c, "debil", "12345")
    assert r.status_code == 200 and r.json()["usuario"]["debe_cambiar_clave"] is True
    token = r.json()["token"]
    # Mientras no la cambie, la app no le entrega datos (y le avisa al navegador por qué)
    r_datos = c.get("/api/inspecciones", headers=_auth(token))
    assert r_datos.status_code == 403
    assert r_datos.headers.get("X-Requiere-Cambio-Clave") == "1"
    assert c.get("/api/usuario-actual", headers=_auth(token)).status_code == 200


def test_cambio_de_clave_propio(test_db):
    c = TestClient(server.app)
    _crear("cambiador", clave="12345")
    token = _login(c, "cambiador", "12345").json()["token"]
    url = "/api/mi-cuenta/cambiar-clave"
    assert c.post(url, json={"clave_actual": "mala", "clave_nueva": CLAVE}, headers=_auth(token)).status_code == 400
    assert c.post(url, json={"clave_actual": "12345", "clave_nueva": "12345678"}, headers=_auth(token)).status_code == 400

    r = c.post(url, json={"clave_actual": "12345", "clave_nueva": CLAVE}, headers=_auth(token))
    assert r.status_code == 200
    nuevo = r.json()["token"]
    assert r.json()["usuario"]["debe_cambiar_clave"] is False
    assert "sesion_version" not in r.json()["usuario"]
    # La sesión vieja quedó cerrada; la nueva entra a los datos
    assert TestClient(server.app).get("/api/usuario-actual", headers=_auth(token)).status_code == 401
    assert TestClient(server.app).get("/api/inspecciones", headers=_auth(nuevo)).status_code == 200
    assert _login(TestClient(server.app), "cambiador", "12345", ip="10.4.0.1").status_code == 401
    assert _login(TestClient(server.app), "cambiador", CLAVE, ip="10.4.0.2").status_code == 200


def test_restablecer_clave_cierra_sesiones_y_exige_cambio(test_db, auth_client):
    c = TestClient(server.app)
    _crear("reseteado")
    token_viejo = _login(c, "reseteado").json()["token"]
    r = auth_client.post("/api/usuarios/reseteado/reset-password", json={"nueva_password": "Temporal-Flota-77"})
    assert r.status_code == 200
    assert TestClient(server.app).get("/api/usuario-actual", headers=_auth(token_viejo)).status_code == 401
    r_login = _login(TestClient(server.app), "reseteado", "Temporal-Flota-77", ip="10.5.0.1")
    assert r_login.json()["usuario"]["debe_cambiar_clave"] is True
    # Y una clave débil no se acepta al restablecer
    assert auth_client.post("/api/usuarios/reseteado/reset-password", json={"nueva_password": "1234"}).status_code == 400


def test_usuario_creado_por_el_admin_cambia_la_clave_al_ingresar(test_db, auth_client):
    base = {"nombre_completo": "Nuevo", "rol": "inspector", "cliente_asignado": "FLOTA PRUEBAS"}
    r_debil = auth_client.post("/api/usuarios", json={**base, "username": "nuevo1", "password": "password123"})
    assert r_debil.status_code == 400 and "más usadas" in r_debil.json()["detail"]
    assert auth_client.post("/api/usuarios", json={**base, "username": "nuevo1", "password": "Inicio-Flota-26"}).status_code == 200
    r = _login(TestClient(server.app), "nuevo1", "Inicio-Flota-26")
    assert r.json()["usuario"]["debe_cambiar_clave"] is True


def test_cerrar_sesion_en_los_demas_equipos(test_db):
    _crear("viajero")
    token_a = _login(TestClient(server.app), "viajero", ip="10.6.0.1").json()["token"]
    token_b = _login(TestClient(server.app), "viajero", ip="10.6.0.2").json()["token"]
    r = TestClient(server.app).post("/api/mi-cuenta/cerrar-otras-sesiones", headers=_auth(token_a))
    assert r.status_code == 200
    assert TestClient(server.app).get("/api/usuario-actual", headers=_auth(token_b)).status_code == 401
    assert TestClient(server.app).get("/api/usuario-actual", headers=_auth(r.json()["token"])).status_code == 200


def test_registro_de_ingresos_en_la_lista_de_usuarios(test_db, auth_client):
    c = TestClient(server.app)
    _crear("registrado")
    _login(c, "registrado", "mala", ip="10.7.0.1")
    _login(c, "registrado", "mala-2", ip="10.7.0.1")
    _login(c, "registrado", ip="10.7.0.1")
    u = next(x for x in auth_client.get("/api/usuarios").json() if x["username"] == "registrado")
    assert u["ultimo_ingreso"] and len(u["ultimo_ingreso"]) == 16  # 'AAAA-MM-DD HH:MM' hora de Bogotá
    assert u["fallos_24h"] == 2
    with database.get_connection() as conn:
        filas = conn.execute("SELECT ip, exito, motivo FROM registro_ingresos WHERE username = 'registrado' ORDER BY id").fetchall()
    assert filas == [("10.7.0.1", 0, "clave_incorrecta"), ("10.7.0.1", 0, "clave_incorrecta"), ("10.7.0.1", 1, "")]


def test_pantalla_tiene_cambio_de_clave():
    with open(os.path.join(os.path.dirname(server.__file__), "templates", "index.html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(os.path.dirname(server.__file__), "static", "js", "app_core.js"), encoding="utf-8") as f:
        js = f.read()
    for id_ in ('id="modalMiCuenta"', 'id="btnMiCuenta"', 'autocomplete="current-password"', 'autocomplete="new-password"'):
        assert id_ in html
    for fn in ("function abrirModalMiCuenta(", "async function guardarCambioClave(", "X-Requiere-Cambio-Clave"):
        assert fn in js
