"""Auditoría, bloque 2: sin valores inventados ni estimados entre clientes."""
import pandas as pd

import database


def _df_precios():
    return pd.DataFrame([
        {"cliente": "CLI A", "dimension": "295/80R22.5", "numero_interno": "A-1", "precio": 2000000},
        {"cliente": "CLI A", "dimension": "295/80R22.5", "numero_interno": "A-2", "precio": 0},
        {"cliente": "CLI B", "dimension": "295/80R22.5", "numero_interno": "B-1", "precio": 0},
        {"cliente": "CLI B", "dimension": "295/80R22.5", "numero_interno": "B-2", "precio": 1800000},
        {"cliente": "CLI B", "dimension": "295/80R22.5", "numero_interno": "B-2", "precio": 0},
    ])


# --- #15: sin precio de la llanta en el cliente se excluye (no se toma de otros) ------------
def test_15_no_toma_precio_de_otro_cliente_ni_de_otra_llanta():
    ref_precio, _ = database.construir_referencias_llanta(_df_precios())
    assert ref_precio("CLI C", "295/80R22.5", "C-1") is None      # otro cliente: antes tomaba la mediana global
    assert ref_precio("CLI A", "295/80R22.5", "A-2") is None      # otra llanta del mismo cliente: antes mediana
    assert ref_precio("CLI B", "295/80R22.5", "B-2") == 1800000   # la misma llanta con precio en otra inspección


# --- #16: sin precio no se inventan $1.450.000 ni marca/diseño/medida -------------------------
INVENTADO = 1450000.0


def _insp_sin_precio(cliente="CLI SIN PRECIO", sn="SP-1"):
    database.insertar_inspeccion({
        "fecha": "2026-10-10", "cliente": cliente, "subcliente": "SEDE", "tipo_operacion": "CARGA", "placa": "SPR001",
        "posicion": 1, "kilometraje": 1000, "tipologia": "Cabezote (6x4)", "marca": "MICHELIN", "diseno": "X MULTI D",
        "dimension": "295/80R22.5", "vida": "Original", "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "psi": 110,
        "prof_inicial": 18, "numero_interno": sn})


def test_16_sincronizar_maestro_no_inventa_costo(test_db):
    _insp_sin_precio()
    database.sincronizar_maestro_desde_inspecciones(cliente_filtro="CLI SIN PRECIO")
    with database.get_connection() as conn:
        costo = conn.execute("SELECT costo_compra_original FROM llantas_maestro WHERE numero_interno = 'SP-1'").fetchone()[0]
    assert costo != INVENTADO and not costo


def test_16_alta_en_bodega_sin_costo_no_inventa(test_db):
    res = database.crear_llanta_en_bodega({"numero_interno": "ALTA-1", "cliente": "CLI SIN PRECIO", "marca": "HANKOOK",
                                           "diseno": "AH35", "dimension": "295/80R22.5", "prof_inicial": 15.5})
    assert res.get("ok"), res
    with database.get_connection() as conn:
        costo = conn.execute("SELECT costo_compra_original FROM llantas_maestro WHERE numero_interno = 'ALTA-1'").fetchone()[0]
    assert costo != INVENTADO and not costo


def test_16_montar_llanta_inexistente_exige_datos(test_db):
    import modulo_bodegas_taller as mbt
    res = mbt.montar_llanta_taller({"placa": "SPR001", "posicion": 1, "cliente": "CLI SIN PRECIO",
                                    "numero_interno": "NO-EXISTE-1", "kilometraje": 1000})
    assert res.get("ok") is False
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM llantas_maestro WHERE numero_interno = 'NO-EXISTE-1'").fetchone()[0] == 0


# --- #19: el CPK del KPI 14 se identifica como CPK proyectado ----------------------------------
def test_19_kpi14_declara_que_cpk_es_proyectado(test_db):
    d = database.obtener_suite_completa_20_kpis({"cliente": "", "licencia": ""})
    k = d["kpi_14"]
    assert k.get("cpk_tipo") == "proyectado"
    assert "proyect" in k.get("cpk_formula", "").lower()
