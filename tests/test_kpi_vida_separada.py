"""KPI 13 y 14: originales y reencauches se muestran por separado (no en un mismo promedio por marca)."""
import database


def _insp(cliente, placa, sn, fecha="2026-10-10", **extra):
    d = {"fecha": fecha, "cliente": cliente, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": placa,
         "posicion": 5, "kilometraje": 10000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
         "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 12, "prof_cent": 12, "prof_int": 12, "psi": 100,
         "prof_inicial": 21.5, "numero_interno": sn}
    d.update(extra)
    return database.insertar_inspeccion(d)


def _cfg(cliente, **campos):
    database.guardar_licencia_cliente(cliente, "PRO")
    with database.get_connection() as conn:
        for k, v in campos.items():
            conn.execute(f"UPDATE configuracion_avanzada_cliente SET {k} = ? WHERE cliente = ?", (v, cliente))
        conn.commit()


def _sembrar():
    _cfg("CLI VIDA", psi_objetivo_traccion=100.0)
    # Original: 50.000 km, 21 -> 11 mm -> 5.000 km/mm
    _insp("CLI VIDA", "VID001", "V-1", kilometraje=150000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=21, precio=1800000)
    # Reencauche de la misma marca: 10.000 km, 16 -> 11 mm -> 2.000 km/mm
    _insp("CLI VIDA", "VID002", "V-2", kilometraje=110000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=16, precio=700000, vida="R1")


def test_kpi13_separa_originales_y_reencauches(test_db):
    _sembrar()
    k13 = database.obtener_suite_completa_20_kpis({"cliente": "CLI VIDA"})["kpi_13"]
    pv = k13["por_vida"]
    i = pv["labels"].index("MICHELIN")
    assert pv["llantas"]["original"][i] == 1 and pv["llantas"]["reencauche"][i] == 1
    assert pv["original"]["km_reales"][i] == 50000
    assert pv["reencauche"]["km_reales"][i] == 10000
    # Las cifras de siempre (mezcladas) se conservan para el PDF
    assert k13["km_reales"][k13["labels"].index("MICHELIN")] == 30000


def test_kpi14_separa_originales_y_reencauches(test_db):
    _sembrar()
    k14 = database.obtener_suite_completa_20_kpis({"cliente": "CLI VIDA", "agrupar_kpi14": "marca"})["kpi_14"]
    pv = k14["por_vida"]
    i = pv["labels"].index("MICHELIN")
    assert round(pv["original"]["km_mm"][i], 1) == 5000.0
    assert round(pv["reencauche"]["km_mm"][i], 1) == 2000.0
    assert len(pv["labels"]) == len(pv["original"]["cpk"]) == len(pv["reencauche"]["cpk"])


def test_marca_sin_reencauches_queda_vacia_en_esa_vida(test_db):
    _cfg("CLI SOLO", psi_objetivo_traccion=100.0)
    _insp("CLI SOLO", "SOL001", "S-1", kilometraje=150000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=21, precio=1800000)
    pv = database.obtener_suite_completa_20_kpis({"cliente": "CLI SOLO"})["kpi_13"]["por_vida"]
    i = pv["labels"].index("MICHELIN")
    assert pv["llantas"]["reencauche"][i] == 0
    assert pv["reencauche"].get("km_reales", [None])[i] is None


def test_reencauches_por_banda_con_referencia_original(test_db):
    _cfg("CLI BANDA", psi_objetivo_traccion=100.0)
    # Original: 50.000 km, 10 mm gastados -> 5.000 km/mm
    _insp("CLI BANDA", "BAN001", "B-1", kilometraje=150000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=21, precio=1800000)
    # Banda buena: 20.000 km, 4 mm -> 5.000 km/mm
    _insp("CLI BANDA", "BAN002", "B-2", kilometraje=120000, km_montaje=100000, prof_ext=12, prof_cent=12, prof_int=12,
          prof_inicial=16, precio=600000, vida="R1", banda_reen="bandag bdm")
    # Banda floja: 10.000 km, 4 mm -> 2.500 km/mm
    _insp("CLI BANDA", "BAN003", "B-3", kilometraje=110000, km_montaje=100000, prof_ext=12, prof_cent=12, prof_int=12,
          prof_inicial=16, precio=600000, vida="R1", banda_reen="VIPAL VT")
    pb = database.obtener_suite_completa_20_kpis({"cliente": "CLI BANDA"})["kpi_14"]["por_banda"]
    bandas = {f["banda"]: f for f in pb["filas"]}
    assert set(bandas) == {"BANDAG BDM", "VIPAL VT"}
    assert bandas["BANDAG BDM"]["km_mm"] == 5000.0 and bandas["VIPAL VT"]["km_mm"] == 2500.0
    # La más barata por km va primero
    assert pb["filas"][0]["banda"] == "BANDAG BDM"
    assert pb["filas"][0]["cpk"] < pb["filas"][1]["cpk"]
    # Referencia: la llanta original de la misma base
    assert pb["original"]["llantas"] == 1 and pb["original"]["km_mm"] == 5000.0
    assert pb["reencauches_sin_banda"] == 0
