"""Auditoría 2026-11-09, lote 5: rendimiento de la suite de KPI (H-26)."""
import sqlite3

import pandas as pd

import database


def _contador_conexiones(monkeypatch):
    cuenta = {"n": 0}
    original = sqlite3.connect

    def contar(*a, **k):
        cuenta["n"] += 1
        return original(*a, **k)

    monkeypatch.setattr(database.sqlite3, "connect", contar)
    return cuenta


def _sembrar(n_placas=6):
    for i in range(n_placas):
        for mes, km, prof in (("2026-08-10", 10000, 14), ("2026-09-10", 20000, 12), ("2026-10-10", 30000, 10)):
            for pos in (1, 2, 3, 4, 5, 6):
                database.insertar_inspeccion({
                    "fecha": mes, "cliente": "CLI PERF" if i % 2 else "CLI RAPIDO", "subcliente": "S", "placa": f"PRF{i:03d}",
                    "posicion": pos, "numero_interno": f"N-{i}-{pos}", "marca": "MICHELIN", "diseno": "XZE",
                    "dimension": "295/80R22.5", "vida": "Original", "kilometraje": km, "km_montaje": 10000,
                    "prof_ext": prof, "prof_cent": prof, "prof_int": prof - (0.5 if pos == 4 else 0), "prof_inicial": 16,
                    "precio": 1200000, "psi": 110, "tipologia": "Cabezote (6x4)"})


def test_memoria_de_consulta_lee_una_vez_y_entrega_copias(test_db, monkeypatch):
    cuenta = _contador_conexiones(monkeypatch)
    with database.memoria_de_consulta():
        a = database.obtener_configuracion_avanzada_cliente("CLI X")
        a["tolerancia_alineacion_mm"] = -99            # quien modifica su copia no altera la guardada
        b = database.obtener_configuracion_avanzada_cliente("CLI X")
    assert cuenta["n"] == 1 and b.get("tolerancia_alineacion_mm") != -99
    cuenta["n"] = 0
    database.obtener_configuracion_avanzada_cliente("CLI X")
    database.obtener_configuracion_avanzada_cliente("CLI X")
    assert cuenta["n"] == 2                            # fuera del cálculo no hay memoria: Catálogos se ve al instante


def test_suite_abre_pocas_conexiones(test_db, monkeypatch):
    _sembrar()
    cuenta = _contador_conexiones(monkeypatch)
    res = database.obtener_suite_completa_20_kpis({})
    assert res["kpi_01"]["vehiculos_inspeccionados"] == 6
    assert cuenta["n"] <= 20, cuenta["n"]              # antes 53 con la base de la auditoría


def test_tendencias_no_calculan_el_cpk_administrativo():
    df = pd.DataFrame([{"id": 1, "fecha": "2026-10-01", "cliente": "C", "subcliente": "", "placa": "P1", "posicion": 3,
                        "numero_interno": "N1", "vida": "Original", "kilometraje": 40000, "km_montaje": 10000,
                        "precio": 1000000, "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "prof_inicial": 16,
                        "marca": "M", "diseno": "D", "dimension": "295/80R22.5", "tipologia": ""}])
    assert database.calcular_cpk_llantas(df, incluir_administrativo=False)["administrativo"] == []
    assert database.calcular_cpk_llantas(df)["flota"] == database.calcular_cpk_llantas(df, incluir_administrativo=False)["flota"]


def test_duales_y_cpk_sin_iterrows_por_grupo():
    src = open(database.__file__, encoding="utf-8").read()
    duales = src[src.index("def _duales_desapareados(grp_v):"):src.index("desapareos_mes = []")]
    assert ".iterrows()" not in duales and "to_dict('records')" not in duales
    cpk = src[src.index("def calcular_cpk_llantas("):src.index("def _cpk_administrativo(")]
    assert "g.iloc[0]" not in cpk
