import io
import os
import time
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Group
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database

def normalizar_rol(rol):
    if not rol: return ''
    r = str(rol).upper().strip()
    if 'DIR' in r: return 'DIR'
    if 'EXT' in r: return 'EXT'
    if 'INT' in r: return 'INT'
    if 'REP' in r: return 'REP'
    if 'SEN' in r or 'LIB' in r: return 'SEN'
    return r[:3]

def dibujar_diagrama_chasis_reportlab(tipologia, filas, limite_retiro=3.0, width=540):
    esquema = database.obtener_esquema_tipologia(tipologia)
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

    num_ejes = len(ejes_rodantes)
    alto_eje = 38
    alto_header = 18
    alto_leyenda = 16
    alto_repuesto = 26 if ejes_repuesto else 0
    total_height = alto_header + (num_ejes * alto_eje) + alto_repuesto + alto_leyenda + 10

    d = Drawing(width, total_height)
    d.add(Rect(0, 0, width, total_height, rx=6, ry=6, fillColor=colors.HexColor('#F8FAFC'), strokeColor=colors.HexColor('#CBD5E1'), strokeWidth=0.75))

    curr_y = total_height - 13
    d.add(String(12, curr_y, "DIAGRAMA TÉCNICO DE CHASIS", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor('#1E293B')))
    d.add(String(width / 2, curr_y, "↑ FRENTE DEL VEHÍCULO", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#2563EB'), textAnchor="middle"))
    d.add(String(width - 55, curr_y, "DERECHA →", fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))
    d.add(String(55, curr_y, "← IZQUIERDA", fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

    curr_y -= 8
    d.add(Line(10, curr_y, width - 10, curr_y, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.75))

    w_llanta = 18
    h_llanta = 28
    cx_vehiculo = width / 2

    for idx, e in enumerate(ejes_rodantes):
        y_eje = curr_y - (idx * alto_eje) - 19
        eje_num = e.get('eje', idx + 1)
        tipo_lbl = str(e.get('tipo', '')).capitalize()
        if 'traccion' in tipo_lbl.lower(): tipo_lbl = 'Tracción'
        elif 'direccional' in tipo_lbl.lower(): tipo_lbl = 'Direccional'

        d.add(String(12, y_eje - 1, f"Eje {eje_num}", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#1E293B')))
        d.add(String(12, y_eje - 8, tipo_lbl, fontName="Helvetica", fontSize=6, fillColor=colors.HexColor('#64748B')))

        posiciones = e.get('posiciones', [])
        izq = [p for p in posiciones if p.get('lado') == 'izq']
        der = [p for p in posiciones if p.get('lado') == 'der']

        x_min_tubo = cx_vehiculo - 145 if (len(izq) > 1 or len(der) > 1) else cx_vehiculo - 110
        x_max_tubo = cx_vehiculo + 145 if (len(izq) > 1 or len(der) > 1) else cx_vehiculo + 110
        d.add(Line(x_min_tubo, y_eje, x_max_tubo, y_eje, strokeColor=colors.HexColor('#94A3B8'), strokeWidth=1.8))
        d.add(Rect(cx_vehiculo - 8, y_eje - 4, 16, 8, rx=2, ry=2, fillColor=colors.HexColor('#CBD5E1'), strokeColor=colors.HexColor('#64748B'), strokeWidth=0.6))
        d.add(Circle(cx_vehiculo, y_eje, 2, fillColor=colors.HexColor('#475569'), strokeColor=colors.HexColor('#334155'), strokeWidth=0.5))

        coords_izq = []
        if len(izq) == 1:
            coords_izq = [(cx_vehiculo - 110, izq[0])]
        elif len(izq) == 2:
            ext_p = next((p for p in izq if 'ext' in str(p.get('rol', '')).lower()), izq[0])
            int_p = next((p for p in izq if p != ext_p), izq[1])
            coords_izq = [(cx_vehiculo - 145, ext_p), (cx_vehiculo - 118, int_p)]

        coords_der = []
        if len(der) == 1:
            coords_der = [(cx_vehiculo + 110, der[0])]
        elif len(der) == 2:
            int_p = next((p for p in der if 'int' in str(p.get('rol', '')).lower()), der[0])
            ext_p = next((p for p in der if p != int_p), der[1])
            coords_der = [(cx_vehiculo + 118, int_p), (cx_vehiculo + 145, ext_p)]

        for wx, p in (coords_izq + coords_der):
            pos_num = p.get('pos')
            rol_txt = normalizar_rol(p.get('rol'))
            info = pos_map.get(pos_num, {})
            registrada = info.get('registrada', False)
            p_min = info.get('p_min', 0.0)
            psi = info.get('psi', 0.0)
            novedades = info.get('novedades', '')

            if not registrada:
                fill_tire = colors.HexColor('#E2E8F0')
                stroke_tire = colors.HexColor('#94A3B8')
                txt_color = colors.HexColor('#64748B')
            elif p_min > 0 and p_min <= limite_retiro:
                fill_tire = colors.HexColor('#FEE2E2')
                stroke_tire = colors.HexColor('#DC2626')
                txt_color = colors.HexColor('#991B1B')
            elif novedades:
                fill_tire = colors.HexColor('#FEF3C7')
                stroke_tire = colors.HexColor('#D97706')
                txt_color = colors.HexColor('#92400E')
            elif p_min > 0 and p_min <= limite_retiro + 2.0:
                fill_tire = colors.HexColor('#FFEDD5')
                stroke_tire = colors.HexColor('#EA580C')
                txt_color = colors.HexColor('#9A3412')
            else:
                fill_tire = colors.HexColor('#DCFCE7')
                stroke_tire = colors.HexColor('#16A34A')
                txt_color = colors.HexColor('#14532D')

            x_box = wx - (w_llanta / 2)
            y_box = y_eje - (h_llanta / 2)
            d.add(Rect(x_box, y_box, w_llanta, h_llanta, rx=3, ry=3, fillColor=fill_tire, strokeColor=stroke_tire, strokeWidth=1))
            d.add(Line(x_box + 5, y_box + 2, x_box + 5, y_box + h_llanta - 2, strokeColor=stroke_tire, strokeWidth=0.5, strokeOpacity=0.5))
            d.add(Line(x_box + 13, y_box + 2, x_box + 13, y_box + h_llanta - 2, strokeColor=stroke_tire, strokeWidth=0.5, strokeOpacity=0.5))

            d.add(String(wx, y_box + h_llanta - 7, f"P{pos_num}", fontName="Helvetica-Bold", fontSize=6.5, fillColor=txt_color, textAnchor="middle"))
            if registrada:
                d.add(String(wx, y_box + h_llanta - 15, f"{p_min:.1f}m", fontName="Helvetica-Bold", fontSize=6, fillColor=txt_color, textAnchor="middle"))
                d.add(String(wx, y_box + 2.5, f"{psi:.0f}p", fontName="Helvetica", fontSize=5.5, fillColor=txt_color, textAnchor="middle"))
            else:
                d.add(String(wx, y_box + 8, "PEND", fontName="Helvetica", fontSize=5, fillColor=txt_color, textAnchor="middle"))

            d.add(String(wx, y_box - 6, rol_txt, fontName="Helvetica-Bold", fontSize=5.5, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

    y_base_rep = 20
    if ejes_repuesto:
        p_rep = ejes_repuesto[0].get('posiciones', [{}])[0].get('pos', 99)
        info_rep = pos_map.get(p_rep, {})
        reg_rep = info_rep.get('registrada', False)
        p_min_rep = info_rep.get('p_min', 0.0)
        d.add(String(cx_vehiculo - 60, y_base_rep + 8, "Soporte Repuesto:", fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor('#475569')))
        col_rep = colors.HexColor('#DCFCE7') if (reg_rep and p_min_rep > limite_retiro) else colors.HexColor('#FEE2E2') if reg_rep else colors.HexColor('#E2E8F0')
        str_rep = colors.HexColor('#16A34A') if (reg_rep and p_min_rep > limite_retiro) else colors.HexColor('#DC2626') if reg_rep else colors.HexColor('#94A3B8')
        d.add(Rect(cx_vehiculo + 15, y_base_rep, 20, 18, rx=2, ry=2, fillColor=col_rep, strokeColor=str_rep, strokeWidth=0.8))
        d.add(String(cx_vehiculo + 25, y_base_rep + 10, f"P{p_rep}", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#1E293B'), textAnchor="middle"))
        if reg_rep:
            d.add(String(cx_vehiculo + 25, y_base_rep + 3, f"{p_min_rep:.1f}m", fontName="Helvetica-Bold", fontSize=5.5, fillColor=colors.HexColor('#1E293B'), textAnchor="middle"))
        y_base_rep += 16

    d.add(Line(10, 14, width - 10, 14, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.5))
    leg_x = 20
    d.add(Rect(leg_x, 4, 7, 7, rx=1.5, ry=1.5, fillColor=colors.HexColor('#DCFCE7'), strokeColor=colors.HexColor('#16A34A'), strokeWidth=0.7))
    d.add(String(leg_x + 10, 5.5, f"Óptima (> {limite_retiro + 2.0:.1f} mm)", fontName="Helvetica", fontSize=6, fillColor=colors.HexColor('#334155')))
    
    leg_x += 110
    d.add(Rect(leg_x, 4, 7, 7, rx=1.5, ry=1.5, fillColor=colors.HexColor('#FFEDD5'), strokeColor=colors.HexColor('#EA580C'), strokeWidth=0.7))
    d.add(String(leg_x + 10, 5.5, f"Próximo Retiro ({limite_retiro:.1f} - {limite_retiro + 2.0:.1f} mm)", fontName="Helvetica", fontSize=6, fillColor=colors.HexColor('#334155')))
    
    leg_x += 140
    d.add(Rect(leg_x, 4, 7, 7, rx=1.5, ry=1.5, fillColor=colors.HexColor('#FEE2E2'), strokeColor=colors.HexColor('#DC2626'), strokeWidth=0.7))
    d.add(String(leg_x + 10, 5.5, f"Retiro / Cambio (<= {limite_retiro:.1f} mm)", fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor('#991B1B')))

    leg_x += 130
    d.add(Rect(leg_x, 4, 7, 7, rx=1.5, ry=1.5, fillColor=colors.HexColor('#FEF3C7'), strokeColor=colors.HexColor('#D97706'), strokeWidth=0.7))
    d.add(String(leg_x + 10, 5.5, "Alerta / Novedad", fontName="Helvetica", fontSize=6, fillColor=colors.HexColor('#92400E')))

    return d

def generar_pdf_profesional(placa, fecha=None):
    filas = database.obtener_datos_inspeccion_vehiculo(placa, fecha)
    if not filas:
        raise ValueError(f"No hay inspecciones para {placa}")

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

    # Cálculos estadísticos
    total_llantas = len(filas)
    def calc_pmin(r):
        v = [float(r.get(c, 0) or 0) for c in ['prof_ext', 'prof_cent', 'prof_int'] if float(r.get(c, 0) or 0) > 0]
        return min(v) if v else 0.0

    df_insp['p_min'] = df_insp.apply(calc_pmin, axis=1)
    llantas_retiro = len(df_insp[(df_insp['p_min'] > 0) & (df_insp['p_min'] <= limite_retiro)])
    llantas_proximo = len(df_insp[(df_insp['p_min'] > limite_retiro) & (df_insp['p_min'] <= limite_retiro + 2.0)])
    llantas_optimas = total_llantas - llantas_retiro - llantas_proximo
    llantas_novedad = len([f for f in filas if str(f.get('novedades', '')).strip()])
    prom_psi = df_insp['psi'].mean() if 'psi' in df_insp.columns else 100.0

    plan_cambio = "NO"
    plan_alineacion = "NO"
    plan_dual = "NO"
    plan_rot_irregular = "NO"
    plan_rot_escalonado = "NO"
    plan_calibracion_psi = "NO"
    det_cambio = "OK"
    det_alineacion = "OK"
    det_dual = "OK"
    det_rot_irregular = "OK"
    det_rot_escalonado = "OK"
    det_calibracion_psi = "OK"
    recom_dual = "OK"

    if not df_analisis.empty:
        r_an = df_analisis.iloc[0]
        plan_cambio = r_an.get('Plan_Cambio_Llanta', 'NO')
        plan_alineacion = r_an.get('Plan_Alineacion', 'NO')
        plan_dual = r_an.get('Plan_Dual_Mal_Apareado', 'NO')
        plan_rot_irregular = r_an.get('Plan_Rotacion_Irregular', 'NO')
        plan_rot_escalonado = r_an.get('Plan_Rotacion_Escalonado', 'NO')
        plan_calibracion_psi = r_an.get('Plan_Calibracion_PSI', 'NO')
        det_cambio = r_an.get('Detalle_Cambio', 'OK')
        det_alineacion = r_an.get('Detalle_Alineacion', 'OK')
        det_dual = r_an.get('Detalle_Dual', 'OK')
        det_rot_irregular = r_an.get('Detalle_Rotacion_Irregular', 'OK')
        det_rot_escalonado = r_an.get('Detalle_Rotacion_Escalonado', 'OK')
        det_calibracion_psi = r_an.get('Detalle_Calibracion_PSI', 'OK')
        recom_dual = r_an.get('Recomendaciones_Dual', 'OK')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=32,
        leftMargin=32,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    style_titulo = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=colors.HexColor('#0F172A'))
    style_subtitulo = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#475569'))
    style_seccion = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#1E3A8A'), spaceBefore=6, spaceAfter=3)
    style_cell_header = ParagraphStyle('CellHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white, alignment=1)
    style_cell_body = ParagraphStyle('CellBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#1E293B'), alignment=1)
    style_cell_alert = ParagraphStyle('CellAlert', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#DC2626'), alignment=1)
    style_kpi_num = ParagraphStyle('KpiNum', fontName='Helvetica-Bold', fontSize=13, leading=15, alignment=1)
    style_kpi_lbl = ParagraphStyle('KpiLbl', fontName='Helvetica', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748B'), alignment=1)

    elements = []

    # 1. ENCABEZADO INSTITUCIONAL
    enc_data = [
        [
            Paragraph("<b>TIRECHECK PRO</b><br/><font size=7 color='#64748b'>Sistema de Inspección & Gestión Técnica de Flotas</font>", style_titulo),
            Paragraph(f"<b>INFORME TÉCNICO Y PLAN DE MANTENIMIENTO</b><br/>Fecha: <b>{fecha_insp}</b> | Inspector: <b>{inspector}</b>", style_subtitulo)
        ]
    ]
    t_enc = Table(enc_data, colWidths=[274, 274])
    t_enc.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_enc)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceBefore=2, spaceAfter=5))

    # 2. FICHA TÉCNICA DEL VEHÍCULO
    info_data = [
        [
            Paragraph(f"<b>Cliente:</b> {cliente}", style_subtitulo),
            Paragraph(f"<b>Vehículo / Placa:</b> <font size=11 color='#1E3A8A'><b>{placa}</b></font>", style_subtitulo)
        ],
        [
            Paragraph(f"<b>Sede / Subcliente:</b> {subcliente} | <b>Operación:</b> {operacion}", style_subtitulo),
            Paragraph(f"<b>Tipología:</b> {tipologia} | <b>Km Odómetro:</b> {km_actual:,.0f} km", style_subtitulo)
        ]
    ]
    t_info = Table(info_data, colWidths=[274, 274])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 4))

    # 3. TARJETAS KPI DE RESUMEN EJECUTIVO (4 Columnas)
    col_cambio_num = '#DC2626' if llantas_retiro > 0 else '#16A34A'
    col_nov_num = '#D97706' if llantas_novedad > 0 else '#16A34A'
    kpi_data = [
        [
            Paragraph(f"<font color='#2563EB'><b>{total_llantas}</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_cambio_num}'><b>{llantas_retiro}</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_nov_num}'><b>{llantas_novedad}</b></font>", style_kpi_num),
            Paragraph(f"<font color='#0F172A'><b>{prom_psi:.0f}</b></font><font size=7 color='#64748B'> PSI</font>", style_kpi_num),
        ],
        [
            Paragraph("Llantas Inspeccionadas", style_kpi_lbl),
            Paragraph(f"Llantas Límite Retiro (<= {limite_retiro:.1f}mm)", style_kpi_lbl),
            Paragraph("Alertas / Novedades", style_kpi_lbl),
            Paragraph("Presión Promedio Calibrada", style_kpi_lbl),
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[137, 137, 137, 137])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFFFF')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t_kpi)
    elements.append(Spacer(1, 5))

    # 4. DIAGRAMA DE CHASIS VECTORIAL
    elements.append(Paragraph("1. Diagrama de Distribución de Ejes y Estado de Desgaste", style_seccion))
    drawing_chasis = dibujar_diagrama_chasis_reportlab(tipologia, filas, limite_retiro=limite_retiro, width=548)
    elements.append(drawing_chasis)
    elements.append(Spacer(1, 5))

    # 5. DIAGNÓSTICO TÉCNICO Y PLANES DE ACCIÓN INMEDIATOS
    elements.append(Paragraph("2. Diagnóstico Técnico y Planes de Acción Inmediatos", style_seccion))
    color_cambio = colors.HexColor('#FEE2E2') if plan_cambio == "SÍ" else colors.HexColor('#F0FDF4')
    color_ali = colors.HexColor('#FEF3C7') if plan_alineacion == "SÍ" else colors.HexColor('#F0FDF4')
    color_dual = colors.HexColor('#FFEDD5') if plan_dual == "SÍ" else colors.HexColor('#F0FDF4')
    color_rot_irr = colors.HexColor('#FEF3C7') if plan_rot_irregular == "SÍ" else colors.HexColor('#F0FDF4')
    color_rot_esc = colors.HexColor('#FFEDD5') if plan_rot_escalonado == "SÍ" else colors.HexColor('#F0FDF4')
    color_psi = colors.HexColor('#FEE2E2') if plan_calibracion_psi == "SÍ" else colors.HexColor('#F0FDF4')

    diag_data = [
        [
            Paragraph("<b>PLAN / ACCIÓN REQUERIDA</b>", style_cell_header),
            Paragraph("<b>ESTADO</b>", style_cell_header),
            Paragraph("<b>DETALLE TÉCNICO Y RECOMENDACIÓN OPERATIVA</b>", style_cell_header)
        ],
        [
            Paragraph("<b>Sugerencia Retiro / Cambio de Llanta</b>", style_cell_body),
            Paragraph(f"<b>{plan_cambio}</b>", style_cell_alert if plan_cambio == "SÍ" else style_cell_body),
            Paragraph(f"Límite de retiro: {limite_retiro:.1f} mm. {det_cambio}", style_cell_body)
        ],
        [
            Paragraph("<b>Plan Alineación Direccional</b>", style_cell_body),
            Paragraph(f"<b>{plan_alineacion}</b>", style_cell_alert if plan_alineacion == "SÍ" else style_cell_body),
            Paragraph(f"{det_alineacion}", style_cell_body)
        ],
        [
            Paragraph("<b>Plan Dual Mal Apareado</b>", style_cell_body),
            Paragraph(f"<b>{plan_dual}</b>", style_cell_alert if plan_dual == "SÍ" else style_cell_body),
            Paragraph(f"{det_dual}" + (f"<br/><font color='#b45309'><b>💡 RECOMENDACIÓN DUAL:</b> {recom_dual}</font>" if recom_dual != "OK" else ""), style_cell_body)
        ],
        [
            Paragraph("<b>Rotación por Desgaste Irregular</b>", style_cell_body),
            Paragraph(f"<b>{plan_rot_irregular}</b>", style_cell_alert if plan_rot_irregular == "SÍ" else style_cell_body),
            Paragraph(f"{det_rot_irregular}", style_cell_body)
        ],
        [
            Paragraph("<b>Rotación por Desgaste Escalonado</b>", style_cell_body),
            Paragraph(f"<b>{plan_rot_escalonado}</b>", style_cell_alert if plan_rot_escalonado == "SÍ" else style_cell_body),
            Paragraph(f"{det_rot_escalonado}", style_cell_body)
        ],
        [
            Paragraph("<b>Calibración de Presión de Aire</b>", style_cell_body),
            Paragraph(f"<b>{plan_calibracion_psi}</b>", style_cell_alert if plan_calibracion_psi == "SÍ" else style_cell_body),
            Paragraph(f"{det_calibracion_psi}", style_cell_body)
        ]
    ]

    t_diag = Table(diag_data, colWidths=[170, 50, 328])
    t_diag.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BACKGROUND', (0,1), (-1,1), color_cambio),
        ('BACKGROUND', (0,2), (-1,2), color_ali),
        ('BACKGROUND', (0,3), (-1,3), color_dual),
        ('BACKGROUND', (0,4), (-1,4), color_rot_irr),
        ('BACKGROUND', (0,5), (-1,5), color_rot_esc),
        ('BACKGROUND', (0,6), (-1,6), color_psi),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_diag)

    # SALTO DE PÁGINA LIMPIO PARA EL DETALLE COMPLETO
    elements.append(PageBreak())

    # 6. PÁGINA 2: TABLA DETALLADA DE TODAS LAS LLANTAS
    elements.append(Paragraph(f"3. Detalle Técnico de Mediciones por Posición ({len(filas)} Llantas Registradas)", style_seccion))

    tabla_data = [
        [
            Paragraph("Pos", style_cell_header),
            Paragraph("No. Ficha", style_cell_header),
            Paragraph("Marca / Diseño", style_cell_header),
            Paragraph("Dimensión", style_cell_header),
            Paragraph("Condición", style_cell_header),
            Paragraph("Prof (Ext - Cent - Int)", style_cell_header),
            Paragraph("P. Mín", style_cell_header),
            Paragraph("PSI", style_cell_header),
            Paragraph("Diagnóstico / Novedad", style_cell_header)
        ]
    ]

    for f in filas:
        p_ext = float(f.get('prof_ext') or 0)
        p_cen = float(f.get('prof_cent') or 0)
        p_int = float(f.get('prof_int') or 0)
        validas = [p for p in (p_ext, p_cen, p_int) if p > 0]
        p_min = min(validas) if validas else 0.0

        es_cambio = (p_min > 0 and p_min <= limite_retiro)
        marca_dis = f"{f.get('marca', '')} {f.get('diseno', '')}".strip() or '-'
        novedad_texto = f.get('novedades', '').strip()
        obs = novedad_texto or ('CAMBIO SUGERIDO' if es_cambio else 'ÓPTIMA (OK)')

        st_pmin = style_cell_alert if es_cambio else style_cell_body
        st_obs = style_cell_alert if (es_cambio or novedad_texto) else style_cell_body

        tabla_data.append([
            Paragraph(f"<b>P{f.get('posicion', '')}</b>", style_cell_body),
            Paragraph(str(f.get('numero_interno') or '-'), style_cell_body),
            Paragraph(marca_dis, style_cell_body),
            Paragraph(str(f.get('dimension') or '-'), style_cell_body),
            Paragraph(str(f.get('vida') or 'Orig'), style_cell_body),
            Paragraph(f"{p_ext:.1f} / {p_cen:.1f} / {p_int:.1f} mm", style_cell_body),
            Paragraph(f"<b>{p_min:.1f} mm</b>", st_pmin),
            Paragraph(f"<b>{f.get('psi', ''):.0f}</b>", style_cell_body),
            Paragraph(obs, st_obs)
        ])

    t_llantas = Table(tabla_data, colWidths=[26, 52, 105, 75, 45, 95, 42, 30, 78])
    t_llantas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_llantas)
    elements.append(Spacer(1, 15))

    # 7. PIE DE PÁGINA Y FIRMAS
    firma_data = [
        [
            Paragraph("__________________________________________<br/><b>Firma del Inspector / Auditor Técnico</b><br/><font size=7 color='#64748b'>Certifico que las mediciones corresponden al vehículo</font>", style_subtitulo),
            Paragraph("__________________________________________<br/><b>Recibido a Conformidad por el Cliente / Operador</b><br/><font size=7 color='#64748b'>Constancia de entrega del plan de mantenimiento</font>", style_subtitulo)
        ]
    ]
    t_firmas = Table(firma_data, colWidths=[274, 274])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(KeepTogether(t_firmas))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

if __name__ == '__main__':
    pdf_b = generar_pdf_profesional('FFF123')
    out_pdf = 'nuevo_informe_profesional.pdf'
    with open(out_pdf, 'wb') as f:
        f.write(pdf_b)
    print(f'PDF generado exitosamente: {out_pdf} ({len(pdf_b)} bytes)')
