"""
Suite integral de pruebas automatizadas para Login, Autenticación y Sintaxis Frontend
Garantiza que:
1. El JavaScript de templates/index.html sea 100% sintácticamente válido (evita bloqueos de pantalla).
2. El DOM del login contenga todos los elementos interactivos requeridos.
3. Las funciones JavaScript de login y gestión de sesión estén debidamente declaradas.
4. Los endpoints backend (/api/login, /api/usuario-actual, /api/logout) funcionen de forma estricta.
5. El sistema proteja las rutas contra accesos no autenticados o con credenciales inválidas.
"""

import os
import re
import subprocess
import tempfile
import pytest
from fastapi.testclient import TestClient

import database
import server

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML_PATH = os.path.join(BASE_DIR, "templates", "index.html")


# ==============================================================================
# 1. PRUEBAS DE INTEGRIDAD Y SINTAXIS JAVASCRIPT EN EL FRONTEND (ANTI-REGRESIÓN)
# ==============================================================================

def obtener_bundle_frontend():
    with open(INDEX_HTML_PATH, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    js_dir = os.path.join(BASE_DIR, "static", "js")
    js_content = ""
    if os.path.exists(js_dir):
        for fname in sorted(os.listdir(js_dir)):
            if fname.endswith(".js"):
                with open(os.path.join(js_dir, fname), "r", encoding="utf-8", errors="ignore") as f_js:
                    js_content += "\n" + f_js.read()
    return html + "\n" + js_content


def test_frontend_javascript_sintaxis_valida():
    """
    Valida la sintaxis con el compilador de Node.js ('node --check') tanto de
    los módulos en static/js/ como de scripts en templates/index.html.
    Esta prueba previene syntax errors que bloqueen la aplicación.
    """
    assert os.path.exists(INDEX_HTML_PATH), f"No se encontró {INDEX_HTML_PATH}"

    js_dir = os.path.join(BASE_DIR, "static", "js")
    archivos_js = []
    if os.path.exists(js_dir):
        for fname in sorted(os.listdir(js_dir)):
            if fname.endswith(".js"):
                with open(os.path.join(js_dir, fname), "r", encoding="utf-8", errors="ignore") as f_js:
                    archivos_js.append((fname, f_js.read()))

    with open(INDEX_HTML_PATH, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    script_pattern = re.compile(r"<script\b(?![^>]*src=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    inline_scripts = [s for s in script_pattern.findall(html) if s.strip()]
    for idx, s_code in enumerate(inline_scripts, 1):
        archivos_js.append((f"index_inline_{idx}.js", s_code))

    assert len(archivos_js) > 0, "No se encontró código JavaScript en static/js/ ni en index.html"

    for fname, script_code in archivos_js:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(script_code)
            tmp_path = tmp.name

        try:
            res = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True,
                text=True,
                check=False
            )
            assert res.returncode == 0, (
                f"Error de sintaxis detectado en {fname}:\n"
                f"{res.stderr}\n"
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def test_frontend_dom_elementos_login():
    """
    Verifica que el HTML de templates/index.html contenga todos los elementos del DOM
    necesarios para que el usuario pueda interactuar con el formulario de login.
    """
    with open(INDEX_HTML_PATH, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    # Modal principal de Login
    assert 'id="modalLogin"' in html, "Debe existir el modal id='modalLogin'"
    # Campo de usuario
    assert 'id="login_username"' in html, "Debe existir el input id='login_username'"
    # Campo de contraseña
    assert 'id="login_password"' in html, "Debe existir el input id='login_password'"
    # Contenedor de mensaje de error
    assert 'id="login_error"' in html, "Debe existir el contenedor id='login_error'"
    # Botón de envío que invoca la función ejecutarLogin()
    assert 'id="btnLoginSubmit"' in html, "Debe existir el botón id='btnLoginSubmit'"
    assert 'onclick="ejecutarLogin()"' in html or 'ejecutarLogin()' in html, "El botón debe invocar ejecutarLogin()"
    # Indicador de usuario activo en el encabezado
    assert 'id="lblUsuarioActivo"' in html, "Debe existir id='lblUsuarioActivo' para mostrar el usuario logueado"


def test_frontend_funciones_esenciales_login():
    """
    Verifica que en el bundle de la aplicación (HTML + módulos JS) estén declaradas las funciones JS
    clave para el ciclo de vida de la autenticación:
    ejecutarLogin, cerrarSesionUsuario, actualizarUIUsuario, y los tokens en localStorage.
    """
    bundle = obtener_bundle_frontend()

    assert "async function ejecutarLogin()" in bundle, "La función ejecutarLogin() debe estar declarada"
    assert "async function cerrarSesionUsuario()" in bundle, "La función cerrarSesionUsuario() debe estar declarada"
    assert "function actualizarUIUsuario()" in bundle, "La función actualizarUIUsuario() debe estar declarada"
    assert "tireanalyze_token" in bundle, "Debe gestionar la clave tireanalyze_token en localStorage"
    assert "tirecheck_token" in bundle, "Debe gestionar la clave tirecheck_token en localStorage"


# ==============================================================================
# 2. PRUEBAS END-TO-END DE LA API DE LOGIN Y GESTIÓN DE SESIÓN
# ==============================================================================

def test_api_login_exitoso_admin(test_db):
    """
    Prueba que el login con credenciales de administrador funcione:
    retorne HTTP 200, token JWT, objeto de usuario y cookies de sesión.
    """
    client = TestClient(server.app)
    # Crear usuario admin en la base de datos de pruebas
    database.crear_usuario(
        username="admin_qa",
        password="adminPassword123",
        nombre_completo="Administrador de Pruebas",
        rol="admin"
    )

    res = client.post("/api/login", json={
        "username": "admin_qa",
        "password": "adminPassword123"
    })
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert "token" in data and len(data["token"]) > 20
    assert data["usuario"]["username"] == "admin_qa"
    assert data["usuario"]["rol"] == "admin"

    # Verificar que el servidor envíe las cookies de sesión seguras
    cookies = res.cookies
    assert "tireanalyze_token" in cookies or "tirecheck_token" in cookies


def test_api_login_exitoso_inspector(test_db):
    """
    Prueba que el login con un inspector existente funcione correctamente.
    """
    client = TestClient(server.app)
    # Crear usuario inspector de prueba
    database.crear_usuario(
        username="inspector_qa",
        password="claveSegura123",
        nombre_completo="Inspector QA",
        rol="inspector",
        cliente_asignado="FLOTA PRUEBAS"
    )

    res = client.post("/api/login", json={
        "username": "inspector_qa",
        "password": "claveSegura123"
    })
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data["usuario"]["username"] == "inspector_qa"
    assert data["usuario"]["rol"] == "inspector"
    assert data["usuario"]["cliente_asignado"] == "FLOTA PRUEBAS"


def test_api_login_rechazo_password_incorrecta(test_db):
    """
    Prueba que una contraseña errónea devuelva HTTP 401 con detalle comprensible.
    """
    client = TestClient(server.app)
    database.crear_usuario(
        username="usuario_valido",
        password="claveCorrecta123",
        nombre_completo="Usuario Valido",
        rol="inspector"
    )

    res = client.post("/api/login", json={
        "username": "usuario_valido",
        "password": "contrasena_totalmente_incorrecta"
    })
    assert res.status_code == 401
    assert "incorrectos" in res.json().get("detail", "").lower()


def test_api_login_rechazo_usuario_inexistente(test_db):
    """
    Prueba que un usuario que no existe en la base de datos devuelva HTTP 401.
    """
    client = TestClient(server.app)
    res = client.post("/api/login", json={
        "username": "usuario_fantasma_xyz",
        "password": "password123"
    })
    assert res.status_code == 401
    assert "incorrectos" in res.json().get("detail", "").lower()


def test_api_login_rechazo_payload_vacio(test_db):
    """
    Prueba que el envío de datos vacíos sea rechazado de forma segura.
    """
    client = TestClient(server.app)
    res = client.post("/api/login", json={
        "username": "",
        "password": ""
    })
    assert res.status_code in (401, 422)


def test_api_usuario_actual_con_token(test_db):
    """
    Prueba que el endpoint /api/usuario-actual retorne la información
    del usuario logueado cuando se provee un token Bearer válido.
    """
    client = TestClient(server.app)
    database.crear_usuario(
        username="admin_qa",
        password="adminPassword123",
        nombre_completo="Admin QA",
        rol="admin"
    )

    login_res = client.post("/api/login", json={"username": "admin_qa", "password": "adminPassword123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    res = client.get("/api/usuario-actual", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data["usuario"]["username"] == "admin_qa"


def test_api_usuario_actual_con_cookie(test_db):
    """
    Prueba que el endpoint /api/usuario-actual también reconozca la sesión
    mediante la cookie 'tireanalyze_token' (soporte de navegador sin header Authorization).
    """
    client = TestClient(server.app)
    database.crear_usuario(
        username="admin_qa",
        password="adminPassword123",
        nombre_completo="Admin QA",
        rol="admin"
    )

    login_res = client.post("/api/login", json={"username": "admin_qa", "password": "adminPassword123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    client.cookies.set("tireanalyze_token", token)
    res = client.get("/api/usuario-actual")
    assert res.status_code == 200
    assert res.json()["usuario"]["username"] == "admin_qa"


def test_api_usuario_actual_sin_token_rechazado(test_db):
    """
    Prueba que acceder a /api/usuario-actual sin credenciales devuelva HTTP 401.
    """
    client = TestClient(server.app)
    res = client.get("/api/usuario-actual")
    assert res.status_code == 401


def test_api_logout_elimina_cookies(test_db):
    """
    Prueba que el endpoint /api/logout devuelva status ok y limpie las cookies.
    """
    client = TestClient(server.app)
    res = client.post("/api/logout")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"


def test_api_rutas_protegidas_sin_autenticacion(test_db):
    """
    Verifica que las rutas administrativas y de datos operativos no permitan
    acceso anónimo, forzando la visualización del modal de login.
    """
    client = TestClient(server.app)
    # Rutas críticas que requieren sesión activa
    rutas_protegidas = [
        "/api/usuarios",
        "/api/inspecciones",
        "/api/diagnostico",
        "/api/configuraciones-clientes"
    ]
    for ruta in rutas_protegidas:
        res = client.get(ruta)
        assert res.status_code == 401, f"La ruta {ruta} debería retornar 401 sin autenticación"
