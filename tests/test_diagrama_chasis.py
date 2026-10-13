import io
import os
import re
import pytest
import pypdf
import pypdfium2 as pdfium
from fastapi.testclient import TestClient

import database
import pdf_generator
import diagrama_chasis_pdf as dg
import server

# =========================================================================
# 1. PRUEBA DE GEOMETRÍA, SIMETRÍA Y AUSENCIA DE SOLAPES EN EL DIAGRAMA
# =========================================================================

def test_geometria_y_simetria_chasis():
    """
    Verifica que la geometría del diagrama de chasis sea matemáticamente simétrica
    y que los elementos de cada neumático (llanta, medallón, rol, valor) no se solapen.
    """
    # 1. Simetría de las posiciones horizontales
    assert dg.TIRE_W == 18.0
    assert dg.TIRE_H == 26.0
    assert dg.X_EXT - dg.X_INT == 26.0  # Centros a 26 pt -> hueco entre llantas de 8 pt
    hueco_duales = (dg.X_EXT - dg.X_INT) - dg.TIRE_W
    assert hueco_duales == 8.0, "El hueco entre duales debe ser exactamente 8 pt"

    # Simetría en eje direccional sencillo
    eje_sencillo = {
        'eje': 1, 'tipo': 'Direccional',
        'posiciones': [
            {'pos': 1, 'lado': 'izq', 'rol': 'DIR'},
            {'pos': 2, 'lado': 'der', 'rol': 'DIR'}
        ]
    }
    llantas_s = dg._llantas_del_eje(eje_sencillo)
    assert len(llantas_s) == 2
    dx_izq, p_izq = llantas_s[0]
    dx_der, p_der = llantas_s[1]
    assert dx_izq == -dg.X_SEN
    assert dx_der == dg.X_SEN
    assert abs(dx_izq) == abs(dx_der), "Llantas direccionales deben ser perfectamente simétricas"

    # Simetría en eje tracción dual
    eje_dual = {
        'eje': 2, 'tipo': 'Tracción',
        'posiciones': [
            {'pos': 3, 'lado': 'izq', 'rol': 'EXT'},
            {'pos': 4, 'lado': 'izq', 'rol': 'INT'},
            {'pos': 5, 'lado': 'der', 'rol': 'INT'},
            {'pos': 6, 'lado': 'der', 'rol': 'EXT'}
        ]
    }
    llantas_d = dg._llantas_del_eje(eje_dual)
    assert len(llantas_d) == 4
    # Orden de izquierda a derecha: -X_EXT, -X_INT, +X_INT, +X_EXT
    coords_x = [dx for dx, _ in llantas_d]
    assert coords_x == [-dg.X_EXT, -dg.X_INT, dg.X_INT, dg.X_EXT]
    assert abs(coords_x[0]) == abs(coords_x[3]), "Duales exteriores deben ser simétricos"
    assert abs(coords_x[1]) == abs(coords_x[2]), "Duales interiores deben ser simétricos"

    # 2. Pila vertical de cada llanta sin solapamientos
    # yb = y_top - TIRE_H
    # cy = yb - GAP_TIRE_BADGE - BADGE_R
    # y_rol = cy - BADGE_R - GAP_BADGE_ROL - ROL_CAP
    # y_val = y_rol - GAP_ROL_VAL - VAL_CAP
    assert dg.GAP_TIRE_BADGE > 0
    assert dg.GAP_BADGE_ROL > 0
    assert dg.GAP_ROL_VAL > 0
    assert dg.PILA_H > dg.TIRE_H + 2 * dg.BADGE_R + dg.ROL_CAP + dg.VAL_CAP

    # 3. Función profundidad_minima como única fuente de verdad
    fila_con_datos = {'prof_ext': '12.5', 'prof_cent': '10.0', 'prof_int': '11.2'}
    assert dg.profundidad_minima(fila_con_datos) == 10.0

    fila_con_ceros = {'prof_ext': 0, 'prof_cent': 0.0, 'prof_int': 0}
    assert dg.profundidad_minima(fila_con_ceros) is None

    fila_vacia = {}
    assert dg.profundidad_minima(fila_vacia) is None


# =========================================================================
# 2. CASO 1: 2 EJES (CAMIÓN 4x2)
# =========================================================================

