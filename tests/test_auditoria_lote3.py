"""Auditoría 2026-11-09, lote 3: una sola regla por cálculo (H-06, H-07, H-08, H-09, H-10, H-11, H-27, H-29, H-30, H-31)."""
import os

import pandas as pd
import pytest

import database
import estructura_ejes as ee

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(rel):
    return open(os.path.join(RAIZ, rel), encoding="utf-8").read()


# --- H-06: semáforo único ------------------------------------------------------------------
@pytest.mark.parametrize("pb, limite, rango, esperado", [
    (4.04, 4.0, 2.0, "amarillo"),   # antes el mapa redondeaba a 4,0 y salía ROJO
    (4.0, 4.0, 2.0, "rojo"),
    (6.0, 4.0, 2.0, "amarillo"),
    (6.01, 4.0, 2.0, "verde"),
    (6.5, 4.0, 3.0, "amarillo"),    # rango amarillo configurado por el cliente
    (0.0, 4.0, 2.0, "gris"),        # sin medición: no es retiro
    (None, 4.0, 2.0, "gris"),
])
def test_h06_evaluar_semaforo(pb, limite, rango, esperado):
    assert database.evaluar_semaforo(pb, limite, rango) == esperado


def test_h06_mapa_de_semaforos_no_redondea_antes_de_comparar(test_db):
    df = pd.DataFrame([{"id": 1, "fecha": "2026-10-01", "placa": "SEM001", "posicion": 3, "cliente": "CLI SEM",
                        "subcliente": "", "tipologia": "", "tipo_operacion": "", "kilometraje": 1000,
                        "prof_ext": 0.0, "prof_cent": 0.0, "prof_int": 0.0, "numero_interno": "S-1"}])
    res = database.calcular_matriz_semaforos_posicion(df)
    assert res["resumen_global"]["gris"] == 1 and res["resumen_global"]["rojo"] == 0  # 0 mm = sin dato
    lim = res["filas"][0]["posiciones"][3]["limite"]  # límite que aplica a esa posición
    df.loc[0, ["prof_ext", "prof_cent", "prof_int"]] = [lim + 0.04] * 3  # se mostraría como el límite al redondear
    res = database.calcular_matriz_semaforos_posicion(df)
    celda = res["filas"][0]["posiciones"][3]
    assert celda["color"] == "amarillo" and res["resumen_global"]["rojo"] == 0


def test_h06_conteos_de_retiro_excluyen_profundidad_cero():
    df = pd.DataFrame({"calc_p_min": [0.0, 2.5, 4.0], "calc_lim_retiro": [3.0, 3.0, 3.0]})
    assert list(database.en_retiro_mask(df)) == [False, True, False]
    src = _leer("database.py")
    assert "['calc_p_min'] <= df_patio['calc_lim_retiro']" not in src
    assert "+ 2.0)" not in src.split("def evaluar_semaforo")[1].split("def _redondear")[0]


# --- H-07: el CPK usa el precio más reciente --------------------------------------------------
def test_h07_cpk_con_el_precio_mas_reciente():
    d = pd.DataFrame([
        {"id": 1, "fecha": "2026-08-01", "cliente": "CLI CPK", "subcliente": "", "placa": "CPK001", "posicion": 3,
         "numero_interno": "N-CPK", "vida": "Original", "kilometraje": 10000, "km_montaje": 10000, "precio": 1000000,
         "prof_ext": 16, "prof_cent": 16, "prof_int": 16, "prof_inicial": 16, "marca": "M", "diseno": "D",
         "dimension": "295/80R22.5", "tipologia": ""},
        {"id": 2, "fecha": "2026-10-01", "cliente": "CLI CPK", "subcliente": "", "placa": "CPK001", "posicion": 3,
         "numero_interno": "N-CPK", "vida": "Original", "kilometraje": 40000, "km_montaje": 10000, "precio": 1300000,
         "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "prof_inicial": 16, "marca": "M", "diseno": "D",
         "dimension": "295/80R22.5", "tipologia": ""},
    ])
    vida = database.calcular_cpk_llantas(d)["llantas"]["CLI CPK|N-CPK"]["vidas"]["Original"]
    assert vida["costo"] == 1300000
    assert vida["cpk_operativo"] == pytest.approx(1300000 / 30000)


# --- H-08 / H-29: «sin dato» en vez de 0 -------------------------------------------------------
def _insp(placa, sn, **campos):
    base = {"fecha": "2026-10-01", "cliente": "CLI TRZ", "subcliente": "S", "placa": placa, "posicion": 3,
            "numero_interno": sn, "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5", "vida": "Original",
            "kilometraje": 40000, "km_montaje": 10000, "prof_ext": 10, "prof_cent": 10, "prof_int": 10,
            "prof_inicial": 16, "precio": 1200000}
    base.update(campos)
    database.insertar_inspeccion(base)


def test_h08_trazabilidad_sin_dato_en_vez_de_cero(test_db):
    _insp("TRZ001", "T-SIN-INI", prof_inicial=0, precio=0)
    _insp("TRZ002", "T-POCO", prof_ext=15.7, prof_cent=15.7, prof_int=15.7)   # 0,3 mm: aún sin madurez
    _insp("TRZ003", "T-OK")                                                     # 6 mm y 30.000 km
    filas = {f["numero_interno"]: f for f in database.obtener_trazabilidad_kpis_llanta("T-", {})}
    sin_ini = filas["T-SIN-INI"]
    for campo in ("desgaste_mm", "porcentaje_desgaste", "km_por_mm", "cpk", "proyeccion_total_km", "km_restantes", "cpk_proyectado"):
        assert sin_ini[campo] is None, campo
    assert filas["T-POCO"]["km_por_mm"] is None and filas["T-POCO"]["proyeccion_total_km"] is None  # umbral 0,5 mm
    ok = filas["T-OK"]
    assert ok["km_por_mm"] == pytest.approx(5000.0) and ok["cpk"] == pytest.approx(1200000 / 30000, rel=1e-3)


