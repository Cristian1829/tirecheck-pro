"""
KPI 01 por mes y por año, Composición de Flota con la foto actual (igual a «Marcas Instaladas»), regla de oro 1,
exportación a Excel y el total de llantas de la flota igual en todas las vistas.
"""
import io

import pandas as pd
import pytest
from openpyxl import load_workbook

import database
import modulo_bodegas_taller as mbt

CLI = "FLOTA COMPOSICION"


def _tipologia():
    with database.get_connection() as conn:
        return conn.execute("SELECT nombre FROM catalogo_tipologias ORDER BY nombre LIMIT 1").fetchone()[0]


def _insp(placa, pos, fecha, marca, serial, vida="Original", banda="", tip=None, km=50000, cliente=CLI):
    database.insertar_inspeccion({
        "fecha": fecha, "cliente": cliente, "subcliente": "SEDE UNO", "tipo_operacion": "CARGA", "placa": placa,
        "posicion": pos, "kilometraje": km, "tipologia": tip or _tipologia(), "marca": marca, "diseno": "DISENO X",
        "dimension": "295/80R22.5", "vida": vida, "banda_reen": banda, "prof_ext": 10, "prof_cent": 10, "prof_int": 10,
        "psi": 100, "prof_inicial": 21.5, "numero_interno": serial})


@pytest.fixture
def flota(test_db):
    """
    Un vehículo con: llanta cambiada en la pos 1, dos llantas «SN» (una con la marca en minúsculas), una sin número
    y una desmontada después de su última inspección. Hoy hay 4 llantas instaladas.
    """
    database.guardar_licencia_cliente(CLI, "PRO")
    _insp("CMP001", 1, "2026-10-05", "MICHELIN", "A-1")
    _insp("CMP001", 1, "2026-10-20", "BRIDGESTONE", "B-1")
    _insp("CMP001", 2, "2026-10-20", "MICHELIN", "SN")
    _insp("CMP001", 3, "2026-10-20", "michelin", "SN")
    _insp("CMP001", 4, "2026-10-20", "GOODYEAR", "")
    _insp("CMP001", 5, "2026-10-20", "PIRELLI", "D-1")
    r = mbt.desmontar_llanta_taller({"numero_interno": "D-1", "cliente_propietario": CLI, "odometro_vehiculo": 51000,
                                     "profundidad": 9, "bodega_destino": "BODEGA_2_RECAMBIO"})
    assert r["ok"], r
    return CLI


def _marcas(filas):
    cuenta = {}
    for f in filas:
        m = str(f.get("marca") or "").upper()
        cuenta[m] = cuenta.get(m, 0) + 1
    return cuenta


ESPERADO = {"BRIDGESTONE": 1, "MICHELIN": 2, "GOODYEAR": 1}


# ================= COMPOSICIÓN = FOTO ACTUAL =================
def test_composicion_cuenta_las_llantas_instaladas_hoy(flota, auth_client):
    filas = auth_client.get(f"/api/kpis-llantas?foto=actual&cliente={CLI}").json()
    assert _marcas(filas) == ESPERADO
    assert sorted(f["posicion"] for f in filas) == [1, 2, 3, 4]
    # La lista por llanta de Trazabilidad (sin foto) sigue igual que antes
    historia = auth_client.get(f"/api/kpis-llantas?cliente={CLI}").json()
    assert {f["numero_interno"] for f in historia} >= {"A-1", "B-1", "D-1"}


def test_participacion_por_marca_igual_a_marcas_instaladas(flota, auth_client):
    filas = auth_client.get(f"/api/kpis-llantas?foto=actual&cliente={CLI}").json()
    k4 = database.obtener_suite_completa_20_kpis({"cliente": CLI})["kpi_04"]
    assert dict(zip(k4["marca"]["labels"], k4["marca"]["valores"])) == _marcas(filas)
    assert k4["total_llantas"] == len(filas) == 4


def test_total_de_llantas_igual_en_todas_las_vistas(flota, auth_client):
    suite = database.obtener_suite_completa_20_kpis({"cliente": CLI})
    with database.get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM inspecciones WHERE cliente = ?", conn, params=(CLI,))
    semaforos = database.calcular_matriz_semaforos_posicion(df)
    composicion = auth_client.get(f"/api/kpis-llantas?foto=actual&cliente={CLI}").json()
    totales = {
        "composicion": len(composicion),
        "kpi04_total": suite["kpi_04"]["total_llantas"],
        "kpi04_marcas": sum(suite["kpi_04"]["marca"]["valores"]),
        "kpi04_dimensiones": sum(suite["kpi_04"]["dimension"]["valores"]),
        "kpi04_tipologias": sum(suite["kpi_04"]["tipologia"]["valores"]),
        "calidad_datos": suite["calidad_datos"]["llantas"],
        "semaforos": semaforos["resumen_global"]["total_llantas"],
    }
    assert set(totales.values()) == {4}, totales


