import os
import shutil
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Asegurar que el directorio de la aplicación esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import server

# Las pruebas nunca usan la base real (data/inspecciones.db): desde que se carga este archivo, DB_PATH apunta a
# una base temporal de la sesión. Así, una prueba que olvide pedir `test_db` tampoco escribe en los datos locales.
_BASE_REAL = os.path.abspath(database.DB_PATH)
_CARPETA_SESION = tempfile.mkdtemp(prefix="tireanalyze_pruebas_")
database.DB_PATH = os.path.join(_CARPETA_SESION, "sesion.db")


@pytest.fixture(scope="session", autouse=True)
def base_de_la_sesion():
    database.inicializar_bd()
    yield
    shutil.rmtree(_CARPETA_SESION, ignore_errors=True)


@pytest.fixture(autouse=True)
def nunca_la_base_real():
    """Falla si alguna prueba (o fixture) dejó DB_PATH apuntando a la base real."""
    assert os.path.abspath(database.DB_PATH) != _BASE_REAL, "La prueba apunta a data/inspecciones.db"
    yield
    assert os.path.abspath(database.DB_PATH) != _BASE_REAL, "La prueba dejó DB_PATH en data/inspecciones.db"


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """
    Las pruebas usan fechas fijas (p. ej. noviembre 2026). Se fija "hoy" al 31/12/2027 para que
    el candado de fechas futuras no dependa del día en que se ejecuta la suite.
    """
    from datetime import date
    monkeypatch.setattr(database, "_hoy_bogota", lambda: date(2027, 12, 31))


@pytest.fixture(autouse=True)
def cifrado_rapido(monkeypatch):
    """Producción cifra las claves con 600.000 iteraciones (~0,4 s por clave); en pruebas bastan 1.000."""
    monkeypatch.setattr(database, "PBKDF2_ITERACIONES", 1_000)


@pytest.fixture
def test_db(tmp_path):
    """Base SQLite nueva y vacía para cada prueba que la pide; al terminar DB_PATH vuelve a la base de la sesión."""
    original_db = database.DB_PATH
    database.DB_PATH = str(tmp_path / "prueba.db")
    database.inicializar_bd()
    yield database.DB_PATH
    database.DB_PATH = original_db


@pytest.fixture
def admin_token(test_db):
    return server.crear_token_acceso("admin", "admin")


@pytest.fixture
def inspector_token(test_db):
    # Un usuario que no es administrador necesita al menos un cliente asignado para ver datos
    with database.get_connection() as conn:
        conn.execute("UPDATE usuarios SET cliente_asignado = 'FLOTA TEST' WHERE username = 'inspector1'")
        conn.commit()
    return server.crear_token_acceso("inspector1", "inspector")


@pytest.fixture
def auth_client(admin_token):
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {admin_token}"})
    return c
