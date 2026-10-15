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

def test_resolucion_limites_retiro_en_memoria(test_db):
    # Guardar límite configurado para CLIENTE_TEST
    database.guardar_limite_retiro_cliente("CLIENTE_TEST", 4.5, "Límite especial")
    
    # Probar que la función pública obtener_limite_retiro_cliente devuelva 4.5
    assert database.obtener_limite_retiro_cliente("CLIENTE_TEST") == 4.5
    
    # Probar que el constructor de caché en memoria _construir_cache_limites_retiro devuelva 4.5
    resolver = database._construir_cache_limites_retiro()
    assert resolver("CLIENTE_TEST") == 4.5
    assert resolver("CLIENTE_TEST", "SEDE_INEXISTENTE") == 4.5
    assert resolver("CLIENTE_INEXISTENTE") == 3.0  # Fallback estándar


def test_kpis_permisos_inspector_flotas(test_db):
    # Insertar llantas de dos flotas distintas
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'FLOTA ALFA',
        'subcliente': 'Sede 1',
        'tipo_operacion': 'Carga',
        'placa': 'ALF-001',
        'posicion': 1,
        'kilometraje': 50000.0,
        'km_montaje': 40000.0,
        'numero_interno': 'LL-ALFA-1',
        'marca': 'Michelin',
        'diseno': 'X Multi',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1500000.0,
        'prof_inicial': 15.0,
        'prof_ext': 10.0,
        'prof_cent': 10.0,
        'prof_int': 10.0,
        'psi': 110.0
    })
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'FLOTA BETA',
        'subcliente': 'Sede 2',
        'tipo_operacion': 'Carga',
        'placa': 'BET-001',
        'posicion': 1,
        'kilometraje': 30000.0,
        'km_montaje': 20000.0,
        'numero_interno': 'LL-BETA-1',
        'marca': 'Bridgestone',
        'diseno': 'R268',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'precio': 1600000.0,
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 110.0
    })

    # Crear inspector asignado a FLOTA ALFA
    database.crear_usuario('insp_alfa', 'Inspector Alfa', 'pass123', 'inspector', cliente_asignado='FLOTA ALFA')
    # Crear inspector sin restricción de flotas (acceso a todas las flotas)
    database.crear_usuario('insp_global', 'Inspector Global', 'pass123', 'inspector', cliente_asignado='')

    # 1. Inspector Alfa consulta KPIs sin especificar cliente -> solo ve FLOTA ALFA
    kpis_alfa = database.obtener_trazabilidad_kpis_llanta('', {'usuario': 'insp_alfa'})
    assert len(kpis_alfa) == 1
    assert kpis_alfa[0]['numero_interno'] == 'LL-ALFA-1'
    assert kpis_alfa[0]['cliente'] == 'FLOTA ALFA'

    # 2. Inspector Alfa intenta consultar FLOTA BETA -> debe recibir lista vacía
    kpis_beta_intento = database.obtener_trazabilidad_kpis_llanta('', {'usuario': 'insp_alfa', 'cliente': 'FLOTA BETA'})
    assert len(kpis_beta_intento) == 0

    # 3. Inspector Global consulta sin cliente -> ve ambas flotas
    kpis_global = database.obtener_trazabilidad_kpis_llanta('', {'usuario': 'insp_global'})
    assert len(kpis_global) == 2

    # 4. Inspector Global filtra por FLOTA BETA -> ve FLOTA BETA
    kpis_global_beta = database.obtener_trazabilidad_kpis_llanta('', {'usuario': 'insp_global', 'cliente': 'FLOTA BETA'})
    assert len(kpis_global_beta) == 1
    assert kpis_global_beta[0]['numero_interno'] == 'LL-BETA-1'


