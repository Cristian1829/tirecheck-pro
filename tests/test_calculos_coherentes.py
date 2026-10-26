"""Pruebas de los cálculos corregidos tras la auditoría de coherencia de cifras."""
import pandas as pd
import pytest

import database


def _insp(**kw):
    base = {
        "fecha": "2026-10-10", "cliente": "FLOTA EJE", "subcliente": "TODOS", "tipo_operacion": "CARGA",
        "placa": "EJE001", "posicion": 1, "kilometraje": 100000, "tipologia": "Cabezote (6x4)",
        "marca": "MICHELIN", "diseno": "X MULTI", "dimension": "295/80R22.5", "vida": "Original",
        "banda_reen": "", "prof_ext": 10.0, "prof_cent": 10.0, "prof_int": 10.0, "psi": 100,
        "novedades": "", "precio": 1500000, "prof_inicial": 18.0, "km_montaje": 50000,
        "numero_interno": "EJE-1", "usuario_registro": "admin",
    }
    base.update(kw)
    return base


def test_candado_rechaza_fecha_futura_y_anio_imposible(monkeypatch):
    from datetime import date
    monkeypatch.setattr(database, "_hoy_bogota", lambda: date(2026, 10, 25))
    assert database.es_fecha_inspeccion_valida("2026-10-25")
    assert not database.es_fecha_inspeccion_valida("2026-11-01")
    assert not database.es_fecha_inspeccion_valida("0012-02-12")
    assert not database.es_fecha_inspeccion_valida("no es fecha")
    res = database.validar_inspeccion_candados(_insp(fecha="2026-11-15"))
    assert not res["valido"] and "fecha de inspección" in res["mensaje"].lower()


def test_filtrar_fechas_validas_quita_futuras_e_imposibles(monkeypatch):
    from datetime import date
    monkeypatch.setattr(database, "_hoy_bogota", lambda: date(2026, 10, 25))
    df = pd.DataFrame({"fecha": ["2026-10-01", "2026-11-13", "0012-02-12"]})
    assert database.filtrar_fechas_validas(df)["fecha"].tolist() == ["2026-10-01"]


def test_limite_de_retiro_por_eje_se_aplica_en_diagnostico(test_db):
    with database.get_connection() as conn:
        conn.execute("INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm) VALUES ('FLOTA EJE', 'TODOS', 'TODOS', 3.0)")
        conn.execute("INSERT INTO configuracion_limites_retiro (cliente, subcliente, eje, limite_retiro_mm) VALUES ('FLOTA EJE', 'TODOS', 'DIRECCIONAL', 5.0)")
        conn.commit()
    # 4,5 mm: retiro en direccional (límite 5,0) pero no en tracción (límite 3,0)
    df = pd.DataFrame([
        _insp(posicion=1, prof_ext=4.5, prof_cent=4.5, prof_int=4.5, numero_interno="E1"),
        _insp(posicion=2, prof_ext=12.0, prof_cent=12.0, prof_int=12.0, numero_interno="E2"),
        _insp(posicion=3, prof_ext=4.5, prof_cent=4.5, prof_int=4.5, numero_interno="E3"),
        _insp(posicion=4, prof_ext=4.5, prof_cent=4.5, prof_int=4.5, numero_interno="E4"),
    ])
    df["id"] = range(1, len(df) + 1)
    r = database.analizar_inspecciones_df(df).iloc[0]
    assert r["Cant_Cambios"] == 1
    assert "Pos 1 (4.5mm <= 5.0mm)" in r["Detalle_Cambio"]


def test_psi_vacio_no_cuenta_como_baja_presion(test_db):
    # Pos 1-2 direccionales (objetivo 110 PSI), 3-4 tracción (objetivo 100 PSI); Pos 1 sin lectura
    for i, psi in enumerate([0, 110, 100, 100], start=1):
        database.insertar_inspeccion(_insp(posicion=i, psi=psi, numero_interno=f"P{i}"))
    k09 = database.obtener_suite_completa_20_kpis({"cliente": "FLOTA EJE", "licencia": "FULL"})["kpi_09"]
    assert k09["distribucion"]["baja_severa"] == 0
    assert k09["llantas_sin_lectura_psi"] == 1
    assert k09["galones_combustible_desperdiciados_mes"] == 0.0


def test_kpi11_total_cuadra_con_una_medicion_por_llanta(test_db):
    # Misma llanta desalineada inspeccionada dos veces en el mes: debe contarse una sola vez
    for fecha in ("2026-10-05", "2026-10-20"):
        database.insertar_inspeccion(_insp(fecha=fecha, posicion=1, prof_ext=8.0, prof_cent=9.0, prof_int=11.0, numero_interno="AL1"))
    k11 = database.obtener_suite_completa_20_kpis({"cliente": "FLOTA EJE", "licencia": "FULL"})["kpi_11"]
    assert k11["total_dinero_perdido_cop"] == sum(k11["dinero_perdido"])


def test_mrp_solo_repone_bajas_recientes(monkeypatch):
    from datetime import date
    monkeypatch.setattr(database, "_hoy_bogota", lambda: date(2026, 10, 25))
    llantas = [
        {"dimension": "295/80R22.5", "ubicacion_bodega": "BODEGA_6_FVU", "fecha_baja": "2026-10-20", "numero_interno": "A", "cliente": "X"},
        {"dimension": "295/80R22.5", "ubicacion_bodega": "BODEGA_7_CHATARRIZADA", "fecha_baja": "2025-01-10", "numero_interno": "B", "cliente": "X"},
        {"dimension": "11R22.5", "ubicacion_bodega": "BODEGA_6_FVU", "fecha_baja": "2026-10-21", "numero_interno": "C", "cliente": "X"},
    ]
    monkeypatch.setattr(database, "resolver_fecha_baja_fvu", lambda: (lambda ll: ll.get("fecha_baja")))
    assert database.contar_bajas_fvu_para_reponer(llantas, "295/80R22.5", dias=30) == 1


def test_ahorro_es_el_mismo_en_diagnostico_y_kpis(test_db):
    for i in range(1, 5):
        database.insertar_inspeccion(_insp(posicion=i, prof_ext=3.5, prof_cent=5.0, prof_int=6.0, psi=80, numero_interno=f"A{i}"))
    suite = database.obtener_suite_completa_20_kpis({"cliente": "FLOTA EJE", "licencia": "FULL"})["ahorro_roi"]
    graf = database.obtener_datos_graficos_diagnostico({"cliente": "FLOTA EJE"})["ahorro_roi"]
    for clave in ("cascos_en_ventana_salvamento", "ahorro_alineacion_oportuna_cop", "ahorro_combustible_anual_psi_cop"):
        assert suite[clave] == graf[clave], clave
