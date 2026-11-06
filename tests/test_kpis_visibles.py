"""
Elegir qué KPI ve cada usuario en la pestaña KPIs: se guarda en el servidor por usuario, al inicio están todos
marcados, solo se aceptan KPI del catálogo y el PDF de KPIs sale completo aunque el usuario oculte algunos.
"""
import io
import os
import re

import pypdf
import pytest
from fastapi.testclient import TestClient

import database
import pdf_kpis
import server

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAS = [clave for _, _, _, kpis in pdf_kpis.SECCIONES for clave, _, _, _ in kpis]


def _cliente_de(username, rol="inspector", vistas="patio,kpis"):
    database.crear_usuario(username=username, password="Clave-Segura-2026", nombre_completo=username.title(), rol=rol,
                           cliente_asignado="FLOTA KPI", vistas_permitidas=vistas)
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(username, rol)}"})
    return c


def _leer(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


def test_al_inicio_todos_marcados_y_catalogo_igual_al_pdf(auth_client):
    data = auth_client.get("/api/kpis/visibles").json()
    assert data["ocultos"] == []
    assert [s["numero"] for s in data["secciones"]] == [1, 2, 3, 4, 5, 6]
    assert [k["clave"] for s in data["secciones"] for k in s["kpis"]] == TODAS
    assert len(TODAS) == 22 and {"kpi_01", "kpi_20", "kpi_cpk", "kpi_tendencias"} <= set(TODAS)
    # Las secciones exclusivas de FULL / PRO vienen marcadas para que la ventana las bloquee en LIGHT
    assert [s["solo_full"] for s in data["secciones"]] == [False, False, True, True, True, False]


def test_la_seleccion_se_guarda_por_usuario(test_db, auth_client):
    ana = _cliente_de("ana_kpis")
    beto = _cliente_de("beto_kpis")

    res = ana.put("/api/kpis/visibles", json={"ocultos": ["kpi_cpk", "kpi_05", "kpi_05"]})
    assert res.status_code == 200
    assert res.json()["ocultos"] == ["kpi_05", "kpi_cpk"]

    # Se conserva para ella (otro equipo o al volver a entrar) y no afecta a nadie más
    assert ana.get("/api/kpis/visibles").json()["ocultos"] == ["kpi_05", "kpi_cpk"]
    assert beto.get("/api/kpis/visibles").json()["ocultos"] == []
    assert auth_client.get("/api/kpis/visibles").json()["ocultos"] == []

    # Volver a marcarlos todos
    assert ana.put("/api/kpis/visibles", json={"ocultos": []}).json()["ocultos"] == []
    assert ana.get("/api/kpis/visibles").json()["ocultos"] == []


def test_rechaza_kpi_que_no_existe_y_no_guarda_nada(test_db):
    ana = _cliente_de("ana_kpis")
    ana.put("/api/kpis/visibles", json={"ocultos": ["kpi_02"]})
    res = ana.put("/api/kpis/visibles", json={"ocultos": ["kpi_02", "kpi_99"]})
    assert res.status_code == 400
    assert "kpi_99" in res.json()["detail"]
    assert ana.get("/api/kpis/visibles").json()["ocultos"] == ["kpi_02"]


def test_datos_viejos_o_danados_no_rompen_la_lectura(test_db, auth_client):
    with database.get_connection() as conn:
        conn.execute("UPDATE usuarios SET kpis_ocultos = 'no es json' WHERE username = 'admin'")
        conn.commit()
    assert auth_client.get("/api/kpis/visibles").json()["ocultos"] == []
    # Un KPI que ya no existe en el catálogo se ignora al leer
    database.guardar_kpis_ocultos_usuario("admin", ["kpi_03", "kpi_retirado"])
    assert auth_client.get("/api/kpis/visibles").json()["ocultos"] == ["kpi_03"]


def test_exige_sesion_y_la_vista_de_kpis(test_db):
    anonimo = TestClient(server.app)
    assert anonimo.get("/api/kpis/visibles").status_code == 401
    assert anonimo.put("/api/kpis/visibles", json={"ocultos": []}).status_code == 401
    sin_kpis = _cliente_de("solo_patio", vistas="patio")
    assert sin_kpis.get("/api/kpis/visibles").status_code == 403
    assert sin_kpis.put("/api/kpis/visibles", json={"ocultos": ["kpi_01"]}).status_code == 403


def test_el_pdf_sale_completo_aunque_el_usuario_oculte_kpis(test_db, auth_client):
    auth_client.put("/api/kpis/visibles", json={"ocultos": TODAS})
    res = auth_client.post("/api/kpis/exportar-pdf", json={"licencia": "FULL", "graficos": {}})
    assert res.status_code == 200
    texto = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(res.content)).pages)
    assert all(titulo in texto for _, titulo, _, _ in pdf_kpis.SECCIONES)


def test_cada_kpi_del_catalogo_tiene_su_tarjeta_en_la_vista():
    """Si se agrega un KPI al PDF sin marcar su tarjeta (o al revés), la ventana de selección quedaría desfasada."""
    html = _leer("templates/index.html")
    vista = html[html.index('id="vista-kpis"'):html.index("<!-- 4. Tabla Detallada de Trazabilidad y KPIs -->")]
    marcadas = re.findall(r'data-kpi="([a-z0-9_]+)"', vista)
    assert sorted(marcadas) == sorted(TODAS)
    assert len(marcadas) == len(set(marcadas))
    # La ventana y su botón existen
    assert 'id="btnElegirKpis"' in html and 'onclick="abrirModalElegirKpis()"' in html
    assert 'id="modalElegirKpis"' in html and 'id="listaElegirKpis"' in html
    assert ".kpi-oculto-usuario { display: none !important; }" in html


def test_la_seleccion_se_pide_antes_que_la_suite():
    """Si se pide después, los KPI desmarcados se ven unos segundos mientras carga la suite (pasó en QA)."""
    js = _leer("static/js/modulo_kpis.js")
    carga = js[js.index("async function cargarSuite20Kpis()"):]
    assert carga.index("cargarPreferenciasKpis();") < carga.index("fetch(`/api/kpis/suite-20?")


def test_el_pdf_muestra_los_kpi_ocultos_mientras_captura_los_graficos():
    js = _leer("static/js/modulo_kpis.js")
    pdf = js[js.index("async function exportarKpisPdf()"):js.index("function cambiarSubpestanaKpis(num)")]
    # Se muestran todos antes de recorrer las pestañas y se vuelve a aplicar la selección al terminar
    assert pdf.index("exportandoPdfKpis = true;") < pdf.index("for (const num of pestanas)")
    final = pdf[pdf.index("} finally {\n        exportandoPdfKpis = false;"):]
    assert "aplicarVisibilidadKpis();" in final
    for funcion in ("function aplicarVisibilidadKpis(", "async function abrirModalElegirKpis(", "function cerrarModalElegirKpis(",
                    "function marcarKpi(", "function marcarSeccionKpis(", "function mostrarTodosLosKpis(",
                    "async function guardarSeleccionKpis("):
        assert funcion in js, funcion
