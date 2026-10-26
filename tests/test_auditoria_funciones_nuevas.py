"""Auditoría, bloque 4: funciones nuevas (sede por usuario, precios, CPK, selector, horas, MRP)."""
from fastapi.testclient import TestClient

import database
import server


def _http(username, rol):
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(username, rol)}"})
    return c


def _insp(cliente, sede, placa, sn, fecha="2026-10-10", **extra):
    d = {"fecha": fecha, "cliente": cliente, "subcliente": sede, "tipo_operacion": "CARGA", "placa": placa,
         "posicion": 5, "kilometraje": 10000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
         "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 12, "prof_cent": 12, "prof_int": 12, "psi": 110,
         "prof_inicial": 21.5, "numero_interno": sn}
    d.update(extra)
    database.insertar_inspeccion(d)
    database.sincronizar_vehiculo_catalogo(placa, "Cabezote (6x4)", cliente, sede)


# --- #3: un usuario puede quedar limitado a una o varias sedes de su cliente -----------------------
def test_3_usuario_de_una_sede_solo_ve_su_sede(test_db):
    _insp("CLI SEDES", "NORTE", "NOR001", "S-N1")
    _insp("CLI SEDES", "SUR", "SUR001", "S-S1")
    assert database.crear_usuario("insp_norte", "12345", "Insp Norte", "inspector", "CLI SEDES", "patio,diagnostico",
                                  sedes_asignadas="CLI SEDES|NORTE")
    c = _http("insp_norte", "inspector")
    placas = {r["placa"] for r in c.get("/api/inspecciones").json()}
    assert placas == {"NOR001"}
    assert c.get("/api/informe-resumen/SUR001").status_code == 403
    r = c.post("/api/inspecciones", json={"fecha": "2026-10-11", "cliente": "CLI SEDES", "subcliente": "SUR",
                                          "placa": "SUR001", "posicion": 6, "prof_ext": 10, "prof_cent": 10,
                                          "prof_int": 10, "vida": "Original", "numero_interno": "S-S2"})
    assert r.status_code == 403


def test_3_sin_sedes_ve_todas_las_de_su_cliente(test_db):
    _insp("CLI SEDES", "NORTE", "NOR001", "S-N1")
    _insp("CLI SEDES", "SUR", "SUR001", "S-S1")
    database.crear_usuario("jefe_cli", "12345", "Jefe", "jefatura", "CLI SEDES", "patio,diagnostico")
    placas = {r["placa"] for r in _http("jefe_cli", "jefatura").get("/api/inspecciones").json()}
    assert placas == {"NOR001", "SUR001"}


def test_3_inspeccion_anterior_valida_cliente_y_sede(test_db):
    _insp("CLI SEDES", "SUR", "SUR001", "S-S1")
    _insp("OTRO CLIENTE", "UNICA", "OTR001", "O-1")
    database.crear_usuario("insp_norte", "12345", "Insp Norte", "inspector", "CLI SEDES", "patio", sedes_asignadas="CLI SEDES|NORTE")
    c = _http("insp_norte", "inspector")
    assert c.get("/api/inspeccion-anterior?placa=OTR001&posicion=5").status_code == 403   # antes: 200 con los datos
    assert c.get("/api/inspeccion-anterior?placa=SUR001&posicion=5").status_code == 403


def test_3_bodegas_solo_de_sus_sedes(test_db):
    for sn, sede in (("BN-1", "NORTE"), ("BS-1", "SUR")):
        r = database.crear_llanta_en_bodega({"cliente": "CLI SEDES", "subcliente": sede, "numero_interno": sn, "marca": "MICHELIN",
                                             "diseno": "X MULTI D", "dimension": "295/80R22.5", "prof_inicial": 21.5})
        assert r["ok"], r
    database.crear_usuario("jefe_norte", "12345", "Jefe Norte", "jefatura", "CLI SEDES", "bodegas", sedes_asignadas="CLI SEDES|NORTE")
    c = _http("jefe_norte", "jefatura")
    inv = c.get("/api/bodegas/inventario?cliente=CLI SEDES").json()
    assert {l["numero_interno"] for l in inv["llantas"]} == {"BN-1"}
    assert c.get("/api/bodegas/inventario?cliente=CLI SEDES&subcliente=SUR").status_code == 403


def test_3_patio_solo_ofrece_sus_sedes(test_db):
    _insp("CLI SEDES", "NORTE", "NOR001", "S-N1")
    _insp("CLI SEDES", "SUR", "SUR001", "S-S1")
    database.crear_usuario("insp_norte", "12345", "Insp Norte", "inspector", "CLI SEDES", "patio", sedes_asignadas="CLI SEDES|NORTE")
    sedes = _http("insp_norte", "inspector").get("/api/valores-campo?campo=subcliente&cliente=CLI SEDES").json()
    assert [s.upper() for s in sedes] == ["NORTE"]


