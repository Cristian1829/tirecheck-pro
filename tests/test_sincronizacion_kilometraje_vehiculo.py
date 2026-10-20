import pytest
import subprocess
import os
import re
import uuid
from datetime import date
from fastapi.testclient import TestClient
import database
from server import app, crear_token_acceso

client = TestClient(app)

@pytest.fixture(autouse=True)
def preparar_bd_pruebas():
    database.inicializar_bd()
    yield

def test_sincronizacion_kilometraje_insertar_inspecciones_misma_jornada():
    """
    Si en una inspección para un vehículo se ingresa un kilometraje en una llanta,
    todas las demás llantas de esa misma inspección deben quedar con el mismo kilometraje.
    """
    placa = f"K{uuid.uuid4().hex[:5].upper()}"
    fecha = "2026-10-20"
    
    # 1. Registrar posición 1 con kilometraje 45000
    insp1 = {
        "fecha": fecha,
        "cliente": "FLOTA TEST KM",
        "subcliente": "Sede Central",
        "tipo_operacion": "CARGA",
        "placa": placa,
        "posicion": 1,
        "kilometraje": 45000,
        "tipologia": "CABEZOTE (6X4)",
        "marca": "MICHELIN",
        "diseno": "X MULTI",
        "dimension": "295/80R22.5",
        "prof_inicial": 16.0,
        "prof_ext": 14.0,
        "prof_cent": 14.0,
        "prof_int": 14.0,
        "psi": 110,
        "vida": "Original"
    }
    id1 = database.insertar_inspeccion(insp1)
    assert id1 > 0

    # 2. Registrar posición 2 con kilometraje 0 (no digitado nuevamente)
    insp2 = dict(insp1)
    insp2["posicion"] = 2
    insp2["kilometraje"] = 0
    id2 = database.insertar_inspeccion(insp2)
    assert id2 > 0

    # Verificar que posición 2 haya heredado automáticamente los 45000 km
    with database.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT kilometraje FROM inspecciones WHERE id = ?", (id2,))
        km2 = c.fetchone()[0]
        assert km2 == 45000, f"Se esperaba 45000 pero se obtuvo {km2}"

    # 3. Si se registra la posición 3 corrigiendo el kilometraje a 45500:
    insp3 = dict(insp1)
    insp3["posicion"] = 3
    insp3["kilometraje"] = 45500
    id3 = database.insertar_inspeccion(insp3)
    assert id3 > 0

    # Todas las llantas de esa inspección deben quedar con 45500
    with database.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT posicion, kilometraje FROM inspecciones WHERE UPPER(TRIM(placa)) = ? AND SUBSTR(fecha, 1, 10) = ?", (placa, fecha))
        filas = c.fetchall()
        assert len(filas) == 3
        for pos, km in filas:
            assert km == 45500, f"La posición {pos} tiene kilometraje {km}, se esperaba 45500"

def test_sincronizacion_kilometraje_actualizar_inspeccion():
    """
    Al actualizar el kilometraje de una llanta en la Base Central,
    todas las demás llantas de esa misma inspección deben actualizarse con ese kilometraje.
    """
    placa = f"K{uuid.uuid4().hex[:5].upper()}"
    fecha = "2026-10-20"
    
    inspA = {
        "fecha": fecha,
        "cliente": "FLOTA TEST KM",
        "subcliente": "Sede Central",
        "tipo_operacion": "CARGA",
        "placa": placa,
        "posicion": 1,
        "kilometraje": 30000,
        "tipologia": "CABEZOTE (6X4)",
        "marca": "GOODYEAR",
        "diseno": "KMAX S",
        "dimension": "295/80R22.5",
        "prof_inicial": 16.0,
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0,
        "psi": 105,
        "vida": "Original"
    }
    idA = database.insertar_inspeccion(inspA)
    inspB = dict(inspA)
    inspB["posicion"] = 2
    idB = database.insertar_inspeccion(inspB)

    # Actualizar la llanta 1 cambiando el kilometraje a 32000
    datos_act = dict(inspA)
    datos_act["kilometraje"] = 32000
    ok = database.actualizar_inspeccion(idA, datos_act)
    assert ok is True

    # Verificar que tanto la llanta 1 como la llanta 2 tengan 32000 km
    with database.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT posicion, kilometraje FROM inspecciones WHERE id IN (?, ?)", (idA, idB))
        filas = dict(c.fetchall())
        assert filas[1] == 32000
        assert filas[2] == 32000

def test_obtener_ultima_inspeccion_posicion_unifica_kilometraje():
    """
    Verifica que obtener_ultima_inspeccion_posicion devuelva el kilometraje de la jornada
    incluso si alguna posición quedó con 0 en la BD histórica.
    """
    placa = f"K{uuid.uuid4().hex[:5].upper()}"
    fecha = "2026-10-20"
    
    with database.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO inspecciones (fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje, tipologia, marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int, psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro)
            VALUES (?, 'CLI', 'SUB', 'CARGA', ?, 1, 60000, 'CABEZOTE', 'MICHELIN', 'X', '295/80R22.5', 'ORIGINAL', '', 10, 10, 10, 100, '', 0, 16, 0, 'LL-01', 'ADMIN')
        """, (fecha, placa))
        c.execute("""
            INSERT INTO inspecciones (fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje, tipologia, marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int, psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro)
            VALUES (?, 'CLI', 'SUB', 'CARGA', ?, 2, 0, 'CABEZOTE', 'MICHELIN', 'X', '295/80R22.5', 'ORIGINAL', '', 10, 10, 10, 100, '', 0, 16, 0, 'LL-02', 'ADMIN')
        """, (fecha, placa))
        conn.commit()

    pos2 = database.obtener_ultima_inspeccion_posicion(placa, 2)
    assert pos2 is not None
    assert pos2["kilometraje"] == 60000

def test_frontend_sincronizacion_kilometraje_dom_y_js():
    """Valida la presencia de la sincronización de kilometraje en index.html y ausencia de errores de sintaxis."""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "kilometrajeInspeccionActual" in html
    assert "alCambiarKilometrajeInput()" in html
    assert 'oninput="alCambiarKilometrajeInput();"' in html

    # Validar sintaxis JS con Node.js
    scripts = re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', html, re.DOTALL)
    assert len(scripts) > 0
    codigo_js = "\n".join(scripts)
    res = subprocess.run(
        ["node", "--check"],
        input=codigo_js,
        text=True,
        encoding="utf-8",
        capture_output=True
    )
    assert res.returncode == 0, f"Error de sintaxis JavaScript: {res.stderr}"

def test_boton_limpiador_y_unico_boton_copiar_marca_diseno():
    """Valida que el limpiador ejecute limpiarTodoParaNuevaInspeccion() y que exista un único botón de copiar marca/diseño."""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. El botón de borrador en el formulario debe limpiar TODO para una nueva inspección y ser diciente
    assert 'onclick="limpiarTodoParaNuevaInspeccion()"' in html
    assert 'Limpiar Todo' in html
    assert 'id="btnLimpiarTodoDesk"' in html

    # 2. Solo debe existir 1 botón en el formulario de captura que llame a copiarMarcaDisenoAnterior()
    matches = re.findall(r'onclick=["\']copiarMarcaDisenoAnterior\(\)["\']', html)
    assert len(matches) == 1, f"Se esperaba 1 solo botón de copiar marca/diseño pero se encontraron {len(matches)}"
    assert 'id="btnCopiarMarcaDisenoAnt"' in html
