"""Auditoría 2026-11-09, lote 2: no perder ni inventar capturas en patio (H-02, H-05, H-17)."""
import os
import re

from fastapi.testclient import TestClient

import database
import server

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(rel):
    return open(os.path.join(RAIZ, rel), encoding="utf-8").read()


def _funcion(js, nombre, siguiente):
    return js[js.index(nombre):js.index(siguiente, js.index(nombre))]


# --- H-05: la presión propuesta es la objetivo del cliente por eje --------------------------
def test_h05_limite_cliente_trae_la_presion_objetivo_por_eje(test_db, auth_client):
    database.guardar_licencia_cliente("CLI PSI", "PRO")
    with database.get_connection() as conn:
        conn.execute("UPDATE configuracion_avanzada_cliente SET psi_objetivo_direccional = 120, psi_objetivo_traccion = 115,"
                     " psi_objetivo_arrastre = 105 WHERE cliente = 'CLI PSI'")
        conn.commit()
    d = auth_client.get("/api/limite-cliente?cliente=CLI PSI").json()
    assert d["psi_objetivo"] == {"direccional": 120.0, "traccion": 115.0, "arrastre": 105.0}
    # Cliente sin configuración: los valores técnicos por defecto (los mismos contra los que miden los KPI)
    assert auth_client.get("/api/limite-cliente?cliente=CLI SIN CONFIG").json()["psi_objetivo"]["direccional"] == 110.0


def test_h05_patio_no_precarga_100_psi_ni_original_ni_dimension_fija():
    patio, core, html = _leer("static/js/modulo_patio.js"), _leer("static/js/app_core.js"), _leer("templates/index.html")
    assert "psi.value = '100'" not in patio and "getElementById('psi').value = '100'" not in patio
    assert "psi: payload.psi || 100" not in core
    assert re.search(r'id="psi"[^>]*value=""', html) and 'value="100"' not in re.search(r'<input[^>]*id="psi"[^>]*>', html).group(0)
    assert "'295/80R22.5'" not in patio and "payload.dimension || '295/80R22.5'" not in core
    assert '<option value="295/80R22.5" selected>' not in html
    # «Original» solo se fuerza por la regla del eje direccional, nunca como valor de arranque
    for linea in patio.splitlines():
        if "selVida.value = 'Original'" in linea:
            assert linea.strip().startswith("selVida.value = 'Original';")  # dentro de la regla del direccional
    assert patio.count("selVida.value = 'Original'") == 2
    assert "prellenarPsiPosicion(" in patio and "psiObjetivoClienteCaptura = (d && d.psi_objetivo)" in patio


def test_h05_guardar_exige_vida_y_dimension():
    patio, html = _leer("static/js/modulo_patio.js"), _leer("templates/index.html")
    envio = patio[patio.index("getElementById('inspectionForm').addEventListener('submit'"):]
    assert "[['vida', 'err_vida'], ['dimension', 'err_dimension']]" in envio
    assert 'id="err_vida"' in html and 'id="err_dimension"' in html


# --- H-02: si el teléfono no guarda, no se anuncia como guardada -----------------------------
def test_h02_falla_del_guardado_local_no_se_anuncia_como_guardada():
    patio = _leer("static/js/modulo_patio.js")
    cola = _funcion(patio, "async function guardarEnColaOffline", "try {\n        if (!navigator.onLine)")
    # Si falla guardarPendiente se avisa y se sale antes de completarGuardadoRueda
    i_fallo = cola.index("avisarCapturaNoGuardada(payload)")
    assert cola.index("return false;", i_fallo) < cola.index("await completarGuardadoRueda(true)")
    assert "function avisarCapturaNoGuardada" in patio and "llanta_no_guardada_" in patio


# --- H-17: sesión vencida o falla del servidor no descartan la llanta ------------------------
def test_h17_401_y_5xx_encolan_y_los_rechazos_de_negocio_no():
    patio = _leer("static/js/modulo_patio.js")
    envio = patio[patio.index("const res = await fetchConTimeoutPatio('/api/inspecciones'"):]
    envio = envio[:envio.index("} catch (errRed)")]
    assert "res.status === 401 || res.status >= 500" in envio
    assert envio.index("guardarEnColaOffline(") < envio.index("mostrarToast(result.detail")


def test_h17_al_ingresar_se_envia_la_cola_y_se_conserva_la_captura():
    patio, core = _leer("static/js/modulo_patio.js"), _leer("static/js/app_core.js")
    ingreso = _funcion(core, "function cargarDatosTrasIngreso", "async function cerrarSesionUsuario")
    assert "sincronizarColaOffline()" in ingreso
    catalogos = _funcion(patio, "async function cargarCatalogos", "async function poblarDatalist")
    assert "seleccionarOp = seleccionarOp ||" in catalogos and "sedePrevia" in catalogos
