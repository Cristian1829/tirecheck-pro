"""Los KPI y sus gráficas muestran solo lo que cae dentro de los filtros (cliente, sede, operación, tipología,
marca y dimensión): ningún dato de otro cliente, sede o marca se cuela en las series."""
import json

import database

A, B = "CLIENTE ALFA", "CLIENTE BETA"
# Valores que solo tiene el cliente B: no pueden aparecer en ninguna gráfica de A
TOKENS_B = ("BBB909", "BBB808", "BETAMARCA", "315/80R22.5", "SEDE BETA", "BETADISENO", "B-FVU")


def _insp(cliente, sede, placa, sn, fecha, km, **extra):
    d = {"fecha": fecha, "cliente": cliente, "subcliente": sede, "tipo_operacion": "CARGA", "placa": placa,
         "posicion": 5, "kilometraje": km, "km_montaje": 1000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN",
         "diseno": "X MULTI D", "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10,
         "prof_int": 10, "psi": 100, "prof_inicial": 21.5, "numero_interno": sn, "precio": 1500000}
    d.update(extra)
    assert database.insertar_inspeccion(d)


def _maestro(cliente, sede, sn, ubicacion, marca, dimension, fecha_baja=None, operacion="CARGA"):
    with database.get_connection() as conn:
        conn.execute("""INSERT INTO llantas_maestro (numero_interno, cliente, subcliente, tipo_operacion, ubicacion_bodega,
                        estado_actual, marca, dimension, vida_actual, num_reencauches, prof_inicial, prof_actual_min,
                        costo_compra_original, costo_ciclo_actual, causal_baja_fvu, fecha_baja)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Original', 0, 21.5, 3.0, 1000000, 1000000, ?, ?)""",
                     (sn, cliente, sede, operacion, ubicacion, ubicacion, marca, dimension,
                      "Fin de vida útil normal" if fecha_baja else None, fecha_baja))
        conn.commit()


def _montaje(cliente, sede, sn, placa, fecha):
    with database.get_connection() as conn:
        conn.execute("""INSERT INTO kardex_movimientos_llanta (fecha_movimiento, cliente, subcliente, numero_interno,
                        bodega_origen, bodega_destino, tipo_movimiento, placa, posicion, vida_ciclo)
                        VALUES (?, ?, ?, ?, 'BODEGA_1_NUEVAS', 'MONTADA_OPERACION', 'MONTAJE', ?, 5, 'Original')""",
                     (fecha, cliente, sede, sn, placa))
        conn.commit()


def _padron(cliente, sede, placa, tipologia):
    with database.get_connection() as conn:
        conn.execute("INSERT INTO padron_vehiculos_cliente (placa, cliente, subcliente, tipologia, activo) VALUES (?, ?, ?, ?, 1)",
                     (placa, cliente, sede, tipologia))
        conn.commit()


def _escenario():
    for cli in (A, B):
        database.guardar_licencia_cliente(cli, "PRO")
    # Cliente A: dos sedes, dos tipologías, dos marcas y dos medidas
    for fecha, km in (("2026-09-10", 20000), ("2026-10-10", 30000)):
        _insp(A, "SEDE NORTE", "AAA101", "A-1", fecha, km)
        _insp(A, "SEDE SUR", "AAA202", "A-2", fecha, km, tipologia="Camión (4x2)", marca="BRIDGESTONE",
              diseno="R268", dimension="11R22.5")
        _insp(B, "SEDE BETA", "BBB909", "B-1", fecha, km * 2, marca="BETAMARCA", diseno="BETADISENO",
              dimension="315/80R22.5")
    for placa, sede, tip in (("AAA101", "SEDE NORTE", "Cabezote (6x4)"), ("AAA202", "SEDE SUR", "Camión (4x2)"),
                             ("AAA303", "SEDE NORTE", "Cabezote (6x4)")):
        _padron(A, sede, placa, tip)
    _padron(B, "SEDE BETA", "BBB808", "Cabezote (6x4)")
    # Bajas: una de A en agosto (mes sin inspecciones) y una de B
    _maestro(A, "SEDE NORTE", "A-FVU", "BODEGA_6_FVU", "MICHELIN", "295/80R22.5", fecha_baja="2026-08-15")
    _maestro(A, "SEDE SUR", "A-FVU2", "BODEGA_6_FVU", "BRIDGESTONE", "11R22.5", fecha_baja="2026-10-01")
    _maestro(B, "SEDE BETA", "B-FVU", "BODEGA_6_FVU", "BETAMARCA", "315/80R22.5", fecha_baja="2026-10-01")
    # Stock en bodega e instalaciones (inversión del CPK administrativo)
    _maestro(A, "SEDE SUR", "A-NUEVA", "MONTADA_OPERACION", "BRIDGESTONE", "11R22.5")
    _maestro(B, "SEDE BETA", "B-NUEVA", "BODEGA_1_NUEVAS", "BETAMARCA", "315/80R22.5")
    _montaje(A, "SEDE SUR", "A-NUEVA", "AAA202", "2026-10-05")


