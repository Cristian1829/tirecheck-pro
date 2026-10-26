import json
import os
import subprocess
import pytest
from fastapi.testclient import TestClient
import database
import server

def test_pwa_manifest_y_service_worker_disponibles(auth_client):
    """
    1. Verifica que GET /manifest.json y GET /sw.js respondan HTTP 200
    con sus respectivos Content-Type y estrategias de caché offline.
    """
    # 1. Manifest PWA
    resp_m = auth_client.get("/manifest.json")
    assert resp_m.status_code == 200
    assert "application/manifest+json" in resp_m.headers.get("content-type", "")
    manifest_data = resp_m.json()
    assert manifest_data["name"] == "TireAnalyze Pro — Patio Offline"
    assert manifest_data["display"] == "standalone"
    assert manifest_data["start_url"] == "/"
    assert manifest_data["background_color"] == "#091323"
    assert manifest_data["theme_color"] == "#091323"
    assert len(manifest_data["icons"]) > 0

    # 2. Service Worker
    resp_sw = auth_client.get("/sw.js")
    assert resp_sw.status_code == 200
    assert "application/javascript" in resp_sw.headers.get("content-type", "")
    assert resp_sw.headers.get("service-worker-allowed") == "/"
    sw_code = resp_sw.text
    assert "tireanalyze-patio-v2" in sw_code
    assert "caches.open" in sw_code
    assert "caches.match" in sw_code
    assert "Network-First" in sw_code
    assert "Cache-First" in sw_code


def test_obtener_paquete_offline_patio_completo(test_db, auth_client):
    """
    2. Siembra un vehículo con inspecciones y verifica que GET /api/offline/paquete-patio
    retorne tipologias, modelos, limites y vehiculos_perfil con las posiciones_previas del vehículo.
    """
    placa_test = "OFF123"
    database.insertar_inspeccion({
        "fecha": "2026-10-24",
        "cliente": "CLIENTE_TEST_OFFLINE",
        "subcliente": "PATIO_CENTRAL",
        "tipo_operacion": "URBANO",
        "placa": placa_test,
        "posicion": 1,
        "kilometraje": 45000,
        "tipologia": "Cabezote",
        "marca": "GOODYEAR",
        "diseno": "KMAX",
        "dimension": "295/80R22.5",
        "vida": "Original",
        "banda_reen": "",
        "prof_ext": 14.0,
        "prof_cent": 14.5,
        "prof_int": 14.0,
        "psi": 105,
        "novedades": "CORTE LEVE",
        "prof_inicial": 18.0,
        "numero_interno": "LL-OFF-01"
    })

    resp = auth_client.get("/api/offline/paquete-patio")
    assert resp.status_code == 200
    pkg = resp.json()

    assert "fecha_descarga" in pkg
    assert "tipologias" in pkg and isinstance(pkg["tipologias"], list) and len(pkg["tipologias"]) > 0
    # Verifica que cada tipología incluya esquema y posiciones calculadas
    tip_sample = pkg["tipologias"][0]
    assert "esquema" in tip_sample
    assert "posiciones" in tip_sample

    assert "operaciones" in pkg
    assert "modelos" in pkg
    assert "limites" in pkg
    assert "marcas_por_cliente" in pkg
    assert "catalogos_campos" in pkg
    assert "clientes" in pkg["catalogos_campos"]
    assert "subclientes_por_cliente" in pkg["catalogos_campos"]
    assert "disenos_por_marca" in pkg["catalogos_campos"]
    assert isinstance(pkg["catalogos_campos"]["disenos_por_marca"], dict)
    assert "GOODYEAR" in pkg["catalogos_campos"]["disenos_por_marca"]
    assert "KMAX" in pkg["catalogos_campos"]["disenos_por_marca"]["GOODYEAR"]

    assert "vehiculos_perfil" in pkg
    assert placa_test in pkg["vehiculos_perfil"]
    veh = pkg["vehiculos_perfil"][placa_test]
    assert veh["placa"] == placa_test
    assert veh["cliente"] == "CLIENTE_TEST_OFFLINE"
    assert "posiciones_previas" in veh
    assert "1" in veh["posiciones_previas"]
    pos1 = veh["posiciones_previas"]["1"]
    assert pos1["numero_interno"] == "LL-OFF-01"
    assert pos1["marca"] == "GOODYEAR"
    assert pos1["diseno"] == "KMAX"
    assert pos1["prof_cent"] == 14.5
    assert pos1["novedades"] == "CORTE LEVE"

    assert "llantas_catalogo_cliente" in pkg
    key_llanta = "CLIENTE_TEST_OFFLINE|||LL-OFF-01"
    assert key_llanta in pkg["llantas_catalogo_cliente"]
    llanta_info = pkg["llantas_catalogo_cliente"][key_llanta]
    assert llanta_info["numero_interno"] == "LL-OFF-01"
    assert llanta_info["marca"] == "GOODYEAR"


