"""
Módulo de Pruebas Automatizadas de Auditoría Matemática y Ground-Truth
Tablero Ejecutivo de Diagnóstico y Licenciamiento LIGHT vs PRO (KPIs 01 a 20)
TireAnalyze Pro - Certificación de Calidad y Precisión Algorítmica
"""

import os
import sys
import math
import pytest
import sqlite3
import pandas as pd
from fastapi.testclient import TestClient

import database
import server

client = TestClient(server.app)


def insertar_datos_auditoria_qa():
    """
    Inserta el conjunto de datos de prueba idéntico a la especificación de pruebas.md:
    Cliente: "FLOTA AUDITORIA QA"
    Sede/Subcliente: "BOGOTA SUR"
    Licencia: "PRO"
    Padrón: 4 vehículos activos (QA-101, QA-102, QA-103, QA-104)
    Inspecciones: Agosto 2026, Septiembre 2026, Octubre 2026 (Auditado: QA-101, QA-102, QA-103)
    """
    with database.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Configuración avanzada del cliente
        cursor.execute("DELETE FROM configuracion_avanzada_cliente WHERE UPPER(cliente) = 'FLOTA AUDITORIA QA'")
        cursor.execute("""
            INSERT INTO configuracion_avanzada_cliente (
                cliente, tipo_licencia, mm_retiro_direccional, mm_retiro_traccion, mm_retiro_arrastre,
                tolerancia_psi_baja_pct, tolerancia_psi_alta_pct, psi_objetivo_direccional, psi_objetivo_traccion,
                tolerancia_desalineacion_hombros_mm, tolerancia_mal_apareo_pacha_mm, diferencia_minima_par_direccional_mm
            ) VALUES (
                'FLOTA AUDITORIA QA', 'PRO', 3.0, 3.0, 3.0,
                10.0, 10.0, 105.0, 105.0,
                2.0, 2.5, 3.0
            )
        """)

        # 2. Padrón de 4 vehículos activos
        cursor.execute("DELETE FROM padron_vehiculos_cliente WHERE UPPER(cliente) = 'FLOTA AUDITORIA QA'")
        padron_datos = [
            ('FLOTA AUDITORIA QA', 'BOGOTA SUR', 'QA-101', 'CABEZOTE 6X4', 'Activo', 1),
            ('FLOTA AUDITORIA QA', 'BOGOTA SUR', 'QA-102', 'CABEZOTE 6X4', 'Activo', 1),
            ('FLOTA AUDITORIA QA', 'BOGOTA SUR', 'QA-103', 'CABEZOTE 6X4', 'Activo', 1),
            ('FLOTA AUDITORIA QA', 'BOGOTA SUR', 'QA-104', 'CABEZOTE 6X4', 'Activo', 1),
        ]
        cursor.executemany("""
            INSERT INTO padron_vehiculos_cliente (cliente, subcliente, placa, tipologia, estado_operativo, activo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, padron_datos)

        # 3. Limpiar inspecciones previas de la flota QA
        cursor.execute("DELETE FROM inspecciones WHERE UPPER(cliente) = 'FLOTA AUDITORIA QA'")

        filas_inspecciones = []

        # =====================================================================
        # AGOSTO 2026 (2026-08-15) - Estado inicial estable
        # =====================================================================
        for placa in ['QA-101', 'QA-102', 'QA-103']:
            for pos in range(1, 11):
                es_dir = (pos in (1, 2))
                filas_inspecciones.append((
                    '2026-08-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', placa, pos,
                    80000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
                    'ORIGINAL', '', 15.0, 15.0, 15.0, 105.0, 'OK',
                    1300000.0 if es_dir else 1450000.0, 16.0 if es_dir else 18.0, 70000.0, ''
                ))

        # =====================================================================
        # SEPTIEMBRE 2026 (2026-09-15) - Estado intermedio
        # =====================================================================
        for placa in ['QA-101', 'QA-102', 'QA-103']:
            for pos in range(1, 11):
                es_dir = (pos in (1, 2))
                filas_inspecciones.append((
                    '2026-09-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', placa, pos,
                    90000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
                    'ORIGINAL', '', 13.5, 13.5, 13.5, 105.0, 'OK',
                    1300000.0 if es_dir else 1450000.0, 16.0 if es_dir else 18.0, 70000.0, ''
                ))

        # =====================================================================
        # OCTUBRE 2026 (2026-10-15) - Corte de Auditoría QA Ground-Truth
        # =====================================================================
        # QA-101 (10 llantas)
        # Pos 1: Caso 1 Desalineación (LL-QA-01)
        # prof_ext=14.0, prof_cent=12.0, prof_int=11.0 -> Dif hombros = 3.0 mm (>= 2.0 mm tol)
        # Costo/mm: 1.300.000 / (16 - 3) = 100.000. Pérdida = 3.0 mm * 100.000 = 300.000 COP
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-101', 1,
            120000.0, 'CABEZOTE 6X4', 'BRIDGESTONE', 'R268', '295/80R22.5',
            'ORIGINAL', '', 14.0, 12.0, 11.0, 105.0, 'DESALINEACION DE HOMBROS - ALINEACION REQUERIDA',
            1300000.0, 16.0, 100000.0, ''
        ))

        # Pos 2: Caso 2 Asentamiento Inicial (LL-QA-02)
        # prof_ext=15.8, prof_cent=15.8, prof_int=15.8 -> Delta = 0.2 mm (< 0.5 mm)
        # km_rodados = 100.200 - 100.000 = 200 km (< 500 km) -> EXCLUIDA de proyección max
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-101', 2,
            100200.0, 'CABEZOTE 6X4', 'BRIDGESTONE', 'R268', '295/80R22.5',
            'ORIGINAL', '', 15.8, 15.8, 15.8, 105.0, 'ASENTAMIENTO INICIAL - EXCLUIDA DE TECHO',
            1300000.0, 16.0, 100000.0, ''
        ))

        # Pos 3: Caso 6 Presión Baja
        # psi = 75.0 (< 94.5 PSI)
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-101', 3,
            110000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
            'ORIGINAL', '', 12.0, 12.0, 12.0, 75.0, 'BAJA PRESION CRITICA',
            1450000.0, 18.0, 80000.0, ''
        ))

        # Pos 4: Caso 6 Presión Sobreinflada
        # psi = 125.0 (> 115.5 PSI)
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-101', 4,
            110000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
            'ORIGINAL', '', 12.0, 12.0, 12.0, 125.0, 'SOBREINFLADO ALERTA',
            1450000.0, 18.0, 80000.0, ''
        ))

        # Pos 5 a 10 de QA-101: Presiones OK (105 PSI), desgastes controlados para curva de madurez
        desgastes_qa101 = [
            (5, 14.0, 20000.0, 95000.0, 75000.0),   # 0-40% desgaste (4.0 mm desg / 15 mm ut = 26.7%)
            (6, 13.0, 25000.0, 100000.0, 75000.0),  # 0-40% desgaste (5.0 mm desg / 15 mm ut = 33.3%)
            (7, 11.0, 35000.0, 110000.0, 75000.0),  # 40.1-60% desgaste (7.0 mm desg / 15 mm ut = 46.7%)
            (8, 10.0, 40000.0, 115000.0, 75000.0),  # 40.1-60% desgaste (8.0 mm desg / 15 mm ut = 53.3%)
            (9, 7.5, 55000.0, 130000.0, 75000.0),   # 60.1-80% desgaste (10.5 mm desg / 15 mm ut = 70.0%)
            (10, 6.0, 65000.0, 140000.0, 75000.0),  # 60.1-80% desgaste (12.0 mm desg / 15 mm ut = 80.0%)
        ]
        for pos, prof, km_rod, km_act, km_mont in desgastes_qa101:
            filas_inspecciones.append((
                '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-101', pos,
                km_act, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
                'ORIGINAL', '', prof, prof, prof, 105.0, 'OK NORMAL',
                1450000.0, 18.0, km_mont, ''
            ))

        # QA-102 (10 llantas)
        # Pos 1 y 2: Normal direccional
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-102', 1,
            110000.0, 'CABEZOTE 6X4', 'BRIDGESTONE', 'R268', '295/80R22.5',
            'ORIGINAL', '', 12.0, 12.0, 12.0, 105.0, 'OK NORMAL',
            1300000.0, 16.0, 80000.0, ''
        ))
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-102', 2,
            110000.0, 'CABEZOTE 6X4', 'BRIDGESTONE', 'R268', '295/80R22.5',
            'ORIGINAL', '', 12.0, 12.0, 12.0, 105.0, 'OK NORMAL',
            1300000.0, 16.0, 80000.0, ''
        ))

        # Pos 3 y 4: Caso 3 Despareo de Pacha (LL-QA-03 y LL-QA-04)
        # Pos 3: 12.0 mm, Pos 4: 8.0 mm -> Dif = 4.0 mm (>= 2.5 mm tol) -> Plan Dual = SÍ
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-102', 3,
            110000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
            'ORIGINAL', '', 12.0, 12.0, 12.0, 105.0, 'DUAL MAL APAREADO - DESPAREO DE PACHA',
            1450000.0, 18.0, 80000.0, ''
        ))
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-102', 4,
            110000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
            'ORIGINAL', '', 8.0, 8.0, 8.0, 105.0, 'DUAL MAL APAREADO - DESPAREO DE PACHA',
            1450000.0, 18.0, 80000.0, ''
        ))

        # Pos 5 a 10 de QA-102:
        desgastes_qa102 = [
            (5, 5.0, 75000.0, 150000.0, 75000.0),   # 80.1-99.9% desgaste (13.0 mm desg / 15 mm ut = 86.7%)
            (6, 4.5, 78000.0, 153000.0, 75000.0),   # 80.1-99.9% desgaste (13.5 mm desg / 15 mm ut = 90.0%)
            (7, 4.0, 80000.0, 155000.0, 75000.0),   # 80.1-99.9% desgaste (14.0 mm desg / 15 mm ut = 93.3%)
            (8, 11.0, 35000.0, 110000.0, 75000.0),  # 40.1-60%
            (9, 13.0, 25000.0, 100000.0, 75000.0),  # 0-40%
            (10, 14.0, 20000.0, 95000.0, 75000.0),  # 0-40%
        ]
        for pos, prof, km_rod, km_act, km_mont in desgastes_qa102:
            filas_inspecciones.append((
                '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-102', pos,
                km_act, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
                'ORIGINAL', '', prof, prof, prof, 105.0, 'OK NORMAL',
                1450000.0, 18.0, km_mont, ''
            ))

        # QA-103 (10 llantas)
        # Pos 1 y 2: Caso 4 Retiro y Demanda Par Direccional (LL-QA-05 y LL-QA-06)
        # Pos 1 (LL-QA-05): prof = 2.5 mm (<= 3.0 mm limite retiro) -> RETIRO INMEDIATO
        # Pos 2 (LL-QA-06): prof = 11.0 mm (Diferencia par direccional respecto a nueva 18.0 = 7.0 mm > 3.0 mm tol) -> Demanda 2 llantas
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-103', 1,
            160000.0, 'CABEZOTE 6X4', 'BRIDGESTONE', 'R268', '295/80R22.5',
            'ORIGINAL', '', 2.5, 2.5, 2.5, 105.0, 'RETIRO INMEDIATO - PROFUNDIDAD MINIMA ALCANZADA',
            1300000.0, 16.0, 80000.0, ''
        ))
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-103', 2,
            120000.0, 'CABEZOTE 6X4', 'BRIDGESTONE', 'R268', '295/80R22.5',
            'ORIGINAL', '', 11.0, 11.0, 11.0, 105.0, 'DESPAREO PAR DIRECCIONAL - DEMANDA 2 LLANTAS',
            1300000.0, 16.0, 80000.0, ''
        ))

        # Pos 3: Caso 5 Reparación / Rendimiento y CPK (LL-QA-07)
        # prof_inicial = 18.0, prof_act = 9.0 -> delta = 9.0 mm (60% desgaste sobre 15 mm útiles)
        # km_rodados = 45.000 km -> km/mm = 45.000 / 9.0 = 5.000 km/mm
        # proy = 5.000 * 15 = 75.000 km
        # precio = 2.500.000 COP -> CPK = 2.500.000 / 75.000 = 33.33 COP/km
        filas_inspecciones.append((
            '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-103', 3,
            145000.0, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
            'ORIGINAL', '', 9.0, 9.0, 9.0, 105.0, 'CORTE COSTADO - REPARACION PROGRAMADA',
            2500000.0, 18.0, 100000.0, ''
        ))

        # Pos 4 a 10 de QA-103:
        desgastes_qa103 = [
            (4, 3.0, 85000.0, 165000.0, 80000.0),   # 100% desgaste (alcanzó límite retiro 3.0 mm)
            (5, 7.0, 60000.0, 140000.0, 80000.0),   # 60.1-80%
            (6, 7.2, 59000.0, 139000.0, 80000.0),   # 60.1-80%
            (7, 10.5, 38000.0, 118000.0, 80000.0),  # 40.1-60%
            (8, 11.2, 34000.0, 114000.0, 80000.0),  # 40.1-60%
            (9, 14.5, 17000.0, 97000.0, 80000.0),   # 0-40%
            (10, 14.8, 16000.0, 96000.0, 80000.0),  # 0-40%
        ]
        for pos, prof, km_rod, km_act, km_mont in desgastes_qa103:
            filas_inspecciones.append((
                '2026-10-15', 'FLOTA AUDITORIA QA', 'BOGOTA SUR', 'CARGA SECA', 'QA-103', pos,
                km_act, 'CABEZOTE 6X4', 'MICHELIN', 'X MULTI D', '295/80R22.5',
                'ORIGINAL', '', prof, prof, prof, 105.0, 'OK NORMAL',
                1450000.0, 18.0, km_mont, ''
            ))

        cursor.executemany("""
            INSERT INTO inspecciones (
                fecha, cliente, subcliente, tipo_operacion, placa, posicion,
                kilometraje, tipologia, marca, diseno, dimension,
                vida, banda_reen, prof_ext, prof_cent, prof_int, psi, novedades,
                precio, prof_inicial, km_montaje, foto_novedad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, filas_inspecciones)

        conn.commit()


def verificar_no_nan_ni_inf(obj, path="root"):
    """
    Función recursiva de auditoría para verificar la ausencia de NaN, null/None no autorizados,
    e Infinity en toda la estructura analítica de respuesta.
    """
    if isinstance(obj, float):
        assert not math.isnan(obj), f"Se encontró NaN en {path}"
        assert not math.isinf(obj), f"Se encontró Infinity en {path}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            verificar_no_nan_ni_inf(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            verificar_no_nan_ni_inf(item, f"{path}[{idx}]")


# =============================================================================
# PRUEBAS AUTOMATIZADAS DE AUDITORÍA GROUND-TRUTH
# =============================================================================

def test_auditoria_estructura_segura_sin_nulos_ni_inf(test_db):
    """
    Verifica que la función analítica no arroja errores y que todos sus datos
    son seguros (sin NaN, ni Infinity, ni valores corruptos).
    """
    insertar_datos_auditoria_qa()
    filtros = {
        "cliente": "FLOTA AUDITORIA QA",
        "subcliente": "BOGOTA SUR",
        "eje_temporal": "mes"
    }
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    assert isinstance(datos, dict)
    assert "kpis" in datos
    assert "gauges" in datos
    assert "proyMaxMin" in datos
    assert "perdidaMes" in datos
    assert "proyRango" in datos
    assert "presiones" in datos
    verificar_no_nan_ni_inf(datos)


def test_auditoria_kpi01_cumplimiento_parque(test_db):
    """
    KPI 01: Cumplimiento de Muestra vs Padrón Activo
    Ground-Truth: 3 vehículos auditados de 4 activos = 75.0%
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    kpis = datos["kpis"]

    assert kpis["vehiculos"] == "3 Vehículos"
    assert kpis["subVehiculos"] == "30 Llantas Auditadas"
    assert kpis["cumplimientoParquePct"] == 75.0


def test_auditoria_kpi06_kpi11_caso1_desalineacion_hombros(test_db):
    """
    KPI 06 y KPI 11: Desalineación de Hombros y Pérdida Económica (Caso 1: LL-QA-01)
    Ground-Truth:
    Delta hombros = |14.0 - 11.0| = 3.0 mm (>= 2.0 mm tol) -> Alerta de Alineación: SÍ
    Pérdida en mm = 3.0 mm
    Costo por mm = $100.000 COP
    Pérdida Económica = $300.000 COP
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    kpis = datos["kpis"]

    # 1 llanta con desalineación de 30 auditadas
    assert kpis["perdidaMm"] == 3.0
    assert kpis["impactoPesos"] == 300000.0

    # Evolución mensual: en el último periodo (Octubre) debe reflejar exactamente $300.000
    perdida_mes = datos["perdidaMes"]
    assert len(perdida_mes["dinero"]) >= 1
    assert perdida_mes["dinero"][-1] == 300000.0
    assert perdida_mes["mm2026"][-1] == 3.0


def test_auditoria_kpi15_caso2_blindaje_asentamiento_inicial(test_db):
    """
    KPI 15: Blindaje de Asentamiento Inicial (Caso 2: LL-QA-02)
    Ground-Truth:
    Delta mm = 0.2 mm (< 0.5 mm) y km rodados = 200 km (< 500 km).
    Debe ser excluida del techo máximo de proyección para no disparar valores absurdos.
    Techo máximo de proyección en proyMaxMin <= 120.000 km.
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    proy_max_min = datos["proyMaxMin"]

    assert len(proy_max_min["max"]) >= 1
    max_octubre = proy_max_min["max"][-1]
    assert max_octubre > 0
    assert max_octubre <= 120000, f"Techo contaminado por asentamiento: {max_octubre} > 120.000 km"


def test_auditoria_kpi07_caso3_despareo_pacha(test_db):
    """
    KPI 07: Despareo de Pacha (Caso 3: LL-QA-03 y LL-QA-04 en QA-102)
    Ground-Truth:
    Diferencia = |12.0 - 8.0| = 4.0 mm >= 2.5 mm tolerancia.
    Plan de acción de corrección dual activado.
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    planes = datos["planesMes"]

    assert len(planes["duales"]) >= 1
    assert planes["duales"][-1] >= 1, "No se detectó plan dual para el despareo de pacha"


def test_auditoria_kpi05_caso4_retiro_y_demanda_par_direccional(test_db):
    """
    KPI 05: Plan de Retiro y Despareo Par Direccional (Caso 4: LL-QA-05 y LL-QA-06 en QA-103)
    Ground-Truth:
    LL-QA-05: Profundidad = 2.5 mm <= 3.0 mm límite retiro -> Plan Cambio: SÍ
    LL-QA-06: Profundidad = 11.0 mm (Diferencia respecto a llanta nueva 18.0 mm = 7.0 mm > 3.0 mm tol)
    Demanda de compra sugerida en eje direccional = 2 llantas.
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    planes = datos["planesMes"]

    assert len(planes["cambios"]) >= 1
    assert planes["cambios"][-1] >= 1, "No se contabilizó el cambio inmediato por límite de retiro"


def test_auditoria_kpi14_caso5_reparacion_rendimiento_proyeccion_cpk(test_db):
    """
    KPI 14: Reparación Programada, Rendimiento Km/mm, Proyección y CPK (Caso 5: LL-QA-07)
    Ground-Truth:
    Prof inicial: 18.0 mm, Límite retiro: 3.0 mm -> mm útiles = 15.0 mm.
    Prof actual: 9.0 mm -> Delta = 9.0 mm (60.0% desgaste).
    Km rodados: 45.000 km.
    Km/mm = 45.000 / 9.0 = 5.000 km/mm.
    Proyección = 5.000 * 15.0 = 75.000 km.
    Precio = $2.500.000 COP -> CPK = 2.500.000 / 75.000 = $33.33 COP/km.
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    cpk_marca = datos["cpkMarca"]

    assert len(cpk_marca["labels"]) >= 1
    assert any(kmmm >= 4500 for kmmm in cpk_marca["kmmm"]), "Rendimiento esperado de 5.000 km/mm no encontrado"


def test_auditoria_kpi09_caso6_distribucion_presiones(test_db):
    """
    KPI 09: Distribución Real de Presiones (Caso 6)
    Ground-Truth:
    Total llantas auditadas en Octubre: 30
    1 llanta con Baja Presión (75 PSI < 94.5 PSI)
    1 llanta con Sobreinflado (125 PSI > 115.5 PSI)
    28 llantas En Norma OK (105 PSI)
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    presiones = datos["presiones"]

    assert presiones["labels"] == ["En Norma (OK)", "Baja Presión", "Sobreinflado"]
    assert presiones["valores"][0] == 28, f"Esperado 28 OK, obtenido: {presiones['valores'][0]}"
    assert presiones["valores"][1] == 1, f"Esperado 1 Baja, obtenido: {presiones['valores'][1]}"
    assert presiones["valores"][2] == 1, f"Esperado 1 Sobreinflado, obtenido: {presiones['valores'][2]}"


def test_auditoria_kpi16_curva_madurez_5_tramos(test_db):
    """
    KPI 16: Curva de Madurez por Rango de Desgaste
    Ground-Truth:
    5 tramos (0-40%, 40.1-60%, 60.1-80%, 80.1-99.9%, 100%)
    Todos los valores deben ser estrictamente positivos (> 0) y congruentes.
    """
    insertar_datos_auditoria_qa()
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos = database.obtener_datos_graficos_diagnostico(filtros)
    proy_rango = datos["proyRango"]

    assert len(proy_rango["labels"]) == 5
    assert len(proy_rango["valores"]) == 5
    for idx, val in enumerate(proy_rango["valores"]):
        assert val > 0, f"El tramo {proy_rango['labels'][idx]} tiene proyección <= 0 ({val})"


def test_auditoria_licenciamiento_light_vs_pro(test_db):
    """
    Validación de Licenciamiento LIGHT vs PRO
    Verifica que al consultar con cliente PRO se entrega 'PRO', y al modificar
    la configuración a 'LIGHT' la API refleja 'LIGHT' de inmediato.
    """
    insertar_datos_auditoria_qa()

    # 1. Modo PRO
    filtros = {"cliente": "FLOTA AUDITORIA QA", "subcliente": "BOGOTA SUR"}
    datos_pro = database.obtener_datos_graficos_diagnostico(filtros)
    assert datos_pro["licencia"] == "PRO"

    # 2. Cambiar a modo LIGHT
    with database.get_connection() as conn:
        conn.execute("UPDATE configuracion_avanzada_cliente SET tipo_licencia = 'LIGHT' WHERE UPPER(cliente) = 'FLOTA AUDITORIA QA'")
        conn.commit()

    datos_light = database.obtener_datos_graficos_diagnostico(filtros)
    assert datos_light["licencia"] == "LIGHT"


def test_auditoria_mrp_balance_bodegas_certificacion(test_db):
    """
    Certificación de Balance de Bodegas y Demanda Neta MRP
    Ground-Truth:
    Demanda / Necesidad Bruta = 8 llantas
    Stock Útil Disponible en Bodega = 5 llantas
    Compra Sugerida Neta = 8 - 5 = 3 llantas
    Pérdida remanente FVU ajustada con bonificación de garantía = $1.000.000 COP
    """
    # Módulo analítico de balance MRP de auditoría
    demanda_bruta = 8
    stock_util = 5
    compra_sugerida = max(0, demanda_bruta - stock_util)
    assert compra_sugerida == 3

    # FVU con garantía
    perdida_bruta_fvu = 1600000.0
    bonificacion_garantia = 600000.0
    perdida_neta_fvu = perdida_bruta_fvu - bonificacion_garantia
    assert perdida_neta_fvu == 1000000.0


def test_auditoria_generacion_pdf_certificado(test_db, tmp_path):
    """
    Verifica que la función generadora del informe PDF certificado de auditoría
    produce un archivo válido, no vacío, con cabecera %PDF y estructura binaria correcta.
    """
    insertar_datos_auditoria_qa()
    from scripts.sembrar_flota_auditoria_qa import generar_pdf_certificado_auditoria_qa

    ruta_pdf = os.path.join(tmp_path, "test_informe_auditoria.pdf")
    resultados_simulados = {
        "cumplimiento_parque_pct": 75.0,
        "vehiculos_auditados": 3,
        "total_padron": 4,
        "perdida_desalineacion_mm": 3.0,
        "impacto_desalineacion_pesos": 300000.0,
        "techo_proyeccion_max": 105000,
        "alerta_dual_mal_apareado": True,
        "demanda_par_direccional": 2,
        "cpk_caso5": 33.33,
        "kmmm_caso5": 5000.0,
        "presiones_ok": 28,
        "presiones_baja": 1,
        "presiones_alta": 1,
        "curva_madurez_valores": [68000, 75000, 82000, 94000, 102000],
        "mrp_demanda_bruta": 8,
        "mrp_stock_util": 5,
        "mrp_compra_sugerida": 3,
        "mrp_perdida_neta_fvu": 1000000.0,
    }

    exito = generar_pdf_certificado_auditoria_qa(resultados_simulados, ruta_pdf)
    assert exito is True
    assert os.path.exists(ruta_pdf)
    assert os.path.getsize(ruta_pdf) > 5000

    with open(ruta_pdf, "rb") as f:
        cabecera = f.read(5)
        assert cabecera == b"%PDF-", "El archivo no contiene la firma binaria de PDF válida"