def _suite(**f):
    return database.obtener_suite_completa_20_kpis({"licencia": "FULL", **f})


def test_cliente_no_mezcla_datos_de_otro_cliente(test_db, hoy_fijo):
    _escenario()
    s = _suite(cliente=A)
    texto = json.dumps(s, ensure_ascii=False, default=str)
    for token in TOKENS_B:
        assert token not in texto, token
    assert s["kpi_02"]["vehiculos"] == [2, 2]
    assert sorted(s["kpi_04"]["marca"]["labels"]) == ["BRIDGESTONE", "MICHELIN"]
    assert s["kpi_17"]["cantidad_fvu"] == 2
    assert s["kpi_20"]["bodegas_resumen"]["BODEGA_1_NUEVAS"]["cantidad"] == 0      # la nueva es de B
    assert s["kpi_01"]["total_padron_activo"] == 3 and len(s["kpi_01"]["placas_pendientes"]) == 1


def test_bajas_y_bodegas_respetan_marca_y_dimension(test_db, hoy_fijo):
    """Antes las bajas y bodegas solo filtraban cliente y sede."""
    _escenario()
    s = _suite(cliente=A, marca="MICHELIN")
    assert s["kpi_17"]["cantidad_fvu"] == 1
    assert s["kpi_18"]["por_marca"]["labels"] == ["MICHELIN"]
    s = _suite(cliente=A, dimension="11R22.5")
    assert s["kpi_17"]["cantidad_fvu"] == 1
    assert [m["dimension"] for m in s["kpi_20"]["matriz_mrp"]] == ["11R22.5"]
    # Montadas en 11R22.5: la de la inspección de AAA202 y la instalada desde bodega
    assert s["kpi_20"]["bodegas_resumen"]["MONTADA_OPERACION"]["cantidad"] == 2


def test_baja_en_mes_sin_inspecciones_sale_en_la_grafica(test_db, hoy_fijo):
    """La serie mensual de bajas suma lo mismo que el total (antes se perdía agosto)."""
    _escenario()
    k17 = _suite(cliente=A)["kpi_17"]
    assert sum(k17["grafico_12m"]["cantidad"]) == k17["cantidad_fvu"] == 2
    assert len(k17["grafico_12m"]["labels"]) == 3 and k17["bajas_sin_fecha"] == 0
    # Una baja cargada sin fecha cuenta en el total y se informa aparte (no se inventa un mes)
    _maestro(A, "SEDE NORTE", "A-SINFECHA", "BODEGA_6_FVU", "MICHELIN", "295/80R22.5")
    with database.get_connection() as conn:
        conn.execute("UPDATE llantas_maestro SET causal_baja_fvu = 'Desgaste' WHERE numero_interno = 'A-SINFECHA'")
        conn.commit()
    k17 = _suite(cliente=A)["kpi_17"]
    assert k17["cantidad_fvu"] == 3 and k17["bajas_sin_fecha"] == 1
    assert sum(k17["grafico_12m"]["cantidad"]) + k17["bajas_sin_fecha"] == k17["cantidad_fvu"]


def test_sede_filtra_graficas_y_cpk_administrativo(test_db, hoy_fijo):
    _escenario()
    s = _suite(cliente=A, subcliente="SEDE NORTE")
    texto = json.dumps(s, ensure_ascii=False, default=str)
    assert "AAA202" not in texto and "BRIDGESTONE" not in texto
    assert s["kpi_02"]["vehiculos"] == [1, 1]
    # La llanta instalada en la sede sur no es inversión de la sede norte
    assert all(m["inversion"] == 0 for m in s["kpi_cpk"]["administrativo"])
    sur = _suite(cliente=A, subcliente="SEDE SUR")["kpi_cpk"]["administrativo"]
    assert [m["inversion"] for m in sur if m["mes"] == "2026-10"] == [1000000]


