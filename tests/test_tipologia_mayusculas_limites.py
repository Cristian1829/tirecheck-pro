import pytest
from datetime import datetime
import database
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_bd():
    database.inicializar_bd()

def test_generar_esquema_desde_composicion_dobletroque_6x4():
    """
    Caso de la imagen:
    - 1 eje direccional sencilla (2 llantas)
    - 2 ejes de tracción dual (8 llantas)
    - 0 ejes libres (0 llantas)
    - 0 llantas de repuesto
    Total = 10 llantas
    """
    esquema, total = database.generar_esquema_desde_composicion(
        ejes_dir=1, tipo_dir='sencilla',
        ejes_trac=2, tipo_trac='dual',
        ejes_libres=0, tipo_libres='dual',
        cant_repuestos=0
    )
    assert total == 10
    assert len(esquema) == 3
    # Eje 1 Direccional
    assert esquema[0]['tipo'] == 'direccional'
    assert len(esquema[0]['posiciones']) == 2
    assert esquema[0]['posiciones'][0]['pos'] == 1
    assert esquema[0]['posiciones'][1]['pos'] == 2
    # Eje 2 Tracción Dual (4 llantas)
    assert esquema[1]['tipo'] == 'traccion'
    assert len(esquema[1]['posiciones']) == 4
    assert [p['pos'] for p in esquema[1]['posiciones']] == [3, 4, 5, 6]
    # Eje 3 Tracción Dual (4 llantas)
    assert esquema[2]['tipo'] == 'traccion'
    assert len(esquema[2]['posiciones']) == 4
    assert [p['pos'] for p in esquema[2]['posiciones']] == [7, 8, 9, 10]

def test_generar_esquema_con_repuestos_y_ejes_libres():
    """
    Trailer / Cabezote con:
    - 1 eje dir sencilla (2)
    - 1 eje tracción dual (4)
    - 2 ejes libres dual (8)
    - 2 repuestos (2)
    Total = 16 llantas
    """
    esquema, total = database.generar_esquema_desde_composicion(
        ejes_dir=1, tipo_dir='sencilla',
        ejes_trac=1, tipo_trac='dual',
        ejes_libres=2, tipo_libres='dual',
        cant_repuestos=2
    )
    assert total == 16
    assert len(esquema) == 5 # 1 dir + 1 trac + 2 libres + 1 repuesto
    # Verificar eje de repuesto
    rep_eje = esquema[-1]
    assert rep_eje['eje'] == 99
    assert rep_eje['tipo'] == 'repuesto'
    assert len(rep_eje['posiciones']) == 2
    assert rep_eje['posiciones'][0]['pos'] == 15
    assert rep_eje['posiciones'][1]['pos'] == 16

def test_guardar_tipologia_persistencia_en_mayusculas():
    nombre_tip = "volqueta cuatro manos 8x4 especial"
    nom_guardado = database.guardar_tipologia(
        nombre=nombre_tip,
        descripcion="vehiculo pesado minero",
        ejes_dir=2, tipo_dir='sencilla',
        ejes_trac=2, tipo_trac='dual',
        ejes_libres=0, tipo_libres='dual',
        cant_repuestos=1
    )
    assert nom_guardado == nombre_tip.upper()

    # Verificar en BD que el nombre y descripción quedaron en mayúsculas
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, descripcion, cant_llantas FROM catalogo_tipologias WHERE nombre = ?", (nombre_tip.upper(),))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == nombre_tip.upper()
        assert row[1] == "VEHICULO PESADO MINERO"
        assert row[2] == 13 # 2*2 + 2*4 + 0 + 1 = 13 llantas