# --- #23: precios por cliente (lista con vigencia) ------------------------------------------------
def test_23_precio_de_la_lista_del_cliente(test_db):
    database.guardar_precio_cliente("CLI P", "MICHELIN", "", "295/80R22.5", "Original", 2000000, "2026-01-01")
    database.guardar_precio_cliente("CLI P", "MICHELIN", "X MULTI D", "295/80R22.5", "Original", 2100000, "2026-01-01")
    database.guardar_precio_cliente("CLI P", "MICHELIN", "X MULTI D", "295/80R22.5", "Original", 2300000, "2026-09-01")
    database.guardar_precio_cliente("CLI P", "BANDAG", "", "295/80R22.5", "Reencauche", 700000, "2026-01-01")
    pl = database.precio_lista_cliente
    assert pl("CLI P", "MICHELIN", "X MULTI D", "295/80R22.5", "Original", "2026-06-15") == 2100000   # vigente en junio
    assert pl("CLI P", "MICHELIN", "X MULTI D", "295/80R22.5", "Original", "2026-10-10") == 2300000   # nuevo precio desde sept
    assert pl("CLI P", "MICHELIN", "XZE2+", "295/80R22.5", "Original", "2026-10-10") == 2000000       # sin diseño exacto: precio de la marca
    assert pl("CLI P", "BANDAG", "BDM", "295/80R22.5", "R2", "2026-10-10") == 700000                 # reencauche (cualquier vida R)
    assert pl("OTRO", "MICHELIN", "X MULTI D", "295/80R22.5", "Original", "2026-10-10") is None       # otro cliente: no se toma
    assert pl("CLI P", "PIRELLI", "TG01", "295/80R22.5", "Original", "2026-10-10") is None           # sin precio: se excluye


def test_23_los_calculos_usan_la_lista_cuando_la_inspeccion_no_trae_precio(test_db):
    database.guardar_precio_cliente("CLI P", "MICHELIN", "X MULTI D", "295/80R22.5", "Original", 2100000, "2026-01-01")
    _insp("CLI P", "SEDE", "PRC001", "P-1", precio=0)
    ref_precio, _ = database.construir_referencias_llanta(database.obtener_todas_inspecciones(incluir_fotos=False))
    assert ref_precio("CLI P", "295/80R22.5", "P-1", marca="MICHELIN", diseno="X MULTI D", vida="Original", fecha="2026-10-10") == 2100000


# --- #20: los 4 CPK, por vida y por ciclo completo -------------------------------------------------
def _serie(sn, filas, cliente="CLI CPK", placa="CPK001"):
    for fecha, km, prof, vida, precio, km_mont in filas:
        _insp(cliente, "SEDE", placa, sn, fecha=fecha, kilometraje=km, prof_ext=prof, prof_cent=prof, prof_int=prof,
              vida=vida, banda_reen="BDM" if vida != "Original" else "", precio=precio, km_montaje=km_mont, prof_inicial=21.0)


def test_20_cpk_operativo_proyectado_y_total_por_vida_y_ciclo(test_db):
    # Original: 2.000.000 / 60.000 km. R1: 700.000 / 30.000 km (montada en km 70.000)
    _serie("C-1", [("2026-01-10", 10000, 21.0, "Original", 2000000, 10000),
                   ("2026-05-10", 70000, 9.0, "Original", 0, 10000),
                   ("2026-07-10", 70000, 21.0, "R1", 700000, 70000),
                   ("2026-10-10", 100000, 15.0, "R1", 0, 70000)])
    r = database.calcular_cpk_llantas(database.obtener_todas_inspecciones(incluir_fotos=False))
    ll = r["llantas"]["CLI CPK|C-1"]
    org, r1 = ll["vidas"]["Original"], ll["vidas"]["R1"]
    assert (org["km"], org["costo"], round(org["cpk_operativo"], 2)) == (60000, 2000000, 33.33)
    assert (r1["km"], r1["costo"], round(r1["cpk_operativo"], 2)) == (30000, 700000, 23.33)
    # proyectado R1: 30.000 km por 6 mm -> 5.000 km/mm; quedan 15 - 3 = 12 mm -> 90.000 km
    assert round(r1["km_proyectados"]) == 90000 and round(r1["cpk_proyectado"], 2) == 7.78
    # ciclo completo: (2.000.000 + 700.000) / (60.000 + 30.000)
    assert round(ll["cpk_total_ciclo"], 2) == 30.0
    assert round(r["flota"]["cpk_total"], 2) == 30.0


