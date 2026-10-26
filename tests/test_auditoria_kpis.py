"""Auditoría, bloque 5: ajustes de KPI."""
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


# --- #32: las etiquetas de presión dicen la tolerancia que realmente se aplica --------------------
def test_32_etiquetas_psi_con_tolerancia_del_cliente(test_db):
    _cfg("CLI PSI", tolerancia_psi_baja_pct=10.0, tolerancia_psi_alta_pct=10.0, psi_objetivo_traccion=100.0)
    _insp("CLI PSI", "PSI001", "P-1", psi=92)          # -8 %: dentro de la tolerancia del 10 %
    k9 = database.obtener_suite_completa_20_kpis({"cliente": "CLI PSI"})["kpi_09"]
    i_ok = k9["valores"].index(1)
    assert k9["labels"][i_ok] == "Correcta (-10% a +10%)"          # antes decía "Correcta (±5%)"
    assert "Baja Moderada (-15% a -10%)" in k9["labels"]


# --- #31: KPI 01 sin padrón ni inspecciones no es 100 % ---------------------------------------------
def test_31_cumplimiento_sin_padron(test_db):
    _cfg("CLI VACIO")
    k1 = database.obtener_suite_completa_20_kpis({"cliente": "CLI VACIO"})["kpi_01"]
    assert k1["cumplimiento_pct"] is None and k1["fuente_padron"] == "sin_padron"   # antes: 100 %
    _cfg("CLI SINPAD")
    _insp("CLI SINPAD", "SP0001", "SP-1")
    k1 = database.obtener_suite_completa_20_kpis({"cliente": "CLI SINPAD"})["kpi_01"]
    assert k1["fuente_padron"] == "vehiculos_inspeccionados"   # se avisa que no es un padrón cargado


# --- #33: la meta de reencauche es la del cliente ----------------------------------------------------
def test_33_meta_reencauche_del_cliente(test_db):
    _cfg("CLI META")
    database.crear_o_actualizar_cliente({"cliente": "CLI META", "tipo_licencia": "PRO", "meta_reencauche_pct": 50})
    _insp("CLI META", "MET001", "MT-1")
    k3 = database.obtener_suite_completa_20_kpis({"cliente": "CLI META"})["kpi_03"]
    assert k3["meta_porcentaje"] == 50        # antes 70 % fijo para todos
    dir_ = {c["cliente"]: c for c in database.obtener_directorio_clientes()}
    assert dir_["CLI META"]["meta_reencauche_pct"] == 50


# --- #22: el CPK de un grupo es Σcosto / Σkm (no el promedio de los CPK) -----------------------------
def test_22_kpi14_cpk_de_grupo_ponderado(test_db):
    _cfg("CLI P22", psi_objetivo_traccion=100.0)
    # A: 50.000 km, 21 -> 11 mm -> 5.000 km/mm -> proy 90.000 km -> CPK 1.800.000 / 90.000 = 20
    _insp("CLI P22", "P22A01", "A-1", kilometraje=150000, km_montaje=100000, prof_ext=11, prof_cent=11, prof_int=11,
          prof_inicial=21, precio=1800000)
    # B: 10.000 km, 21 -> 16 mm -> 2.000 km/mm -> proy 36.000 km -> CPK 50
    _insp("CLI P22", "P22B01", "B-1", kilometraje=110000, km_montaje=100000, prof_ext=16, prof_cent=16, prof_int=16,
          prof_inicial=21, precio=1800000)
    k14 = database.obtener_suite_completa_20_kpis({"cliente": "CLI P22", "agrupar_kpi14": "marca"})["kpi_14"]
    i = k14["labels"].index("MICHELIN")
    assert round(k14["cpk"][i], 2) == 28.57          # 3.600.000 / 126.000 km (antes promedio 35)
    assert round(k14["km_mm"][i], 1) == 4000.0       # 60.000 km / 15 mm (antes promedio 3.500)


