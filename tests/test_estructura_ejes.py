"""Pruebas de la estructura de ejes: direccionales, duales, equis y repuestos salen del esquema de la tipología."""
import estructura_ejes as ee
import database


ESQ_6X4 = [
    {"eje": 1, "tipo": "direccional", "posiciones": [{"pos": 1, "lado": "izq", "rol": "direccional"}, {"pos": 2, "lado": "der", "rol": "direccional"}]},
    {"eje": 2, "tipo": "traccion", "posiciones": [{"pos": 3, "lado": "izq", "rol": "ext"}, {"pos": 4, "lado": "izq", "rol": "int"}, {"pos": 5, "lado": "der", "rol": "int"}, {"pos": 6, "lado": "der", "rol": "ext"}]},
    {"eje": 3, "tipo": "traccion", "posiciones": [{"pos": 7, "lado": "izq", "rol": "ext"}, {"pos": 8, "lado": "izq", "rol": "int"}, {"pos": 9, "lado": "der", "rol": "int"}, {"pos": 10, "lado": "der", "rol": "ext"}]},
]
ESQ_TRAILER_REP = [
    {"eje": 1, "tipo": "remolque", "posiciones": [{"pos": 1, "lado": "izq", "rol": "ext"}, {"pos": 2, "lado": "izq", "rol": "int"}, {"pos": 3, "lado": "der", "rol": "int"}, {"pos": 4, "lado": "der", "rol": "ext"}]},
    {"eje": 99, "tipo": "repuesto", "posiciones": [{"pos": 5, "lado": "centro", "rol": "repuesto"}]},
]


def test_estructura_6x4():
    e = ee.EstructuraVehiculo(ESQ_6X4)
    assert e.pares_direccionales() == [(1, 2)]
    assert sorted(e.duales()) == [(4, 3), (5, 6), (8, 7), (9, 10)]
    assert sorted(e.cruce_equis(*e.ejes_de(ee.TRACCION))) == [(3, 9), (4, 10), (5, 7), (6, 8)]
    assert e.posiciones_alineacion() == [1, 2]


def test_en_trailer_la_posicion_1_no_es_direccional_y_el_repuesto_no_rueda():
    e = ee.EstructuraVehiculo(ESQ_TRAILER_REP)
    assert e.tipo_eje(1) == ee.LIBRE
    assert e.pares_direccionales() == []
    assert sorted(e.duales()) == [(2, 1), (3, 4)]
    assert e.es_repuesto(5)
    assert 5 not in e.posiciones()


def test_nombre_de_tipologia_se_empareja_sin_tildes_ni_signos(test_db):
    with database.get_connection() as conn:
        import json
        conn.execute("INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, '', 10, ?)",
                     ("Volqueta Prueba (6x4)", json.dumps(ESQ_6X4)))
        conn.commit()
    est = database.construir_resolver_estructura()
    assert not est("VOLQUETA PRUEBA 6X4").inferida
    assert est("Tipología que no existe", [1, 2, 3, 4]).inferida


def test_limite_por_eje_usa_la_estructura_en_trailer(test_db):
    import json
    with database.get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, '', 5, ?)",
                     ("Remolque Prueba", json.dumps(ESQ_TRAILER_REP)))
        conn.execute("INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm) VALUES ('CLI EJE', 'TODOS', 'DIRECCIONAL', 6.0)")
        conn.execute("INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm) VALUES ('CLI EJE', 'TODOS', 'LIBRE', 2.5)")
        conn.commit()
    lim = database.construir_resolver_limite_posicion()
    # En un remolque la Pos 1 es eje libre: aplica 2,5 mm, no el límite direccional
    assert lim('CLI EJE', 'TODOS', 'Remolque Prueba', 1, [1, 2, 3, 4, 5]) == 2.5


def test_profundidad_maxima_por_rin_y_catalogo():
    assert database.rin_de_dimension('295/80R22.5') == 22.5
    assert database.profundidad_maxima_permitida(dimension='215/75R17.5')[0] == 18.0
    assert database.profundidad_maxima_permitida(dimension='29.5R25')[0] == database.PROF_MAXIMA_OTR