def test_20_cpk_sin_precio_se_excluye(test_db):
    _serie("C-2", [("2026-01-10", 10000, 21.0, "Original", 0, 10000), ("2026-05-10", 50000, 15.0, "Original", 0, 10000)])
    r = database.calcular_cpk_llantas(database.obtener_todas_inspecciones(incluir_fotos=False))
    v = r["llantas"]["CLI CPK|C-2"]["vidas"]["Original"]
    assert v["cpk_operativo"] is None and r["flota"]["llantas_sin_precio"] == 1


def test_20_cpk_administrativo_mensual(test_db):
    # Inversión de octubre: una llanta nueva montada desde Bodega 1 ($2.000.000).
    r = database.crear_llanta_en_bodega({"cliente": "CLI CPK", "subcliente": "SEDE", "numero_interno": "ADM-1", "marca": "MICHELIN",
                                         "diseno": "X MULTI D", "dimension": "295/80R22.5", "prof_inicial": 21.0, "costo_compra": 2000000})
    assert r["ok"]
    with database.get_connection() as conn:
        database.registrar_kardex(conn.cursor(), "ADM-1", "CLI CPK", "BODEGA_1_NUEVAS", "MONTADA_OPERACION", "MONTAJE",
                                  fecha="2026-10-05", placa="CPK001", posicion=5, vida="Original")
        conn.commit()
    # Km de flota: CPK001 pasa de 100.000 (corte sept) a 140.000 (corte oct) = 40.000 km
    _insp("CLI CPK", "SEDE", "CPK001", "X-1", fecha="2026-09-28", kilometraje=100000)
    _insp("CLI CPK", "SEDE", "CPK001", "X-1", fecha="2026-10-28", kilometraje=140000)
    adm = {m["mes"]: m for m in database.calcular_cpk_llantas(database.obtener_todas_inspecciones(incluir_fotos=False))["administrativo"]}
    oct_ = adm["2026-10"]
    assert (oct_["inversion"], oct_["km_flota"], oct_["cpk_administrativo"]) == (2000000, 40000, 50.0)


# --- #11: selector última inspección / historial completo -----------------------------------------
def test_11_kpis_por_ultima_inspeccion_o_historial(test_db):
    database.guardar_licencia_cliente("CLI BASE", "PRO")
    # Una misma posición inspeccionada dos veces: primero con presión baja, después corregida
    _insp("CLI BASE", "SEDE", "BAS001", "B-1", fecha="2026-09-10", psi=80)
    _insp("CLI BASE", "SEDE", "BAS001", "B-1", fecha="2026-10-10", psi=110)
    k_ult = database.obtener_suite_completa_20_kpis({"cliente": "CLI BASE", "base": "ultima"})
    k_his = database.obtener_suite_completa_20_kpis({"cliente": "CLI BASE", "base": "historial"})
    assert k_ult["base"] == "ultima" and k_his["base"] == "historial"
    total = lambda k: sum(k["kpi_09"]["valores"])
    assert total(k_ult) == 1 and total(k_his) == 2   # una medición vs las dos del historial


# --- #10: vehículos medidos por horas de motor ----------------------------------------------------
def test_10_placa_por_horas_y_kpis_por_unidad(test_db):
    database.guardar_licencia_cliente("CLI H", "PRO")
    # Cargador medido en horas: 2.000 h -> 2.600 h (600 h), 21 -> 15 mm, precio 3.000.000
    _insp("CLI H", "SEDE", "CARG01", "H-1", fecha="2026-05-10", kilometraje=2000, km_montaje=2000, precio=3000000, unidad_medida="HORAS")
    _insp("CLI H", "SEDE", "CARG01", "H-1", fecha="2026-10-10", kilometraje=2600, km_montaje=2000, prof_ext=15, prof_cent=15, prof_int=15)
    # Camión medido en km
    _insp("CLI H", "SEDE", "CAM001", "K-1", fecha="2026-10-10", kilometraje=90000)
    assert database.obtener_perfil_vehiculo("CARG01")["unidad_medida"] == "HORAS"   # la unidad queda en la placa
    with database.get_connection() as conn:
        assert conn.execute("SELECT unidad_medida FROM inspecciones WHERE placa = 'CARG01' AND fecha = '2026-10-10'").fetchone()[0] == "HORAS"
    k_h = database.obtener_suite_completa_20_kpis({"cliente": "CLI H", "unidad": "horas"})
    k_km = database.obtener_suite_completa_20_kpis({"cliente": "CLI H", "unidad": "km"})
    assert k_h["unidad"] == "horas" and k_km["unidad"] == "km"
    assert round(k_h["kpi_cpk"]["flota"]["cpk_operativo"]) == 5000          # 3.000.000 / 600 h
    assert sum(k_h["kpi_09"]["valores"]) == 1 and sum(k_km["kpi_09"]["valores"]) == 1   # cada unidad con sus vehículos


