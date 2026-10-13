import io
import os
import sys
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Group
import pypdfium2 as pdfium

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database

def format_num_es(val, decimals=1):
    if val is None:
        return '0,0'
    try:
        return f"{float(val):.{decimals}f}".replace('.', ',')
    except (ValueError, TypeError):
        return str(val)

def normalizar_rol_txt(rol):
    if not rol: return ''
    r = str(rol).upper().strip()
    if 'DIR' in r: return 'DIR'
    if 'EXT' in r: return 'EXT'
    if 'INT' in r: return 'INT'
    if 'REP' in r: return 'REP'
    if 'SEN' in r or 'LIB' in r: return 'SEN'
    return r[:3]

def dibujar_diagrama_chasis_estilo_ejemplo(tipologia, filas, limite_retiro=3.0, width=540):
    try:
        esquema = database.obtener_esquema_tipologia(tipologia)
    except Exception:
        esquema = None
    if not esquema:
        return Spacer(1, 5)

    pos_map = {}
    for f in filas:
        p = int(f.get('posicion', 0))
        p_ext = float(f.get('prof_ext') or 0)
        p_cen = float(f.get('prof_cent') or 0)
        p_int = float(f.get('prof_int') or 0)
        validas = [v for v in (p_ext, p_cen, p_int) if v > 0]
        p_min = min(validas) if validas else 0.0
        psi = float(f.get('psi') or 0)
        novedades = str(f.get('novedades') or '').strip()
        pos_map[p] = {
            'p_min': p_min,
            'psi': psi,
            'novedades': novedades,
            'numero_interno': str(f.get('numero_interno') or ''),
            'marca': str(f.get('marca') or ''),
            'registrada': True
        }

    ejes_rodantes = [e for e in esquema if e.get('eje') != 99 and (e.get('tipo') or '').lower() != 'repuesto']
    ejes_repuesto = [e for e in esquema if e.get('eje') == 99 or (e.get('tipo') or '').lower() == 'repuesto']

    num_ejes = max(1, len(ejes_rodantes))
    if num_ejes <= 2:
        alto_eje = 56
    elif num_ejes == 3:
        alto_eje = 52
    else:
        alto_eje = 46

    alto_header = 22
    alto_leyenda = 18
    alto_repuesto = 54 if ejes_repuesto else 0
    total_height = alto_header + (num_ejes * alto_eje) + alto_repuesto + alto_leyenda + 8

    d = Drawing(width, total_height)
    d.add(Rect(0, 0, width, total_height, rx=4, ry=4, fillColor=colors.white, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.75))

    cx = width / 2.0

    # 1. Cabecera con orientación
    curr_y = total_height - 12
    d.add(String(20, curr_y, "IZQUIERDA", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#64748B')))
    d.add(String(cx, curr_y, "▲ FRENTE", fontName="Helvetica-Bold", fontSize=7.0, fillColor=colors.HexColor('#1E3A8A'), textAnchor="middle"))
    d.add(String(width - 20, curr_y, "DERECHA", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#64748B'), textAnchor="end"))

    curr_y -= 6
    d.add(Line(12, curr_y, width - 12, curr_y, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.6))

    X_SEN_IZQ = 135.0
    X_EXT_IZQ = 110.0
    X_INT_IZQ = 160.0

    X_INT_DER = 380.0
    X_EXT_DER = 430.0
    X_SEN_DER = 405.0

    w_llanta = 16.0
    h_llanta = 24.0

    # 2. Renderizado de cada eje rodante
    for idx, e in enumerate(ejes_rodantes):
        y_eje = curr_y - (idx * alto_eje) - 18
        eje_num = e.get('eje', idx + 1)
        tipo_raw = str(e.get('tipo', '')).lower()
        tipo_lbl = 'Direccional' if 'dir' in tipo_raw else 'Tracción' if 'trac' in tipo_raw else 'Libre'

        # Etiqueta de eje a la izquierda
        d.add(String(16, y_eje + 6, f"Eje {eje_num} · {tipo_lbl}", fontName="Helvetica-Bold", fontSize=7.0, fillColor=colors.HexColor('#0F172A')))

        # Barra transversal del eje
        d.add(Line(X_EXT_IZQ, y_eje, X_EXT_DER, y_eje, strokeColor=colors.HexColor('#CBD5E1'), strokeWidth=1.8))
        d.add(Circle(cx, y_eje, 3.2, fillColor=colors.HexColor('#94A3B8'), strokeColor=colors.HexColor('#64748B'), strokeWidth=0.6))

        posiciones = e.get('posiciones', [])
        izq = [p for p in posiciones if p.get('lado') == 'izq']
        der = [p for p in posiciones if p.get('lado') == 'der']

        coords = []
        if len(izq) == 1:
            coords.append((X_SEN_IZQ, izq[0]))
        elif len(izq) >= 2:
            ext_p = next((p for p in izq if 'ext' in str(p.get('rol', '')).lower()), izq[0])
            int_p = next((p for p in izq if p != ext_p), izq[1])
            coords.append((X_EXT_IZQ, ext_p))
            coords.append((X_INT_IZQ, int_p))

        if len(der) == 1:
            coords.append((X_SEN_DER, der[0]))
        elif len(der) >= 2:
            int_p = next((p for p in der if 'int' in str(p.get('rol', '')).lower()), der[0])
            ext_p = next((p for p in der if p != int_p), der[1])
            coords.append((X_INT_DER, int_p))
            coords.append((X_EXT_DER, ext_p))

        for wx, p in coords:
            pos_num = p.get('pos')
            rol_txt = normalizar_rol_txt(p.get('rol'))
            info = pos_map.get(pos_num, {})
            registrada = info.get('registrada', False)
            p_min = info.get('p_min', 0.0)
            novedades = info.get('novedades', '')

            xb = wx - (w_llanta / 2.0)
            yb = y_eje - (h_llanta / 2.0)
            d.add(Rect(xb, yb, w_llanta, h_llanta, rx=3, ry=3, fillColor=colors.HexColor('#1E293B'), strokeColor=colors.HexColor('#0F172A'), strokeWidth=0.8))
            d.add(Line(xb + 4.5, yb + 2.5, xb + 4.5, yb + h_llanta - 2.5, strokeColor=colors.HexColor('#475569'), strokeWidth=0.6))
            d.add(Line(xb + w_llanta - 4.5, yb + 2.5, xb + w_llanta - 4.5, yb + h_llanta - 2.5, strokeColor=colors.HexColor('#475569'), strokeWidth=0.6))

            y_badge = yb - 5.5
            es_retiro = (p_min > 0 and p_min <= limite_retiro)
            tiene_novedad = bool(novedades)

            if not registrada:
                badge_stroke = colors.HexColor('#94A3B8')
                badge_fill = colors.white
            elif es_retiro:
                badge_stroke = colors.HexColor('#DC2626')
                badge_fill = colors.HexColor('#FEE2E2')
            elif tiene_novedad:
                badge_stroke = colors.HexColor('#D97706')
                badge_fill = colors.HexColor('#FEF3C7')
            else:
                badge_stroke = colors.HexColor('#10B981')
                badge_fill = colors.white

            d.add(Circle(wx, y_badge, 4.8, fillColor=badge_fill, strokeColor=badge_stroke, strokeWidth=1.0))
            d.add(String(wx, y_badge - 1.8, str(pos_num), fontName="Helvetica-Bold", fontSize=5.5, fillColor=colors.HexColor('#0F172A'), textAnchor="middle"))

            y_rol = y_badge - 7.0
            d.add(String(wx, y_rol, rol_txt, fontName="Helvetica", fontSize=5.0, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

            y_mm = y_rol - 6.5
            if registrada and p_min > 0:
                color_mm = colors.HexColor('#DC2626') if es_retiro else colors.HexColor('#0F172A')
                d.add(String(wx, y_mm, format_num_es(p_min), fontName="Helvetica-Bold", fontSize=6.0, fillColor=color_mm, textAnchor="middle"))
            elif registrada:
                d.add(String(wx, y_mm, "0,0", fontName="Helvetica", fontSize=5.5, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))
            else:
                d.add(String(wx, y_mm, "PEND", fontName="Helvetica", fontSize=5.0, fillColor=colors.HexColor('#94A3B8'), textAnchor="middle"))

    # 3. Soporte de Repuesto (si aplica)
    if ejes_repuesto:
        y_rep = alto_leyenda + 32
        p_rep = ejes_repuesto[0].get('posiciones', [{}])[0].get('pos', 99)
        info_rep = pos_map.get(p_rep, {})
        reg_rep = info_rep.get('registrada', False)
        p_min_rep = info_rep.get('p_min', 0.0)
        nov_rep = info_rep.get('novedades', '')
        es_ret_rep = (p_min_rep > 0 and p_min_rep <= limite_retiro)

        d.add(String(16, y_rep + 4, "Repuesto", fontName="Helvetica-Bold", fontSize=7.0, fillColor=colors.HexColor('#0F172A')))

        xb_rep = cx - (w_llanta / 2.0)
        yb_rep = y_rep - (h_llanta / 2.0) + 4
        d.add(Rect(xb_rep, yb_rep, w_llanta, h_llanta, rx=3, ry=3, fillColor=colors.HexColor('#1E293B'), strokeColor=colors.HexColor('#0F172A'), strokeWidth=0.8))
        d.add(Line(xb_rep + 4.5, yb_rep + 2.5, xb_rep + 4.5, yb_rep + h_llanta - 2.5, strokeColor=colors.HexColor('#475569'), strokeWidth=0.6))
        d.add(Line(xb_rep + w_llanta - 4.5, yb_rep + 2.5, xb_rep + w_llanta - 4.5, yb_rep + h_llanta - 2.5, strokeColor=colors.HexColor('#475569'), strokeWidth=0.6))

        y_badge_rep = yb_rep - 5.5
        badge_st_rep = colors.HexColor('#DC2626') if es_ret_rep else colors.HexColor('#D97706') if nov_rep else colors.HexColor('#10B981')
        badge_bg_rep = colors.HexColor('#FEE2E2') if es_ret_rep else colors.HexColor('#FEF3C7') if nov_rep else colors.white

        d.add(Circle(cx, y_badge_rep, 4.8, fillColor=badge_bg_rep, strokeColor=badge_st_rep, strokeWidth=1.0))
        d.add(String(cx, y_badge_rep - 1.8, str(p_rep), fontName="Helvetica-Bold", fontSize=5.5, fillColor=colors.HexColor('#0F172A'), textAnchor="middle"))

        d.add(String(cx, y_badge_rep - 7.0, "REP", fontName="Helvetica", fontSize=5.0, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

        if reg_rep and p_min_rep > 0:
            color_mm_rep = colors.HexColor('#DC2626') if es_ret_rep else colors.HexColor('#0F172A')
            d.add(String(cx, y_badge_rep - 13.5, format_num_es(p_min_rep), fontName="Helvetica-Bold", fontSize=6.0, fillColor=color_mm_rep, textAnchor="middle"))
        elif reg_rep:
            d.add(String(cx, y_badge_rep - 13.5, "0,0", fontName="Helvetica", fontSize=5.5, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

    # 4. Barra de Leyenda al pie
    y_leg = 6
    d.add(Line(12, y_leg + 11, width - 12, y_leg + 11, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.6))

    # Cuadro verde Registrada
    d.add(Rect(18, y_leg, 8, 8, rx=2, ry=2, fillColor=colors.HexColor('#047857'), strokeColor=colors.HexColor('#065F46'), strokeWidth=0.6))
    d.add(String(29, y_leg + 1.8, "Registrada", fontName="Helvetica", fontSize=6.0, fillColor=colors.HexColor('#334155')))

    # Cuadro naranja Con novedad
    d.add(Rect(75, y_leg, 8, 8, rx=2, ry=2, fillColor=colors.HexColor('#B45309'), strokeColor=colors.HexColor('#92400E'), strokeWidth=0.6))
    d.add(String(86, y_leg + 1.8, "Con novedad", fontName="Helvetica", fontSize=6.0, fillColor=colors.HexColor('#334155')))

    # Texto aclaratorio
    d.add(String(145, y_leg + 1.8, "Valor bajo cada llanta: profundidad mínima (mm); en rojo si es menor o igual al límite de retiro.", fontName="Helvetica", fontSize=5.8, fillColor=colors.HexColor('#64748B')))

    return d


def crear_banner_superior(num_informe, fecha_emision, width=540):
    logo_drawing = Drawing(26, 26)
    logo_drawing.add(Rect(0, 0, 26, 26, rx=4, ry=4, fillColor=colors.HexColor('#2563EB'), strokeColor=None))
    logo_drawing.add(String(13, 7.5, "T", fontName="Helvetica-Bold", fontSize=15, fillColor=colors.white, textAnchor="middle"))

    styles = getSampleStyleSheet()
    style_tit = ParagraphStyle('BannTit', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=colors.white)
    style_sub = ParagraphStyle('BannSub', fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#94A3B8'))
    style_inf_num = ParagraphStyle('BannNum', fontName='Helvetica-Bold', fontSize=8.0, leading=10, textColor=colors.white, alignment=2)
    style_inf_fec = ParagraphStyle('BannFec', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#94A3B8'), alignment=2)

    col_izq = Table([
        [
            logo_drawing,
            [
                Paragraph("<b>TireCheck Pro</b>", style_tit),
                Paragraph("Informe de inspección de vehículo", style_sub)
            ]
        ]
    ], colWidths=[32, 280])
    col_izq.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    col_der = [
        Paragraph(f"<b>Informe N.º {num_informe}</b>", style_inf_num),
        Paragraph(f"Emitido: {fecha_emision}", style_inf_fec)
    ]

    banner = Table([
        [col_izq, col_der]
    ], colWidths=[320, 220])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B192C')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    return banner


def generar_pdf_estilo_base(placa, fecha=None):
    filas = database.obtener_datos_inspeccion_vehiculo(placa, fecha)
    if not filas:
        raise ValueError(f"No se encontraron registros de inspección para {placa}")

    primera = filas[0]
    cliente = primera.get('cliente', 'No Especificado')
    subcliente = primera.get('subcliente', 'General')
    operacion = primera.get('tipo_operacion', 'General')
    tipologia = primera.get('tipologia', 'Vehículo')
    km_actual = primera.get('kilometraje', 0)
    fecha_insp = primera.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    inspector = primera.get('usuario_registro', 'Inspector de Flota')

    df_insp = pd.DataFrame(filas)
    df_analisis = database.analizar_inspecciones_df(df_insp)
    limite_retiro = database.obtener_limite_retiro_cliente(cliente)

    def calc_pmin(r):
        v = [float(r.get(c, 0) or 0) for c in ['prof_ext', 'prof_cent', 'prof_int'] if float(r.get(c, 0) or 0) > 0]
        return min(v) if v else 0.0

    df_insp['p_min'] = df_insp.apply(calc_pmin, axis=1)

    total_auditadas = len(filas)
    # Total de posiciones esperadas según esquema
    esquema = database.obtener_esquema_tipologia(tipologia) or []
    posiciones_esquema = []
    for e in esquema:
        for p in e.get('posiciones', []):
            posiciones_esquema.append(p.get('pos'))
    total_posiciones = len(posiciones_esquema) if posiciones_esquema else total_auditadas

    # KPIs
    valid_pmins = df_insp[df_insp['p_min'] > 0]
    if not valid_pmins.empty:
        idx_min = valid_pmins['p_min'].idxmin()
        p_min_global = valid_pmins.loc[idx_min, 'p_min']
        pos_min_global = valid_pmins.loc[idx_min, 'posicion']
        p_prom_global = valid_pmins['p_min'].mean()
    else:
        p_min_global = 0.0
        pos_min_global = 1
        p_prom_global = 0.0

    # Detección detallada de alertas
    alertas_lista = []
    # 1. Cambios por límite de retiro
    for f in filas:
        p = f.get('posicion')
        p_m = calc_pmin(f)
        if 0 < p_m <= limite_retiro:
            alertas_lista.append({
                'tipo': 'Cambio',
                'tipo_color': '#DC2626',
                'posicion': str(p),
                'detalle': f"Retirar llanta en posición {p} (remanente {format_num_es(p_m)} mm <= {format_num_es(limite_retiro)} mm de límite).",
                'accion': 'Retirar la llanta y programar su cambio.'
            })

    # 2. Alineación y duales desde df_analisis si existe
    if not df_analisis.empty:
        r_an = df_analisis.iloc[0]
        if r_an.get('Plan_Alineacion') == 'SÍ':
            alertas_lista.append({
                'tipo': 'Alineación',
                'tipo_color': '#D97706',
                'posicion': '1 y 2',
                'detalle': str(r_an.get('Detalle_Alineacion', 'Diferencia excesiva entre directores.')),
                'accion': 'Alinear y balancear.'
            })
        if r_an.get('Plan_Dual_Mal_Apareado') == 'SÍ':
            alertas_lista.append({
                'tipo': 'Dual mal apareado',
                'tipo_color': '#D97706',
                'posicion': 'Duales',
                'detalle': str(r_an.get('Detalle_Dual', 'Diferencia milimétrica mayor a 2.0 mm en llantas duales.')),
                'accion': 'Rotar y aparear.'
            })

    # 3. Novedades registradas
    for f in filas:
        nov = str(f.get('novedades') or '').strip()
        if nov:
            alertas_lista.append({
                'tipo': 'Novedad mecánica',
                'tipo_color': '#D97706',
                'posicion': str(f.get('posicion')),
                'detalle': nov,
                'accion': 'Revisar componente y corregir condición.'
            })

    n_cambios = len([a for a in alertas_lista if a['tipo'] == 'Cambio'])
    n_ali = len([a for a in alertas_lista if a['tipo'] == 'Alineación'])
    n_duales = len([a for a in alertas_lista if a['tipo'] == 'Dual mal apareado'])
    total_alertas = len(alertas_lista)

    fecha_emision = datetime.now().strftime('%d/%m/%Y')
    num_informe = f"INF-{placa}-{datetime.now().strftime('%Y%m%d')}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    style_tit_doc = ParagraphStyle('DocTit', fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=2)
    style_sub_doc = ParagraphStyle('DocSub', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#64748B'), spaceAfter=8)
    style_sec_tit = ParagraphStyle('SecTit', fontName='Helvetica-Bold', fontSize=10.0, leading=13, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=4)
    style_kpi_num = ParagraphStyle('KpiNum', fontName='Helvetica-Bold', fontSize=13, leading=15, alignment=1)
    style_kpi_lbl = ParagraphStyle('KpiLbl', fontName='Helvetica', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748B'), alignment=1)
    style_cell_head = ParagraphStyle('CellH', fontName='Helvetica-Bold', fontSize=6.5, leading=8.5, textColor=colors.white, alignment=0)
    style_cell_body = ParagraphStyle('CellB', fontName='Helvetica', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#1E293B'), alignment=0)

    elements = []

    # =========================================================================
    # PÁGINA 1
    # =========================================================================
    # 1. Banner superior
    elements.append(crear_banner_superior(num_informe, fecha_emision))

    # 2. Título y Subtítulo
    elements.append(Paragraph("Informe de inspección de vehículo", style_tit_doc))
    elements.append(Paragraph(f"Placa {placa} · {tipologia} · Inspección del {fecha_insp}", style_sub_doc))

    # 3. Ficha Técnica General (3 cols x 3 filas)
    style_lbl_meta = ParagraphStyle('MetaLbl', fontName='Helvetica-Bold', fontSize=5.5, leading=7, textColor=colors.HexColor('#64748B'))
    style_val_meta = ParagraphStyle('MetaVal', fontName='Helvetica-Bold', fontSize=8.0, leading=10, textColor=colors.HexColor('#0F172A'))

    def celda_meta(lbl, val):
        return [
            Paragraph(lbl.upper(), style_lbl_meta),
            Spacer(1, 1),
            Paragraph(str(val), style_val_meta)
        ]

    data_meta = [
        [celda_meta("CLIENTE", cliente), celda_meta("SEDE", subcliente), celda_meta("OPERACIÓN", operacion)],
        [celda_meta("PLACA", placa), celda_meta("TIPOLOGÍA", tipologia), celda_meta("KILOMETRAJE", f"{km_actual:,.0f} km".replace(',', '.'))],
        [celda_meta("FECHA DE INSPECCIÓN", fecha_insp), celda_meta("INSPECTOR", inspector), celda_meta("LÍMITE DE RETIRO DEL CLIENTE", f"{format_num_es(limite_retiro)} mm")]
    ]
    t_meta = Table(data_meta, colWidths=[180, 180, 180])
    t_meta.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (-1,-1), colors.white)
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 5))

    # 4. Tarjetas KPI de Resumen
    col_kpi_alerta = '#DC2626' if total_alertas > 0 else '#16A34A'
    col_kpi_min = '#DC2626' if (0 < p_min_global <= limite_retiro) else '#0F172A'

    data_kpi = [
        [
            Paragraph(f"<font color='#0F172A'><b>{total_auditadas} de {total_posiciones}</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_kpi_min}'><b>{format_num_es(p_min_global)} mm</b></font>", style_kpi_num),
            Paragraph(f"<font color='#0F172A'><b>{format_num_es(p_prom_global)} mm</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_kpi_alerta}'><b>{total_alertas}</b></font>", style_kpi_num),
        ],
        [
            Paragraph("Posiciones inspeccionadas", style_kpi_lbl),
            Paragraph(f"Profundidad mínima (posición {pos_min_global})", style_kpi_lbl),
            Paragraph("Promedio de profundidades mínimas", style_kpi_lbl),
            Paragraph(f"Alertas: {n_cambios} cambio, {n_ali} alineación, {n_duales} duales", style_kpi_lbl),
        ]
    ]
    t_kpi = Table(data_kpi, colWidths=[135, 135, 135, 135])
    t_kpi.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t_kpi)
    elements.append(Spacer(1, 4))

    # 5. Diagnóstico y acciones recomendadas
    elements.append(Paragraph("Diagnóstico y acciones recomendadas", style_sec_tit))
    data_diag = [
        [
            Paragraph("<b>TIPO</b>", style_cell_head),
            Paragraph("<b>POSICIÓN</b>", style_cell_head),
            Paragraph("<b>DETALLE</b>", style_cell_head),
            Paragraph("<b>ACCIÓN</b>", style_cell_head)
        ]
    ]

    if alertas_lista:
        for a in alertas_lista[:4]:  # Hasta 4 para garantizar ajuste vertical en pág 1
            style_tipo = ParagraphStyle('TipoAlerta', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor(a['tipo_color']))
            data_diag.append([
                Paragraph(a['tipo'], style_tipo),
                Paragraph(a['posicion'], style_cell_body),
                Paragraph(a['detalle'], style_cell_body),
                Paragraph(a['accion'], style_cell_body)
            ])
    else:
        style_ok = ParagraphStyle('TipoOk', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor('#16A34A'))
        data_diag.append([
            Paragraph("Óptimo", style_ok),
            Paragraph("Todas", style_cell_body),
            Paragraph(f"Todas las llantas están sobre el límite de retiro ({format_num_es(limite_retiro)} mm) y sin novedades mecánicas activas.", style_cell_body),
            Paragraph("Operación normal y próxima inspección periódica.", style_cell_body)
        ])

    t_diag = Table(data_diag, colWidths=[95, 45, 250, 150])
    t_diag.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_diag)
    elements.append(Spacer(1, 4))

    # 6. Distribución por ejes (Chasis Vectorial)
    elements.append(Paragraph("Distribución por ejes", style_sec_tit))
    drawing_chasis = dibujar_diagrama_chasis_estilo_ejemplo(tipologia, filas, limite_retiro=limite_retiro, width=540)
    elements.append(drawing_chasis)
    elements.append(Spacer(1, 6))

    # 7. Pie de Página 1
    style_foot_izq = ParagraphStyle('FootIzq', fontName='Helvetica', fontSize=6.5, textColor=colors.HexColor('#94A3B8'))
    style_foot_der = ParagraphStyle('FootDer', fontName='Helvetica', fontSize=6.5, textColor=colors.HexColor('#64748B'), alignment=2)
    t_foot1 = Table([
        [
            Paragraph("TireCheck Pro · Sistema de Inspección y Gestión Técnica de Flotas", style_foot_izq),
            Paragraph("Página 1 de 2", style_foot_der)
        ]
    ], colWidths=[400, 140])
    t_foot1.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_foot1)

    # =========================================================================
    # PÁGINA 2
    # =========================================================================
    elements.append(PageBreak())

    # Banner superior pág 2
    elements.append(crear_banner_superior(num_informe, fecha_emision))

    # Título Detalle por llanta
    elements.append(Paragraph("Detalle por llanta", style_sec_tit))

    # Tabla Detalle por Llanta agrupada por Eje
    data_llantas = [
        [
            Paragraph("<b>POS.</b>", style_cell_head),
            Paragraph("<b>EJE / ROL</b>", style_cell_head),
            Paragraph("<b>MARCA / DISEÑO</b>", style_cell_head),
            Paragraph("<b>DIM.</b>", style_cell_head),
            Paragraph("<b>N.º INT.</b>", style_cell_head),
            Paragraph("<b>VIDA</b>", style_cell_head),
            Paragraph("<b>EXT</b>", style_cell_head),
            Paragraph("<b>CENT</b>", style_cell_head),
            Paragraph("<b>INT</b>", style_cell_head),
            Paragraph("<b>MÍN</b>", style_cell_head),
            Paragraph("<b>PSI</b>", style_cell_head),
            Paragraph("<b>ESTADO</b>", style_cell_head)
        ]
    ]

    # Agrupar llantas por eje según el esquema
    pos_to_eje = {}
    pos_to_rol_desc = {}
    if esquema:
        for e in esquema:
            e_num = e.get('eje', 1)
            t_lbl = 'Repuesto' if e_num == 99 or (e.get('tipo') or '').lower() == 'repuesto' else f"Eje {e_num} · {str(e.get('tipo', '')).capitalize()}"
            for p in e.get('posiciones', []):
                p_n = p.get('pos')
                pos_to_eje[p_n] = t_lbl
                lado = 'Izq.' if p.get('lado') == 'izq' else 'Der.' if p.get('lado') == 'der' else ''
                rol_str = normalizar_rol_txt(p.get('rol'))
                pos_to_rol_desc[p_n] = f"{lado} · {rol_str}".strip(' ·')

    # Identificar ejes únicos en orden
    ejes_orden = []
    for f in filas:
        p_num = int(f.get('posicion', 0))
        eje_lbl = pos_to_eje.get(p_num, 'Eje Principal')
        if eje_lbl not in ejes_orden:
            ejes_orden.append(eje_lbl)

    style_eje_subhead = ParagraphStyle('EjeSub', fontName='Helvetica-Bold', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#0F172A'))

    for eje_lbl in ejes_orden:
        # Fila de separación de Eje
        data_llantas.append([
            Paragraph(f"<b>{eje_lbl}</b>", style_eje_subhead),
            "", "", "", "", "", "", "", "", "", "", ""
        ])
        filas_eje = [f for f in filas if pos_to_eje.get(int(f.get('posicion', 0)), 'Eje Principal') == eje_lbl]
        for f in filas_eje:
            p_n = int(f.get('posicion', 0))
            p_ext = float(f.get('prof_ext') or 0)
            p_cen = float(f.get('prof_cent') or 0)
            p_int = float(f.get('prof_int') or 0)
            validas = [v for v in (p_ext, p_cen, p_int) if v > 0]
            p_min = min(validas) if validas else 0.0

            es_cambio = (p_min > 0 and p_min <= limite_retiro)
            novedad_texto = str(f.get('novedades') or '').strip()

            if es_cambio:
                estado_txt = "Cambio sugerido"
                col_est = '#DC2626'
            elif novedad_texto:
                estado_txt = "Con novedad"
                col_est = '#D97706'
            else:
                estado_txt = "Registrada"
                col_est = '#16A34A'

            st_pmin = ParagraphStyle('PMinCell', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor('#DC2626') if es_cambio else colors.HexColor('#0F172A'))
            st_estado = ParagraphStyle('EstCell', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor(col_est))

            marca_dis = f"{f.get('marca', '')} {f.get('diseno', '')}".strip() or '-'
            rol_lbl = pos_to_rol_desc.get(p_n, normalizar_rol_txt(f.get('rol', '')))

            data_llantas.append([
                Paragraph(f"<b>{p_n}</b>", style_cell_body),
                Paragraph(rol_lbl, style_cell_body),
                Paragraph(marca_dis, style_cell_body),
                Paragraph(str(f.get('dimension') or '-'), style_cell_body),
                Paragraph(str(f.get('numero_interno') or '-'), style_cell_body),
                Paragraph(str(f.get('vida') or 'Orig'), style_cell_body),
                Paragraph(format_num_es(p_ext), style_cell_body),
                Paragraph(format_num_es(p_cen), style_cell_body),
                Paragraph(format_num_es(p_int), style_cell_body),
                Paragraph(format_num_es(p_min), st_pmin),
                Paragraph(f"{float(f.get('psi') or 0):.0f}", style_cell_body),
                Paragraph(estado_txt, st_estado)
            ])

    # ColWidths suma 540
    # 22 + 55 + 115 + 68 + 42 + 45 + 26 + 26 + 26 + 28 + 25 + 62 = 540
    t_llantas = Table(data_llantas, colWidths=[22, 55, 115, 68, 42, 45, 26, 26, 26, 28, 25, 62])
    
    tstyle = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 2.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.2),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]
    # Aplicar SPAN y fondo en las filas de cabecera de eje
    row_idx = 0
    for row in data_llantas:
        if row[1] == "" and row[2] == "":
            tstyle.append(('SPAN', (0, row_idx), (-1, row_idx)))
            tstyle.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#F1F5F9')))
            tstyle.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 2.5))
            tstyle.append(('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 2.5))
        row_idx += 1

    t_llantas.setStyle(TableStyle(tstyle))
    elements.append(t_llantas)

    style_subnota = ParagraphStyle('SubNota', fontName='Helvetica', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#64748B'), spaceBefore=3, spaceAfter=4)
    elements.append(Paragraph("Profundidades en mm. PSI: presión registrada.", style_subnota))

    # Novedades registradas
    elements.append(Paragraph("Novedades registradas", style_sec_tit))
    filas_con_nov = [f for f in filas if str(f.get('novedades') or '').strip()]
    data_nov = [
        [
            Paragraph("<b>POS.</b>", style_cell_head),
            Paragraph("<b>NOVEDAD REGISTRADA</b>", style_cell_head)
        ]
    ]
    if filas_con_nov:
        for f in filas_con_nov:
            data_nov.append([
                Paragraph(str(f.get('posicion')), style_cell_body),
                Paragraph(str(f.get('novedades')).strip(), style_cell_body)
            ])
    else:
        data_nov.append([
            Paragraph("-", style_cell_body),
            Paragraph("No se registraron novedades o anomalías mecánicas en las llantas inspeccionadas.", style_cell_body)
        ])

    t_nov = Table(data_nov, colWidths=[40, 500])
    t_nov.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_nov)
    elements.append(Spacer(1, 4))

    # Observaciones del inspector
    elements.append(Paragraph("Observaciones del inspector", style_sec_tit))
    # Generar texto descriptivo inteligente
    obs_lines = []
    if n_cambios > 0:
        pos_cambios = [str(a['posicion']) for a in alertas_lista if a['tipo'] == 'Cambio']
        obs_lines.append(f"Se recomienda programar el retiro de la(s) llanta(s) en posición {', '.join(pos_cambios)} por encontrarse en o por debajo del límite de retiro ({format_num_es(limite_retiro)} mm).")
    if n_ali > 0:
        obs_lines.append("En el eje direccional se observa una diferencia de desgaste entre directores; se sugiere revisar alineación y balanceo preventivo.")
    if n_duales > 0:
        obs_lines.append("En los conjuntos duales se recomienda rotar o aparear llantas para evitar fatiga prematura por diferencia de radio rodante.")
    if not obs_lines:
        obs_lines.append(f"El vehículo opera en condiciones mecánicas y de desgaste óptimas. Todas las llantas registradas superan el límite de retiro ({format_num_es(limite_retiro)} mm) y mantienen presiones conformes.")

    style_par_obs = ParagraphStyle('ObsPar', fontName='Helvetica', fontSize=7.0, leading=9.5, textColor=colors.HexColor('#1E293B'))
    elements.append(Paragraph(" ".join(obs_lines), style_par_obs))
    elements.append(Spacer(1, 4))

    # Criterios de diagnóstico aplicados
    elements.append(Paragraph("Criterios de diagnóstico aplicados", style_sec_tit))
    criterios_html = f"""
    <b>Cambio de llanta:</b> la profundidad mínima de una llanta es menor o igual al límite de retiro configurado para el cliente ({format_num_es(limite_retiro)} mm).<br/>
    <b>Alineación:</b> diferencia de 2,0 mm o más entre la profundidad mínima de las llantas direccionales izquierda y derecha.<br/>
    <b>Dual mal apareado:</b> diferencia de 2,0 mm o más entre la profundidad mínima de la llanta interior y la exterior del mismo lado.<br/>
    La profundidad mínima de cada llanta es el menor de los tres valores medidos: exterior, centro e interior.
    """
    style_crit = ParagraphStyle('CritPar', fontName='Helvetica', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#475569'))
    elements.append(Paragraph(criterios_html, style_crit))
    elements.append(Spacer(1, 10))

    # Firmas
    style_sub_firma = ParagraphStyle('FirmSub', fontName='Helvetica', fontSize=7.0, leading=9.0, textColor=colors.HexColor('#0F172A'), alignment=1)
    firma_data = [
        [
            Paragraph(f"__________________________________________<br/><b>Inspector · {inspector}</b>", style_sub_firma),
            Paragraph("__________________________________________<br/><b>Responsable del cliente · Nombre y firma</b>", style_sub_firma)
        ]
    ]
    t_firmas = Table(firma_data, colWidths=[270, 270])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(KeepTogether(t_firmas))
    elements.append(Spacer(1, 6))

    # Pie de Página 2
    t_foot2 = Table([
        [
            Paragraph("TireCheck Pro · Sistema de Inspección y Gestión Técnica de Flotas", style_foot_izq),
            Paragraph("Página 2 de 2", style_foot_der)
        ]
    ], colWidths=[400, 140])
    t_foot2.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_foot2)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


if __name__ == '__main__':
    print("Probando generación de nuevo informe...")
    # Probar con TLK357 (Cabezote 6x4)
    pdf_tlk = generar_pdf_estilo_base('TLK357')
    with open('test_tlk357_nuevo.pdf', 'wb') as f:
        f.write(pdf_tlk)
    doc1 = pdfium.PdfDocument('test_tlk357_nuevo.pdf')
    doc1[0].render(scale=2.0).to_pil().save('c:/Users/crist/.gemini/antigravity-ide/brain/c6d723f3-0d84-4040-a969-80008634f91f/test_tlk357_p1.png')
    doc1[1].render(scale=2.0).to_pil().save('c:/Users/crist/.gemini/antigravity-ide/brain/c6d723f3-0d84-4040-a969-80008634f91f/test_tlk357_p2.png')
    print("Rendered TLK357!")

    # Probar con R54331 (Trailer con repuesto)
    pdf_r54 = generar_pdf_estilo_base('R54331')
    with open('test_r54331_repuesto.pdf', 'wb') as f:
        f.write(pdf_r54)
    doc2 = pdfium.PdfDocument('test_r54331_repuesto.pdf')
    doc2[0].render(scale=2.0).to_pil().save('c:/Users/crist/.gemini/antigravity-ide/brain/c6d723f3-0d84-4040-a969-80008634f91f/test_r54331_p1.png')
    doc2[1].render(scale=2.0).to_pil().save('c:/Users/crist/.gemini/antigravity-ide/brain/c6d723f3-0d84-4040-a969-80008634f91f/test_r54331_p2.png')
    print("Rendered R54331 con repuesto!")