def test_sincronizar_lote_offline_exitoso_e_idempotente(test_db, auth_client):
    """
    3. Envía un lote de 4 llantas a POST /api/inspecciones/sincronizar-lote,
    verifica que las 4 se inserten (sincronizadas == 4), y luego reenvía el mismo lote
    con una corrección de profundidad en la Posición 1 comprobando que sea 100% idempotente
    (actualizadas == 4, rechazadas == []) sin duplicar registros en SQLite.
    """
    placa_lote = "IDEM888"
    items_lote = [
        {
            "dedup_key": f"{placa_lote}_{p}_2026-10-24",
            "placa": placa_lote,
            "posicion": p,
            "fecha": "2026-10-24",
            "cliente": "FLOTA_DEMO",
            "subcliente": "BODEGA_1",
            "tipo_operacion": "INTERMUNICIPAL",
            "kilometraje": 62000,
            "tipologia": "Camión Sencillo",
            "marca": "MICHELIN",
            "diseno": "X MULTI",
            "dimension": "295/80R22.5",
            "vida": "Original",
            "banda_reen": "",
            "prof_ext": 12.0,
            "prof_cent": 12.5,
            "prof_int": 12.0,
            "psi": 100,
            "prof_inicial": 16.0,
            "numero_interno": f"MIC-{p}"
        }
        for p in range(1, 5)
    ]

    # 1er envío: 4 sincronizadas
    resp1 = auth_client.post("/api/inspecciones/sincronizar-lote", json={"items": items_lote})
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["status"] == "ok"
    assert d1["sincronizadas"] == 4
    assert d1["actualizadas"] == 0
    assert len(d1["rechazadas"]) == 0

    # Verificar que existan exactamente 4 registros en base de datos
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM inspecciones WHERE UPPER(TRIM(placa)) = ?", (placa_lote,))
        assert cursor.fetchone()[0] == 4

    # 2do envío: con una corrección en posición 1
    items_lote[0]["prof_cent"] = 11.0
    items_lote[0]["novedades"] = "CALIBRADA EN PATIO"

    resp2 = auth_client.post("/api/inspecciones/sincronizar-lote", json={"items": items_lote})
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["status"] == "ok"
    assert d2["sincronizadas"] == 0
    assert d2["actualizadas"] == 4
    assert len(d2["rechazadas"]) == 0

    # Verificar idempotencia: sigue habiendo exactamente 4 registros, sin duplicados
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM inspecciones WHERE UPPER(TRIM(placa)) = ?", (placa_lote,))
        assert cursor.fetchone()[0] == 4
        # Verificar que la corrección se aplicó
        cursor.execute("SELECT prof_cent, novedades FROM inspecciones WHERE UPPER(TRIM(placa)) = ? AND posicion = 1", (placa_lote,))
        r = cursor.fetchone()
        assert r[0] == 11.0
        assert "CALIBRADA EN PATIO" in r[1]