# --- #18: cada KPI dice cuántos registros quedaron fuera y por qué ------------------------------------
def test_18_resumen_de_datos_excluidos(test_db):
    _cfg("CLI Q")
    _insp("CLI Q", "Q00001", "Q-1", psi=0)                      # sin presión
    _insp("CLI Q", "Q00002", "Q-2", prof_inicial=0, marca="SIN CATALOGO", diseno="X")  # sin profundidad inicial
    _insp("CLI Q", "Q00003", "Q-3", precio=1500000)            # completa
    q = database.obtener_suite_completa_20_kpis({"cliente": "CLI Q"})["calidad_datos"]
    assert q["llantas"] == 3
    assert q["sin_psi"] == 1 and q["sin_prof_inicial"] == 1 and q["sin_precio"] == 2


# --- #14: el kilometraje no retrocede, ni en importación ni en edición ------------------------------
def _datos_km(fecha, km, sn):
    return {"fecha": fecha, "cliente": "CLI KM", "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": "KMS001",
            "posicion": 5, "kilometraje": km, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
            "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 12, "prof_cent": 12, "prof_int": 12, "psi": 100,
            "prof_inicial": 21.5, "numero_interno": sn}


def test_14_importacion_no_acepta_km_menor_que_una_inspeccion_anterior(test_db):
    database.insertar_inspeccion(_datos_km("2026-05-10", 100000, "K-1"))
    r = database.validar_inspeccion_candados(_datos_km("2026-08-10", 90000, "K-2"), es_cargue_masivo=True)
    assert r["valido"] is False and "kilometraje" in r["mensaje"].lower()    # antes la importación lo aceptaba


def test_14_importacion_historica_valida_contra_la_inspeccion_posterior(test_db):
    database.insertar_inspeccion(_datos_km("2026-08-10", 100000, "K-1"))
    assert database.validar_inspeccion_candados(_datos_km("2026-05-10", 80000, "K-0"), es_cargue_masivo=True)["valido"]
    r = database.validar_inspeccion_candados(_datos_km("2026-05-10", 120000, "K-0"), es_cargue_masivo=True)
    assert r["valido"] is False and "posterior" in r["mensaje"]


def test_14_editar_una_inspeccion_antigua_no_se_compara_con_la_mas_reciente(test_db):
    id_ene = database.insertar_inspeccion(_datos_km("2026-01-10", 50000, "K-1"))
    database.insertar_inspeccion(_datos_km("2026-10-10", 90000, "K-2"))
    r = database.validar_inspeccion_candados(_datos_km("2026-01-10", 52000, "K-1"), excluir_id=id_ene)
    assert r["valido"], r                                                       # antes: bloqueado por los 90.000 km de octubre


# --- #34: tendencias mensuales para gerencia ---------------------------------------------------------
def test_34_tendencias_mes_a_mes(test_db):
    _cfg("CLI TEND", tolerancia_psi_baja_pct=10.0, psi_objetivo_traccion=100.0)
    # Septiembre: presión baja (80) en la única llanta; octubre: corregida (100)
    _insp("CLI TEND", "TEN001", "T-1", fecha="2026-09-10", psi=80, prof_ext=10, prof_cent=10, prof_int=10)
    _insp("CLI TEND", "TEN001", "T-1", fecha="2026-10-10", psi=100, prof_ext=9, prof_cent=9, prof_int=9)
    t = {m["mes"]: m for m in database.obtener_suite_completa_20_kpis({"cliente": "CLI TEND"})["kpi_tendencias"]["meses"]}
    assert t["2026-09"]["pct_presion_correcta"] == 0.0 and t["2026-10"]["pct_presion_correcta"] == 100.0
    assert t["2026-09"]["prof_minima_promedio"] == 10.0 and t["2026-10"]["prof_minima_promedio"] == 9.0
    assert t["2026-10"]["vehiculos_inspeccionados"] == 1
