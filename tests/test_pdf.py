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