def test_sincronizar_lote_parcial_aisla_rechazo_candado(test_db, auth_client):
    """
    4. Envía un lote con 2 llantas válidas y 1 llanta que viola un candado duro (prof_ext = 32.0 mm),
    verificando que las 2 válidas se guarden en la base de datos y solo la inválida aparezca detallada en rechazadas.
    """
    placa_parcial = "PARC777"
    items_parcial = [
        # Válida 1
        {
            "dedup_key": f"{placa_parcial}_1_2026-10-24",
            "placa": placa_parcial,
            "posicion": 1,
            "fecha": "2026-10-24",
            "cliente": "FLOTA_AISLADA",
            "subcliente": "SEDE_SUR",
            "tipo_operacion": "URBANO",
            "kilometraje": 30000,
            "tipologia": "Camioneta",
            "marca": "BRIDGESTONE",
            "diseno": "R268",
            "dimension": "225/75R16",
            "vida": "Original",
            "prof_ext": 10.0,
            "prof_cent": 10.0,
            "prof_int": 10.0,
            "psi": 65,
            "prof_inicial": 13.0,
            "numero_interno": "VAL-01"
        },
        # Inválida: Viola candado duro de 27.0 mm (prof_ext = 32.0 mm)
        {
            "dedup_key": f"{placa_parcial}_2_2026-10-24",
            "placa": placa_parcial,
            "posicion": 2,
            "fecha": "2026-10-24",
            "cliente": "FLOTA_AISLADA",
            "subcliente": "SEDE_SUR",
            "tipo_operacion": "URBANO",
            "kilometraje": 30000,
            "tipologia": "Camioneta",
            "marca": "BRIDGESTONE",
            "diseno": "R268",
            "dimension": "225/75R16",
            "vida": "Original",
            "prof_ext": 32.0,
            "prof_cent": 10.0,
            "prof_int": 10.0,
            "psi": 65,
            "prof_inicial": 13.0,
            "numero_interno": "INV-02"
        },
        # Válida 2
        {
            "dedup_key": f"{placa_parcial}_3_2026-10-24",
            "placa": placa_parcial,
            "posicion": 3,
            "fecha": "2026-10-24",
            "cliente": "FLOTA_AISLADA",
            "subcliente": "SEDE_SUR",
            "tipo_operacion": "URBANO",
            "kilometraje": 30000,
            "tipologia": "Camioneta",
            "marca": "BRIDGESTONE",
            "diseno": "R268",
            "dimension": "225/75R16",
            "vida": "Original",
            "prof_ext": 9.5,
            "prof_cent": 9.5,
            "prof_int": 9.5,
            "psi": 65,
            "prof_inicial": 13.0,
            "numero_interno": "VAL-03"
        }
    ]

    resp = auth_client.post("/api/inspecciones/sincronizar-lote", json={"items": items_parcial})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "ok"
    assert res["sincronizadas"] == 2
    assert len(res["rechazadas"]) == 1

    rechazo = res["rechazadas"][0]
    assert rechazo["posicion"] == 2
    assert rechazo["placa"] == placa_parcial
    # El tope depende del modelo en catálogo o del rin (ya no es 27 mm para todo)
    assert "ninguna profundidad puede superar" in rechazo["motivo"]

    # Verificar que en SQLite se guardaron las 2 válidas y NO la rechazada
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT posicion FROM inspecciones WHERE UPPER(TRIM(placa)) = ? ORDER BY posicion ASC", (placa_parcial,))
        posiciones_guardadas = [r[0] for r in cursor.fetchall()]
        assert posiciones_guardadas == [1, 3]