def test_caso_2_ejes(test_db):
    placa = "DOS-002"
    fecha = "2026-10-12"
    # Insertar 6 llantas (2 directores + 4 tracción)
    for pos, rol, p_ext, p_cen, p_int in [
        (1, 'DIR', 12.0, 12.0, 12.0),
        (2, 'DIR', 12.0, 12.0, 12.0),
        (3, 'EXT', 14.0, 14.0, 14.0),
        (4, 'INT', 14.0, 14.0, 14.0),
        (5, 'INT', 14.0, 14.0, 14.0),
        (6, 'EXT', 14.0, 14.0, 14.0),
    ]:
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Transportes A',
            'subcliente': 'Sede Bogotá',
            'tipo_operacion': 'Carga General',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 85000.0,
            'tipologia': 'Camión (4x2)',
            'marca': 'Goodyear',
            'dimension': '295/80R22.5',
            'prof_ext': p_ext,
            'prof_cent': p_cen,
            'prof_int': p_int,
            'psi': 105.0,
            'rol': rol,
            'usuario_registro': 'Inspector A'
        })

    pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento(placa)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b'%PDF-')
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    texto = "\n".join(p.extract_text() for p in reader.pages)
    assert "DOS-002" in texto
    assert "Eje 1 · Direccional" in texto
    assert "Eje 2 · Tracción" in texto


# =========================================================================
# 3. CASO 2: 3 EJES CON REPUESTO (CABEZOTE 6x4)
# =========================================================================

def test_caso_3_ejes_con_repuesto(test_db):
    placa = "REP-003"
    fecha = "2026-10-12"
    # Trailer 3 ejes + repuesto (12 llantas rodantes + repuesto en pos 13)
    tipologia = "Trailer (3 Ejes - 12 Llantas + Repuesto)"
    for pos in range(1, 14):
        es_rep = (pos == 13)
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Logística Pesada',
            'subcliente': 'Patio Central',
            'tipo_operacion': 'Troncal',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 120000.0,
            'tipologia': tipologia,
            'marca': 'Michelin',
            'dimension': '295/80R22.5',
            'prof_ext': 11.0,
            'prof_cent': 11.0,
            'prof_int': 11.0,
            'psi': 100.0,
            'rol': 'REP' if es_rep else ('EXT' if pos in (1, 4, 5, 8, 9, 12) else 'INT'),
            'usuario_registro': 'Inspector Central'
        })

    pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento(placa)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join(p.extract_text() for p in reader.pages)
    assert "REP-003" in texto
    assert "Repuesto" in texto
    assert "Eje 1 · Remolque" in texto


# =========================================================================
# 4. CASO 3: 4 EJES Y 12 POSICIONES CON VARIAS LLANTAS BAJO EL LÍMITE
# =========================================================================

def test_caso_4_ejes_12_posiciones_con_retiro(test_db):
    placa = "CUA-012"
    fecha = "2026-10-12"
    # Camión 8x4 Cuatro Manos (12 posiciones):
    # Llantas 1 y 7 bajo límite de retiro (<= 3.0 mm)
    for pos in range(1, 13):
        es_retiro = (pos in (1, 7))
        prof = 2.1 if es_retiro else 11.5
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Minera del Norte',
            'subcliente': 'Tajo 1',
            'tipo_operacion': 'Minería Pesada',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 180000.0,
            'tipologia': 'Camión Cuatro Manos (8x4)',
            'marca': 'Bridgestone',
            'dimension': '315/80R22.5',
            'prof_ext': prof,
            'prof_cent': prof,
            'prof_int': prof,
            'psi': 110.0,
            'rol': 'DIR' if pos in (1, 2, 3, 4) else 'EXT' if pos in (5, 8, 9, 12) else 'INT',
            'usuario_registro': 'Inspector Minas'
        })

    datos = pdf_generator.construir_datos_informe(placa)
    assert datos['n_cambios'] == 2
    assert datos['p_min_global'] == 2.1
    assert any("Posición 1" in a['detalle'] or "posición 1" in a['detalle'] for a in datos['alertas_lista'])
    assert any("Posición 7" in a['detalle'] or "posición 7" in a['detalle'] for a in datos['alertas_lista'])

    pdf_bytes = pdf_generator.renderizar_informe(datos)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join(p.extract_text() for p in reader.pages)
    assert "CUA-012" in texto
    assert "Cambio" in texto


# =========================================================================
# 5. CASO 4: SIN LECTURAS (VALORES CERO / NULOS -> "—")
# =========================================================================

def test_caso_sin_lecturas(test_db):
    placa = "VAC-000"
    fecha = "2026-10-12"
    for pos in [1, 2]:
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Flota Prueba',
            'subcliente': 'Taller',
            'tipo_operacion': 'Urbano',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 50000.0,
            'tipologia': 'Camión (4x2)',
            'prof_ext': 0.0,
            'prof_cent': 0.0,
            'prof_int': 0.0,
            'psi': 0.0,
            'usuario_registro': 'Inspector Prueba'
        })

    datos = pdf_generator.construir_datos_informe(placa)
    assert datos['p_min_global'] is None
    assert datos['p_prom_global'] is None

    pdf_bytes = pdf_generator.renderizar_informe(datos)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join(p.extract_text() for p in reader.pages)
    assert "VAC-000" in texto
    # Verificar que aparece el guion largo "—" correspondiente a sin lecturas
    assert "—" in texto or "PEND" in texto