def test_persistencia_mayusculas_en_inspecciones():
    """
    Todos los campos deben quedar en mayúsculas así se ingresen en minúsculas.
    """
    datos = {
        'fecha': datetime.now().strftime('%Y-%m-%d'),
        'cliente': 'transportes del valle s.a.s.',
        'subcliente': 'sede bogota norte',
        'tipo_operacion': 'distribucion urbana',
        'placa': 'xyz987',
        'posicion': 1,
        'kilometraje': 45000,
        'tipologia': 'camion sencillo 4x2',
        'marca': 'goodyear',
        'diseno': 'kmax s',
        'dimension': '295/80r22.5',
        'vida': 'original',
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 105.0,
        'novedades': 'desgaste uniforme en hombro',
        'numero_interno': 'll-valle-001',
        'usuario_registro': 'inspector_bogota'
    }

    insp_id = database.insertar_inspeccion(datos)
    assert insp_id is not None

    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cliente, subcliente, tipo_operacion, placa, tipologia, marca,
                   diseno, dimension, vida, novedades, numero_interno, usuario_registro
            FROM inspecciones WHERE id = ?
        """, (insp_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 'TRANSPORTES DEL VALLE S.A.S.'
        assert row[1] == 'SEDE BOGOTA NORTE'
        assert row[2] == 'DISTRIBUCION URBANA'
        assert row[3] == 'XYZ987'
        assert row[4] == 'CAMION SENCILLO 4X2'
        assert row[5] == 'GOODYEAR'
        assert row[6] == 'KMAX S'
        assert row[7] == '295/80R22.5'
        assert row[8] == 'ORIGINAL'
        assert row[9] == 'DESGASTE UNIFORME EN HOMBRO'
        assert row[10] == 'LL-VALLE-001'
        assert row[11] == 'INSPECTOR_BOGOTA'

def test_limites_retiro_por_cliente_subcliente_y_eje():
    """
    Configuración de límites con granularidad:
    - Cliente general
    - Cliente + Subcliente (Sede)
    - Cliente + Subcliente + Eje específico
    """
    # 1. Regla general para el cliente: 3.0 mm
    database.guardar_limite_retiro_cliente(
        cliente='coltrans',
        subcliente='TODOS',
        eje='TODOS',
        limite_retiro_mm=3.0,
        observaciones='politica estandar'
    )

    # 2. Regla para eje direccional en todo Coltrans: 4.5 mm (mayor exigencia)
    database.guardar_limite_retiro_cliente(
        cliente='coltrans',
        subcliente='TODOS',
        eje='DIRECCIONAL',
        limite_retiro_mm=4.5,
        observaciones='seguridad eje delantero'
    )

    # 3. Regla específica para Sede Mina en Eje Tracción: 5.0 mm
    database.guardar_limite_retiro_cliente(
        cliente='coltrans',
        subcliente='SEDE MINA',
        eje='TRACCIÓN',
        limite_retiro_mm=5.0,
        observaciones='terreno rocoso severo'
    )

    # Validar búsqueda en cascada:
    # A) Eje direccional en cualquier sede -> debe retornar 4.5 mm
    lim_dir = database.obtener_limite_retiro_cliente('coltrans', subcliente='SEDE SUR', eje='DIRECCIONAL')
    assert lim_dir == 4.5

    # B) Eje tracción en SEDE MINA -> debe retornar 5.0 mm
    lim_mina_trac = database.obtener_limite_retiro_cliente('coltrans', subcliente='SEDE MINA', eje='TRACCIÓN')
    assert lim_mina_trac == 5.0

    # C) Eje tracción en otra sede (ej. SEDE CALI) -> fallback a Coltrans general (3.0 mm)
    lim_cali_trac = database.obtener_limite_retiro_cliente('coltrans', subcliente='SEDE CALI', eje='TRACCIÓN')
    assert lim_cali_trac == 3.0

    # D) Cliente no registrado -> default 3.0 mm
    lim_desconocido = database.obtener_limite_retiro_cliente('cliente_inexistente', subcliente='TODOS', eje='TODOS')
    assert lim_desconocido == 3.0

def test_eliminar_limite_retiro_cliente():
    database.guardar_limite_retiro_cliente(
        cliente='empresa_prueba_del',
        subcliente='SEDE 1',
        eje='LIBRE',
        limite_retiro_mm=2.5,
        observaciones='prueba eliminacion'
    )
    todas = database.obtener_todas_configuraciones_clientes()
    regla = [r for r in todas if r['cliente'] == 'EMPRESA_PRUEBA_DEL' and r['subcliente'] == 'SEDE 1' and r['eje'] == 'LIBRE']
    assert len(regla) == 1
    regla_id = regla[0]['id']

    ok = database.eliminar_limite_retiro_cliente(regla_id)
    assert ok is True

    todas_despues = database.obtener_todas_configuraciones_clientes()
    regla_despues = [r for r in todas_despues if r['cliente'] == 'EMPRESA_PRUEBA_DEL' and r['subcliente'] == 'SEDE 1' and r['eje'] == 'LIBRE']
    assert len(regla_despues) == 0
