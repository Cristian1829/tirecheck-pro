"""
Montar y desmontar llantas durante la inspección: solo versión PRO, el formulario trae la llanta que está hoy
en la posición, la llanta nueva se puede inspeccionar y el movimiento se ve en la Base de inspecciones.
"""
import os
import re

import pytest

import database
import modulo_bodegas_taller as mbt

CLI_PRO = "FLOTA TALLER PRO"
CLI_LIGHT = "FLOTA TALLER LIGHT"
PLACA = "TLR101"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


def _inspeccionar(client, serial, fecha, km=50000.0, prof=8.0, pos=3, cliente=CLI_PRO, placa=PLACA, **extra):
    datos = dict(
        fecha=fecha, cliente=cliente, subcliente="PRINCIPAL", tipo_operacion="CARGA", placa=placa, posicion=pos,
        kilometraje=km, tipologia="Cabezote (6x4)", marca="MICHELIN", diseno="XZE", dimension="295/80R22.5",
        vida="Original", prof_ext=prof, prof_cent=prof, prof_int=prof, psi=100, numero_interno=serial,
        prof_inicial=18.0, precio=1500000, km_montaje=10000,
    )
    datos.update(extra)
    return client.post("/api/inspecciones", json=datos)


def _stock(serial, cliente=CLI_PRO, marca="BRIDGESTONE", diseno="R268", dimension="11R22.5", prof=17.5, precio=1234567):
    r = mbt.crear_llantas_stock({"cliente_propietario": cliente, "modo": "individual", "numero_interno": serial,
                                 "marca_origen": marca, "diseno_origen": diseno, "dimension": dimension,
                                 "precio_compra_inicial": precio, "prof_inicial_nueva": prof})
    assert r["ok"], r


@pytest.fixture
def pro(auth_client, test_db):
    database.guardar_licencia_cliente(CLI_PRO, "PRO")
    database.guardar_licencia_cliente(CLI_LIGHT, "LIGHT")
    return auth_client


def _montar(client, serial, km=60123.0, pos=3, placa=PLACA, cliente=CLI_PRO, **extra):
    return client.post("/api/taller/montar", json=dict(placa=placa, posicion=pos, numero_interno=serial,
                                                       cliente_propietario=cliente, odometro_vehiculo=km, **extra))


def _ubicacion(serial):
    with database.get_connection() as conn:
        return conn.execute("SELECT ubicacion_bodega, placa_actual, posicion_actual FROM llantas_maestro WHERE numero_interno = ?",
                            (serial,)).fetchone()


# ================= SOLO VERSIÓN PRO =================
def test_panel_oculto_por_defecto_y_sin_textos_de_light():
    html = _leer("templates/index.html")
    seccion = re.search(r'<div id="seccionTallerPatio" class="([^"]*)"', html)
    assert "hidden" in seccion.group(1).split()
    assert "bannerTallerLight" not in html and "LIGHT (Solo Lectura)" not in html
    js = _leer("static/js/modulo_bodegas.js")
    assert "Plan FULL" not in js and "return true;\n    }\n\n    /**\n     * Consulta" not in js.replace("\r\n", "\n")


def test_posicion_info_solo_permite_taller_en_pro(pro):
    assert pro.get(f"/api/taller/posicion-info?placa={PLACA}&posicion=1&cliente={CLI_PRO}").json()["permite_taller"] is True
    assert pro.get(f"/api/taller/posicion-info?placa=LGT1&posicion=1&cliente={CLI_LIGHT}").json()["permite_taller"] is False
    # Sin licencia configurada: LIGHT. Sin cliente: tampoco se ofrece.
    assert pro.get("/api/taller/posicion-info?placa=LGT2&posicion=1&cliente=SIN CONFIG").json()["permite_taller"] is False
    assert pro.get("/api/taller/posicion-info?placa=NOEXISTE&posicion=1").json()["permite_taller"] is False
    assert pro.get("/api/taller/posicion-info?placa=NOEXISTE&posicion=1&cliente=TODOS").json()["permite_taller"] is False


