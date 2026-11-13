"""El límite de cambio programado para el cliente es el que usan todos los indicadores."""
import database


def _reglas(cliente):
    with database.get_connection() as conn:
        return {(r[0], r[1]): r[2] for r in conn.execute(
            "SELECT subcliente, eje, limite_retiro_mm FROM configuracion_limites_retiro WHERE cliente = ?", (cliente,))}


def _avanzada(cliente):
    cfg = database.obtener_configuracion_avanzada_cliente(cliente)
    return (cfg["mm_retiro_direccional"], cfg["mm_retiro_traccion"], cfg["mm_retiro_arrastre"])


def test_cambiar_el_limite_del_cliente_arrastra_las_copias_por_sede(test_db):
    database.crear_o_actualizar_cliente({"cliente": "FLOTA UNO", "limite_retiro_mm": 3.0, "subclientes": "NORTE"})
    assert _reglas("FLOTA UNO")[("NORTE", "TODOS")] == 3.0
    database.crear_o_actualizar_cliente({"cliente": "FLOTA UNO", "limite_retiro_mm": 4.0, "subclientes": "NORTE"})
    assert _reglas("FLOTA UNO") == {("TODOS", "TODOS"): 4.0, ("NORTE", "TODOS"): 4.0}
    for eje in ("DIRECCIONAL", "TRACCIÓN", "LIBRE"):
        assert database.obtener_limite_retiro_cliente("FLOTA UNO", "NORTE", eje) == 4.0
    assert _avanzada("FLOTA UNO") == (4.0, 4.0, 4.0)


def test_una_excepcion_por_sede_distinta_del_general_se_respeta(test_db):
    database.crear_o_actualizar_cliente({"cliente": "FLOTA DOS", "limite_retiro_mm": 3.0})
    database.guardar_limite_retiro_cliente("FLOTA DOS", 5.0, "MINA", "SEDE MINA", "TODOS")
    database.crear_o_actualizar_cliente({"cliente": "FLOTA DOS", "limite_retiro_mm": 4.0})
    assert database.obtener_limite_retiro_cliente("FLOTA DOS", "SEDE MINA", "TRACCIÓN") == 5.0
    assert database.obtener_limite_retiro_cliente("FLOTA DOS", "OTRA", "TRACCIÓN") == 4.0


def test_una_regla_de_sede_no_cambia_el_limite_general_del_cliente(test_db):
    database.crear_o_actualizar_cliente({"cliente": "FLOTA TRES", "limite_retiro_mm": 4.0})
    database.guardar_limite_retiro_cliente("FLOTA TRES", 3.0, "", "SEDE X", "TODOS")
    lista = {c["cliente"]: c["limite_retiro_mm"] for c in database.obtener_todas_configuraciones_clientes()}
    assert lista["FLOTA TRES"] == 4.0
    assert _avanzada("FLOTA TRES") == (4.0, 4.0, 4.0)


def test_regla_por_eje_queda_en_la_configuracion_avanzada(test_db):
    database.crear_o_actualizar_cliente({"cliente": "FLOTA CUATRO", "limite_retiro_mm": 3.0})
    database.guardar_limite_retiro_cliente("FLOTA CUATRO", 4.5, "", "TODOS", "DIRECCIONAL")
    assert _avanzada("FLOTA CUATRO") == (4.5, 3.0, 3.0)


def test_limite_de_una_llanta_en_bodega_usa_sede_y_eje_del_cliente(test_db):
    database.crear_o_actualizar_cliente({"cliente": "FLOTA CINCO", "limite_retiro_mm": 3.0})
    database.guardar_limite_retiro_cliente("FLOTA CINCO", 4.0, "", "SEDE NORTE", "TODOS")
    database.guardar_limite_retiro_cliente("FLOTA CINCO", 5.0, "", "TODOS", "DIRECCIONAL")
    database.insertar_inspeccion({
        "fecha": "2026-10-10", "cliente": "FLOTA CINCO", "subcliente": "SEDE SUR", "placa": "CIN001", "posicion": 1,
        "numero_interno": "C1", "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5", "vida": "Original",
        "kilometraje": 10000, "km_montaje": 5000, "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "prof_inicial": 16,
        "precio": 1200000, "psi": 110, "tipologia": "Cabezote (6x4)"})
    assert database.limite_retiro_llanta("FLOTA CINCO", "SEDE NORTE") == 4.0       # sede, tracción
    assert database.limite_retiro_llanta("FLOTA CINCO", "SEDE SUR") == 3.0         # general del cliente
    assert database.limite_retiro_llanta("FLOTA CINCO", "SEDE SUR", "CIN001", 1) == 5.0  # salió de direccional


