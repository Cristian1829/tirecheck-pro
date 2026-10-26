"""Auditoría, bloque 3: estados, movimientos, transiciones y vida de la llanta."""
import database
import modulo_bodegas_taller as mbt

CLI = "CLI CICLO"


def _alta(sn, ubicacion="BODEGA_1_NUEVAS", vida="Original"):
    res = database.crear_llanta_en_bodega({
        "numero_interno": sn, "cliente": CLI, "subcliente": "SEDE", "marca": "MICHELIN", "diseno": "X MULTI D",
        "dimension": "295/80R22.5", "prof_inicial": 21.5, "prof_actual_min": 21.5, "costo_compra": 2000000,
        "ubicacion_bodega": ubicacion, "vida_actual": vida})
    assert res.get("ok"), res
    return res


def _fila(sn):
    with database.get_connection() as conn:
        cur = conn.execute("SELECT * FROM llantas_maestro WHERE numero_interno = ?", (sn,))
        cols = [d[0] for d in cur.description]
        r = cur.fetchone()
    return dict(zip(cols, r)) if r else None


def _mover(sn, destino, **extra):
    datos = {"cliente": CLI, "numero_interno": sn, "bodega_destino": destino, "usuario_registro": "tester"}
    datos.update(extra)
    return database.registrar_movimiento_bodega(datos)


# --- #28: un solo vocabulario de estados -------------------------------------------------------
def test_28_taller_desmonta_al_ocupante_montado_por_bodegas(test_db):
    _alta("OC-1")
    _alta("OC-2")
    assert _mover("OC-1", "MONTADA_OPERACION", placa="CIC001", posicion=3, km_vehiculo=1000)["ok"]
    res = mbt.montar_llanta_taller({"placa": "CIC001", "posicion": 3, "cliente": CLI, "numero_interno": "OC-2",
                                    "kilometraje": 1500, "usuario_responsable": "tester"})
    assert res["ok"], res
    with database.get_connection() as conn:
        montadas = conn.execute("SELECT numero_interno FROM llantas_maestro WHERE placa_actual = 'CIC001' "
                                "AND posicion_actual = 3 AND ubicacion_bodega = 'MONTADA_OPERACION'").fetchall()
    assert [m[0] for m in montadas] == ["OC-2"]          # antes quedaban las dos montadas
    assert _fila("OC-1")["ubicacion_bodega"] == "BODEGA_2_RECAMBIO"


def test_28_estados_escritos_por_taller_son_los_oficiales(test_db):
    _alta("EST-1")
    mbt.montar_llanta_taller({"placa": "CIC002", "posicion": 1, "cliente": CLI, "numero_interno": "EST-1", "kilometraje": 100})
    f = _fila("EST-1")
    assert (f["ubicacion_bodega"], f["estado_actual"]) == ("MONTADA_OPERACION", database.UBICACIONES_LLANTA["MONTADA_OPERACION"])


def test_28_migracion_lleva_estados_antiguos_a_los_oficiales(test_db):
    antiguos = [
        ("LEG-1", "2. Bodega Llantas Listas", "DISPONIBLE", "", "BODEGA_4_REENCAUCHADAS"),
        ("LEG-2", "3. Pulmón Nuevas", "NUEVA", "", "BODEGA_1_NUEVAS"),
        ("LEG-3", "5. En Planta Reencauchadora", "EN_RENOVADO", "", "BODEGA_3_REENCAUCHE"),
        ("LEG-4", "7. Chatarra / Scrap", "BAJA_FVU", "", "BODEGA_6_FVU"),
        ("LEG-5", "7. Chatarra / Scrap", "BAJA_FVU", "ACTA-001", "BODEGA_7_CHATARRIZADA"),
        ("LEG-6", "MONTADA_OPERACION", "Montada", "", "MONTADA_OPERACION"),
        ("LEG-7", "BODEGA_7_CHATARRIZADA", "Bodega_7_FVU", "", "BODEGA_6_FVU"),  # baja FVU de Taller sin acta
    ]
    with database.get_connection() as conn:
        for sn, ubi, est, acta, _ in antiguos:
            conn.execute("INSERT INTO llantas_maestro (numero_interno, cliente, ubicacion_bodega, estado_actual, numero_acta_ambiental) "
                         "VALUES (?, ?, ?, ?, ?)", (sn, CLI, ubi, est, acta))
        conn.execute("DELETE FROM _control_migraciones WHERE nombre = 'normalizar_estados_llantas_v1'")
        conn.commit()
        database.migrar_normalizar_estados_llantas(conn)
        conn.commit()
    for sn, _, _, _, esperado in antiguos:
        f = _fila(sn)
        assert f["ubicacion_bodega"] == esperado, sn
        assert f["estado_actual"] == database.UBICACIONES_LLANTA[esperado], sn


