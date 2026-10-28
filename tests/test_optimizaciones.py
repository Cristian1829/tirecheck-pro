"""Optimizaciones del barrido: índices que sí se usan, importación que actualiza Bodegas, lista sin fotos,
conexión compartida y último corte por vehículo calculado en bloque."""
import json

import pandas as pd

import database


def _insp(cliente, placa, pos, sn, fecha, **extra):
    d = {"fecha": fecha, "cliente": cliente, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": placa,
         "posicion": pos, "kilometraje": 50000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
         "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "psi": 100,
         "prof_inicial": 21.5, "numero_interno": sn}
    d.update(extra)
    return database.insertar_inspeccion(d)


def _plan(sql):
    with database.get_connection() as conn:
        return " ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql))


def test_busquedas_con_upper_usan_indice(test_db):
    """La sincronización de llantas y el perfil del vehículo buscan con UPPER(...): no deben recorrer la tabla."""
    assert "USING" in _plan("SELECT id FROM llantas_maestro WHERE UPPER(cliente) = 'X' AND UPPER(numero_interno) = 'Y'")
    assert "USING" in _plan("SELECT id FROM llantas_maestro WHERE UPPER(cliente) = 'X' AND UPPER(placa_actual) = 'P' AND posicion_actual = 1")
    assert "USING" in _plan("SELECT fecha_movimiento FROM kardex_movimientos_llanta WHERE UPPER(cliente) = 'X' AND UPPER(numero_interno) = 'Y'")
    assert "USING" in _plan("SELECT fecha FROM inspecciones WHERE UPPER(TRIM(placa)) = 'P' ORDER BY fecha DESC, id DESC LIMIT 1")
    assert "USING" in _plan("SELECT cliente FROM catalogo_vehiculos WHERE UPPER(TRIM(placa)) = 'P'")


def test_importar_excel_actualiza_bodegas_sin_reiniciar(test_db, tmp_path):
    ruta = tmp_path / "insp.xlsx"
    pd.DataFrame([{"Fecha": "2026-10-08", "Cliente": "FLOTA EXCEL", "Sede": "SEDE", "Placa": "EXC001", "Posicion": 1,
                   "Tipologia": "Cabezote (6x4)", "Marca": "MICHELIN", "Dimension": "295/80R22.5", "Prof Ext": 10,
                   "Prof Cent": 10, "Prof Int": 10, "PSI": 100, "Kilometraje": 1000, "Numero Interno": "SN-EXC-1"}]).to_excel(ruta, index=False)
    assert database.cargar_excel_a_bd(str(ruta)) == 1
    with database.get_connection() as conn:
        fila = conn.execute("SELECT ubicacion_bodega, placa_actual FROM llantas_maestro WHERE numero_interno = 'SN-EXC-1'").fetchone()
    assert fila == ("MONTADA_OPERACION", "EXC001")


def test_lista_de_inspecciones_sin_fotos_trae_la_cantidad(test_db, auth_client):
    una = "data:image/jpeg;base64,AAAA"
    i1 = _insp("FLOTA FOTOS", "FOT001", 1, "SN-F1", "2026-10-08", foto_novedad=json.dumps([una, una, una]))
    i2 = _insp("FLOTA FOTOS", "FOT001", 2, "SN-F2", "2026-10-08", foto_novedad=una)
    i3 = _insp("FLOTA FOTOS", "FOT001", 3, "SN-F3", "2026-10-08")
    lista = {r["id"]: r for r in auth_client.get("/api/inspecciones").json()}
    assert all(lista[i]["foto_novedad"] == "" for i in (i1, i2, i3))
    assert (lista[i1]["fotos_cantidad"], lista[i2]["fotos_cantidad"], lista[i3]["fotos_cantidad"]) == (3, 1, 0)
    # La inspección individual (galería y edición) sí trae las fotos completas
    assert auth_client.get(f"/api/inspecciones/{i1}").json()["foto_novedad"].count(una) == 3


def test_conexion_compartida_reutiliza_una_sola_conexion(test_db):
    with database.conexion_compartida() as c1:
        with database.get_connection() as c2, database.get_connection() as c3:
            assert c1 is c2 is c3
    # Fuera del bloque cada llamada vuelve a abrir su propia conexión
    with database.get_connection() as a, database.get_connection() as b:
        assert a is not b


def test_paquete_offline_sigue_completo(test_db):
    _insp("FLOTA OFF", "OFF001", 1, "SN-O1", "2026-10-08")
    paquete = database.obtener_paquete_offline_patio("FLOTA OFF")
    assert "OFF001" in json.dumps(paquete, default=str)


def test_ultimo_corte_por_vehiculo_igual_al_calculo_por_vehiculo():
    """El cálculo en bloque da lo mismo que el ciclo por vehículo que reemplazó (última fecha y último dato por posición)."""
    df = pd.DataFrame([
        {"id": 1, "placa": "A", "posicion": 1, "fecha_str": "2026-09-01", "prof": 10.0},
        {"id": 2, "placa": "A", "posicion": 1, "fecha_str": "2026-10-01", "prof": 9.0},
        {"id": 3, "placa": "A", "posicion": 1, "fecha_str": "2026-10-01", "prof": None},
        {"id": 4, "placa": "A", "posicion": 2, "fecha_str": "2026-10-01", "prof": 8.0},
        {"id": 5, "placa": "B", "posicion": 1, "fecha_str": "2026-08-01", "prof": 7.0},
        {"id": 6, "placa": None, "posicion": 1, "fecha_str": "2026-10-01", "prof": 6.0},
    ])
    viejo = []
    for _, grp in df.groupby('placa'):
        g = grp[grp['fecha_str'] == grp['fecha_str'].max()]
        viejo.append(g.sort_values('id').groupby('posicion', as_index=False).last())
    viejo = pd.concat(viejo, ignore_index=True)
    nuevo = database._ultimo_corte_por_vehiculo(df)
    pd.testing.assert_frame_equal(nuevo[sorted(nuevo.columns)].reset_index(drop=True),
                                  viejo[sorted(viejo.columns)].reset_index(drop=True), check_dtype=False)
    assert database._ultimo_corte_por_vehiculo(pd.DataFrame()).empty
