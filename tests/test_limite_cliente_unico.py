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
