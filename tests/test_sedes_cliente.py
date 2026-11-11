"""Las sedes creadas o editadas en Catálogos se ofrecen en la inspección, aunque aún no tengan inspecciones."""
import database


def _inspeccion(cliente, sede):
    database.insertar_inspeccion({
        "fecha": "2026-10-10", "cliente": cliente, "subcliente": sede, "placa": "SED001", "posicion": 1,
        "numero_interno": "S-1", "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5", "vida": "Original",
        "kilometraje": 10000, "km_montaje": 5000, "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "prof_inicial": 16,
        "precio": 1200000, "psi": 110, "tipologia": "Cabezote (6x4)"})


def test_sede_nueva_del_catalogo_aparece_en_el_campo_sede(test_db):
    _inspeccion("CLIENTE SEDES", "SEDE NORTE")
    # Antes de editar el cliente solo existe la sede de la inspección
    assert database.obtener_valores_unicos_campo("subcliente", "CLIENTE SEDES") == ["SEDE NORTE"]

    res = database.crear_o_actualizar_cliente({"cliente": "CLIENTE SEDES", "subclientes": "SEDE NORTE, SEDE CENTRO, Bodega Sur"})
    assert res["ok"]
    sedes = database.obtener_valores_unicos_campo("subcliente", "CLIENTE SEDES")
    assert sedes == ["BODEGA SUR", "SEDE CENTRO", "SEDE NORTE"]


def test_sedes_de_un_cliente_no_se_mezclan_con_las_de_otro(test_db):
    database.crear_o_actualizar_cliente({"cliente": "CLIENTE UNO", "subclientes": "UNO A"})
    database.crear_o_actualizar_cliente({"cliente": "CLIENTE DOS", "subclientes": "DOS A, DOS B"})
    assert database.obtener_valores_unicos_campo("subcliente", "CLIENTE UNO") == ["UNO A"]
    assert database.obtener_valores_unicos_campo("subcliente", "CLIENTE DOS") == ["DOS A", "DOS B"]
    # La regla general del cliente («TODOS») no es una sede
    assert "TODOS" not in database.obtener_valores_unicos_campo("subcliente", "CLIENTE UNO")


def test_paquete_sin_conexion_incluye_las_sedes_del_catalogo(test_db):
    database.crear_o_actualizar_cliente({"cliente": "CLIENTE OFFLINE", "subclientes": "PATIO 1, PATIO 2"})
    paquete = database.obtener_paquete_offline_patio()
    por_cliente = paquete["catalogos_campos"]["subclientes_por_cliente"]
    assert sorted(por_cliente.get("CLIENTE OFFLINE", [])) == ["PATIO 1", "PATIO 2"]


def test_sede_del_parque_automotor_aparece_en_el_campo_sede(test_db):
    with database.get_connection() as conn:
        conn.execute("INSERT INTO catalogo_vehiculos (placa, tipologia, cliente, subcliente) VALUES ('PRQ001', 'Cabezote (6x4)', 'CLIENTE PARQUE', 'Patio Central')")
        conn.execute("INSERT INTO catalogo_vehiculos (placa, tipologia, cliente, subcliente) VALUES ('PRQ002', 'Cabezote (6x4)', 'OTRO CLIENTE', 'Otra Sede')")
        conn.commit()
    assert database.obtener_valores_unicos_campo("subcliente", "CLIENTE PARQUE") == ["PATIO CENTRAL"]
