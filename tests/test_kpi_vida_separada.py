"""KPI 13 y 14: originales por marca de la carcasa y reencauches solo por su banda (nunca mezclados)."""
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
    # Carcasa de la misma marca reencauchada con banda DVRT: 10.000 km, 16 -> 11 mm -> 2.000 km/mm
    _insp("CLI VIDA", "VID002", "V-2", kilometraje=110000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=16, precio=700000, vida="R1", banda_reen="DVRT")


def test_kpi13_separa_originales_y_reencauches(test_db):
    _sembrar()
    k13 = database.obtener_suite_completa_20_kpis({"cliente": "CLI VIDA"})["kpi_13"]
    pv = k13["por_vida"]
    i, j = pv["labels"].index("MICHELIN"), pv["labels"].index("DVRT")
    # La carcasa MICHELIN solo con su ciclo original; la reencauchada sale como su banda
    assert pv["llantas"]["original"][i] == 1 and pv["llantas"]["reencauche"][i] == 0
    assert pv["original"]["km_reales"][i] == 50000
    assert pv["llantas"]["reencauche"][j] == 1 and pv["llantas"]["original"][j] == 0
    assert pv["reencauche"]["km_reales"][j] == 10000
    # Las cifras que usa el PDF tampoco mezclan carcasa y banda
    assert k13["km_reales"][k13["labels"].index("MICHELIN")] == 50000
    assert k13["km_reales"][k13["labels"].index("DVRT")] == 10000


def test_kpi14_separa_originales_y_reencauches(test_db):
    _sembrar()
    k14 = database.obtener_suite_completa_20_kpis({"cliente": "CLI VIDA", "agrupar_kpi14": "marca"})["kpi_14"]
    pv = k14["por_vida"]
    i, j = pv["labels"].index("MICHELIN"), pv["labels"].index("DVRT")
    assert round(pv["original"]["km_mm"][i], 1) == 5000.0
    assert pv["reencauche"]["km_mm"][i] is None
    assert round(pv["reencauche"]["km_mm"][j], 1) == 2000.0
    assert "MICHELIN" in k14["labels"] and "DVRT" in k14["labels"]
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


def test_referencia_originales_por_marca_diseno_medida_y_eje(test_db):
    _cfg("CLI REF", psi_objetivo_traccion=100.0)
    _insp("CLI REF", "REF001", "R-1", posicion=1, kilometraje=150000, km_montaje=100000, prof_ext=11, prof_cent=11,
          prof_int=11, prof_inicial=21, precio=1800000, marca="HANKOOK", diseno="AM09")
    _insp("CLI REF", "REF001", "R-2", posicion=5, kilometraje=150000, km_montaje=100000, prof_ext=11, prof_cent=11,
          prof_int=11, prof_inicial=21, precio=1800000, marca="HANKOOK", diseno="AM09")
    pr = database.obtener_suite_completa_20_kpis({"cliente": "CLI REF"})["kpi_14"]["por_referencia"]
    claves = {(f["marca"], f["diseno"], f["dimension"], f["eje"]) for f in pr["originales"]}
    # La misma referencia en dirección y en tracción va en filas distintas
    assert ("HANKOOK", "AM09", "295/80R22.5", "Direccional") in claves
    assert ("HANKOOK", "AM09", "295/80R22.5", "Tracción") in claves
    assert pr["reencauches"] == []


def test_referencia_reencauche_agrupa_la_banda_sin_importar_la_carcasa(test_db):
    _cfg("CLI BAN2", psi_objetivo_traccion=100.0)
    for i, carcasa in enumerate(["DOUBLE COIN", "HANKOOK", "JK TYRE"]):
        _insp("CLI BAN2", f"BB{i:04d}", f"BB-{i}", kilometraje=120000, km_montaje=100000, prof_ext=12, prof_cent=12,
              prof_int=12, prof_inicial=16, precio=600000, vida="R1", banda_reen="BANDAG BDM", marca=carcasa)
    # Misma banda en otra medida: fila aparte
    _insp("CLI BAN2", "BB0009", "BB-9", kilometraje=110000, km_montaje=100000, prof_ext=12, prof_cent=12, prof_int=12,
          prof_inicial=16, precio=600000, vida="R1", banda_reen="BANDAG BDM", dimension="315/80R22.5")
    pr = database.obtener_suite_completa_20_kpis({"cliente": "CLI BAN2"})["kpi_14"]["por_referencia"]
    filas = {(f["banda"], f["dimension"]): f for f in pr["reencauches"]}
    f295 = filas[("BANDAG BDM", "295/80R22.5")]
    assert f295["llantas"] == 3 and f295["carcasas"] == ["DOUBLE COIN", "HANKOOK", "JK TYRE"]
    assert f295["km_reales"] == 20000
    assert filas[("BANDAG BDM", "315/80R22.5")]["llantas"] == 1
    assert pr["originales"] == []


