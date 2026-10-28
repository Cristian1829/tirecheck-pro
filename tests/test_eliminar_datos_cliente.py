"""Deshacer un cargue de inspecciones por error: el administrador borra los datos de cargue de un cliente
(con vista previa, confirmación por nombre y copia de seguridad) sin tocar a los demás clientes."""
import os

from fastapi.testclient import TestClient

import database
import server

MALO, OTRO = "TRANSPORTES DE PRUEBA", "OTRO CLIENTE"


def _insp(cliente, placa):
    assert database.insertar_inspeccion({
        "fecha": "2026-10-08", "cliente": cliente, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": placa,
        "posicion": 1, "kilometraje": 50000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN",
        "diseno": "X MULTI D", "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10,
        "prof_int": 10, "psi": 100, "prof_inicial": 21.5, "numero_interno": f"SN-{placa}"})
    database.sincronizar_vehiculo_catalogo(placa, "Cabezote (6x4)", cliente, "SEDE")


def _escenario():
    for p in ("M1", "M2", "M3"):
        _insp(MALO, p)
    _insp(OTRO, "O1")
    database.guardar_licencia_cliente(MALO, "PRO")


def test_vista_previa_no_borra(test_db):
    _escenario()
    r = database.eliminar_datos_cargados_cliente(MALO.lower())
    insp = next(d for d in r["detalle"] if d["tabla"] == "inspecciones")
    assert insp["registros"] == 3 and not r["ejecutado"]
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM inspecciones").fetchone()[0] == 4


def test_borra_solo_el_cliente_y_conserva_su_licencia(test_db):
    _escenario()
    database.eliminar_datos_cargados_cliente(MALO, ejecutar=True)
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM inspecciones WHERE cliente = ?", (MALO,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM catalogo_vehiculos WHERE cliente = ?", (MALO,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM inspecciones WHERE cliente = ?", (OTRO,)).fetchone()[0] == 1
    assert database.obtener_licencia_cliente(MALO) == "PRO"


def test_endpoint_exige_admin_confirmacion_y_hace_respaldo(test_db, auth_client, inspector_token):
    _escenario()
    prev = auth_client.get(f"/api/admin/datos-cliente?cliente={MALO}")
    assert prev.status_code == 200 and prev.json()["total"] >= 3

    # Sin escribir bien el nombre no se borra nada
    mal = auth_client.post("/api/admin/datos-cliente/eliminar", json={"cliente": MALO, "confirmacion": "OTRO"})
    assert mal.status_code == 400

    otro = TestClient(server.app)
    otro.headers.update({"Authorization": f"Bearer {inspector_token}"})
    assert otro.get(f"/api/admin/datos-cliente?cliente={MALO}").status_code == 403
    assert otro.post("/api/admin/datos-cliente/eliminar",
                     json={"cliente": MALO, "confirmacion": MALO}).status_code == 403

    ok = auth_client.post("/api/admin/datos-cliente/eliminar", json={"cliente": MALO, "confirmacion": MALO.lower()})
    assert ok.status_code == 200, ok.text
    respaldo = os.path.join(os.path.dirname(os.path.abspath(database.DB_PATH)), "backups", ok.json()["respaldo"])
    assert os.path.exists(respaldo)
    os.remove(respaldo)
    assert auth_client.get(f"/api/admin/datos-cliente?cliente={MALO}").json()["total"] == 0
    # Ya sin datos, un segundo intento no hace nada
    assert auth_client.post("/api/admin/datos-cliente/eliminar",
                            json={"cliente": MALO, "confirmacion": MALO}).status_code == 404