def test_montar_y_desmontar_rechazados_fuera_de_pro(pro):
    assert _montar(pro, "X1", cliente=CLI_LIGHT).status_code == 403
    assert _montar(pro, "X1", cliente="SIN CONFIG").status_code == 403
    assert _montar(pro, "X1", cliente="", placa="NOEXISTE").status_code == 400
    r = pro.post("/api/taller/desmontar", json={"numero_interno": "X1", "cliente_propietario": CLI_LIGHT})
    assert r.status_code == 403


# ================= EL FORMULARIO TRAE LA LLANTA NUEVA =================
def test_al_seleccionar_la_posicion_trae_la_llanta_montada(pro):
    assert _inspeccionar(pro, "VIEJA-1", "2026-10-01").status_code == 200, "inspección inicial"
    _stock("NUEVA-1")
    assert _montar(pro, "NUEVA-1").status_code == 200

    d = pro.get(f"/api/inspeccion-anterior?placa={PLACA}&posicion=3").json()
    assert d["encontrado"] is True and d["llanta_cambiada"] is True
    datos = d["datos"]
    assert datos["numero_interno"] == "NUEVA-1"
    assert datos["marca"] == "BRIDGESTONE" and datos["diseno"] == "R268" and datos["dimension"] == "11R22.5"
    assert datos["prof_inicial"] == 17.5 and datos["precio"] == 1234567 and datos["km_montaje"] == 60123
    assert datos["prof_ext"] is None and datos["novedades"] == ""
    assert datos["cliente"] == CLI_PRO  # lo del vehículo se conserva

    # El panel muestra los mismos datos
    ll = pro.get(f"/api/taller/posicion-info?placa={PLACA}&posicion=3&cliente={CLI_PRO}").json()["llanta_instalada"]
    assert ll["numero_interno"] == "NUEVA-1" and ll["prof_actual_min"] == 17.5 and ll["km_montaje_actual"] == 60123
    assert _ubicacion("VIEJA-1")[0] == "BODEGA_2_RECAMBIO"


def test_sin_cambios_sigue_trayendo_la_ultima_inspeccion(pro):
    _inspeccionar(pro, "IGUAL-1", "2026-10-01")
    d = pro.get(f"/api/inspeccion-anterior?placa={PLACA}&posicion=3").json()
    assert d["datos"]["numero_interno"] == "IGUAL-1" and not d.get("llanta_cambiada")
    assert d["datos"]["prof_ext"] == 8.0


def test_posicion_sin_inspecciones_trae_la_llanta_montada(pro):
    _stock("PRIMERA-1")
    _montar(pro, "PRIMERA-1", pos=5)
    d = pro.get(f"/api/inspeccion-anterior?placa={PLACA}&posicion=5").json()
    assert d["llanta_cambiada"] is True and d["datos"]["numero_interno"] == "PRIMERA-1"


def test_tras_desmontar_la_posicion_queda_vacia(pro):
    _inspeccionar(pro, "SALE-1", "2026-10-01")
    r = pro.post("/api/taller/desmontar", json={"numero_interno": "SALE-1", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 61000,
                                                "profundidad": 7.0, "bodega_destino": "Bodega_2_Reutilizable"})
    assert r.status_code == 200, r.text
    d = pro.get(f"/api/inspeccion-anterior?placa={PLACA}&posicion=3").json()
    assert d["encontrado"] is False and d["llanta_retirada"] is True
    info = pro.get(f"/api/taller/posicion-info?placa={PLACA}&posicion=3&cliente={CLI_PRO}").json()
    assert info["llanta_instalada"] is None  # antes seguía mostrando la llanta retirada


