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
