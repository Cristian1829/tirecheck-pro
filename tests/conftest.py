import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Asegurar que el directorio de la aplicación esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import server


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """
    Las pruebas usan fechas fijas (p. ej. noviembre 2026). Se fija "hoy" al 31/12/2027 para que
    el candado de fechas futuras no dependa del día en que se ejecuta la suite.
    """
    from datetime import date
    monkeypatch.setattr(database, "_hoy_bogota", lambda: date(2027, 12, 31))


@pytest.fixture
def test_db():
    """
    Fixture que crea una base de datos SQLite temporal y redirige database.DB_PATH
    para evitar modificar la base de datos de producción durante las pruebas.
    """
    original_db = database.DB_PATH
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    database.DB_PATH = temp_db_path
    database.inicializar_bd()
    
    yield temp_db_path
    
    database.DB_PATH = original_db
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass

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
