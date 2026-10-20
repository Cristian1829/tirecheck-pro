import pandas as pd
import pytest
import database

def test_diagnostico_alineacion_direccional():
    # Vehículo con diferencia >= 2mm entre prof_int y prof_ext en posición 1
    datos = [
        {
            'placa': 'V-ALIN',
            'posicion': 1,
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 4.0,
            'prof_cent': 6.0,
            'prof_ext': 7.0, # diff = 3.0 mm >= 2.0 mm
            'dimension': '295/80R22.5',
            'cliente': 'Test',
            'kilometraje': 100000
        },
        {
            'placa': 'V-ALIN',
            'posicion': 2,
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 8.0,
            'prof_cent': 8.0,
            'prof_ext': 8.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test',
            'kilometraje': 100000
        }
    ]
    df = pd.DataFrame(datos)
    res = database.analizar_inspecciones_df(df)
    assert not res.empty
    fila = res.iloc[0]
    assert fila['Plan_Alineacion'] == 'SÍ'
    assert 'Pos 1' in fila['Detalle_Alineacion']

def test_diagnostico_dual_mal_apareado():
    # Posiciones duales 3 y 4 con diferencia >= 2mm en prof más baja
    datos = [
        {
            'placa': 'V-DUAL',
            'posicion': 1,
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 10.0,
            'prof_cent': 10.0,
            'prof_ext': 10.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test',
            'kilometraje': 100000
        },
        {
            'placa': 'V-DUAL',
            'posicion': 3,
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 4.0,
            'prof_cent': 4.0,
            'prof_ext': 4.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test',
            'kilometraje': 100000
        },
        {
            'placa': 'V-DUAL',
            'posicion': 4,
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 8.0,
            'prof_cent': 8.0,
            'prof_ext': 8.0, # diff = 4.0 mm >= 2.0 mm
            'dimension': '295/80R22.5',
            'cliente': 'Test',
            'kilometraje': 100000
        }
    ]
    df = pd.DataFrame(datos)
    res = database.analizar_inspecciones_df(df)
    assert not res.empty
    fila = res.iloc[0]
    assert fila['Plan_Dual_Mal_Apareado'] == 'SÍ'
    assert 'Dual 3-4' in fila['Detalle_Dual']

def test_diagnostico_sugerencia_cambio(test_db):
    # Cliente configurado con límite 3.0 mm. Llanta con 2.5 mm debe activar sugerencia cambio
    datos = [
        {
            'placa': 'V-RETIRO',
            'posicion': 1,
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 2.5,
            'prof_cent': 2.5,
            'prof_ext': 2.5,
            'dimension': '295/80R22.5',
            'cliente': 'Test Cliente',
            'kilometraje': 100000
        }
    ]
    df = pd.DataFrame(datos)
    res = database.analizar_inspecciones_df(df)
    assert not res.empty
    fila = res.iloc[0]
    assert fila['Plan_Cambio_Llanta'] == 'SÍ'
    assert 'Pos 1' in fila['Detalle_Cambio']

def test_diagnostico_ignora_inspecciones_meses_anteriores(test_db):
    # Inserta para una misma placa una llanta en 2.0 mm en 2026-06-01 y luego la misma posición renovada en 15.0 mm en 2026-10-01
    datos = [
        {
            'placa': 'V-RENOVAR',
            'posicion': 1,
            'fecha': '2026-06-01',
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 2.0,
            'prof_cent': 2.0,
            'prof_ext': 2.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test Cliente',
            'kilometraje': 80000
        },
        {
            'placa': 'V-RENOVAR',
            'posicion': 1,
            'fecha': '2026-10-01',
            'tipologia': 'Cabezote (6x4)',
            'prof_int': 15.0,
            'prof_cent': 15.0,
            'prof_ext': 15.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test Cliente',
            'kilometraje': 95000
        }
    ]
    df = pd.DataFrame(datos)
    res = database.analizar_inspecciones_df(df)
    assert not res.empty
    fila = res.iloc[0]
    assert fila['Llantas Inspeccionadas'] == 1
    assert fila['Plan_Cambio_Llanta'] == 'NO'
    assert fila['Fecha'] == '2026-10-01'

def test_diagnostico_orden_fecha_mas_reciente_a_mas_antigua():
    # Verifica que analizar_inspecciones_df ordene de la inspección más reciente a la más antigua
    datos = [
        {
            'placa': 'AAA100',
            'posicion': 1,
            'fecha': '2026-01-15',
            'tipologia': 'Camión Sencillo (4x2)',
            'prof_int': 8.0,
            'prof_cent': 8.0,
            'prof_ext': 8.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test Cliente',
            'kilometraje': 10000
        },
        {
            'placa': 'ZZZ999',
            'posicion': 1,
            'fecha': '2026-10-20',
            'tipologia': 'Camión Sencillo (4x2)',
            'prof_int': 9.0,
            'prof_cent': 9.0,
            'prof_ext': 9.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test Cliente',
            'kilometraje': 20000
        },
        {
            'placa': 'MMM500',
            'posicion': 1,
            'fecha': '2026-05-10',
            'tipologia': 'Camión Sencillo (4x2)',
            'prof_int': 7.0,
            'prof_cent': 7.0,
            'prof_ext': 7.0,
            'dimension': '295/80R22.5',
            'cliente': 'Test Cliente',
            'kilometraje': 15000
        }
    ]
    df = pd.DataFrame(datos)
    res = database.analizar_inspecciones_df(df)
    assert len(res) == 3
    # ZZZ999 tiene fecha 2026-10-20 (más reciente)
    assert res.iloc[0]['Vehículo/Placa'] == 'ZZZ999'
    assert res.iloc[0]['Fecha'] == '2026-10-20'
    # MMM500 tiene fecha 2026-05-10
    assert res.iloc[1]['Vehículo/Placa'] == 'MMM500'
    assert res.iloc[1]['Fecha'] == '2026-05-10'
    # AAA100 tiene fecha 2026-01-15 (más antigua)
    assert res.iloc[2]['Vehículo/Placa'] == 'AAA100'
    assert res.iloc[2]['Fecha'] == '2026-01-15'