def test_semaforos_cuentan_todas_las_posiciones_del_vehiculo(test_db):
    """Antes, si en la última fecha se inspeccionó una sola posición, el vehículo salía con una sola llanta."""
    database.guardar_licencia_cliente(CLI, "PRO")
    for pos in (1, 2, 3):
        _insp("SEM001", pos, "2026-09-10", "MICHELIN", f"S-{pos}")
    _insp("SEM001", 1, "2026-10-10", "MICHELIN", "S-1")
    with database.get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM inspecciones WHERE placa = 'SEM001'", conn)
    assert database.calcular_matriz_semaforos_posicion(df)["resumen_global"]["total_llantas"] == 3


def test_marcas_instaladas_suman_el_total_con_otras(test_db):
    database.guardar_licencia_cliente(CLI, "PRO")
    marcas = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"]
    for i, m in enumerate(marcas, 1):
        _insp(f"OTR{i:03d}", 1, "2026-10-20", m, f"O-{i}")
    k4 = database.obtener_suite_completa_20_kpis({"cliente": CLI})["kpi_04"]
    assert len(k4["marca"]["labels"]) == 8 and k4["marca"]["labels"][-1] == "Otras"
    assert sum(k4["marca"]["valores"]) == k4["total_llantas"] == 10


# ================= REGLA DE ORO 1 =================
def test_foto_actual_trae_eje_y_permiso_de_reencauche_en_direccion(flota, auth_client):
    filas = auth_client.get(f"/api/kpis-llantas?foto=actual&cliente={CLI}").json()
    assert all("permite_reencauche_direccion" in f and f["tipo_eje"] for f in filas)


