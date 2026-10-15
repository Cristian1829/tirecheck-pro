from datetime import datetime
import pytest
import database

def test_candado_placa_requerida(test_db):
    res = database.validar_inspeccion_candados({'placa': ''})
    assert not res['valido']
    assert 'Placa' in res['mensaje']

def test_candado_limite_profundidad_r225(test_db):
    # Dimensión R22.5 con profundidad > 27.0 mm debe fallar
    datos = {
        'placa': 'TEST01',
        'dimension': '295/80R22.5',
        'prof_ext': 28.5,
        'prof_cent': 15.0,
        'prof_int': 15.0,
        'prof_inicial': 30.0
    }
    res = database.validar_inspeccion_candados(datos)
    assert not res['valido']
    assert '27.0 mm' in res['mensaje']

def test_candado_limite_prof_inicial(test_db):
    # Profundidad medida mayor a profundidad inicial debe fallar
    datos = {
        'placa': 'TEST01',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 17.5,
        'prof_cent': 15.0,
        'prof_int': 15.0
    }
    res = database.validar_inspeccion_candados(datos)
    assert not res['valido']
    assert 'Profundidad Inicial' in res['mensaje']

def test_candado_duplicidad_numero_interno(test_db):
    # Insertar primera llanta en vehículo TEST01
    datos1 = {
        'fecha': '2026-10-01',
        'cliente': 'Cliente Prueba',
        'subcliente': 'Sede A',
        'placa': 'TEST01',
        'posicion': 1,
        'kilometraje': 100000,
        'numero_interno': 'LL-100',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    database.insertar_inspeccion(datos1)

    # Intentar asignar la misma LL-100 a otro vehículo TEST02 del mismo cliente debe fallar
    datos2 = {
        'fecha': '2026-10-02',
        'cliente': 'Cliente Prueba',
        'subcliente': 'Sede A',
        'placa': 'TEST02',
        'posicion': 2,
        'kilometraje': 80000,
        'numero_interno': 'LL-100',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    res = database.validar_inspeccion_candados(datos2)
    assert not res['valido']
    assert 'CANDADO DE NÚMERO INTERNO' in res['mensaje']

def test_candado_frecuencia_mensual_misma_posicion(test_db):
    # Insertar inspección en 2026-10-01
    datos1 = {
        'fecha': '2026-10-01',
        'placa': 'TEST03',
        'posicion': 1,
        'kilometraje': 50000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 10.0,
        'prof_cent': 10.0,
        'prof_int': 10.0
    }
    id1 = database.insertar_inspeccion(datos1)

    # Intentar segunda inspección en el mismo mes 2026-10-15 en la misma posición debe fallar
    datos2 = {
        'fecha': '2026-10-15',
        'placa': 'TEST03',
        'posicion': 1,
        'kilometraje': 52000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 9.0,
        'prof_cent': 9.0,
        'prof_int': 9.0
    }
    res = database.validar_inspeccion_candados(datos2)
    assert not res['valido']
    assert 'ya fue inspeccionado en la Posición 1' in res['mensaje']

    # Sin embargo, si excluimos id1 (por ejemplo, al editar esa misma fila), debe ser válido
    res_edit = database.validar_inspeccion_candados(datos2, excluir_id=id1)
    assert res_edit.get('valido', True)

def test_candado_kilometraje_no_regresivo(test_db):
    # Insertar con km 120,000 en 2026-09-01
    datos1 = {
        'fecha': '2026-09-01',
        'placa': 'TEST04',
        'posicion': 1,
        'kilometraje': 120000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    database.insertar_inspeccion(datos1)

    # Intentar km 110,000 en 2026-10-25 (pasado el siguiente mes + 20 días) debe fallar por kilometraje
    datos2 = {
        'fecha': '2026-10-25',
        'placa': 'TEST04',
        'posicion': 2,
        'kilometraje': 110000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    res = database.validar_inspeccion_candados(datos2)
    assert not res['valido']
    assert 'CANDADO DE KILOMETRAJE' in res['mensaje']

def test_candado_desgaste_negativo(test_db):
    # Insertar con profundidad 6.0 mm en 2026-09-01
    datos1 = {
        'fecha': '2026-09-01',
        'placa': 'TEST05',
        'posicion': 1,
        'kilometraje': 100000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 6.0,
        'prof_cent': 6.0,
        'prof_int': 6.0
    }
    database.insertar_inspeccion(datos1)

    # Intentar subir profundidad a 9.0 mm en 2026-10-25 (aumento > 1 mm de tolerancia) debe fallar
    datos2 = {
        'fecha': '2026-10-25',
        'placa': 'TEST05',
        'posicion': 1,
        'kilometraje': 105000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 9.0,
        'prof_cent': 9.0,
        'prof_int': 9.0
    }
    res = database.validar_inspeccion_candados(datos2)
    assert not res['valido']
    assert 'candado de desgaste' in res['mensaje'].lower() or 'subió' in res['mensaje'].lower()

def test_generacion_automatica_consecutivo_temporal_tmp(test_db):
    # Cuando no se ingresa número interno, debe generarse TMP-001 consecutivo y no repetible
    datos1 = {
        'fecha': '2026-10-14',
        'placa': 'TMP01',
        'posicion': 1,
        'kilometraje': 10000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'numero_interno': ''
    }
    val1 = database.validar_inspeccion_candados(datos1)
    assert val1['valido'] is True
    assert datos1['numero_interno'] == 'TMP-001'
    id1 = database.insertar_inspeccion(datos1)

    # Segunda llanta sin número interno debe generar TMP-002
    datos2 = {
        'fecha': '2026-10-14',
        'placa': 'TMP01',
        'posicion': 2,
        'kilometraje': 10000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'numero_interno': '   '
    }
    val2 = database.validar_inspeccion_candados(datos2)
    assert val2['valido'] is True
    assert datos2['numero_interno'] == 'TMP-002'
    id2 = database.insertar_inspeccion(datos2)

    assert id1 != id2

def test_candado_eje_direccional_solo_original(test_db):
    # En posiciones de eje direccional (pos 1 y 2 en cabezote/sencillo), no se puede seleccionar Reencauche
    datos_dir_reencauche = {
        'fecha': '2026-10-14',
        'placa': 'DIR01',
        'posicion': 1,
        'tipologia': 'Cabezote (6x4)',
        'kilometraje': 20000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'vida': 'Reencauche'
    }
    val = database.validar_inspeccion_candados(datos_dir_reencauche)
    assert not val['valido']
    assert 'eje direccional' in val['mensaje'].lower()
    assert 'reencauche' in val['mensaje'].lower()

    # En condición Original debe ser aprobado
    datos_dir_original = dict(datos_dir_reencauche)
    datos_dir_original['vida'] = 'Original'
    val_ok = database.validar_inspeccion_candados(datos_dir_original)
    assert val_ok['valido'] is True

def test_candado_frecuencia_siguiente_mes_mas_20_dias(test_db):
    # Vehículo inspeccionado el 2026-08-10
    datos1 = {
        'fecha': '2026-08-10',
        'placa': 'FREQ01',
        'posicion': 1,
        'kilometraje': 50000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    database.insertar_inspeccion(datos1)

    # Intentar nueva inspección el 2026-09-15 (aún en el siguiente mes pero antes de los 20 días calculados) debe fallar
    datos2 = {
        'fecha': '2026-09-15',
        'placa': 'FREQ01',
        'posicion': 1,
        'kilometraje': 51000,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 11.5,
        'prof_cent': 11.5,
        'prof_int': 11.5
    }
    val_bloq = database.validar_inspeccion_candados(datos2)
    assert not val_bloq['valido']
    assert 'frecuencia' in val_bloq['mensaje'].lower()

    # Una vez transcurrido el siguiente mes más 20 días (ej. 2026-10-01), debe ser permitida
    datos3 = dict(datos2)
    datos3['fecha'] = '2026-10-01'
    val_perm = database.validar_inspeccion_candados(datos3)
    assert val_perm['valido'] is True
