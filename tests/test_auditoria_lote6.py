"""Auditoría 2026-11-09, lote 6: accesibilidad (H-12, H-13, H-19, H-20, H-22, H-28), papelera (H-40) y arranque (H-45)."""
import os
import re

import database
import server

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(rel):
    return open(os.path.join(RAIZ, rel), encoding="utf-8").read()


HTML = _leer("templates/index.html")


def test_h12_zoom_permitido():
    assert "user-scalable=no" not in HTML and "maximum-scale" not in HTML


def test_h13_foco_visible_en_llantas():
    assert re.search(r"\.tire-interactive-node:focus-visible \{\s*outline: 3px solid", HTML)


def test_h19_placeholder_con_contraste():
    bloque = HTML[HTML.index("input::placeholder, textarea::placeholder {"):][:200]
    assert "#64748B" in bloque and "opacity: 1" in bloque


def test_h20_etiquetas_y_botones_con_nombre():
    labels = re.findall(r"<label\b[^>]*>", HTML)
    con_for = sum("for=" in l for l in labels)
    assert con_for >= 190, con_for                    # antes 5 de 236
    for m in re.finditer(r'<label\b[^>]*\bfor="([^"]+)"', HTML):
        assert f'id="{m.group(1)}"' in HTML, m.group(1)
    solo_icono = re.findall(r"<button\b([^>]*)>\s*<i\b[^>]*></i>\s*</button>", HTML)
    assert all("aria-label" in a or "title=" in a for a in solo_icono)


def test_h22_graficas_con_nombre_accesible():
    canvas = re.findall(r"<canvas\b[^>]*>", HTML)
    assert canvas and all('role="img"' in c and "aria-label=" in c for c in canvas)
    assert "id: 'resumenAccesible'" in _leer("static/js/app_core.js")


def test_h28_modales_accesibles():
    js = _leer("static/js/accesibilidad_modales.js")
    for pieza in ("setAttribute('role', 'dialog')", "aria-modal", "e.key === 'Escape'", "e.key !== 'Tab'", "origenFoco"):
        assert pieza in js, pieza
    # El archivo se carga con un número de versión (?v=…) para que el navegador no use una copia vieja
    assert '<script src="/static/js/accesibilidad_modales.js' in HTML


# --- H-40: papelera ------------------------------------------------------------------------------
def _una_inspeccion():
    database.insertar_inspeccion({"fecha": "2026-10-01", "cliente": "CLI PAP", "subcliente": "S", "placa": "PAP001",
                                  "posicion": 3, "numero_interno": "N-PAP", "marca": "MICHELIN", "dimension": "295/80R22.5",
                                  "vida": "Original", "kilometraje": 1000, "prof_ext": 10, "prof_cent": 10, "prof_int": 10,
                                  "novedades": "CORTE"})
    with database.get_connection() as conn:
        return conn.execute("SELECT id FROM inspecciones WHERE placa = 'PAP001'").fetchone()[0]


def test_h40_borrar_deja_rastro_y_se_puede_restaurar(test_db, auth_client):
    iid = _una_inspeccion()
    r = auth_client.delete(f"/api/inspecciones/{iid}?motivo=Cargada%20dos%20veces")
    assert r.status_code == 200, r.text
    assert auth_client.get(f"/api/inspecciones/{iid}").status_code == 404
    pap = auth_client.get("/api/inspecciones/papelera").json()
    assert len(pap) == 1 and pap[0]["inspeccion_id"] == iid and pap[0]["motivo"] == "Cargada dos veces"
    assert pap[0]["eliminado_por"] == "admin" and pap[0]["eliminado_en"]
    r = auth_client.post(f"/api/inspecciones/papelera/{pap[0]['id']}/restaurar")
    assert r.status_code == 200 and r.json()["id"] == iid
    assert auth_client.get(f"/api/inspecciones/{iid}").json()["novedades"] == "CORTE"
    assert auth_client.post(f"/api/inspecciones/papelera/{pap[0]['id']}/restaurar").status_code == 400  # una sola vez
    assert auth_client.get("/api/inspecciones/papelera").json()[0]["restaurado_por"] == "admin"


def test_h40_borrar_inexistente_es_404(test_db, auth_client):
    assert auth_client.delete("/api/inspecciones/999999").status_code == 404


def test_h40_papelera_solo_administrador(test_db):
    from fastapi.testclient import TestClient
    database.crear_usuario("jefe_pap", "Clave-Segura-9", "Jefe", "jefatura", "CLI PAP", vistas_permitidas="basedatos")
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso('jefe_pap', 'jefatura')}"})
    assert c.get("/api/inspecciones/papelera").status_code == 403


# --- H-45: arranque con lifespan ------------------------------------------------------------------
def test_h45_sin_on_event_obsoleto():
    src = _leer("server.py")
    assert not re.search(r"^@app\.on_event\(", src, re.M) and "lifespan=_ciclo_de_vida" in src