# --- #27: una sola fuente de movimientos (kardex) ----------------------------------------------
def _historial(sn):
    hv = mbt.obtener_hoja_vida_llanta(sn, CLI)
    return [m.get("tipo_movimiento") for m in hv.get("historial_movimientos", [])]


def test_27_hoja_de_vida_muestra_movimientos_de_bodegas_y_taller(test_db):
    _alta("HV-1")
    _mover("HV-1", "MONTADA_OPERACION", placa="CIC003", posicion=1, km_vehiculo=1000)
    mbt.desmontar_llanta_taller({"numero_interno": "HV-1", "cliente": CLI, "bodega_destino": "BODEGA_2_RECAMBIO",
                                 "kilometraje": 9000, "profundidad": 15})
    tipos = _historial("HV-1")
    assert "ALTA_NUEVA" in tipos and "MONTAJE" in tipos      # hechos desde Bodegas: antes no aparecían
    assert any(t.startswith("DESMONTE") for t in tipos)     # hecho desde Taller


# --- #24: el montaje valida de dónde viene la llanta ---------------------------------------------
def _a_fvu(sn):
    _alta(sn)
    assert _mover(sn, "MONTADA_OPERACION", placa="CIC010", posicion=1, km_vehiculo=1000)["ok"]
    assert _mover(sn, "BODEGA_6_FVU", prof_min_mm=4.0, causal_o_motivo="Corte lateral")["ok"]


def test_24_no_se_monta_desde_fvu_sin_trazabilidad(test_db):
    _a_fvu("FVU-1")
    res = mbt.montar_llanta_taller({"placa": "CIC011", "posicion": 2, "cliente": CLI, "numero_interno": "FVU-1", "kilometraje": 2000})
    assert res["ok"] is False and "motivo" in res["message"] and "foto" in res["message"]
    assert _fila("FVU-1")["ubicacion_bodega"] == "BODEGA_6_FVU"


def test_24_reingreso_desde_fvu_con_motivo_responsable_y_foto(test_db):
    _a_fvu("FVU-2")
    res = mbt.montar_llanta_taller({"placa": "CIC011", "posicion": 2, "cliente": CLI, "numero_interno": "FVU-2", "kilometraje": 2000,
                                    "motivo_reingreso": "Reparada por vulcanizadora", "responsable_reingreso": "jefe taller",
                                    "foto_reingreso": "data:image/png;base64,AAA"})
    assert res["ok"], res
    with database.get_connection() as conn:
        k = conn.execute("SELECT tipo_movimiento, bodega_origen, usuario_registro, foto_soporte FROM kardex_movimientos_llanta "
                         "WHERE numero_interno = 'FVU-2' ORDER BY id DESC LIMIT 1").fetchone()
    assert k == ("REINGRESO_MONTAJE", "BODEGA_6_FVU", "jefe taller", "data:image/png;base64,AAA")