def test_vista_tiene_boton_y_ventana_de_la_regla_de_oro_1():
    import os
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html = open(os.path.join(raiz, "templates", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(raiz, "static", "js", "modulo_trazabilidad.js"), encoding="utf-8").read()
    assert 'id="btnReglaOro1Vehiculos"' in html and 'id="modalReglaOro1"' in html
    assert "abrirModalReglaOro1" in js and "permite_reencauche_direccion" in js
    assert "/api/kpis-llantas?foto=actual" in js


# ================= EXCEL DE COMPOSICIÓN =================
def _llanta(placa, pos, marca, diseno, dim, reenc=False, eje="traccion", permite=False, serial="X"):
    return {"cliente": CLI, "subcliente": "SEDE UNO", "placa": placa, "posicion": pos, "tipo_eje": eje, "tipologia": "TRACTO",
            "numero_interno": serial, "marca": marca, "diseno": diseno, "dimension": dim, "vida": "R1" if reenc else "ORIGINAL",
            "banda_reen": "BDM" if reenc else "", "prof_actual_min": 10.0, "fecha_ult_insp": "2026-10-20",
            "es_reencauche": reenc, "permite_reencauche_direccion": permite}


def test_exportar_excel_de_composicion_organizado(auth_client, test_db):
    llantas = [
        _llanta("AAA111", 1, "MICHELIN", "XZE", "295/80R22.5", reenc=True, eje="direccional", serial="=CMD()"),
        _llanta("AAA111", 2, "MICHELIN", "XZE", "295/80R22.5", eje="direccional"),
        _llanta("AAA111", 3, "MICHELIN", "XDE", "295/80R22.5", reenc=True),
        _llanta("BBB222", 1, "BRIDGESTONE", "R268", "11R22.5", reenc=True, eje="direccional", permite=True),
        _llanta("BBB222", 2, "BRIDGESTONE", "R268", "11R22.5"),
    ]
    r = auth_client.post("/api/composicion/exportar-excel", json={"filtros": {"Cliente": CLI}, "tarjetas": [], "reglas": [], "llantas": llantas})
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Resumen", "Matriz", "Por marca", "Por dimensión", "Inventario llantas", "Regla de oro 1"]

    filas = [list(f) for f in wb["Matriz"].iter_rows(min_row=2, values_only=True)]
    # Agrupada por marca (la de más llantas primero), con subtotal por marca y total de la flota
    assert [f[0] for f in filas] == ["MICHELIN", "MICHELIN", "Subtotal MICHELIN", "BRIDGESTONE", "Subtotal BRIDGESTONE", "TOTAL FLOTA"]
    assert filas[0][:6] == ["MICHELIN", "XZE", "295/80R22.5", 1, 1, 2]
    assert filas[2][3:7] == [1, 2, 3, 0.6]
    assert filas[-1][3:7] == [2, 3, 5, 1]
    marcas = {f[0]: f[3] for f in wb["Por marca"].iter_rows(min_row=2, values_only=True)}
    assert marcas == {"MICHELIN": 3, "BRIDGESTONE": 2, "TOTAL": 5}

    # Regla de oro 1: solo el reencauche en dirección de una tipología no autorizada
    r1 = [f for f in wb["Regla de oro 1"].iter_rows(min_row=2, values_only=True)]
    assert len(r1) == 1 and r1[0][0] == "AAA111" and r1[0][4] == 1
    # Un texto que parece fórmula no se ejecuta
    inv = [f for f in wb["Inventario llantas"].iter_rows(min_row=2, values_only=True)]
    assert any(c == "'=CMD()" or c == "=CMD()" for f in inv for c in f)
    celda = next(c for row in wb["Inventario llantas"].iter_rows(min_row=2) for c in row if "CMD" in str(c.value))
    assert celda.data_type != "f"


def test_exportar_excel_exige_vista_de_composicion():
    from fastapi.testclient import TestClient
    import server
    assert TestClient(server.app).post("/api/composicion/exportar-excel", json={}).status_code == 401


# ================= KPI 01 POR MES Y POR AÑO =================
def test_kpi01_por_mes_y_por_anio_contra_la_flota(test_db):
    tip = _tipologia()
    database.guardar_licencia_cliente(CLI, "PRO")
    for p in ("PER001", "PER002", "PER003", "PER004"):
        assert database.guardar_vehiculo_padron(CLI, p, tip)["status"] == "ok"
    _insp("PER001", 1, "2027-11-10", "MICHELIN", "P-1", tip=tip)
    _insp("PER001", 1, "2027-12-10", "MICHELIN", "P-1", tip=tip, km=52000)
    _insp("PER002", 1, "2027-12-12", "MICHELIN", "P-2", tip=tip)
    _insp("PER003", 1, "2026-10-12", "MICHELIN", "P-3", tip=tip)

    k = database.obtener_suite_completa_20_kpis({"cliente": CLI})["kpi_01"]
    assert k["periodo_actual"] == "2027-12"  # el «hoy» de las pruebas es 31/12/2027
    meses = {m["clave"]: m for m in k["por_mes"]}
    assert (meses["2027-12"]["inspeccionados"], meses["2027-12"]["total"], meses["2027-12"]["pct"]) == (2, 4, 50.0)
    assert sorted(meses["2027-12"]["pendientes"]) == ["PER003", "PER004"]
    assert (meses["2027-11"]["inspeccionados"], meses["2027-11"]["pct"]) == (1, 25.0)
    assert meses["2026-10"]["inspeccionados"] == 1
    anios = {a["clave"]: a for a in k["por_anio"]}
    assert (anios["2027"]["inspeccionados"], anios["2027"]["pct"]) == (2, 50.0)
    assert (anios["2026"]["inspeccionados"], anios["2026"]["pct"]) == (1, 25.0)
    # Datos para la lista de pendientes de cualquier periodo
    assert k["parque"]["PER003"]["ultima_inspeccion"] == "2026-10-12" and k["parque"]["PER004"]["ultima_inspeccion"] == ""
    # Última inspección de una pendiente = la anterior al periodo, nunca una posterior:
    # PER002 solo se inspeccionó en diciembre, así que en noviembre figura sin inspección previa
    assert "PER002" in meses["2027-11"]["pendientes"] and "PER002" not in meses["2027-11"]["ultima_previa"]
    assert k["parque"]["PER002"]["ultima_inspeccion"] == "2027-12-12"
    assert meses["2027-12"]["ultima_previa"] == {"PER003": "2026-10-12"}
    assert anios["2027"]["pendientes"] == ["PER003", "PER004"] and anios["2027"]["ultima_previa"] == {"PER003": "2026-10-12"}
    # El total del historial sigue igual que antes
    assert (k["vehiculos_inspeccionados"], k["total_padron_activo"]) == (3, 4)


def test_kpi01_mes_en_curso_sin_inspecciones_sale_en_cero(test_db):
    tip = _tipologia()
    database.guardar_licencia_cliente(CLI, "PRO")
    database.guardar_vehiculo_padron(CLI, "CER001", tip)
    _insp("CER001", 1, "2027-10-10", "MICHELIN", "C-1", tip=tip)
    k = database.obtener_suite_completa_20_kpis({"cliente": CLI})["kpi_01"]
    actual = next(m for m in k["por_mes"] if m["clave"] == "2027-12")
    assert (actual["inspeccionados"], actual["total"], actual["pct"], actual["pendientes"]) == (0, 1, 0.0, ["CER001"])


def test_kpi01_vista_tiene_selector_de_periodo_y_grafico():
    import os
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html = open(os.path.join(raiz, "templates", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(raiz, "static", "js", "modulo_kpis.js"), encoding="utf-8").read()
    assert 'id="kpi01_periodo"' in html and 'id="canvasKpi01_meses"' in html
    assert "aplicarPeriodoKpi01" in js and "renderChartKpi01Meses" in js