def test_posicion_cambiada_vuelve_a_pendiente_el_mismo_dia(pro):
    hoy = "2026-11-05"
    _inspeccionar(pro, "HOY-1", hoy)
    assert pro.get(f"/api/posiciones-inspeccionadas?placa={PLACA}&fecha={hoy}").json()["posiciones"] == [3]
    _stock("HOY-2")
    with database.get_connection() as conn:
        conn.execute("UPDATE inspecciones SET novedades = 'CORTE' WHERE numero_interno = 'HOY-1'")
        conn.commit()
    mbt.montar_llanta_taller({"placa": PLACA, "posicion": 3, "numero_interno": "HOY-2", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 60000})
    with database.get_connection() as conn:  # el montaje queda con la misma fecha de la inspección
        conn.execute("UPDATE kardex_movimientos_llanta SET fecha_movimiento = ? WHERE numero_interno = 'HOY-2'", (hoy,))
        conn.commit()
    det = pro.get(f"/api/posiciones-inspeccionadas?placa={PLACA}&fecha={hoy}").json()
    assert det["posiciones"] == [] and det["posiciones_con_novedad"] == []


def test_llanta_de_inventario_sin_inspecciones_se_encuentra_por_numero(pro):
    _stock("SOLO-INV")
    d = pro.get(f"/api/llanta-por-cliente?numero_interno=SOLO-INV&cliente={CLI_PRO}").json()
    assert d["encontrado"] is True
    assert d["datos"]["marca"] == "BRIDGESTONE" and d["datos"]["precio"] == 1234567 and d["datos"]["prof_inicial"] == 17.5


# ================= LA LLANTA NUEVA SE PUEDE INSPECCIONAR =================
def test_candados_no_bloquean_la_primera_inspeccion_de_la_llanta_montada(pro):
    """Frecuencia, desgaste («subió la profundidad») y misma fecha se refieren a la llanta anterior."""
    assert _inspeccionar(pro, "GASTADA", "2027-12-20", prof=4.0).status_code == 200
    _stock("ESTRENO")
    assert _montar(pro, "ESTRENO", km=60000).status_code == 200
    with database.get_connection() as conn:  # montada después de esa inspección
        conn.execute("UPDATE kardex_movimientos_llanta SET fecha_movimiento = '2027-12-25' WHERE numero_interno = 'ESTRENO'")
        conn.commit()
    r = _inspeccionar(pro, "ESTRENO", "2027-12-31", km=60000, prof=17.0, marca="BRIDGESTONE", diseno="R268", prof_inicial=17.5)
    assert r.status_code == 200, r.text
    # Ya inspeccionada, vuelven a aplicar los candados normales
    r = _inspeccionar(pro, "ESTRENO", "2027-12-31", km=60000, prof=17.0, marca="BRIDGESTONE", diseno="R268", prof_inicial=17.5)
    assert r.status_code == 400


def test_llanta_movida_de_otra_placa_el_mismo_mes_se_puede_inspeccionar(pro):
    assert _inspeccionar(pro, "VIAJERA", "2027-12-10", placa="TLR201", pos=3).status_code == 200
    assert pro.post("/api/taller/desmontar", json={"numero_interno": "VIAJERA", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 60000,
                                                   "profundidad": 8.0, "bodega_destino": "Bodega_2_Reutilizable"}).status_code == 200
    assert _montar(pro, "VIAJERA", placa="TLR202", pos=4, km=30000).status_code == 200
    r = _inspeccionar(pro, "VIAJERA", "2027-12-31", placa="TLR202", pos=4, km=30000)
    assert r.status_code == 200, r.text


def test_candados_siguen_activos_sin_movimiento_registrado(pro):
    """Escribir otro número no salta los candados: sin montaje en el kardex no hay excepción."""
    assert _inspeccionar(pro, "A-1", "2027-12-20", prof=4.0).status_code == 200
    assert _inspeccionar(pro, "B-1", "2027-12-31", prof=4.0).status_code == 400


# ================= REINICIO DEL SERVIDOR =================
def test_reiniciar_no_desmonta_la_llanta_recien_montada(pro):
    """La sincronización al arrancar devolvía a Bodega 2 la llanta montada y dejaba vacía la posición."""
    _inspeccionar(pro, "ANTES-1", "2026-10-01")
    _stock("DESPUES-1")
    assert _montar(pro, "DESPUES-1").status_code == 200
    assert _ubicacion("DESPUES-1")[0] == "MONTADA_OPERACION"

    database.sincronizar_maestro_desde_inspecciones()

    assert _ubicacion("DESPUES-1") == ("MONTADA_OPERACION", PLACA, 3)
    assert _ubicacion("ANTES-1")[0] == "BODEGA_2_RECAMBIO"