# =========================================================================
# 6. CASO 5: 8 ALERTAS
# =========================================================================

def test_caso_8_alertas(test_db):
    placa = "ALT-008"
    fecha = "2026-10-12"
    # Diseñar un vehículo que detone exactamente 8 alertas:
    # 1. Tres llantas en retiro (pos 1, 2, 3) con prof <= 3.0 mm -> 3 alertas de Cambio
    # 2. Desgaste disparejo en directores: pos 1 prof_int=3.0, prof_ext=1.0 -> genera Alineación -> 1 alerta
    # 3. Dual mal apareado en pos 5-6 (pos 5=9.0mm, pos 6=6.0mm, dif 3.0mm >= 2.0mm) -> 1 alerta
    # 4. Tres novedades mecánicas reportadas en pos 4, 7, 8 -> 3 alertas
    # Total = 3 + 1 + 1 + 3 = 8 alertas!
    pos_data = [
        (1, 'DIR', 1.0, 2.0, 3.0, ''),       # Cambio + dif int-ext 2.0 -> Alineación
        (2, 'DIR', 2.5, 2.5, 2.5, ''),       # Cambio
        (3, 'EXT', 2.8, 2.8, 2.8, ''),       # Cambio
        (4, 'INT', 9.0, 9.0, 9.0, 'Corte en banda de rodamiento'), # Novedad 1
        (5, 'INT', 9.0, 9.0, 9.0, ''),       # Dual mal apareado con pos 6
        (6, 'EXT', 6.0, 6.0, 6.0, ''),       # dif=3.0mm
        (7, 'EXT', 10.0, 10.0, 10.0, 'Válvula defectuosa con fuga'), # Novedad 2
        (8, 'INT', 10.0, 10.0, 10.0, 'Desgaste anormal en hombro'), # Novedad 3
    ]
    for pos, rol, p_ext, p_cen, p_int, nov in pos_data:
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Flota Alertas',
            'subcliente': 'Base',
            'tipo_operacion': 'Carga',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 150000.0,
            'tipologia': 'Cabezote (6x4)',
            'marca': 'Pirelli',
            'dimension': '295/80R22.5',
            'prof_ext': p_ext,
            'prof_cent': p_cen,
            'prof_int': p_int,
            'psi': 100.0,
            'rol': rol,
            'novedades': nov,
            'usuario_registro': 'Inspector Alertas'
        })

    datos = pdf_generator.construir_datos_informe(placa)
    assert datos['total_alertas'] >= 8, f"Se esperaban al menos 8 alertas, se encontraron {datos['total_alertas']}"
    assert len(datos['alertas_lista']) >= 8
    # Comprobar que no hay recorte artificial a 4
    pdf_bytes = pdf_generator.renderizar_informe(datos)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join(p.extract_text() for p in reader.pages)
    assert "Corte en banda" in texto
    assert "Válvula defectuosa" in texto
    assert "Desgaste anormal" in texto


# =========================================================================
# 7. CASO 6: INFORME QUE PASE DE 2 PÁGINAS (PAGINACIÓN DINÁMICA N >= 3)
# =========================================================================

def test_caso_informe_pasa_de_2_paginas(test_db):
    placa = "PAG-003"
    fecha = "2026-10-12"
    # Vehículo de 4 ejes (12 posiciones) con múltiples novedades extensas
    # que empujan el contenido y la tabla detallada de llantas a 3 páginas
    for pos in range(1, 13):
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Transportes Transcontinentales de Carga Pesada S.A.',
            'subcliente': 'Operación Fronteriza Norte',
            'tipo_operacion': 'Transporte Especial Refrigerado de Alta Exigencia',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 295000.0,
            'tipologia': 'Camión Cuatro Manos (8x4)',
            'marca': 'Continental Hybrid Multi-Track Ultra Premium',
            'diseno': 'Conti EcoPlus HD3 High Mileage Long Distance',
            'dimension': '315/80R22.5 156/150K',
            'prof_ext': 2.5 if pos % 2 == 0 else 12.0,
            'prof_cent': 2.5 if pos % 2 == 0 else 12.0,
            'prof_int': 2.5 if pos % 2 == 0 else 12.0,
            'psi': 105.0,
            'rol': 'DIR' if pos in (1, 2, 3, 4) else 'EXT' if pos in (5, 8, 9, 12) else 'INT',
            'novedades': f"Posición {pos}: Inspección detallada con desgaste en banda, corte lateral superficial por piedras en vía, requiere seguimiento en próximo mantenimiento programado de la flota.",
            'usuario_registro': 'Inspector de Garantías Técnicas y Certificación de Flotas'
        })

    pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento(placa)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    num_paginas = len(reader.pages)
    assert num_paginas >= 3, f"El informe con alto volumen de alertas y novedades debe superar 2 páginas (generó {num_paginas})"

    # Verificar que el footer tenga la numeración dinámica 'Página X de Y'
    ultimo_texto = reader.pages[-1].extract_text()
    assert f"Página {num_paginas} de {num_paginas}" in ultimo_texto


