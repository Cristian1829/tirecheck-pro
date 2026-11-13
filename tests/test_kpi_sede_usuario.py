"""Un usuario con sedes asignadas solo ve en los KPI las bajas, bodegas y vehículos de sus sedes."""
import database

CLI = "FLOTA SEDES"


def _sembrar():
    database.crear_o_actualizar_cliente({"cliente": CLI, "tipo_licencia": "PRO", "limite_retiro_mm": 3.0,
                                         "subclientes": "NORTE, SUR"})
    database.guardar_licencia_cliente(CLI, "PRO")
    for placa, sede in (("NOR001", "NORTE"), ("SUR001", "SUR"), ("SUR002", "SUR")):
        database.guardar_vehiculo_padron(CLI, placa, "Cabezote (6x4)", sede)
    for placa, sede in (("NOR001", "NORTE"), ("SUR001", "SUR")):
        database.insertar_inspeccion({
            "fecha": "2026-10-10", "cliente": CLI, "subcliente": sede, "placa": placa, "posicion": 3,
            "numero_interno": f"{placa}-3", "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5",
            "vida": "Original", "kilometraje": 60000, "km_montaje": 10000, "prof_ext": 9, "prof_cent": 9, "prof_int": 9,
            "prof_inicial": 16, "precio": 1200000, "psi": 100, "tipologia": "Cabezote (6x4)"})
    with database.get_connection() as conn:
        for num, sede, dim in (("FVU-N", "NORTE", "295/80R22.5"), ("FVU-S1", "SUR", "315/80R22.5"), ("FVU-S2", "SUR", "315/80R22.5")):
            conn.execute("""INSERT INTO llantas_maestro (numero_interno, cliente, subcliente, marca, dimension, vida_actual,
                            ubicacion_bodega, causal_baja_fvu) VALUES (?, ?, ?, 'MICHELIN', ?, 'Original', 'BODEGA_6_FVU', 'Fatiga')""",
                         (num, CLI, sede, dim))
        conn.commit()
    database.crear_usuario("insp_norte_test", "clave-de-prueba-123", "Inspector Norte", rol="inspector",
                           cliente_asignado=CLI, vistas_permitidas="patio,kpis", sedes_asignadas=f"{CLI}|NORTE")


def test_usuario_de_una_sede_no_ve_bajas_ni_parque_de_otra(test_db):
    _sembrar()
    d = database.obtener_suite_completa_20_kpis({"cliente": CLI, "usuario": "insp_norte_test"})
    assert d["kpi_17"]["cantidad_fvu"] == 1
    assert d["kpi_18"]["por_marca"]["valores"] == [1]
    assert {m["dimension"] for m in d["kpi_20"]["matriz_mrp"]} == {"295/80R22.5"}
    assert d["kpi_01"]["total_padron"] == 1


def test_sin_restriccion_de_sede_ve_todo_el_cliente(test_db):
    _sembrar()
    d = database.obtener_suite_completa_20_kpis({"cliente": CLI})
    assert d["kpi_17"]["cantidad_fvu"] == 3
    assert d["kpi_01"]["total_padron"] == 3