def test_sincronizar_no_devuelve_a_su_posicion_anterior_una_llanta_rotada(pro):
    _inspeccionar(pro, "ROTA-1", "2026-10-01", pos=3)
    with database.get_connection() as conn:
        conn.execute("UPDATE llantas_maestro SET posicion_actual = 4, fecha_ultimo_movimiento = '2026-11-01' WHERE numero_interno = 'ROTA-1'")
        database.registrar_kardex(conn.cursor(), "ROTA-1", CLI_PRO, database.MONTADA, database.MONTADA, "ROTACION",
                                  fecha="2026-11-01", placa=PLACA, posicion=4)
        conn.commit()
    database.sincronizar_maestro_desde_inspecciones()
    assert _ubicacion("ROTA-1") == ("MONTADA_OPERACION", PLACA, 4)


# ================= VALOR Y KILOMETRAJE EXACTOS =================
def test_valor_y_kilometraje_aceptan_cualquier_numero():
    html = _leer("templates/index.html")
    assert 'step="1000"' not in html and 'step="100"' not in html
    for campo in ("precio", "km_montaje", "mont_nueva_precio", "mont_odometro", "desm_odometro"):
        etiqueta = re.search(rf'<input[^>]*id="{campo}"[^>]*>', html).group(0)
        assert 'step="any"' in etiqueta, campo


def test_valores_exactos_se_guardan_sin_redondear(pro):
    r = pro.post("/api/taller/montar", json={
        "placa": PLACA, "posicion": 3, "numero_interno": "EXACTA-1", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 123457,
        "es_nueva_directa": True, "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5", "prof_inicial": 16.5, "precio_compra": 1653249,
    })
    assert r.status_code == 200, r.text
    datos = pro.get(f"/api/inspeccion-anterior?placa={PLACA}&posicion=3").json()["datos"]
    assert datos["precio"] == 1653249 and datos["km_montaje"] == 123457 and datos["prof_inicial"] == 16.5

    r = _inspeccionar(pro, "EXACTA-1", "2027-12-31", km=123457, precio=1653249, km_montaje=123457, prof=11.0, prof_inicial=16.5)
    assert r.status_code == 200, r.text
    with database.get_connection() as conn:
        fila = conn.execute("SELECT precio, km_montaje FROM inspecciones WHERE numero_interno = 'EXACTA-1'").fetchone()
    assert fila == (1653249, 123457)


# ================= REVISIÓN DEL MÓDULO =================
def test_nueva_directa_no_pisa_una_llanta_existente(pro):
    _stock("YA-EXISTE")
    r = _montar(pro, "YA-EXISTE", es_nueva_directa=True)
    assert r.status_code == 400 and "ya existe" in r.json()["detail"]


def test_odometro_no_retrocede(pro):
    _inspeccionar(pro, "ODO-1", "2026-10-01", km=50000)
    _stock("ODO-2")
    r = _montar(pro, "ODO-2", km=49000)
    assert r.status_code == 400 and "odómetro" in r.json()["detail"].lower()
    assert _montar(pro, "ODO-2", km=52000).status_code == 200
    r = pro.post("/api/taller/desmontar", json={"numero_interno": "ODO-2", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 51000,
                                                "profundidad": 15, "bodega_destino": "Bodega_2_Reutilizable"})
    assert r.status_code == 400
    assert _ubicacion("ODO-2")[0] == "MONTADA_OPERACION"