# =========================================================================
# 8. CASO 7: COMPARACIÓN DE LOS TRES CAMINOS (TEXTO EXACTAMENTE IGUAL)
# =========================================================================

def test_comparacion_tres_caminos(test_db):
    placa = "CAM-999"
    # Insertar dos fechas distintas: inspección anterior y última inspección
    fecha_ant = "2026-10-01"
    fecha_ult = "2026-10-12"

    for f_fecha in (fecha_ant, fecha_ult):
        for pos in (1, 2):
            database.insertar_inspeccion({
                'fecha': f_fecha,
                'cliente': 'Cliente Tres Caminos',
                'subcliente': 'Sede 1',
                'tipo_operacion': 'Troncal',
                'placa': placa,
                'posicion': pos,
                'kilometraje': 100000.0 if f_fecha == fecha_ant else 105000.0,
                'tipologia': 'Camión (4x2)',
                'prof_ext': 8.0 if f_fecha == fecha_ant else 7.0,
                'prof_cent': 8.0 if f_fecha == fecha_ant else 7.0,
                'prof_int': 8.0 if f_fecha == fecha_ant else 7.0,
                'psi': 100.0,
                'usuario_registro': 'Inspector Caminos'
            })

    # Camino 1: Función directa sin fecha (debe resolver a la última fecha: 2026-10-12)
    pdf1 = pdf_generator.generar_pdf_plan_mantenimiento(placa)

    # Camino 2: Función directa con fecha explícita de la última inspección
    pdf2 = pdf_generator.generar_pdf_plan_mantenimiento(placa, fecha_ult)

    # Camino 3: Endpoint de API FastAPI
    client = TestClient(server.app)
    resp = client.get(f"/api/informe-pdf/{placa}?fecha={fecha_ult}")
    assert resp.status_code == 200
    pdf3 = resp.content

    def extraer_texto_limpio(pdf_b):
        r = pypdf.PdfReader(io.BytesIO(pdf_b))
        txt = " ".join(p.extract_text() for p in r.pages)
        # Normalizar espacios en blanco
        return re.sub(r'\s+', ' ', txt).strip()

    txt1 = extraer_texto_limpio(pdf1)
    txt2 = extraer_texto_limpio(pdf2)
    txt3 = extraer_texto_limpio(pdf3)

    assert txt1 == txt2, "El PDF sin fecha (última inspección) debe ser idéntico al PDF con fecha explícita"
    assert txt1 == txt3, "El PDF vía endpoint API debe ser idéntico al generado directamente"


# =========================================================================
# 9. RENDERIZADO DE PÁGINAS A PNG CON PYPDFIUM2
# =========================================================================

def test_renderizar_paginas_png(test_db):
    """
    Renderiza las páginas del informe a archivos PNG con pypdfium2 y valida su generación.
    """
    placa = "PNG-101"
    fecha = "2026-10-12"
    for pos in [1, 2, 3, 4]:
        database.insertar_inspeccion({
            'fecha': fecha,
            'cliente': 'Flota Visual',
            'subcliente': 'Base Visual',
            'tipo_operacion': 'Reparto',
            'placa': placa,
            'posicion': pos,
            'kilometraje': 45000.0,
            'tipologia': 'Camión (4x2)',
            'prof_ext': 9.0,
            'prof_cent': 9.0,
            'prof_int': 9.0,
            'psi': 100.0,
            'usuario_registro': 'Inspector Visual'
        })

    pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento(placa, fecha)
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    assert len(pdf_doc) > 0

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ejemplos")
    os.makedirs(out_dir, exist_ok=True)

    archivos_generados = []
    for idx, page in enumerate(pdf_doc):
        image = page.render(scale=2).to_pil()
        png_path = os.path.join(out_dir, f"test_{placa}_pagina_{idx + 1}.png")
        image.save(png_path)
        assert os.path.exists(png_path)
        assert os.path.getsize(png_path) > 1000
        archivos_generados.append(png_path)

    assert len(archivos_generados) == len(pdf_doc)
