"""Auditoría 2026-11-09, lote 4: robustez (H-16, H-23, H-24, H-34, H-35, H-37)."""
import io
import os
import zipfile

import openpyxl
import pandas as pd
import pytest

import database
import server

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(rel):
    return open(os.path.join(RAIZ, rel), encoding="utf-8").read()


def _subir(cliente_http, contenido, nombre="cargue.xlsx", ruta="/api/inspecciones/importar-excel"):
    return cliente_http.post(ruta, files={"file": (nombre, contenido, "application/vnd.ms-excel")})


def _excel(filas):
    buf = io.BytesIO()
    pd.DataFrame(filas).to_excel(buf, index=False)
    buf.seek(0)
    return buf


_BASE = {"Fecha": "2026-10-08", "Cliente": "FLOTA IMP", "Sede": "SEDE", "Placa": "IMP100", "Posicion": 1,
         "Tipologia": "Cabezote (6x4)", "Marca": "MICHELIN", "Dimension": "295/80R22.5", "Prof Ext": 10,
         "Prof Cent": 10, "Prof Int": 10, "PSI": 100, "Kilometraje": 1000}


# --- H-16: error visible en la suite de KPI -----------------------------------------------------
def test_h16_error_de_la_suite_se_muestra_y_oculta_cifras_viejas():
    js, html = _leer("static/js/modulo_kpis.js"), _leer("templates/index.html")
    assert "console.warn('No se pudo cargar la suite de 20 KPIs" not in js
    assert "function mostrarErrorSuiteKpis(mensaje)" in js and "mostrarErrorSuiteKpis(null)" in js
    assert 'id="kpiErrorCarga"' in html and 'onclick="cargarSuite20Kpis()"' in html


# --- H-23: importación con filas rechazadas -----------------------------------------------------
def test_h23_filas_invalidas_se_rechazan_con_motivo(test_db, auth_client):
    filas = [dict(_BASE),
             dict(_BASE, Placa="IMP101", Fecha="no es fecha"),
             dict(_BASE, Placa="IMP102", Posicion=None),
             dict(_BASE, Placa=None),
             dict(_BASE, Placa="IMP103", Posicion=0)]
    r = _subir(auth_client, _excel(filas))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["registros_importados"] == 1 and d["total_rechazadas"] == 4
    motivos = {x["fila"]: x["motivo"] for x in d["rechazadas"]}
    assert "fecha" in motivos[3] and "posición" in motivos[4] and motivos[5] == "sin placa" and "posición" in motivos[6]
    with database.get_connection() as conn:
        assert [r[0] for r in conn.execute("SELECT fecha FROM inspecciones")] == ["2026-10-08"]  # no inventó «hoy»


def test_h23_sin_columnas_obligatorias_no_escribe_nada(test_db, auth_client):
    sin_placa = {k: v for k, v in _BASE.items() if k != "Placa"}
    r = _subir(auth_client, _excel([sin_placa]))
    assert r.status_code == 400 and "placa" in r.json()["detail"]
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM inspecciones").fetchone()[0] == 0


# --- H-24: el service worker no guarda la API ----------------------------------------------------
def test_h24_service_worker_no_cachea_api(auth_client):
    sw = auth_client.get("/sw.js").text
    assert "if (url.pathname.startsWith('/api/')) return;" in sw
    assert "tireanalyze-patio-v3" in sw
    core = _leer("static/js/app_core.js")
    assert "function borrarRespuestasApiEnCache()" in core
    assert core.count("borrarRespuestasApiEnCache();") >= 2  # al cargar y al cerrar sesión


# --- H-34: fechas por defecto en hora local -------------------------------------------------------
def test_h34_fechas_por_defecto_en_hora_local():
    for rel in ("static/js/modulo_bodegas.js", "static/js/modulo_catalogos.js"):
        js = _leer(rel)
        assert "new Date().toISOString().split('T')[0]" not in js
        assert "new Date().toISOString().slice(0, 10)" not in js
        assert "fechaLocalISO()" in js


# --- H-35: Excel sin fórmulas vivas ni fotos recortadas ------------------------------------------
def test_h35_excel_seguro():
    foto = '["' + "A" * 40000 + '", "B"]'
    df = pd.DataFrame({"novedades": ["=1+1", "-2", "- CORTE", "x" * 40000, "@SUMA(A1)"], "foto_novedad": [foto, "", None, "", ""],
                       "km": [1, 2, 3, 4, 5]})
    out = server.df_seguro_para_excel(df)
    assert list(out["novedades"][:3]) == ["'=1+1", "-2", "- CORTE"]
    assert out["novedades"][3].endswith("[texto recortado]") and len(out["novedades"][3]) == server.MAX_CELDA_EXCEL
    assert out["novedades"][4] == "'@SUMA(A1)"
    assert out["foto_novedad"][0] == "2 foto(s): ver en la aplicación" and out["foto_novedad"][1] == ""
    buf = io.BytesIO()
    out.to_excel(buf, index=False)
    buf.seek(0)
    ws = openpyxl.load_workbook(buf).active
    assert all(c.data_type != "f" for fila in ws.iter_rows() for c in fila)


def test_h35_diagnostico_usa_el_helper():
    src = _leer("server.py")
    assert 'df_seguro_para_excel(df_insp).to_excel(writer, sheet_name="Detalle_Inspecciones"' in src
    assert 'df_seguro_para_excel(df_analisis_excel).to_excel' in src


# --- H-37: tamaño máximo de los Excel subidos -----------------------------------------------------
def test_h37_archivo_grande_responde_413(test_db, auth_client, monkeypatch):
    monkeypatch.setattr(server, "MAX_EXCEL_SUBIDO_BYTES", 1000)
    r = _subir(auth_client, io.BytesIO(b"x" * 5000))
    assert r.status_code == 413


def test_h37_bomba_de_descompresion_responde_413(test_db, auth_client, monkeypatch):
    monkeypatch.setattr(server, "MAX_EXCEL_DESCOMPRIMIDO_BYTES", 10_000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", "0" * 100_000)
    buf.seek(0)
    for ruta in ("/api/inspecciones/importar-excel", "/api/precios-cliente/importar-excel", "/api/padron/importar-excel?cliente=X"):
        buf.seek(0)
        assert _subir(auth_client, buf, ruta=ruta).status_code == 413, ruta
