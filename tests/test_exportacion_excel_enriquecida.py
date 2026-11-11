"""
Test de Exportación Enriquecida a Excel — TireCheck Pro
Valida que la exportación de la base de inspecciones incluya:
  1. Hoja «Inspecciones» con las 33 columnas analíticas (Eje, Km rodados, Mm gastados, Km/mm, Límite retiro, Proyección y CPKs).
  2. Hoja «Resumen_Rendimiento» con las 3 matrices analíticas jerárquicas (Originales, Reencauches y Comparativo).
  3. Hoja «Filtros_Aplicados».
"""

import io
import openpyxl
import pandas as pd
import pytest

import database
import server


def test_exportacion_excel_enriquecida_estructura(test_db):
    # Insertar datos de prueba: una llanta original y un reencauche
    inspecciones_prueba = [
        {
            'fecha': '2026-11-10', 'cliente': 'CIUDAD LIMPIA', 'subcliente': 'BOGOTA',
            'tipo_operacion': 'RECOLECCIÓN BASURA', 'placa': '3032', 'tipologia': 'COMPACTADOR DOBLE',
            'posicion': 1, 'numero_interno': 'CL4464', 'marca': 'HAOHUA', 'diseno': 'GT23',
            'dimension': '295/80R22.5', 'vida': 'ORIGINAL', 'banda_reen': '', 'kilometraje': 36109,
            'unidad_medida': 'KM', 'prof_ext': 8.0, 'prof_cent': 8.0, 'prof_int': 8.0, 'psi': 110.0,
            'prof_inicial': 18.0, 'km_montaje': 22603, 'precio': 1285200, 'usuario_registro': 'ADMIN'
        },
        {
            'fecha': '2026-11-10', 'cliente': 'CIUDAD LIMPIA', 'subcliente': 'BOGOTA',
            'tipo_operacion': 'RECOLECCIÓN BASURA', 'placa': '3032', 'tipologia': 'COMPACTADOR DOBLE',
            'posicion': 3, 'numero_interno': 'CL4522', 'marca': 'KUMHO', 'diseno': 'KMD 41',
            'dimension': '295/80R22.5', 'vida': 'R1', 'banda_reen': 'DVMT', 'kilometraje': 36109,
            'unidad_medida': 'KM', 'prof_ext': 12.0, 'prof_cent': 12.0, 'prof_int': 11.0, 'psi': 100.0,
            'prof_inicial': 20.0, 'km_montaje': 25536, 'precio': 650000, 'usuario_registro': 'ADMIN'
        }
    ]
    for ins in inspecciones_prueba:
        database.insertar_inspeccion(ins)

    df_raw = database.obtener_todas_inspecciones(incluir_fotos=False)
    assert not df_raw.empty, "La base de datos debe contener las inspecciones insertadas"

    # Exportar a Excel
    buf = server.construir_excel_inspecciones(df_raw, filtros={"Cliente": "CIUDAD LIMPIA"})
    assert isinstance(buf, (bytes, bytearray))
    assert len(buf) > 1000, "El archivo Excel generado debe tener un tamaño válido"

    # Cargar workbook generado
    wb = openpyxl.load_workbook(io.BytesIO(buf), data_only=True)
    assert "Inspecciones" in wb.sheetnames
    assert "Resumen_Rendimiento" in wb.sheetnames
    assert "Filtros_Aplicados" in wb.sheetnames

    # Validar columnas de la hoja Inspecciones
    ws_insp = wb["Inspecciones"]
    headers = [ws_insp.cell(1, c).value for c in range(1, ws_insp.max_column + 1)]
    assert len(headers) == 33

    columnas_esperadas = [
        "Fecha", "Cliente", "Sede", "Operación", "Placa", "Tipología", "Posición", "Eje", "N.º interno",
        "Marca", "Diseño", "Dimensión", "Vida", "Banda reencauche", "Kilometraje", "Unidad",
        "Prof. exterior (mm)", "Prof. centro (mm)", "Prof. interior (mm)", "Presión (PSI)",
        "Prof. inicial (mm)", "Km al montaje", "Precio", "Movimiento", "Novedades", "Registrado por",
        "Km rodados", "Mm gastados", "Km/mm", "Prof. retiro (mm)", "Proyección (km)",
        "CPK operativo ($/km)", "CPK proyectado ($/km)"
    ]
    assert headers == columnas_esperadas

    # Validar valores calculados en la fila 2 (Original)
    # Km rodados = 36109 - 22603 = 13506
    assert ws_insp.cell(2, 27).value == 13506
    # Eje = Direccional
    assert ws_insp.cell(2, 8).value == "Direccional"
    # Mm gastados = 18 - 8 = 10.0
    assert ws_insp.cell(2, 28).value == 10.0

    # Validar hoja Resumen_Rendimiento
    ws_resumen = wb["Resumen_Rendimiento"]
    assert ws_resumen.max_row >= 5
    primer_titulo = ws_resumen.cell(1, 1).value
    assert "1. RENDIMIENTO DE LLANTAS ORIGINALES" in str(primer_titulo)