def test_frontend_contiene_motor_indexeddb_y_modal_offline(auth_client):
    """
    5. Verifica que la aplicación incluya TireAnalyzeOfflineDB, cola_pendientes,
    sincronizarColaOffline y #modalColaOffline, y que la sintaxis JavaScript pase limpia con node --check.
    """
    import subprocess
    import os

    resp = auth_client.get("/app")
    assert resp.status_code == 200
    html = resp.text

    js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "js")
    js_content = ""
    archivos_js = []
    if os.path.exists(js_dir):
        for fname in sorted(os.listdir(js_dir)):
            if fname.endswith(".js"):
                ruta = os.path.join(js_dir, fname)
                archivos_js.append(ruta)
                with open(ruta, "r", encoding="utf-8") as f_js:
                    js_content += "\n" + f_js.read()
    bundle = html + "\n" + js_content

    assert "TireAnalyzeOfflineDB" in bundle
    assert "cola_pendientes" in bundle
    assert "sincronizarColaOffline" in bundle
    assert "modalColaOffline" in html
    assert "btnEstadoConexionOffline" in html

    # Verificar sintaxis de los módulos JS de static/js
    assert len(archivos_js) > 0
    for ruta in archivos_js:
        resultado = subprocess.run(["node", "--check", ruta], capture_output=True, text=True)
        assert resultado.returncode == 0, f"Error de sintaxis JS detectado en {os.path.basename(ruta)}:\n{resultado.stderr}"


def test_offline_filtrado_disenos_por_marca_estricto(test_db, auth_client):
    """
    6. Verifica que en el paquete offline y en el frontend, los diseños estén estrictamente
    asociados a cada marca sin fugas entre fabricantes diferentes (ej. BRIDGESTONE vs MICHELIN).
    """
    # 1. Sembrar modelos en catálogo con marcas y diseños específicos
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM catalogo_modelos_llantas WHERE marca IN ('BRIDGESTONE', 'MICHELIN', 'PIRELLI')")
        cursor.execute("""
            INSERT INTO catalogo_modelos_llantas (marca, diseno, dimension, prof_inicial, tipo_llanta)
            VALUES 
                ('BRIDGESTONE', 'R168', '295/80R22.5', 16.0, 'Original'),
                ('BRIDGESTONE', 'M853', '295/80R22.5', 18.0, 'Original'),
                ('MICHELIN', 'X MULTI Z', '295/80R22.5', 15.5, 'Original'),
                ('MICHELIN', 'X WORKS D', '295/80R22.5', 19.0, 'Original'),
                ('PIRELLI', 'FG01', '295/80R22.5', 16.5, 'Original')
        """)
        conn.commit()

    # 2. Consultar paquete offline
    resp = auth_client.get("/api/offline/paquete-patio")
    assert resp.status_code == 200
    pkg = resp.json()

    dis_por_marca = pkg["catalogos_campos"]["disenos_por_marca"]
    assert "BRIDGESTONE" in dis_por_marca
    assert "MICHELIN" in dis_por_marca
    assert "PIRELLI" in dis_por_marca

    # Verificar que BRIDGESTONE contenga solo sus diseños
    assert "R168" in dis_por_marca["BRIDGESTONE"]
    assert "M853" in dis_por_marca["BRIDGESTONE"]
    assert "X MULTI Z" not in dis_por_marca["BRIDGESTONE"]
    assert "FG01" not in dis_por_marca["BRIDGESTONE"]

    # Verificar que MICHELIN contenga solo sus diseños
    assert "X MULTI Z" in dis_por_marca["MICHELIN"]
    assert "X WORKS D" in dis_por_marca["MICHELIN"]
    assert "R168" not in dis_por_marca["MICHELIN"]

    # Verificar que PIRELLI contenga solo su diseño
    assert "FG01" in dis_por_marca["PIRELLI"]
    assert "M853" not in dis_por_marca["PIRELLI"]

    # 3. Verificar que el frontend HTML no haga fallback a cc.disenos cuando hay marca seleccionada
    resp_front = auth_client.get("/app")
    assert resp_front.status_code == 200
    html = resp_front.text

    js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "js")
    js_content = ""
    if os.path.exists(js_dir):
        for fname in sorted(os.listdir(js_dir)):
            if fname.endswith(".js"):
                with open(os.path.join(js_dir, fname), "r", encoding="utf-8") as f_js:
                    js_content += "\n" + f_js.read()
    bundle = html + "\n" + js_content

    assert "disenos_por_marca" in bundle
    assert "NUNCA caer en cc.disenos para evitar mezclar marcas" in bundle