def test_modulo_c_resistencia_de_carcasas_por_marca_y_medida(test_db):
    _cfg("CLI CARC", psi_objetivo_traccion=100.0)
    # Tres carcasas DOUBLE COIN 295: una sigue en uso en R1, dos se dieron de baja (una en R2, otra en R3)
    _insp("CLI CARC", "CAR001", "C-1", vida="R1", banda_reen="BANDAG BDM", marca="DOUBLE COIN", precio=600000)
    _insp("CLI CARC", "CAR002", "C-2", marca="DOUBLE COIN", precio=1500000)
    _insp("CLI CARC", "CAR003", "C-3", marca="DOUBLE COIN", precio=1500000)
    # Una HANKOOK 315 nueva
    _insp("CLI CARC", "CAR004", "C-4", marca="HANKOOK", dimension="315/80R22.5", precio=1700000)
    with database.get_connection() as conn:
        conn.execute("UPDATE llantas_maestro SET ubicacion_bodega='BODEGA_6_FVU', causal_baja_fvu='Fatiga de costados', num_reencauches=2 WHERE numero_interno='C-2'")
        conn.execute("UPDATE llantas_maestro SET ubicacion_bodega='BODEGA_6_FVU', causal_baja_fvu='Fatiga de costados', num_reencauches=3 WHERE numero_interno='C-3'")
        conn.commit()
    filas = database.obtener_suite_completa_20_kpis({"cliente": "CLI CARC", "base": "historial"})["kpi_18"]["carcasas"]
    dc = next(f for f in filas if f["marca"] == "DOUBLE COIN" and f["dimension"] == "295/80R22.5")
    assert dc["carcasas"] == 3
    assert dc["reencauches_por_carcasa"] == 2.0          # (1 + 2 + 3) / 3
    assert dc["bajas"] == 2 and dc["reencauches_al_baja"] == 2.5
    assert dc["ciclos"] == {"Original": 0, "R1": 1, "R2": 1, "R3+": 1}
    assert dc["causa_principal"] == "Fatiga de costados" and dc["causa_pct"] == 100.0
    hk = next(f for f in filas if f["marca"] == "HANKOOK")
    assert hk["dimension"] == "315/80R22.5" and hk["reencauches_por_carcasa"] == 0 and hk["bajas"] == 0
    # La marca que más reencauches aguanta va primero
    assert filas[0]["marca"] == "DOUBLE COIN"


def test_reencauches_de_una_banda_juntan_todas_sus_vidas(test_db):
    _cfg("CLI JUNTA", psi_objetivo_traccion=100.0)
    _insp("CLI JUNTA", "JUN001", "J-1", kilometraje=110000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=16, precio=700000, vida="R1", banda_reen="DVRT", marca="DOUBLE COIN")
    _insp("CLI JUNTA", "JUN002", "J-2", kilometraje=130000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=16, precio=700000, vida="R2", banda_reen="DVRT", marca="HANKOOK")
    k13 = database.obtener_suite_completa_20_kpis({"cliente": "CLI JUNTA"})["kpi_13"]
    pv = k13["por_vida"]
    assert pv["labels"] == ["DVRT"]                      # ni DOUBLE COIN ni HANKOOK
    assert pv["llantas"]["reencauche"] == [2]
    assert pv["reencauche"]["km_reales"] == [20000]       # (10.000 + 30.000) / 2


def test_carcasas_muestran_km_por_vida_y_de_toda_la_vida(test_db):
    _cfg("CLI KMV", psi_objetivo_traccion=100.0)
    _insp("CLI KMV", "KMV001", "K-1", fecha="2026-01-10", kilometraje=100000, km_montaje=100000, marca="DOUBLE COIN", precio=1500000)
    _insp("CLI KMV", "KMV001", "K-1", fecha="2026-05-10", kilometraje=160000, km_montaje=100000, marca="DOUBLE COIN",
          prof_ext=6, prof_cent=6, prof_int=6, precio=1500000)
    _insp("CLI KMV", "KMV002", "K-1", fecha="2026-06-10", kilometraje=200000, km_montaje=200000, marca="DOUBLE COIN",
          vida="R1", banda_reen="DVRT", prof_inicial=16, prof_ext=16, prof_cent=16, prof_int=16, precio=600000)
    _insp("CLI KMV", "KMV002", "K-1", fecha="2026-09-10", kilometraje=240000, km_montaje=200000, marca="DOUBLE COIN",
          vida="R1", banda_reen="DVRT", prof_inicial=16, prof_ext=9, prof_cent=9, prof_int=9, precio=600000)
    filas = database.obtener_suite_completa_20_kpis({"cliente": "CLI KMV", "base": "historial"})["kpi_18"]["carcasas"]
    dc = next(f for f in filas if f["marca"] == "DOUBLE COIN")
    assert dc["km_por_vida"] == {"Original": 60000, "R1": 40000}
    assert dc["km_vida_promedio"] == 100000