def test_km_de_llanta_con_montaje_de_la_inspeccion_no_se_pierden(pro):
    _inspeccionar(pro, "KM-1", "2026-10-01", km=50000, km_montaje=40000)
    with database.get_connection() as conn:
        conn.execute("UPDATE llantas_maestro SET km_montaje_actual = 0, km_montaje_ciclo = 40000 WHERE numero_interno = 'KM-1'")
        conn.commit()
    r = pro.post("/api/taller/desmontar", json={"numero_interno": "KM-1", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 55000,
                                                "profundidad": 7, "bodega_destino": "Bodega_2_Reutilizable"}).json()
    assert r["delta_km"] == 15000


def test_mismo_numero_en_dos_clientes_no_se_cruza(pro):
    database.guardar_licencia_cliente("OTRA FLOTA", "PRO")
    _inspeccionar(pro, "CRUCE", "2026-10-01", cliente="OTRA FLOTA", placa="OTR001")
    _inspeccionar(pro, "CRUCE", "2026-10-01")
    r = pro.post("/api/taller/desmontar", json={"numero_interno": "CRUCE", "cliente_propietario": CLI_PRO, "odometro_vehiculo": 60000,
                                                "profundidad": 7, "bodega_destino": "Bodega_2_Reutilizable"})
    assert r.status_code == 200
    with database.get_connection() as conn:
        ubic = dict(conn.execute("SELECT cliente, ubicacion_bodega FROM llantas_maestro WHERE numero_interno = 'CRUCE'").fetchall())
    assert ubic == {CLI_PRO: "BODEGA_2_RECAMBIO", "OTRA FLOTA": "MONTADA_OPERACION"}


# ================= BASE DE INSPECCIONES =================
def _movs(client):
    r = client.get("/api/inspecciones/movimientos")
    assert r.status_code == 200, r.text
    return r.json()


def test_base_muestra_el_montaje_pendiente_y_luego_en_su_inspeccion(pro):
    _inspeccionar(pro, "OLD-9", "2026-10-01")
    _stock("NEW-9")
    _montar(pro, "NEW-9", km=60123)

    m = _movs(pro)
    # La llanta nueva aún sin inspección aparece como fila de movimiento
    fila = next(x for x in m["sin_inspeccion"] if x["numero_interno"] == "NEW-9")
    assert fila["es_movimiento"] is True and fila["placa"] == PLACA and fila["posicion"] == 3
    assert fila["marca"] == "BRIDGESTONE"
    assert "Montada" in fila["movimientos"][0]["texto"] and "60.123 km" in fila["movimientos"][0]["texto"]
    assert "reemplaza a OLD-9" in fila["movimientos"][0]["texto"]
    # Y la inspección de la llanta retirada dice a dónde se fue
    id_old = next(r["id"] for r in pro.get("/api/inspecciones").json() if r["numero_interno"] == "OLD-9")
    retiro = m["por_inspeccion"][str(id_old)][0]
    assert retiro["tipo"] == "RETIRO" and "Bodega 2" in retiro["texto"]

    # Al inspeccionarla, el movimiento pasa a su fila de inspección
    assert _inspeccionar(pro, "NEW-9", "2027-12-31", km=60123, prof=17.0, prof_inicial=17.5, marca="BRIDGESTONE", diseno="R268").status_code == 200
    m = _movs(pro)
    assert not [x for x in m["sin_inspeccion"] if x["numero_interno"] == "NEW-9"]
    id_new = next(r["id"] for r in pro.get("/api/inspecciones").json() if r["numero_interno"] == "NEW-9")
    assert m["por_inspeccion"][str(id_new)][0]["tipo"] == "MONTAJE"


def test_base_no_cambia_la_lista_de_inspecciones_ni_cuenta_movimientos(pro):
    _stock("MOV-LISTA")
    _montar(pro, "MOV-LISTA")
    assert pro.get("/api/inspecciones").json() == []
    assert len(_movs(pro)["sin_inspeccion"]) == 1


def test_movimientos_respetan_el_cliente_del_usuario(pro):
    _stock("MOV-AJENO")
    _montar(pro, "MOV-AJENO")
    database.crear_usuario("insp_otro", "Clave-Segura-77", "Otro", "inspector", "OTRO CLIENTE", "basedatos,patio")
    assert database.obtener_movimientos_base_inspecciones(usuario="insp_otro")["sin_inspeccion"] == []
    assert len(database.obtener_movimientos_base_inspecciones()["sin_inspeccion"]) == 1


