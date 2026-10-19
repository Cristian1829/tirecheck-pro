import pytest
import pdf_generator
import database

def test_generar_pdf_plan_mantenimiento(test_db):
    # Insertar datos mínimos de un vehículo
    datos = {
        'fecha': '2026-10-01',
        'cliente': 'Cliente PDF',
        'subcliente': 'Sede Central',
        'tipo_operacion': 'Carga',
        'placa': 'PDF-001',
        'posicion': 1,
        'kilometraje': 100000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 105.0,
        'usuario_registro': 'Inspector Test'
    }
    database.insertar_inspeccion(datos)

    pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento('PDF-001')
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b'%PDF-')

def test_generar_pdf_consolidado(test_db):
    # Insertar datos para consolidado
    datos = {
        'fecha': '2026-10-01',
        'cliente': 'Cliente Consolidado',
        'subcliente': 'Sede Norte',
        'tipo_operacion': 'Carga',
        'placa': 'PDF-002',
        'posicion': 1,
        'kilometraje': 100000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 10.0,
        'prof_cent': 10.0,
        'prof_int': 10.0,
        'psi': 105.0
    }
    database.insertar_inspeccion(datos)

    pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada(cliente='Cliente Consolidado')
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b'%PDF-')

def test_generar_pdf_consolidado_cliente_y_sede(test_db):
    # Probar filtrado estricto por cliente y sede
    datos = {
        'fecha': '2026-10-01',
        'cliente': 'Cliente Consolidado',
        'subcliente': 'Sede Norte',
        'tipo_operacion': 'Carga',
        'placa': 'PDF-003',
        'posicion': 1,
        'kilometraje': 100000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 10.0,
        'prof_cent': 10.0,
        'prof_int': 10.0,
        'psi': 105.0
    }
    database.insertar_inspeccion(datos)
    pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada(cliente='Cliente Consolidado', subcliente='Sede Norte')
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b'%PDF-')


def test_generar_pdf_consolidado_con_alertas_multiples(test_db):
    # Vehículo 1: tiene cambio, alineación y dual simultáneamente (debe contar como 1 vehículo con alerta, no como 3)
    # Posición 1 y 2 para dual y alineación
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'Flota Test Alertas',
        'subcliente': 'Sede Principal',
        'tipo_operacion': 'Ruta',
        'placa': 'V-CRITICO',
        'posicion': 1,
        'kilometraje': 50000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 2.0,  # <= 3.0 mm (retiro) y diferencia >= 2.0 (alineación)
        'prof_cent': 5.0,
        'prof_int': 6.0,
        'psi': 100.0
    })
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'Flota Test Alertas',
        'subcliente': 'Sede Principal',
        'tipo_operacion': 'Ruta',
        'placa': 'V-CRITICO',
        'posicion': 2,
        'kilometraje': 50000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 100.0
    })

    # Vehículo 2: completamente sano (0 alertas)
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'Flota Test Alertas',
        'subcliente': 'Sede Principal',
        'tipo_operacion': 'Ruta',
        'placa': 'V-OPTIMO',
        'posicion': 1,
        'kilometraje': 20000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 110.0
    })

    pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada(cliente='Flota Test Alertas')
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b'%PDF-')


def test_pdf_tecnico_y_consolidado_dimensiones_mixtas(test_db):
    # Vehículo con dos dimensiones distintas: Pos 1 (295/80R22.5) y Pos 2 (275/70R22.5)
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'Flota Dims Mixtas',
        'subcliente': 'Sede Centro',
        'tipo_operacion': 'Urbano',
        'placa': 'V-DIMS',
        'posicion': 1,
        'kilometraje': 40000.0,
        'dimension': '295/80R22.5',
        'prof_inicial': 16.0,
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 105.0
    })
    database.insertar_inspeccion({
        'fecha': '2026-10-01',
        'cliente': 'Flota Dims Mixtas',
        'subcliente': 'Sede Centro',
        'tipo_operacion': 'Urbano',
        'placa': 'V-DIMS',
        'posicion': 2,
        'kilometraje': 40000.0,
        'dimension': '275/70R22.5',
        'prof_inicial': 15.0,
        'prof_ext': 11.0,
        'prof_cent': 11.0,
        'prof_int': 11.0,
        'psi': 105.0
    })

    # 1. Informe Técnico
    datos = pdf_generator.construir_datos_informe('V-DIMS', '2026-10-01')
    assert datos['tiene_dims_distintas'] is True
    assert any(a['tipo'] == 'Dimensiones mixtas' for a in datos['alertas_lista'])
    pdf_tecnico = pdf_generator.generar_pdf_plan_mantenimiento('V-DIMS', '2026-10-01')
    assert isinstance(pdf_tecnico, bytes)
    assert len(pdf_tecnico) > 1000
    assert pdf_tecnico.startswith(b'%PDF-')

    # 2. Informe Consolidado / Ejecutivo
    pdf_consolidado = pdf_generator.generar_pdf_consolidado_jornada(cliente='Flota Dims Mixtas')
    assert isinstance(pdf_consolidado, bytes)
    assert len(pdf_consolidado) > 1000
    assert pdf_consolidado.startswith(b'%PDF-')