def test_24_disposicion_final_exige_acta_real(test_db):
    _a_fvu("FVU-3")
    res = _mover("FVU-3", "BODEGA_7_CHATARRIZADA")                 # antes inventaba "ACTA-AAAAMM-FVU-3"
    assert res["ok"] is False and "acta" in res["mensaje"]
    assert _mover("FVU-3", "BODEGA_7_CHATARRIZADA", documento_soporte="ACTA-AMB-778")["ok"]
    assert _fila("FVU-3")["numero_acta_ambiental"] == "ACTA-AMB-778"


def test_24_desmontar_una_llanta_que_no_esta_montada(test_db):
    _alta("STK-1")
    res = mbt.desmontar_llanta_taller({"numero_interno": "STK-1", "cliente": CLI, "bodega_destino": "BODEGA_2_RECAMBIO"})
    assert res["ok"] is False and _fila("STK-1")["ubicacion_bodega"] == "BODEGA_1_NUEVAS"


# --- #25: reencauche solo si pasó por la planta ----------------------------------------------------
def _casco(sn):
    _alta(sn)
    assert _mover(sn, "MONTADA_OPERACION", placa="CIC020", posicion=5, km_vehiculo=1000)["ok"]
    r = mbt.desmontar_llanta_taller({"numero_interno": sn, "cliente": CLI, "bodega_destino": "Bodega_3_Reencauche",
                                     "kilometraje": 80000, "profundidad": 5})
    assert r["ok"], r


def test_25_no_se_recibe_reencauchada_una_llanta_montada_o_no_despachada(test_db):
    _alta("REN-1")
    _mover("REN-1", "MONTADA_OPERACION", placa="CIC021", posicion=5, km_vehiculo=1000)
    datos = {"numero_interno": "REN-1", "cliente": CLI, "diseno_banda": "BDM", "prof_banda_nueva": 19}
    assert mbt.recepcionar_llanta_reencauchada(datos)["ok"] is False          # montada: antes pasaba a R1
    _casco("REN-2")
    datos["numero_interno"] = "REN-2"
    r = mbt.recepcionar_llanta_reencauchada(datos)
    assert r["ok"] is False and "despachada" in r["message"]                 # casco sin despachar


def test_25_flujo_completo_original_a_r1(test_db):
    _casco("REN-3")
    d = mbt.despachar_lote_planta_reencauche({"numeros_internos": ["REN-3"], "cliente": CLI,
                                               "proveedor_planta": "RENOVADORA X", "guia_remision": "G-1"})
    assert d["ok"], d
    assert mbt.despachar_lote_planta_reencauche({"numeros_internos": ["REN-3"], "cliente": CLI, "proveedor_planta": "X",
                                                  "guia_remision": "G-2"})["ok"] is False  # ya despachada
    r = mbt.recepcionar_llanta_reencauchada({"numero_interno": "REN-3", "cliente": CLI, "diseno_banda": "BDM", "prof_banda_nueva": 19})
    assert r["ok"] and r["vida"] == "R1"
    f = _fila("REN-3")
    assert (f["ubicacion_bodega"], f["vida_actual"], f["num_reencauches"], f["prof_inicial"]) == ("BODEGA_4_REENCAUCHADAS", "R1", 1, 19.0)


def test_25_recepcion_exige_banda_y_profundidad(test_db):
    _casco("REN-4")
    mbt.despachar_lote_planta_reencauche({"numeros_internos": ["REN-4"], "cliente": CLI, "proveedor_planta": "X", "guia_remision": "G"})
    r = mbt.recepcionar_llanta_reencauchada({"numero_interno": "REN-4", "cliente": CLI})   # antes: Bandag BDL 17 mm $720.000
    assert r["ok"] is False


