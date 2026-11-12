"""Cada cliente tiene su propia numeración de llantas: el autocompletado nunca trae datos de otro cliente."""
import database


def _inspeccion(cliente, placa, marca, diseno, dimension):
    database.insertar_inspeccion({
        "fecha": "2026-10-10", "cliente": cliente, "subcliente": "SEDE", "placa": placa, "posicion": 1,
        "numero_interno": "100", "marca": marca, "diseno": diseno, "dimension": dimension, "vida": "Original",
        "kilometraje": 10000, "km_montaje": 5000, "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "prof_inicial": 16,
        "precio": 1200000, "psi": 110, "tipologia": "Cabezote (6x4)"})


def test_mismo_numero_en_dos_clientes_trae_solo_la_del_cliente(test_db):
    _inspeccion("CLIENTE UNO", "UNO001", "MICHELIN", "XZE", "295/80R22.5")
    _inspeccion("CLIENTE DOS", "DOS001", "BRIDGESTONE", "R268", "11R22.5")
    uno = database.obtener_llanta_por_cliente("CLIENTE UNO", "100")
    dos = database.obtener_llanta_por_cliente("CLIENTE DOS", "100")
    assert (uno["cliente"], uno["marca"], uno["dimension"]) == ("CLIENTE UNO", "MICHELIN", "295/80R22.5")
    assert (dos["cliente"], dos["marca"], dos["dimension"]) == ("CLIENTE DOS", "BRIDGESTONE", "11R22.5")


def test_numero_que_solo_existe_en_otro_cliente_no_se_encuentra(test_db):
    _inspeccion("CLIENTE DOS", "DOS001", "BRIDGESTONE", "R268", "11R22.5")
    assert database.obtener_llanta_por_cliente("CLIENTE UNO", "100") is None


def test_sin_cliente_no_busca_en_todos_los_clientes(test_db):
    _inspeccion("CLIENTE DOS", "DOS001", "BRIDGESTONE", "R268", "11R22.5")
    assert database.obtener_llanta_por_cliente("", "100") is None
    # Con la placa se deduce el cliente del vehículo
    assert database.obtener_llanta_por_cliente("", "100", placa="DOS001")["cliente"] == "CLIENTE DOS"


def test_paquete_sin_conexion_no_tiene_llave_sin_cliente(test_db):
    _inspeccion("CLIENTE UNO", "UNO001", "MICHELIN", "XZE", "295/80R22.5")
    _inspeccion("CLIENTE DOS", "DOS001", "BRIDGESTONE", "R268", "11R22.5")
    cat = database.obtener_paquete_offline_patio()["llantas_catalogo_cliente"]
    assert "|||100" not in cat
    assert cat["CLIENTE UNO|||100"]["marca"] == "MICHELIN"
    assert cat["CLIENTE DOS|||100"]["marca"] == "BRIDGESTONE"


def _insp(cliente, placa, pos, num, marca, fecha="2026-10-10", km=10000, prof=10):
    database.insertar_inspeccion({
        "fecha": fecha, "cliente": cliente, "subcliente": "SEDE", "placa": placa, "posicion": pos,
        "numero_interno": num, "marca": marca, "diseno": "XZE", "dimension": "295/80R22.5", "vida": "Original",
        "kilometraje": km, "km_montaje": 5000, "prof_ext": prof, "prof_cent": prof, "prof_int": prof, "prof_inicial": 16,
        "precio": 1200000, "psi": 110, "tipologia": "Cabezote (6x4)"})


def test_trazabilidad_no_mezcla_el_mismo_numero_de_dos_clientes(test_db):
    _insp("CLIENTE UNO", "UNO001", 1, "100", "MICHELIN")
    _insp("CLIENTE DOS", "DOS001", 1, "100", "BRIDGESTONE")
    filas = [f for f in database.obtener_trazabilidad_kpis_llanta() if f["numero_interno"] == "100"]
    assert sorted((f["cliente"], f["marca"]) for f in filas) == [("CLIENTE DOS", "BRIDGESTONE"), ("CLIENTE UNO", "MICHELIN")]


def test_trazabilidad_cada_llanta_sn_es_su_propia_fila(test_db):
    _insp("CLIENTE UNO", "UNO001", 1, "SN", "MICHELIN")
    _insp("CLIENTE UNO", "UNO001", 2, "SN", "GOODYEAR")
    _insp("CLIENTE UNO", "UNO002", 1, "SN", "CONTINENTAL")
    # La misma posición inspeccionada dos veces sigue siendo una sola llanta
    _insp("CLIENTE UNO", "UNO001", 1, "SN", "MICHELIN", fecha="2026-11-30", km=20000, prof=8)
    filas = [f for f in database.obtener_trazabilidad_kpis_llanta() if f["numero_interno"] == "SN"]
    assert sorted((f["placa"], f["posicion"], f["marca"]) for f in filas) == [
        ("UNO001", 1, "MICHELIN"), ("UNO001", 2, "GOODYEAR"), ("UNO002", 1, "CONTINENTAL")]
    p1 = next(f for f in filas if f["placa"] == "UNO001" and f["posicion"] == 1)
    assert p1["total_inspecciones"] == 2