def test_reencauche_sin_numero_queda_como_r1(test_db):
    assert database.normalizar_vida_y_banda("Reencauche", "")[0] == "R1"
    assert database.normalizar_vida_y_banda("", "BANDAG BDR")[0] == "R1"
    assert database.normalizar_vida_y_banda("R2", "BANDAG")[0] == "R2"
    with database.get_connection() as conn:
        conn.execute("INSERT INTO inspecciones (fecha, cliente, placa, posicion, numero_interno, vida) "
                     "VALUES ('2026-10-10', 'FLOTA R', 'R00001', 1, 'X1', 'REENCAUCHE'), "
                     "('2026-10-10', 'FLOTA R', 'R00001', 2, 'X2', 'R2')")
        conn.commit()
    database.migrar_normalizar_vida_llantas()
    with database.get_connection() as conn:
        vidas = dict(conn.execute("SELECT numero_interno, vida FROM inspecciones WHERE cliente = 'FLOTA R'").fetchall())
    assert vidas == {"X1": "R1", "X2": "R2"}


def test_ciudad_limpia_queda_en_4mm_aunque_la_sede_bogota_tenga_3mm(test_db):
    with database.get_connection() as conn:
        conn.execute("INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm) "
                     "VALUES ('CIUDAD LIMPIA', 'BOGOTA', 'TODOS', 3.0)")
        if conn.execute("SELECT name FROM sqlite_master WHERE name = '_control_migraciones'").fetchone():
            conn.execute("DELETE FROM _control_migraciones WHERE nombre LIKE 'limite_ciudad_limpia_4mm%'")
        conn.commit()
    assert database.obtener_limite_retiro_cliente("CIUDAD LIMPIA", "BOGOTA", "TRACCIÓN") == 3.0
    assert database.migrar_limite_ciudad_limpia_4mm()["status"] == "ok"
    for eje in ("DIRECCIONAL", "TRACCIÓN", "LIBRE"):
        assert database.obtener_limite_retiro_cliente("CIUDAD LIMPIA", "BOGOTA", eje) == 4.0
    assert database.migrar_limite_ciudad_limpia_4mm()["status"] == "already_applied"


def test_kpi12_dice_cual_es_la_llanta_mas_baja_y_su_limite(test_db):
    database.crear_o_actualizar_cliente({"cliente": "FLOTA DOCE", "limite_retiro_mm": 4.0, "tipo_licencia": "PRO"})
    for pos, prof in ((5, 9.0), (6, 3.0)):
        database.insertar_inspeccion({
            "fecha": "2026-10-10", "cliente": "FLOTA DOCE", "subcliente": "SEDE", "placa": "DOC001", "posicion": pos,
            "numero_interno": f"D{pos}", "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5", "vida": "Original",
            "kilometraje": 60000, "km_montaje": 10000, "prof_ext": prof, "prof_cent": prof, "prof_int": prof,
            "prof_inicial": 16, "precio": 1200000, "psi": 110, "tipologia": "Cabezote (6x4)"})
    k12 = database.obtener_suite_completa_20_kpis({"cliente": "FLOTA DOCE"})["kpi_12"]
    assert k12["profundidad_actual"] == 3.0
    lb = k12["llanta_mas_baja"]
    assert (lb["placa"], lb["posicion"], lb["numero_interno"], lb["limite_retiro"]) == ("DOC001", 6, "D6", 4.0)
    assert k12["limites_retiro"] == [4.0]
    assert k12["llantas_en_limite"] == 1
