import pytest
import subprocess
import os
import re
from datetime import date
from fastapi.testclient import TestClient
import database
from server import app, crear_token_acceso

client = TestClient(app)

@pytest.fixture(autouse=True)
def preparar_bd_pruebas():
    database.inicializar_bd()
    yield

def test_perfil_vehiculo_frecuencia_en_periodo_restringido():
    """Valida que un vehículo inspeccionado recientemente reporte en_periodo_restringido = True y fecha mínima."""
    placa_test = "FRQ999"
    hoy = date.today().strftime("%Y-%m-%d")
    
    # Insertar una inspección reciente para esta placa
    datos_insp = {
        "fecha": hoy,
        "placa": placa_test,
        "numero_interno": "LL-TEST-01",
        "marca": "GOODYEAR",
        "diseno": "KMAX S",
        "dimension": "295/80R22.5",
        "posicion": 1,
        "prof_inicial": 16.0,
        "prof_ext": 14.0,
        "prof_cent": 14.0,
        "prof_int": 14.0,
        "psi": 110,
        "kilometraje": 50000,
        "cliente": "CLIENTE PRUEBA FRECUENCIA",
        "tipologia": "TRACTOMULA 3S3"
    }
    database.insertar_inspeccion(datos_insp)
    
    perfil = database.obtener_perfil_vehiculo(placa_test)
    assert perfil["encontrado"] is True
    assert perfil["placa"] == placa_test
    assert perfil["ultima_fecha_inspeccion"] == hoy
    assert perfil["en_periodo_restringido"] is True
    assert perfil["dias_para_nueva_inspeccion"] > 0
    assert perfil["fecha_minima_permitida"] > hoy
    assert perfil["ultima_marca"] == "GOODYEAR"
    assert perfil["ultimo_diseno"] == "KMAX S"

def test_perfil_vehiculo_nuevo_sin_restriccion():
    """Valida que un vehículo sin inspecciones previas no tenga restricción de frecuencia."""
    placa_nueva = "NUEVO123"
    perfil = database.obtener_perfil_vehiculo(placa_nueva)
    assert perfil["en_periodo_restringido"] is False
    assert perfil["dias_para_nueva_inspeccion"] == 0

def test_obtener_ultima_marca_diseno_vehiculo():
    """Valida la función dedicada a obtener marca y diseño anteriores de un vehículo."""
    placa_test = "MRK888"
    datos_insp = {
        "fecha": "2026-05-10",
        "placa": placa_test,
        "numero_interno": "LL-MRK-88",
        "marca": "BRIDGESTONE",
        "diseno": "M729",
        "dimension": "295/80R22.5",
        "posicion": 2,
        "prof_inicial": 21.0,
        "prof_ext": 18.0,
        "prof_cent": 18.0,
        "prof_int": 18.0,
        "psi": 105,
        "kilometraje": 80000,
        "cliente": "FLOTA TRANSPORTE",
        "tipologia": "CAMION SENCILLO 4X2"
    }
    database.insertar_inspeccion(datos_insp)
    
    res = database.obtener_ultima_marca_diseno_vehiculo(placa_test)
    assert res["encontrado"] is True
    assert res["marca"] == "BRIDGESTONE"
    assert res["diseno"] == "M729"
    assert res["dimension"] == "295/80R22.5"

    res_inexistente = database.obtener_ultima_marca_diseno_vehiculo("NOEXISTE")
    assert res_inexistente["encontrado"] is False

def test_api_vehiculo_perfil_y_ultima_marca_diseno():
    """Valida los endpoints REST con token de autenticación."""
    token = crear_token_acceso("admin", "admin")
    headers = {"Authorization": f"Bearer {token}"}
    
    placa = "API777"
    datos = {
        "fecha": date.today().strftime("%Y-%m-%d"),
        "placa": placa,
        "numero_interno": "LL-API-77",
        "marca": "MICHELIN",
        "diseno": "X MULTI Z",
        "dimension": "295/80R22.5",
        "posicion": 1,
        "prof_inicial": 16.5,
        "prof_ext": 15.0,
        "prof_cent": 15.0,
        "prof_int": 15.0,
        "psi": 110,
        "kilometraje": 30000,
        "cliente": "CLIENTE API",
        "tipologia": "PATINETA 2S2"
    }
    database.insertar_inspeccion(datos)
    
    # 1. Endpoint /api/vehiculo-perfil
    resp_perfil = client.get(f"/api/vehiculo-perfil?placa={placa}", headers=headers)
    assert resp_perfil.status_code == 200
    data_perfil = resp_perfil.json()
    assert data_perfil["encontrado"] is True
    assert data_perfil["en_periodo_restringido"] is True
    assert data_perfil["ultima_marca"] == "MICHELIN"
    assert data_perfil["ultimo_diseno"] == "X MULTI Z"
    
    # 2. Endpoint /api/inspecciones/ultima-marca-diseno
    resp_marca = client.get(f"/api/inspecciones/ultima-marca-diseno?placa={placa}", headers=headers)
    assert resp_marca.status_code == 200
    data_marca = resp_marca.json()
    assert data_marca["encontrado"] is True
    assert data_marca["marca"] == "MICHELIN"
    assert data_marca["diseno"] == "X MULTI Z"

