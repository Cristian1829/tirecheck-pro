"""Parque automotor por cliente cargado por el administrador: reemplaza el parque, mide el % de inspección
del KPI 01 y de las tendencias mes a mes, y sin archivo cargado todo sigue como antes."""
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import database
import server

CLI = "FLOTA PARQUE"


def _tipologia():
    with database.get_connection() as conn:
        return conn.execute("SELECT nombre FROM catalogo_tipologias ORDER BY nombre LIMIT 1").fetchone()[0]


def _excel(tmp_path, filas, nombre="parque.xlsx"):
    ruta = tmp_path / nombre
    pd.DataFrame(filas).to_excel(ruta, index=False)
    return str(ruta)


def _insp(placa, fecha, tip):
    assert database.insertar_inspeccion({
        "fecha": fecha, "cliente": CLI, "subcliente": "SEDE UNO", "tipo_operacion": "CARGA", "placa": placa,
        "posicion": 1, "kilometraje": 50000, "tipologia": tip, "marca": "MICHELIN", "diseno": "X MULTI D",
        "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10, "prof_int": 10,
        "psi": 100, "prof_inicial": 21.5, "numero_interno": f"SN-{placa}-{fecha}"})


def _parque(tmp_path, placas, tip):
    filas = [{"Placa / N° interno": p, "Tipología": tip, "Km actual": 100000 + i, "Fabricante": "KENWORTH",
              "Línea": "T800"} for i, p in enumerate(placas)]
    return database.importar_padron_cliente_excel(_excel(tmp_path, filas), CLI)


def test_archivo_reemplaza_el_parque(test_db, tmp_path):
    tip = _tipologia()
    # Antes del archivo el parque se arma solo con lo inspeccionado (origen 'auto')
    for p in ("OLD1", "OLD2", "AAA001"):
        _insp(p, "2026-09-05", tip)
    with database.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO padron_vehiculos_cliente (cliente, subcliente, placa, tipologia) "
                     "SELECT DISTINCT cliente, subcliente, placa, tipologia FROM inspecciones")
        conn.commit()
    assert not database.cliente_tiene_parque_cargado(CLI)

    res = _parque(tmp_path, [f"AAA{i:03d}" for i in range(1, 11)], tip)
    assert (res["nuevos"], res["actualizados"], res["desactivados"]) == (9, 1, 2)
    assert database.cliente_tiene_parque_cargado(CLI)
    lista = database.listar_padron_cliente(CLI)
    activos = {v["placa"] for v in lista if v["activo"]}
    assert len(activos) == 10 and "OLD1" not in activos
    assert {v["placa"] for v in lista if not v["activo"]} == {"OLD1", "OLD2"}
    v1 = next(v for v in lista if v["placa"] == "AAA001")
    assert v1["fabricante"] == "KENWORTH" and v1["linea"] == "T800" and v1["ultima_inspeccion"] == "2026-09-05"
    # La tipología y el km quedan en el catálogo para la inspección
    with database.get_connection() as conn:
        assert conn.execute("SELECT tipologia FROM catalogo_vehiculos WHERE placa = 'AAA005'").fetchone()[0] == tip.upper()


def test_errores_por_fila_no_detienen_el_cargue(test_db, tmp_path):
    tip = _tipologia()
    filas = [
        {"Placa / N° interno": "BBB001", "Tipología": tip, "Línea": 4300},
        {"Placa / N° interno": "BBB002", "Tipología": ""},
        {"Placa / N° interno": "BBB003", "Tipología": "NO EXISTE"},
        {"Placa / N° interno": "bbb001 ", "Tipología": tip},
        {"Placa / N° interno": 101.0, "Tipología": tip.lower()},
    ]
    res = database.importar_padron_cliente_excel(_excel(tmp_path, filas), CLI)
    assert res["nuevos"] == 2 and res["total_errores"] == 3
    assert any("sin tipología" in e for e in res["errores"])
    assert any("NO EXISTE" in e for e in res["errores"])
    assert any("repetida" in e for e in res["errores"])
    # Los números internos que Excel lee como 101.0 quedan como "101"
    lista = database.listar_padron_cliente(CLI)
    assert {v["placa"] for v in lista} == {"BBB001", "101"}
    # La línea numérica de Excel no queda como "4300.0"
    assert next(v for v in lista if v["placa"] == "BBB001")["linea"] == "4300"


