"""El catálogo trae los modelos comunes en Colombia y la carga no pisa ni resucita datos del cliente."""
import database
import catalogo_modelos_colombia as cat


def _contar(conn):
    return conn.execute("SELECT COUNT(*) FROM catalogo_modelos_llantas").fetchone()[0]


def test_filas_validas_y_sin_duplicados():
    filas = cat.modelos_colombia()
    llaves = [(t, m.lower(), d.lower(), dim) for t, m, d, dim, _, _ in filas]
    assert len(llaves) == len(set(llaves))
    for tipo, marca, diseno, dim, prof, _ in filas:
        assert tipo in ("Nueva", "Reencauche") and marca and diseno
        assert database.rin_de_dimension(dim) in (17.5, 19.5, 22.5)
        # la profundidad inicial debe caber dentro del tope del rin (prof + 1 mm de tolerancia)
        assert 8 <= prof <= database.profundidad_maxima_permitida(dimension=dim)[0], (marca, diseno, dim, prof)


def test_se_cargan_una_sola_vez_y_respetan_lo_borrado(test_db):
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM _control_migraciones WHERE nombre='catalogo_modelos_colombia_v1'").fetchone()[0] == 1
        total = _contar(conn)
        assert total >= 100
        conn.execute("DELETE FROM catalogo_modelos_llantas WHERE UPPER(marca)='LINGLONG'")
        conn.commit()
        borradas = total - _contar(conn)
    assert borradas > 0
    database.inicializar_bd()
    with database.get_connection() as conn:
        assert _contar(conn) == total - borradas


def test_dimension_de_modelo_en_varias_medidas(test_db):
    dims = database.buscar_dimensiones_modelo("Michelin", "X Multi D")["dimensiones"]
    assert {"295/80R22.5", "315/80R22.5", "11R22.5"} <= set(dims)