def test_10_la_unidad_de_una_placa_existente_no_cambia_por_una_inspeccion(test_db):
    _insp("CLI H", "SEDE", "CARG02", "H-2", fecha="2026-05-10", kilometraje=2000, unidad_medida="HORAS")
    _insp("CLI H", "SEDE", "CARG02", "H-2", fecha="2026-10-10", kilometraje=2400, unidad_medida="KM")  # p. ej. un envío sin conexión
    assert database.obtener_perfil_vehiculo("CARG02")["unidad_medida"] == "HORAS"
    with database.get_connection() as conn:
        assert conn.execute("SELECT unidad_medida FROM inspecciones WHERE placa = 'CARG02' AND fecha = '2026-10-10'").fetchone()[0] == "HORAS"


# --- #29 / #30: MRP proyectado y stock de seguridad por medida y eje --------------------------------
def _flota_mrp():
    """Llanta de tracción (pos 5): 21 -> 15 mm en 30.000 km (5.000 km/mm); el vehículo rueda 10.000 km/mes.
    Le quedan 15 - 3 = 12 mm -> 60.000 km -> 6 meses. Otra llanta (pos 6) ya está en 3 mm (en el límite)."""
    _insp("CLI MRP", "SEDE", "MRP001", "M-5", fecha="2026-07-10", kilometraje=100000, km_montaje=100000, prof_ext=21, prof_cent=21, prof_int=21)
    _insp("CLI MRP", "SEDE", "MRP001", "M-5", fecha="2026-10-10", kilometraje=130000, km_montaje=100000, prof_ext=15, prof_cent=15, prof_int=15)
    _insp("CLI MRP", "SEDE", "MRP001", "M-6", fecha="2026-10-10", kilometraje=130000, posicion=6, prof_ext=3, prof_cent=3, prof_int=3)
    database.guardar_licencia_cliente("CLI MRP", "PRO")
    with database.get_connection() as conn:
        conn.execute("UPDATE configuracion_avanzada_cliente SET stock_seguridad_default = 0, porcentaje_aprobacion_reencauche = 100 WHERE cliente = 'CLI MRP'")
        conn.commit()


def _fila_mrp(horizonte):
    b = database.obtener_balance_bodegas_mrp({"cliente": "CLI MRP", "horizonte_meses": horizonte})
    return next(f for f in b["matriz_mrp"] if f["dimension"] == "295/80R22.5")


def test_29_demanda_proyectada_en_el_horizonte(test_db):
    _flota_mrp()
    assert _fila_mrp(3)["demanda_traccion"] == 1       # solo la que ya está en el límite (la otra llega en 6 meses)
    f6 = _fila_mrp(6)
    assert f6["demanda_traccion"] == 2 and f6["horizonte_meses"] == 6   # antes: siempre 1, sin proyección
    assert f6["retorno_reencauche_proyectado"] == 2 and f6["desecho_proyectado"] == 0   # 100 % reencauchables


def test_30_stock_de_seguridad_por_medida_y_eje(test_db):
    _flota_mrp()
    database.guardar_stock_seguridad("CLI MRP", "295/80R22.5", "DIRECCIONAL", 2)
    database.guardar_stock_seguridad("CLI MRP", "295/80R22.5", "TRACCION", 3)
    f = _fila_mrp(3)
    assert (f["stock_seguridad_direccional"], f["stock_seguridad_otros"], f["stock_seguridad"]) == (2, 3, 5)
    assert f["compra_nuevas_direccional"] == 2          # la reserva de dirección solo se cubre con nuevas


def test_20_cpk_tolera_inspecciones_sin_cliente_ni_numero(test_db):
    _serie("C-9", [("2026-01-10", 10000, 21.0, "Original", 2000000, 10000), ("2026-05-10", 50000, 15.0, "Original", 0, 10000)])
    with database.get_connection() as conn:   # datos antiguos incompletos (en producción existen)
        conn.execute("INSERT INTO inspecciones (fecha, placa, posicion, vida) VALUES ('2026-10-07', 'SINCLI', 1, 'ORIGINAL')")
        conn.commit()
    r = database.calcular_cpk_llantas(database.obtener_todas_inspecciones(incluir_fotos=False))
    assert "CLI CPK|C-9" in r["llantas"] and isinstance(r["administrativo"], list)