def test_exportar_excel_incluye_el_movimiento(pro):
    import io

    import pandas as pd
    _inspeccionar(pro, "XLS-OLD", "2026-10-01")
    _stock("XLS-NEW")
    _montar(pro, "XLS-NEW")
    r = pro.get("/api/inspecciones/exportar-excel")
    assert r.status_code == 200
    df = pd.read_excel(io.BytesIO(r.content))
    assert "Retirada" in df.loc[df["N.º interno"] == "XLS-OLD", "Movimiento"].iloc[0]


# ================= NUEVA DIRECTA: LISTAS DE MARCA, DISEÑO Y DIMENSIÓN =================
def test_nueva_directa_usa_listas_desplegables():
    html = _leer("templates/index.html")
    for campo in ("mont_nueva_marca", "mont_nueva_diseno", "mont_nueva_dimension"):
        assert f'<select id="{campo}"' in html, campo
        assert f'<input type="text" id="{campo}"' not in html, campo
    prof = re.search(r'<input[^>]*id="mont_nueva_prof"[^>]*>', html).group(0)
    assert 'value="16.0"' not in prof  # la profundidad sale del catálogo, no de un valor fijo


def test_precio_lista_del_cliente_para_la_llanta(pro):
    database.guardar_precio_cliente(CLI_PRO, "MICHELIN", "XZE", "295/80R22.5", "NUEVA", 1287631, "2020-01-01")
    q = "marca=MICHELIN&diseno=XZE&dimension=295/80R22.5"
    assert pro.get(f"/api/precio-lista?cliente={CLI_PRO}&{q}").json()["precio"] == 1287631
    # Sin precio del cliente no se inventa ni se toma de otro cliente
    assert pro.get(f"/api/precio-lista?cliente={CLI_LIGHT}&{q}").json()["precio"] is None
    assert pro.get(f"/api/precio-lista?{q}").json()["precio"] is None
    assert pro.get(f"/api/precio-lista?cliente={CLI_PRO}&marca=MICHELIN&diseno=XZE&dimension=11R22.5").json()["precio"] is None


def test_precio_lista_exige_sesion():
    from fastapi.testclient import TestClient
    import server
    assert TestClient(server.app).get("/api/precio-lista?cliente=X").status_code == 401


# ================= DAR DE ALTA EN BODEGA: LISTAS Y BODEGA ELEGIDA =================
def test_alta_en_bodega_usa_listas_desplegables():
    html = _leer("templates/index.html")
    for campo in ("alta_marca", "alta_diseno", "alta_dimension", "alta_banda_reen"):
        assert f'<select id="{campo}"' in html, campo
        assert f'<input type="text" id="{campo}"' not in html, campo
    prof = re.search(r'<input[^>]*id="alta_prof_inicial"[^>]*>', html).group(0)
    assert 'value="18.0"' not in prof
    js = _leer("static/js/modulo_bodegas.js")
    assert "|| 18.0" not in js  # la profundidad no se inventa
    assert "bodega_inicial:" not in js  # el servidor espera ubicacion_bodega


def test_alta_respeta_la_bodega_elegida_y_los_datos(pro):
    for bodega in ("BODEGA_2_RECAMBIO", "BODEGA_4_REENCAUCHADAS"):
        serial = f"ALTA-{bodega[7]}"
        r = pro.post("/api/bodegas/alta", json={
            "cliente": CLI_PRO, "numero_interno": serial, "ubicacion_bodega": bodega, "marca": "MICHELIN", "diseno": "XZE",
            "dimension": "295/80R22.5", "vida_actual": "R1", "banda_reen": "BDM", "prof_inicial": 14.5, "prof_actual_min": 14.5, "costo_compra": 987653,
        })
        assert r.status_code == 200, r.text
        assert _ubicacion(serial)[0] == bodega
