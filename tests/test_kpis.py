import pytest
import database

def test_calculo_trazabilidad_kpis(test_db):
    # Insertar una llanta con datos conocidos para validar fórmulas
    datos = {
        'fecha': '2026-10-01',
        'cliente': 'Flota KPI',
        'subcliente': 'Principal',
        'tipo_operacion': 'Carga Seca',
        'placa': 'KPI-101',
        'posicion': 1,
        'kilometraje': 100000.0,
        'km_montaje': 60000.0,     # km_rodados = 100000 - 60000 = 40000
        'numero_interno': 'LL-KPI-1',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 2000000.0,
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,          # prof_actual_min = 12.0. Desgaste = 16 - 12 = 4.0 mm
        'psi': 110.0
    }
    database.insertar_inspeccion(datos)

    kpis = database.obtener_trazabilidad_kpis_llanta('LL-KPI-1')
    assert len(kpis) == 1
    k = kpis[0]

    assert k['km_rodados'] == 40000.0
    assert k['desgaste_mm'] == 4.0
    # km_por_mm = 40000 / 4.0 = 10000.0 km/mm
    assert k['km_por_mm'] == 10000.0
    # CPK = 2000000 / 40000 = 50.0 $/km
    assert k['cpk'] == 50.0

    # Límite por defecto = 3.0 mm
    # Km restantes = 10000 * (12.0 - 3.0) = 90000 km
    assert k['km_restantes'] == 90000.0
    # Proyección total = 10000 * (16.0 - 3.0) = 130000 km
    assert k['proyeccion_total_km'] == 130000.0