# --- #26: máximo de reencauches por cliente y marca -------------------------------------------------
def test_26_respeta_maximo_de_reencauches(test_db):
    assert database.guardar_maximo_reencauches(CLI, "MICHELIN", 1)
    _casco("MAX-1")
    with database.get_connection() as conn:
        conn.execute("UPDATE llantas_maestro SET num_reencauches = 1, vida_actual = 'R1' WHERE numero_interno = 'MAX-1'")
        conn.commit()
    d = mbt.despachar_lote_planta_reencauche({"numeros_internos": ["MAX-1"], "cliente": CLI, "proveedor_planta": "X", "guia_remision": "G"})
    assert d["ok"] is False and "máximo" in d["mensaje"]
    assert database.maximo_reencauches(CLI, "PIRELLI") is None             # sin regla para la marca ni general
    database.guardar_maximo_reencauches(CLI, "TODAS", 3)
    assert database.maximo_reencauches(CLI, "PIRELLI") == 3                # regla general del cliente


def test_24_inspeccion_no_monta_sola_una_llanta_en_fvu(test_db):
    _a_fvu("FVU-9")
    database.insertar_inspeccion({
        "fecha": "2027-06-01", "cliente": CLI, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": "CIC099",
        "posicion": 1, "kilometraje": 5000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
        "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 9, "prof_cent": 9, "prof_int": 9, "psi": 110,
        "prof_inicial": 21.5, "numero_interno": "FVU-9"})
    database.sincronizar_maestro_desde_inspecciones(cliente_filtro=CLI, numero_interno_filtro="FVU-9")
    assert _fila("FVU-9")["ubicacion_bodega"] == "BODEGA_6_FVU"
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM llantas_novedades_registro WHERE numero_interno = 'FVU-9' "
                            "AND tipo_novedad = 'Inconsistencia de inventario'").fetchone()[0] == 1


# --- #12 / #13: vida exacta en la inspección y secuencia de vidas --------------------------------
def _insp(sn, fecha, vida, placa="VID001", banda=""):
    datos = {"fecha": fecha, "cliente": CLI, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": placa,
             "posicion": 5, "kilometraje": 1000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
             "dimension": "295/80R22.5", "vida": vida, "banda_reen": banda, "prof_ext": 9, "prof_cent": 9,
             "prof_int": 9, "psi": 110, "prof_inicial": 21.5, "numero_interno": sn}
    return datos


def test_12_la_inspeccion_guarda_la_vida_exacta(test_db):
    database.insertar_inspeccion(_insp("VX-1", "2026-03-10", "R2", banda="BDM"))
    with database.get_connection() as conn:
        assert conn.execute("SELECT vida FROM inspecciones WHERE numero_interno = 'VX-1'").fetchone()[0] == "R2"  # antes 'REENCAUCHE'
    assert database.normalizar_vida_y_banda("Reencauche 3", "B")[0] == "R3"
    assert database.normalizar_vida_y_banda("Original", "BDM") == ("ORIGINAL", "")


def test_13_secuencia_de_vida_entre_inspecciones(test_db):
    database.insertar_inspeccion(_insp("VS-1", "2026-03-10", "R1", banda="BDM"))
    r = database.validar_inspeccion_candados(_insp("VS-1", "2026-05-10", "Original"))
    assert r["valido"] is False and "no puede volver a Original" in r["mensaje"]
    database.insertar_inspeccion(_insp("VS-2", "2026-03-10", "Original"))
    r = database.validar_inspeccion_candados(_insp("VS-2", "2026-05-10", "R2", banda="BDM"))
    assert r["valido"] is False and "solo puede pasar a R1" in r["mensaje"]
    assert database.validar_inspeccion_candados(_insp("VS-2", "2026-05-10", "R1", banda="BDM"))["valido"]


def test_12_el_arranque_no_borra_el_numero_de_vida(test_db):
    database.insertar_inspeccion(_insp("VX-2", "2026-03-10", "R2", banda="BDM"))
    database.migrar_normalizar_vida_llantas()   # corre en cada arranque: antes convertía R2 en 'REENCAUCHE'
    with database.get_connection() as conn:
        assert conn.execute("SELECT vida FROM inspecciones WHERE numero_interno = 'VX-2'").fetchone()[0] == "R2"
