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


def test_numero_interno_sn_permitido_multiples_veces_en_version_light(test_db):
    """
    Validar que para la versión LIGHT se permite ingresar las veces que sea necesario
    la palabra 'SN', y que si se ingresa en minúscula ('sn') se convierte directamente a mayúscula ('SN').
    """
    cliente = "Flota Distribucion Light"
    database.guardar_licencia_cliente(cliente, "LIGHT")

    # 1. Registrar primera llanta en vehículo LT01 Pos 1 con 'sn' en minúscula
    datos1 = {
        'fecha': '2026-10-01',
        'cliente': cliente,
        'subcliente': 'Sede Principal',
        'placa': 'LT01',
        'posicion': 1,
        'kilometraje': 40000,
        'numero_interno': 'sn',  # minúscula
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    val1 = database.validar_inspeccion_candados(datos1)
    assert val1['valido'] is True
    assert datos1['numero_interno'] == 'SN'  # convertido directamente a mayúsculas
    database.insertar_inspeccion(datos1)

    # 2. Registrar segunda llanta en el MISMO vehículo LT01 Pos 2 con 'SN' en el mismo mes
    datos2 = {
        'fecha': '2026-10-01',
        'cliente': cliente,
        'subcliente': 'Sede Principal',
        'placa': 'LT01',
        'posicion': 2,
        'kilometraje': 40000,
        'numero_interno': 'SN',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 13.0,
        'prof_cent': 13.0,
        'prof_int': 13.0
    }
    val2 = database.validar_inspeccion_candados(datos2)
    assert val2['valido'] is True, f"Fallo al validar segunda llanta SN en version LIGHT: {val2.get('mensaje')}"
    database.insertar_inspeccion(datos2)

    # 3. Registrar tercera llanta en OTRO vehículo LT02 Pos 1 también con 'sn' en el mismo mes
    datos3 = {
        'fecha': '2026-10-02',
        'cliente': cliente,
        'subcliente': 'Sede Principal',
        'placa': 'LT02',
        'posicion': 1,
        'kilometraje': 30000,
        'numero_interno': 'sn',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0
    }
    val3 = database.validar_inspeccion_candados(datos3)
    assert val3['valido'] is True, f"Fallo al validar tercera llanta sn en version LIGHT: {val3.get('mensaje')}"
    assert datos3['numero_interno'] == 'SN'
    database.insertar_inspeccion(datos3)


def test_numero_interno_sn_bloqueado_duplicado_en_version_pro(test_db):
    """
    Validar que en la versión PRO, 'SN' NO está exonerado del candado de duplicidad
    (solo se permite ingresar múltiples veces 'SN' en la versión LIGHT).
    """
    cliente = "Flota Operativa Pro"
    database.guardar_licencia_cliente(cliente, "PRO")

    datos1 = {
        'fecha': '2026-10-01',
        'cliente': cliente,
        'placa': 'PRO01',
        'posicion': 1,
        'kilometraje': 80000,
        'numero_interno': 'SN',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    val1 = database.validar_inspeccion_candados(datos1)
    assert val1['valido'] is True
    database.insertar_inspeccion(datos1)

    # En versión PRO, intentar ingresar otro 'SN' para el mismo cliente en el mismo mes debe ser bloqueado
    datos2 = {
        'fecha': '2026-10-02',
        'cliente': cliente,
        'placa': 'PRO02',
        'posicion': 1,
        'kilometraje': 75000,
        'numero_interno': 'sn',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0
    }
    val2 = database.validar_inspeccion_candados(datos2)
    assert val2['valido'] is False
    assert 'CANDADO DE NÚMERO INTERNO' in val2['mensaje']


def test_numero_interno_no_sn_sigue_bloqueado_en_version_light(test_db):
    """
    Validar que en la versión LIGHT, si se ingresa un número de llanta real (ej. 'LL-500'),
    la protección de no duplicidad sigue activa; la excepción de duplicidad aplica únicamente para 'SN'.
    """
    cliente = "Flota Mixta Light"
    database.guardar_licencia_cliente(cliente, "LIGHT")

    datos1 = {
        'fecha': '2026-10-01',
        'cliente': cliente,
        'placa': 'MIX01',
        'posicion': 1,
        'kilometraje': 60000,
        'numero_interno': 'LL-500',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    database.insertar_inspeccion(datos1)

    datos2 = {
        'fecha': '2026-10-02',
        'cliente': cliente,
        'placa': 'MIX02',
        'posicion': 2,
        'kilometraje': 55000,
        'numero_interno': 'll-500',  # minúscula
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    }
    val2 = database.validar_inspeccion_candados(datos2)
    assert val2['valido'] is False
    assert 'CANDADO DE NÚMERO INTERNO' in val2['mensaje']


def test_obtener_llanta_por_cliente_ignora_sn(test_db):
    """
    Validar que 'SN' (y 'sn') no se confundan con una llanta única persistida,
    evitando falsos autocompletados.
    """
    cliente = "Flota Pruebas SN"
    database.guardar_licencia_cliente(cliente, "LIGHT")

    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': cliente,
        'placa': 'SN01',
        'posicion': 1,
        'kilometraje': 10000,
        'numero_interno': 'SN',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0
    })

    assert database.obtener_llanta_por_cliente(cliente, 'SN') is None
    assert database.obtener_llanta_por_cliente(cliente, 'sn') is None