def test_archivo_sin_columnas_obligatorias(test_db, tmp_path):
    with pytest.raises(ValueError):
        database.importar_padron_cliente_excel(_excel(tmp_path, [{"Placa": "X1"}]), CLI)
    with pytest.raises(ValueError):
        database.importar_padron_cliente_excel(_excel(tmp_path, [{"Placa": "X1", "Tipología": _tipologia()}]), "")


def test_kpi01_y_tendencias_con_parque_cargado(test_db, tmp_path):
    tip = _tipologia()
    database.guardar_licencia_cliente(CLI, "LIGHT")
    _parque(tmp_path, [f"CCC{i:03d}" for i in range(1, 11)], tip)
    for p in ("CCC001", "CCC002", "CCC003", "CCC004", "FUERA01"):
        _insp(p, "2026-10-08", tip)
    for p in ("CCC001", "CCC002"):
        _insp(p, "2026-09-08", tip)

    s = database.obtener_suite_completa_20_kpis({"cliente": CLI, "fecha_desde": "2026-10-01", "fecha_hasta": "2026-10-31"})
    assert s["licencia"] == "LIGHT"
    k = s["kpi_01"]
    assert k["disponible"] and k["parque_cargado"]
    assert (k["vehiculos_inspeccionados"], k["total_padron_activo"], k["porcentaje_cumplimiento"]) == (4, 10, 40.0)
    assert len(k["placas_pendientes"]) == 6 and k["placas_inspeccionadas_fuera_padron"] == 1
    p5 = next(p for p in k["placas_pendientes"] if p["placa"] == "CCC005")
    assert p5["fabricante"] == "KENWORTH" and p5["ultima_inspeccion"] == ""

    todo = database.obtener_suite_completa_20_kpis({"cliente": CLI})
    meses = {m["mes"]: m for m in todo["kpi_tendencias"]["meses"]}
    assert meses["2026-09"]["pct_cumplimiento_parque"] == 20.0
    assert meses["2026-10"]["pct_cumplimiento_parque"] == 40.0


def test_sin_parque_cargado_funciona_como_antes(test_db):
    tip = _tipologia()
    database.guardar_licencia_cliente(CLI, "LIGHT")
    _insp("DDD001", "2026-10-08", tip)
    s = database.obtener_suite_completa_20_kpis({"cliente": CLI})
    assert not s["kpi_01"]["disponible"] and not s["kpi_01"]["parque_cargado"]
    assert all("pct_cumplimiento_parque" not in m for m in s["kpi_tendencias"]["meses"])


def test_pdf_kpis_con_parque(test_db, tmp_path):
    import pdf_kpis
    tip = _tipologia()
    _parque(tmp_path, [f"EEE{i:03d}" for i in range(1, 6)], tip)
    _insp("EEE001", "2026-10-08", tip)
    datos = database.obtener_suite_completa_20_kpis({"cliente": CLI})
    assert pdf_kpis.generar_pdf_kpis(datos, {}, {"cliente": CLI}).startswith(b"%PDF")


def test_endpoints_solo_admin(test_db, tmp_path, auth_client, inspector_token):
    tip = _tipologia()
    ruta = _excel(tmp_path, [{"Placa / N° interno": "FFF001", "Tipología": tip}])
    plantilla = auth_client.get("/api/padron/plantilla-excel")
    assert plantilla.status_code == 200 and plantilla.content[:2] == b"PK"
    with open(ruta, "rb") as fh:
        r = auth_client.post(f"/api/padron/importar-excel?cliente={CLI}",
                             files={"file": ("parque.xlsx", fh, "application/vnd.ms-excel")})
    assert r.status_code == 200 and r.json()["nuevos"] == 1
    lista = auth_client.get(f"/api/padron?cliente={CLI}").json()
    assert lista["parque_cargado"] and lista["vehiculos"][0]["placa"] == "FFF001"
    assert auth_client.get(f"/api/padron/exportar-excel?cliente={CLI}").status_code == 200

    otro = TestClient(server.app)
    otro.headers.update({"Authorization": f"Bearer {inspector_token}"})
    assert otro.get(f"/api/padron?cliente={CLI}").status_code == 403
    assert otro.get("/api/padron/plantilla-excel").status_code == 403
    with open(ruta, "rb") as fh:
        assert otro.post(f"/api/padron/importar-excel?cliente={CLI}",
                         files={"file": ("parque.xlsx", fh, "application/vnd.ms-excel")}).status_code == 403