def test_frontend_dom_modal_frecuencia_y_boton_copiar_marca():
    """Valida la presencia física de los elementos HTML en templates/index.html."""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Modal de alerta de vehículo ya inspeccionado
    assert 'id="modalVehiculoYaInspeccionado"' in html
    assert 'id="popup_placa_vehiculo"' in html
    assert 'id="popup_fecha_ultima_inspeccion"' in html
    assert 'id="popup_fecha_permitida_inspeccion"' in html
    assert 'id="popup_dias_restantes_texto"' in html
    assert 'cerrarModalVehiculoYaInspeccionado()' in html
    
    # Botón para copiar marca y diseño anterior
    assert 'id="btnCopiarMarcaDisenoAnt"' in html
    assert 'copiarMarcaDisenoAnterior()' in html
    
    # Funciones JavaScript
    assert "function mostrarModalVehiculoYaInspeccionado(" in html
    assert "function cerrarModalVehiculoYaInspeccionado(" in html
    assert "async function copiarMarcaDisenoAnterior(" in html
    assert "cacheUltimaMarcaVehiculo" in html

def test_frontend_javascript_sintaxis_valida():
    """Valida con Node.js que no existan errores de sintaxis en el código JavaScript de index.html."""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    scripts = re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', content, re.DOTALL)
    assert len(scripts) > 0, "No se encontraron etiquetas <script> en index.html"

    codigo_js = "\n".join(scripts)
    res = subprocess.run(
        ["node", "--check"],
        input=codigo_js,
        text=True,
        encoding="utf-8",
        capture_output=True
    )
    assert res.returncode == 0, f"Error de sintaxis en JavaScript de templates/index.html: {res.stderr}"

def test_fecha_minima_permitida_exacta_dia_20_mes_siguiente():
    """Verifica que la fecha mínima permitida para una inspección sea el día 20 del mes siguiente."""
    # Caso puntual del usuario: última inspección 2026-10-20 -> debe ser 2026-11-20
    f_min = database.calcular_fecha_minima_siguiente_inspeccion("2026-10-20")
    assert str(f_min) == "2026-11-20"

    # Caso fin de año: 2026-12-05 -> debe ser 2027-01-20
    f_min_diciembre = database.calcular_fecha_minima_siguiente_inspeccion("2026-12-05")
    assert str(f_min_diciembre) == "2027-01-20"

def test_subcliente_obligatorio_en_api():
    """Valida que la Sede / Subcliente sea obligatoria al registrar inspecciones."""
    import uuid
    token = crear_token_acceso("admin", "admin")
    headers = {"Authorization": f"Bearer {token}"}
    
    placa_base = f"S{uuid.uuid4().hex[:5].upper()}"
    payload_sin_sub = {
        "fecha": "2026-10-20",
        "cliente": "CLIENTE PRUEBA SUB",
        "subcliente": "",
        "tipo_operacion": "CARGA",
        "placa": placa_base,
        "posicion": 1,
        "kilometraje": 10000,
        "tipologia": "CABEZOTE (6X4)",
        "marca": "MICHELIN",
        "diseno": "X MULTI",
        "dimension": "295/80R22.5",
        "prof_inicial": 16.0,
        "prof_ext": 12.0,
        "prof_cent": 12.0,
        "prof_int": 12.0,
        "psi": 110,
        "vida": "Original"
    }
    # Con subcliente vacío debe dar 400
    res_vacio = client.post("/api/inspecciones", json=payload_sin_sub, headers=headers)
    assert res_vacio.status_code == 400
    assert "subcliente" in res_vacio.json()["detail"].lower()

    # Con placeholder de selección debe dar 400
    payload_placeholder = dict(payload_sin_sub)
    payload_placeholder["subcliente"] = "ej. Principal (Seleccionar sede)"
    res_placeholder = client.post("/api/inspecciones", json=payload_placeholder, headers=headers)
    assert res_placeholder.status_code == 400

    # Con sede válida debe registrar exitosamente
    placa_ok = f"K{uuid.uuid4().hex[:5].upper()}"
    payload_valido = dict(payload_sin_sub)
    payload_valido["placa"] = placa_ok
    payload_valido["subcliente"] = "Sede Norte"
    res_ok = client.post("/api/inspecciones", json=payload_valido, headers=headers)
    assert res_ok.status_code == 200

