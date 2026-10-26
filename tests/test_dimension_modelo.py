"""Al elegir un diseño, la dimensión se completa con la medida de ese modelo."""
import database


def _modelo(marca, diseno, dimension, prof=18.0, tipo="Nueva"):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO catalogo_modelos_llantas (tipo_llanta, marca, diseno, dimension, prof_inicial, descripcion) VALUES (?, ?, ?, ?, ?, '')",
            (tipo, marca, diseno, dimension, prof))
        conn.commit()


def test_dimension_del_modelo_desde_el_catalogo(test_db):
    _modelo("MARCAX", "MODELO UNICO", "11R22.5")
    res = database.buscar_dimensiones_modelo("marcax", "modelo unico")
    assert res == {"dimensiones": ["11R22.5"], "origen": "catalogo"}


def test_modelo_en_varias_medidas_las_devuelve_todas(test_db):
    _modelo("MARCAX", "MODELO DOBLE", "295/80R22.5")
    _modelo("MARCAX", "MODELO DOBLE", "315/80R22.5")
    assert database.buscar_dimensiones_modelo("MARCAX", "MODELO DOBLE")["dimensiones"] == ["295/80R22.5", "315/80R22.5"]


def test_no_mezcla_modelos_de_otra_marca(test_db):
    _modelo("MARCAX", "MISMO NOMBRE", "11R22.5")
    _modelo("MARCAY", "MISMO NOMBRE", "12R22.5")
    assert database.buscar_dimensiones_modelo("MARCAY", "MISMO NOMBRE")["dimensiones"] == ["12R22.5"]


def test_si_no_esta_en_catalogo_usa_el_historial_mas_frecuente(test_db):
    for i, dim in enumerate(["12R22.5", "12R22.5", "11R22.5"], start=1):
        database.insertar_inspeccion({
            "fecha": "2026-10-10", "cliente": "C", "subcliente": "S", "tipo_operacion": "CARGA", "placa": f"HIS00{i}",
            "posicion": 1, "kilometraje": 1000, "tipologia": "Cabezote (6x4)", "marca": "NOCAT", "diseno": "SOLO HISTORIAL",
            "dimension": dim, "vida": "Original", "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "psi": 110,
            "prof_inicial": 18, "numero_interno": f"HIS-{i}"})
    res = database.buscar_dimensiones_modelo("NOCAT", "SOLO HISTORIAL")
    assert res["origen"] == "historial" and res["dimensiones"][0] == "12R22.5"


def test_endpoint_y_valores_vacios(test_db, auth_client):
    _modelo("MARCAX", "MODELO API", "275/70R22.5")
    r = auth_client.get("/api/dimensiones-modelo?marca=MARCAX&diseno=MODELO API")
    assert r.status_code == 200 and r.json()["dimensiones"] == ["275/70R22.5"]
    assert auth_client.get("/api/dimensiones-modelo?marca=MARCAX&diseno=").json()["dimensiones"] == []
    assert auth_client.get("/api/dimensiones-modelo?marca=X&diseno=__nuevo__").json()["dimensiones"] == []