def test_h29_inicial_en_o_bajo_el_limite_es_sin_dato(test_db):
    _insp("TRZ004", "T-BAJO", prof_inicial=2.5, prof_ext=2.2, prof_cent=2.2, prof_int=2.2)
    fila = database.obtener_trazabilidad_kpis_llanta("T-BAJO", {})[0]
    assert fila["porcentaje_desgaste"] is None and fila["proyeccion_total_km"] is None
    assert "max(1.0, p_ini" not in _leer("database.py")


# --- H-09: CPK administrativo por mes calendario ----------------------------------------------
def test_h09_recorrido_repartido_por_meses_calendario():
    d = pd.DataFrame([
        {"_cli": "CLI ADM", "fecha": "2026-08-15", "placa": "ADM001", "kilometraje": 10000},
        {"_cli": "CLI ADM", "fecha": "2026-10-15", "placa": "ADM001", "kilometraje": 40000},
    ])
    serie = {m["mes"]: m for m in database._cpk_administrativo(d)}
    assert list(serie) == ["2026-08", "2026-09", "2026-10"]  # septiembre aparece aunque no tenga datos
    assert serie["2026-09"]["km_flota"] == 15000 and serie["2026-10"]["km_flota"] == 15000  # antes octubre = 30.000


# --- H-10: KPI 11 y KPI 06 sobre el corte vigente ----------------------------------------------
def test_h10_totales_sobre_el_corte_vigente():
    src = _leer("database.py")
    assert "_perdidas_corte(df_corte if not df.empty else None)" in src
    kpi06 = src[src.index("# KPI 06: Alineación en el eje direccional"):src.index("kpi_06 = {")]
    assert "for pl, grp_p in df_corte.groupby('placa')" in kpi06


# --- H-11: hoja de vida sin divisores ni profundidades supuestas -------------------------------
def test_h11_hoja_de_vida_sin_valores_supuestos():
    src = _leer("modulo_bodegas_taller.py")
    hv = src[src.index("cpk_global = "):src.index("# Timeline formateado")]
    assert "max(1.0" not in hv and "16.0" not in hv and ", 3.0)" not in hv
    assert "cpk_global = round(costo_total / km_totales, 4) if (costo_total > 0 and km_totales > 0) else None" in hv


# --- H-27: alineación solo en dirección, por hombros o «hombro caído» --------------------------
@pytest.mark.parametrize("eje, pe, pi, nov, esperado", [
    (ee.DIRECCIONAL, 12.0, 10.0, "", True),            # 2,0 mm = tolerancia
    (ee.DIRECCIONAL, 12.0, 10.5, "", False),
    (ee.DIRECCIONAL, 12.0, 12.0, "Hombros caídos lado externo", True),
    (ee.DIRECCIONAL, 12.0, 12.0, "HOMBRO CAIDO", True),
    (ee.LIBRE, 12.0, 8.0, "", False),                  # antes los ejes libres también alertaban
    (ee.TRACCION, 12.0, 12.0, "hombro caído", False),
])
def test_h27_regla_de_alineacion(eje, pe, pi, nov, esperado):
    assert database.alerta_alineacion(eje, pe, pi, nov, 2.0) is esperado


def test_h27_no_compara_izquierda_con_derecha():
    est = ee.EstructuraVehiculo([{"eje": 1, "tipo": "DIRECCIONAL", "posiciones": [{"pos": 1}, {"pos": 2}]},
                                 {"eje": 2, "tipo": "LIBRE", "posiciones": [{"pos": 3}, {"pos": 4}]}])
    assert est.posiciones_alineacion() == [1, 2]
    assert "hombro caído" in _leer("docs/REGLAS_NEGOCIO.md")


# --- H-30: duales con >= y el umbral del cliente ------------------------------------------------
def test_h30_duales_mayor_o_igual_y_texto_con_el_valor_real():
    src, js, pdf = _leer("database.py"), _leer("static/js/modulo_kpis.js"), _leer("pdf_kpis.py")
    assert "if diff_pb >= tol_dual:" in src and "abs(a_val - b_val) >= tol_apareo" in src
    assert '"tolerancia_mm": tol_apareo' in src
    assert "desbalance &gt; 3 mm" not in js and "d.tolerancia_mm" in js
    assert "> 2,5 mm" not in pdf and "más de 3 mm" not in pdf


# --- H-31: una sola agregación para el KPI 14 ---------------------------------------------------
def test_h31_agregacion_suma_sobre_suma():
    grp = pd.DataFrame({"calc_km_mm": [5000.0, 2000.0, None], "calc_km_rodados": [30000.0, 2000.0, 500.0],
                        "calc_desgaste_mm": [6.0, 1.0, 0.1], "calc_cpk": [20.0, 50.0, None],
                        "calc_precio": [1200000.0, 1000000.0, 900000.0], "calc_proy_total": [60000.0, 20000.0, None]})
    km_mm, cpk = database.agregar_rendimiento_y_cpk(grp)
    assert km_mm == pytest.approx(32000 / 7)            # Σkm / Σmm, no el promedio 3.500
    assert cpk == pytest.approx(2200000 / 80000)        # Σprecio / Σproyección, no el promedio 35
    assert "tot.get('cpk')" in _leer("pdf_kpis.py")