def test_cumplimiento_por_tipologia_y_sin_efecto_de_marca(test_db, hoy_fijo):
    _escenario()
    k1 = _suite(cliente=A, tipologia="Camión (4x2)")["kpi_01"]
    assert k1["total_padron_activo"] == 1 and k1["porcentaje_cumplimiento"] == 100.0   # antes: 1 de 3
    # Filtrar una marca no vuelve "no inspeccionadas" a las placas que tienen otra marca
    sin_marca = _suite(cliente=A)["kpi_01"]
    con_marca = _suite(cliente=A, marca="MICHELIN")["kpi_01"]
    assert con_marca["vehiculos_inspeccionados"] == sin_marca["vehiculos_inspeccionados"] == 2


def test_tabla_trazabilidad_filtra_tipologia(test_db, hoy_fijo):
    _escenario()
    filas = database.obtener_trazabilidad_kpis_llanta("", {"cliente": A, "tipologia": "Camión (4x2)"})
    assert {f.get("numero_interno") for f in filas} == {"A-2"}


def test_marca_escrita_distinto_es_una_sola_barra(test_db, hoy_fijo):
    """'Bridgestone' (datos viejos) y 'BRIDGESTONE' salían como dos marcas en composición y en KPI 13-15."""
    _escenario()
    _insp(A, "SEDE SUR", "AAA505", "A-5", "2026-10-11", 30000, marca="Bridgestone", dimension="11R22.5")
    s = _suite(cliente=A)
    assert sorted(s["kpi_04"]["marca"]["labels"]) == ["BRIDGESTONE", "MICHELIN"]
    assert s["kpi_04"]["marca"]["valores"][s["kpi_04"]["marca"]["labels"].index("BRIDGESTONE")] == 2


def test_llanta_desmontada_no_sale_en_la_foto_actual(test_db, hoy_fijo):
    """Una llanta inspeccionada y luego desmontada en Bodegas seguía en composición y KPI 13-15 con su marca
    (caso reportado: salía la marca ZETA en un cliente que ya no tiene llantas ZETA montadas)."""
    import modulo_bodegas_taller as taller
    _escenario()
    _insp(A, "SEDE NORTE", "AAA101", "Z-1", "2026-10-12", 31000, posicion=6, marca="ZETA", prof_ext=15,
          prof_cent=15, prof_int=15)
    assert "ZETA" in _suite(cliente=A)["kpi_04"]["marca"]["labels"]
    r = taller.desmontar_llanta_taller({"numero_interno": "Z-1", "cliente": A, "bodega_destino": "BODEGA_2_RECAMBIO",
                                        "odometro_vehiculo": 31000, "motivo": "Cambio de marca"})
    assert r.get("ok"), r
    s = _suite(cliente=A)
    for clave in ("kpi_04", "kpi_13", "kpi_14", "kpi_15"):
        assert "ZETA" not in json.dumps(s[clave]), clave
    # Las demás llantas montadas siguen igual
    assert sorted(s["kpi_04"]["marca"]["labels"]) == ["BRIDGESTONE", "MICHELIN"]
    # En el historial completo la inspección de la ZETA sí cuenta: fue real
    assert "ZETA" in _suite(cliente=A, base="historial")["kpi_04"]["marca"]["labels"]


def test_filtros_con_tilde(test_db, hoy_fijo):
    """UPPER de SQLite no sube las tildes: 'Camión' y 'CAMIÓN' no coincidían en padrón ni bodegas."""
    _escenario()
    _padron(A, "SEDE SUR", "AAA404", "Camión (4x2)")            # guardado con minúsculas y tilde
    _maestro(A, "SEDE SUR", "A-LIQ", "BODEGA_6_FVU", "MICHELIN", "295/80R22.5", fecha_baja="2026-10-02",
             operacion="Líquidos / Tanque")
    k1 = _suite(cliente=A, tipologia="CAMIÓN (4X2)")["kpi_01"]
    assert k1["total_padron_activo"] == 2 and [p["placa"] for p in k1["placas_pendientes"]] == ["AAA404"]
    assert _suite(cliente=A, tipo_operacion="LÍQUIDOS / TANQUE")["kpi_17"]["cantidad_fvu"] == 1
