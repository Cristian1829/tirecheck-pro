import html
import io
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Polygon
import database
from fotos_informe import seccion_fotos
import diagrama_chasis_pdf as dg

BOGOTA_TZ = ZoneInfo("America/Bogota")

def ahora_bogota():
    return datetime.now(BOGOTA_TZ)

def es_novedad_alerta(texto: str) -> bool:
    """
    Retorna False si el texto está vacío o coincide con observaciones benignas
    o estados normales ('ok', 'normal', 'desgaste normal y parejo').
    """
    if not texto or not isinstance(texto, str):
        return False
    limpio = " ".join(texto.strip().lower().split()).rstrip(".;,")
    if not limpio:
        return False
    frases_benignas = {
        'ok', 'normal', 'sin novedad', 'sin novedades', 'ninguna', 'ninguno',
        'buen estado', 'desgaste normal', 'desgaste normal y parejo', 'desgaste parejo',
        'optimo', 'óptimo', 'en buen estado', 'bien', 'sin problema', 'sin problemas'
    }
    return limpio not in frases_benignas

def formatear_fecha_ddmmyyyy(f_str):
    if not f_str:
        return ""
    try:
        partes = str(f_str).split("T")[0].split("-")
        if len(partes) == 3 and len(partes[0]) == 4:
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
    except Exception:
        pass
    return str(f_str)

def format_num_es(val, decimals=1):
    if val is None:
        return '—'
    try:
        return f"{float(val):.{decimals}f}".replace('.', ',')
    except (ValueError, TypeError):
        return str(val)

def normalizar_rol_pdf(rol):
    return dg._rol(rol)

def dibujar_diagrama_chasis_reportlab(tipologia, filas, limite_retiro=3.0, width=540):
    try:
        esquema = database.obtener_esquema_tipologia(tipologia)
    except Exception:
        esquema = None
    if not esquema:
        return Spacer(1, 5)
    return dg.dibujar_diagrama_chasis(esquema, filas, limite_retiro, width)

BANNER_IMG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "banner_tireanalyze_hd.png")
if not os.path.exists(BANNER_IMG_PATH):
    BANNER_IMG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banner_tireanalyze_hd.png")

class NumberedCanvas(canvas.Canvas):
    _num_informe = ""
    _fecha_emision = ""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self._draw_header()
            self._draw_footer(n)
            super().showPage()
        super().save()

    def _draw_header(self):
        self.saveState()
        x = 36
        y_top = 780
        w = 540
        h_banner = 42
        h_sub = 14
        h_total = h_banner + h_sub
        y_banner = y_top - h_banner
        y_sub = y_banner - h_sub

        # Fondo del contenedor
        self.setFillColor(colors.HexColor('#0B192C'))
        self.roundRect(x, y_sub, w, h_total, 3, fill=1, stroke=0)

        # Imagen oficial HD de TireAnalyze Pro
        if os.path.exists(BANNER_IMG_PATH):
            self.drawImage(BANNER_IMG_PATH, x, y_banner, width=w, height=h_banner, preserveAspectRatio=False, mask='auto')

        # Sub-barra inferior integrada con datos de informe
        self.setFillColor(colors.HexColor('#060D1A'))
        self.roundRect(x, y_sub, w, h_sub, 0, fill=1, stroke=0)

        # Línea divisoria cian sutil
        self.setStrokeColor(colors.HexColor('#1E3A8A'))
        self.setLineWidth(0.5)
        self.line(x, y_banner, x + w, y_banner)

        # Título técnico en cian
        self.setFillColor(colors.HexColor('#38BDF8'))
        self.setFont("Helvetica-Bold", 6.8)
        self.drawString(x + 10, y_sub + 4, "INFORME TÉCNICO DE INSPECCIÓN Y GESTIÓN DE FLOTA")

        num_inf = getattr(self, '_num_informe', '')
        fec_em = getattr(self, '_fecha_emision', '')
        info_der = []
        if num_inf:
            info_der.append(f"Informe N.º {num_inf}")
        if fec_em:
            info_der.append(f"Emitido: {fec_em}")

        if info_der:
            self.setFillColor(colors.white)
            self.setFont("Helvetica", 6.8)
            self.drawRightString(x + w - 10, y_sub + 4, "   ·   ".join(info_der))

        self.restoreState()

    def _draw_footer(self, n):
        self.saveState()
        self.setStrokeColor(colors.HexColor('#E2E8F0'))
        self.setLineWidth(0.5)
        self.line(36, 26, 576, 26)

        self.setFont("Helvetica", 6.5)
        self.setFillColor(colors.HexColor('#94A3B8'))
        self.drawString(36, 14, "TireAnalyze Pro · Sistema Integral de Inspección y Diagnóstico Técnico de Llantas")

        self.setFillColor(colors.HexColor('#64748B'))
        self.drawRightString(576, 14, f"Página {self._pageNumber} de {n}")
        self.restoreState()

class ConsolidadoNumberedCanvas(canvas.Canvas):
    _fecha = ""
    _cliente = ""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self._draw_header()
            self._draw_footer(n)
            super().showPage()
        super().save()

    def _draw_header(self):
        self.saveState()
        x = 36
        y_top = 780
        w = 540
        h_banner = 42
        h_sub = 14
        h_total = h_banner + h_sub
        y_banner = y_top - h_banner
        y_sub = y_banner - h_sub

        self.setFillColor(colors.HexColor('#0B192C'))
        self.roundRect(x, y_sub, w, h_total, 3, fill=1, stroke=0)

        if os.path.exists(BANNER_IMG_PATH):
            self.drawImage(BANNER_IMG_PATH, x, y_banner, width=w, height=h_banner, preserveAspectRatio=False, mask='auto')

        self.setFillColor(colors.HexColor('#060D1A'))
        self.roundRect(x, y_sub, w, h_sub, 0, fill=1, stroke=0)

        self.setStrokeColor(colors.HexColor('#1E3A8A'))
        self.setLineWidth(0.5)
        self.line(x, y_banner, x + w, y_banner)

        self.setFillColor(colors.HexColor('#38BDF8'))
        self.setFont("Helvetica-Bold", 6.8)
        self.drawString(x + 10, y_sub + 4, "INFORME EJECUTIVO & DIAGNÓSTICO CONSOLIDADO DE FLOTA")

        fec_txt = getattr(self, '_fecha', '') or 'Histórico General'
        ahora_txt = ahora_bogota().strftime('%d/%m/%Y %H:%M')
        self.setFillColor(colors.white)
        self.setFont("Helvetica", 6.8)
        self.drawRightString(x + w - 10, y_sub + 4, f"Corte: {fec_txt}   ·   Generado: {ahora_txt}")

        self.restoreState()

    def _draw_footer(self, n):
        self.saveState()
        self.setStrokeColor(colors.HexColor('#E2E8F0'))
        self.setLineWidth(0.5)
        self.line(36, 26, 576, 26)

        self.setFont("Helvetica", 6.5)
        self.setFillColor(colors.HexColor('#94A3B8'))
        self.drawString(36, 14, "TireAnalyze Pro · Suite Integral de Diagnóstico y Gestión de Flotas")

        self.setFillColor(colors.HexColor('#64748B'))
        self.drawRightString(576, 14, f"Página {self._pageNumber} de {n}")
        self.restoreState()

def obtener_canvas_reporte_vehiculo(num_informe, fecha_emision):
    class ReporteNumberedCanvas(NumberedCanvas):
        _num_informe = num_informe
        _fecha_emision = fecha_emision
    return ReporteNumberedCanvas

def obtener_canvas_consolidado_flota(fecha="", cliente=""):
    class ReporteConsolidadoCanvas(ConsolidadoNumberedCanvas):
        _fecha = fecha
        _cliente = cliente
    return ReporteConsolidadoCanvas

def crear_banner_superior_reporte(num_informe, fecha_emision, width=540):
    styles = getSampleStyleSheet()
    style_inf_num = ParagraphStyle('BannNum', fontName='Helvetica-Bold', fontSize=8.0, leading=10, textColor=colors.white, alignment=2)
    style_inf_fec = ParagraphStyle('BannFec', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#94A3B8'), alignment=2)

    col_der = [
        Paragraph(f"<b>Informe N.º {num_informe}</b>", style_inf_num),
        Paragraph(f"Emitido: {fecha_emision}", style_inf_fec)
    ]

    banner = Table([
        ["", col_der]
    ], colWidths=[width - 220, 220])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B192C')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    return banner

def resolver_fecha_informe(placa, fecha=None):
    if fecha and str(fecha).strip():
        return str(fecha).strip()
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(fecha) FROM inspecciones WHERE UPPER(TRIM(placa)) = UPPER(TRIM(?))", (placa,))
        row = cursor.fetchone()
        if row and row[0]:
            return str(row[0])
    return None

def construir_datos_informe(placa, fecha=None) -> dict:
    placa_limpia = str(placa or '').strip().upper()
    fecha_resuelta = resolver_fecha_informe(placa_limpia, fecha)
    filas = database.obtener_datos_inspeccion_vehiculo(placa_limpia, fecha_resuelta)
    if not filas and fecha:
        # Intento sin fecha de rescate
        filas = database.obtener_datos_inspeccion_vehiculo(placa_limpia, None)
    if not filas:
        raise ValueError(f"No se encontraron registros de inspección para el vehículo con placa {placa_limpia}")

    primera = filas[0]
    cliente_raw = str(primera.get('cliente') or '').strip()
    cliente = 'General' if not cliente_raw or cliente_raw.upper() in ('NAN', 'NONE', 'NO ESPECIFICADO') else cliente_raw

    subcliente_raw = str(primera.get('subcliente') or '').strip()
    subcliente = 'General' if not subcliente_raw or subcliente_raw.upper() in ('NAN', 'NONE') else subcliente_raw

    operacion_raw = str(primera.get('tipo_operacion') or '').strip()
    operacion = 'General' if not operacion_raw or operacion_raw.upper() in ('NAN', 'NONE') else operacion_raw

    tipologia_raw = str(primera.get('tipologia') or '').strip()
    tipologia = 'Estándar' if not tipologia_raw or tipologia_raw.upper() in ('NAN', 'NONE') else tipologia_raw

    km_actual = float(primera.get('kilometraje') or 0)
    fecha_insp = primera.get('fecha', ahora_bogota().strftime('%Y-%m-%d'))
    fecha_insp_fmt = formatear_fecha_ddmmyyyy(fecha_insp)

    if km_actual <= 0 or pd.isna(km_actual):
        km_str = "No registrado"
    else:
        km_str = f"{km_actual:,.0f} km".replace(',', '.')

    inspector_usr = str(primera.get('usuario_registro') or 'admin').strip()
    try:
        usr_info = database.obtener_usuario_por_username(inspector_usr)
        inspector_nombre = usr_info.get('nombre_completo') if (usr_info and usr_info.get('nombre_completo')) else inspector_usr
    except Exception:
        inspector_nombre = inspector_usr

    limite_retiro = database.obtener_limite_retiro_cliente(cliente) or 3.0

    # Usar dg.profundidad_minima como ÚNICA definición de profundidad mínima
    for f in filas:
        f['p_min'] = dg.profundidad_minima(f)

    df_insp = pd.DataFrame(filas)
    df_analisis = database.analizar_inspecciones_df(df_insp)

    try:
        esquema = database.obtener_esquema_tipologia(tipologia) or []
    except Exception:
        esquema = []

    posiciones_esquema = []
    for e in esquema:
        for p in e.get('posiciones', []):
            posiciones_esquema.append(p.get('pos'))
    total_posiciones = len(posiciones_esquema) if posiciones_esquema else len(filas)
    total_auditadas = len(filas)
    posiciones_pendientes = [p for p in posiciones_esquema if p not in [int(f.get('posicion', 0)) for f in filas]]

    valid_pmins = [f['p_min'] for f in filas if f.get('p_min') is not None]
    if valid_pmins:
        p_min_global = min(valid_pmins)
        pos_min_global = next(f.get('posicion') for f in filas if f.get('p_min') == p_min_global)
        p_prom_global = sum(valid_pmins) / len(valid_pmins)
    else:
        p_min_global = None
        pos_min_global = '-'
        p_prom_global = None

    # Alertas completas
    alertas_lista = []

    # 1. Alertas de Cambio (Profundidad <= Límite de Retiro)
    llantas_cambio = []
    for f in filas:
        p = int(f.get('posicion', 0))
        p_m = f.get('p_min')
        if p_m is not None and p_m <= limite_retiro:
            llantas_cambio.append((p, p_m))
    n_cambios = len(llantas_cambio)

    if n_cambios > 3:
        # Agrupación inteligente de alertas de cambio cuando son más de 3
        pos_cambio_str = ", ".join(str(p) for p, _ in llantas_cambio)
        pos_detalles = ", ".join(f"Posición {p}" for p, _ in llantas_cambio)
        alertas_lista.append({
            'tipo': 'Cambio',
            'tipo_color': '#DC2626',
            'posicion': pos_cambio_str,
            'detalle': f"Retirar llantas en {pos_detalles} (remanente <= {format_num_es(limite_retiro)} mm de límite).",
            'accion': 'Retirar las llantas de estas posiciones y programar su cambio.'
        })
    else:
        for p, p_m in llantas_cambio:
            alertas_lista.append({
                'tipo': 'Cambio',
                'tipo_color': '#DC2626',
                'posicion': str(p),
                'detalle': f"Retirar llanta en Posición {p} (remanente {format_num_es(p_m)} mm <= {format_num_es(limite_retiro)} mm de límite).",
                'accion': 'Retirar la llanta y programar su cambio.'
            })

    # 2. Alineación y duales
    if not df_analisis.empty:
        r_an = df_analisis.iloc[0]
        if r_an.get('Plan_Alineacion') == 'SÍ':
            det_ali = str(r_an.get('Detalle_Alineacion', 'Diferencia excesiva entre directores.'))
            pos_mencionadas = re.findall(r'(?:pos(?:ición)?|pos)\s*(\d+)', det_ali, re.IGNORECASE)
            if pos_mencionadas:
                pos_unicas = list(dict.fromkeys(pos_mencionadas))
                if len(pos_unicas) == 1:
                    pos_ali = pos_unicas[0]
                elif len(pos_unicas) == 2:
                    pos_ali = f"{pos_unicas[0]} y {pos_unicas[1]}"
                else:
                    pos_ali = ", ".join(pos_unicas[:-1]) + f" y {pos_unicas[-1]}"
            else:
                pos_ali = '1 y 2'

            alertas_lista.append({
                'tipo': 'Alineación',
                'tipo_color': '#D97706',
                'posicion': pos_ali,
                'detalle': det_ali,
                'accion': 'Alinear y balancear.'
            })
        if r_an.get('Plan_Dual_Mal_Apareado') == 'SÍ':
            alertas_lista.append({
                'tipo': 'Dual mal apareado',
                'tipo_color': '#D97706',
                'posicion': 'Duales',
                'detalle': str(r_an.get('Detalle_Dual', 'Diferencia en conjunto dual mayor al umbral permitido.')),
                'accion': 'Rotar y aparear.'
            })

    # 3. Novedades mecánicas registradas (filtrando observaciones benignas)
    for f in filas:
        nov = str(f.get('novedades') or '').strip()
        if es_novedad_alerta(nov):
            alertas_lista.append({
                'tipo': 'Novedad mecánica',
                'tipo_color': '#D97706',
                'posicion': str(f.get('posicion')),
                'detalle': nov,
                'accion': 'Revisar componente y corregir condición.'
            })

    n_ali = sum(1 for a in alertas_lista if a['tipo'] == 'Alineación')
    n_duales = sum(1 for a in alertas_lista if a['tipo'] == 'Dual mal apareado')
    n_nov = sum(1 for a in alertas_lista if a['tipo'] == 'Novedad mecánica')
    total_alertas = n_cambios + n_ali + n_duales + n_nov

    return {
        'placa': placa_limpia,
        'fecha_insp': fecha_insp,
        'fecha_insp_fmt': fecha_insp_fmt,
        'cliente': cliente,
        'subcliente': subcliente,
        'operacion': operacion,
        'tipologia': tipologia,
        'km_str': km_str,
        'inspector_nombre': inspector_nombre,
        'limite_retiro': limite_retiro,
        'esquema': esquema,
        'filas': filas,
        'total_auditadas': total_auditadas,
        'total_posiciones': total_posiciones,
        'posiciones_pendientes': posiciones_pendientes,
        'p_min_global': p_min_global,
        'pos_min_global': pos_min_global,
        'p_prom_global': p_prom_global,
        'alertas_lista': alertas_lista,
        'n_cambios': n_cambios,
        'n_ali': n_ali,
        'n_duales': n_duales,
        'n_nov': n_nov,
        'total_alertas': total_alertas,
        'df_analisis': df_analisis
    }

def renderizar_informe(datos) -> bytes:
    placa = datos['placa']
    tipologia = datos['tipologia']
    fecha_insp_fmt = datos['fecha_insp_fmt']
    cliente = datos['cliente']
    subcliente = datos['subcliente']
    operacion = datos['operacion']
    km_str = datos['km_str']
    inspector_nombre = datos['inspector_nombre']
    limite_retiro = datos['limite_retiro']
    total_auditadas = datos['total_auditadas']
    total_posiciones = datos['total_posiciones']
    p_min_global = datos['p_min_global']
    pos_min_global = datos['pos_min_global']
    p_prom_global = datos['p_prom_global']
    alertas_lista = datos['alertas_lista']
    n_cambios = datos['n_cambios']
    n_ali = datos['n_ali']
    n_duales = datos['n_duales']
    n_nov = datos['n_nov']
    total_alertas = datos['total_alertas']
    filas = datos['filas']
    esquema = datos['esquema']

    fecha_emision = ahora_bogota().strftime('%d/%m/%Y')
    num_informe = f"INF-{placa}-{ahora_bogota().strftime('%Y%m%d')}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=68,
        bottomMargin=32
    )

    styles = getSampleStyleSheet()
    style_ficha_tit = ParagraphStyle('FichaTit', fontName='Helvetica-Bold', fontSize=8.5, leading=10, textColor=colors.HexColor('#0F172A'), spaceBefore=2, spaceAfter=4)
    style_sec_tit = ParagraphStyle('SecTit', fontName='Helvetica-Bold', fontSize=10.0, leading=13, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=4, keepWithNext=True)
    style_kpi_num = ParagraphStyle('KpiNum', fontName='Helvetica-Bold', fontSize=13, leading=15, alignment=1)
    style_kpi_lbl = ParagraphStyle('KpiLbl', fontName='Helvetica', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748B'), alignment=1)
    style_cell_head = ParagraphStyle('CellH', fontName='Helvetica-Bold', fontSize=6.5, leading=8.5, textColor=colors.white, alignment=0)
    style_cell_body = ParagraphStyle('CellB', fontName='Helvetica', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#1E293B'), alignment=0)

    elements = []

    # =========================================================================
    # SECCIÓN 1: ENCABEZADO Y FICHA TÉCNICA
    # =========================================================================
    tipo_limpio = tipologia.strip('() ').strip() if tipologia else 'Estándar'
    if not tipo_limpio or tipo_limpio.upper() in ('NAN', 'NONE'):
        tipo_limpio = 'Estándar'
    elements.append(Paragraph(f"<b>FICHA TÉCNICA Y RESUMEN OPERATIVO · VEHÍCULO {html.escape(placa)} ({html.escape(tipo_limpio)})</b>", style_ficha_tit))

    style_lbl_meta = ParagraphStyle('MetaLbl', fontName='Helvetica-Bold', fontSize=5.5, leading=7, textColor=colors.HexColor('#64748B'))
    style_val_meta = ParagraphStyle('MetaVal', fontName='Helvetica-Bold', fontSize=8.0, leading=10, textColor=colors.HexColor('#0F172A'))

    def celda_meta(lbl, val):
        return [
            Paragraph(lbl.upper(), style_lbl_meta),
            Spacer(1, 1),
            Paragraph(html.escape(str(val)), style_val_meta)
        ]

    data_meta = [
        [celda_meta("CLIENTE", cliente), celda_meta("SEDE", subcliente), celda_meta("OPERACIÓN", operacion)],
        [celda_meta("PLACA", placa), celda_meta("TIPOLOGÍA", tipologia), celda_meta("KILOMETRAJE", km_str)],
        [celda_meta("FECHA DE INSPECCIÓN", fecha_insp_fmt), celda_meta("INSPECTOR", inspector_nombre), celda_meta("LÍMITE DE RETIRO DEL CLIENTE", f"{format_num_es(limite_retiro)} mm")]
    ]
    t_meta = Table(data_meta, colWidths=[180, 180, 180])
    t_meta.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 4))

    # =========================================================================
    # SECCIÓN 2: TARJETAS KPI (DESGLOSE CONSISTENTE)
    # =========================================================================
    col_kpi_alerta = '#DC2626' if total_alertas > 0 else '#16A34A'
    col_kpi_min = '#DC2626' if (p_min_global is not None and p_min_global <= limite_retiro) else '#0F172A'

    txt_pmin_glo = f"{format_num_es(p_min_global)} mm" if p_min_global is not None else "—"
    txt_prom_glo = f"{format_num_es(p_prom_global)} mm" if p_prom_global is not None else "—"
    desglose_alertas_txt = f"Alertas: {n_cambios} cambio, {n_ali} alineación, {n_duales} duales, {n_nov} novedades"

    data_kpi = [
        [
            Paragraph(f"<font color='#0F172A'><b>{total_auditadas} de {total_posiciones}</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_kpi_min}'><b>{txt_pmin_glo}</b></font>", style_kpi_num),
            Paragraph(f"<font color='#0F172A'><b>{txt_prom_glo}</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_kpi_alerta}'><b>{total_alertas}</b></font>", style_kpi_num),
        ],
        [
            Paragraph("Posiciones inspeccionadas", style_kpi_lbl),
            Paragraph(f"Profundidad mínima (posición {pos_min_global})", style_kpi_lbl),
            Paragraph("Promedio de profundidades mínimas", style_kpi_lbl),
            Paragraph(desglose_alertas_txt, style_kpi_lbl),
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

    # =========================================================================
    # SECCIÓN 3: DIAGNÓSTICO Y ACCIONES RECOMENDADAS (TODAS LAS ALERTAS)
    # =========================================================================
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
        for a in alertas_lista:
            style_tipo = ParagraphStyle('TipoAlerta', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor(a['tipo_color']))
            data_diag.append([
                Paragraph(html.escape(a['tipo']), style_tipo),
                Paragraph(html.escape(a['posicion']), style_cell_body),
                Paragraph(html.escape(a['detalle']), style_cell_body),
                Paragraph(html.escape(a['accion']), style_cell_body)
            ])
    else:
        style_ok = ParagraphStyle('TipoOk', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor('#16A34A'))
        pos_diag = "Todas"
        det_diag = f"Todas las llantas están sobre el límite de retiro ({format_num_es(limite_retiro)} mm) y sin alertas configuradas."
        pos_pendientes = datos.get('posiciones_pendientes', [])
        if total_auditadas < total_posiciones:
            pos_diag = f"{total_auditadas} de {total_posiciones} eval."
            det_diag = f"Las {total_auditadas} llantas evaluadas están sobre el límite de retiro ({format_num_es(limite_retiro)} mm). Quedan {len(pos_pendientes)} posiciones pendientes por registrar."
        data_diag.append([
            Paragraph("Sin alertas", style_ok),
            Paragraph(pos_diag, style_cell_body),
            Paragraph(det_diag, style_cell_body),
            Paragraph("Operación normal y próxima inspección periódica.", style_cell_body)
        ])

    t_diag = Table(data_diag, colWidths=[95, 45, 250, 150], repeatRows=1)
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

    # =========================================================================
    # SECCIÓN 4: DISTRIBUCIÓN POR EJES (DIAGRAMA CHASIS VECTORIAL)
    # =========================================================================
    tit_chasis = Paragraph("Distribución por ejes", style_sec_tit)
    drawing_chasis = dibujar_diagrama_chasis_reportlab(tipologia, filas, limite_retiro=limite_retiro, width=540)
    elements.append(KeepTogether([tit_chasis, drawing_chasis, Spacer(1, 4)]))

    # =========================================================================
    # SECCIÓN 5: DETALLE POR LLANTA
    # =========================================================================
    elements.append(Paragraph("Detalle por llanta", style_sec_tit))

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

    pos_to_eje = {}
    pos_to_rol_desc = {}
    pos_to_info_esq = {}
    if esquema:
        for e in esquema:
            e_num = e.get('eje', 1)
            t_raw = str(e.get('tipo', '')).lower()
            if e_num == 99 or 'rep' in t_raw:
                t_lbl = 'Repuesto'
            elif 'dir' in t_raw:
                t_lbl = f"Eje {e_num} · Direccional"
            elif 'trac' in t_raw:
                t_lbl = f"Eje {e_num} · Tracción"
            elif 'rem' in t_raw or 'trailer' in t_raw:
                t_lbl = f"Eje {e_num} · Remolque"
            else:
                t_lbl = f"Eje {e_num} · {str(e.get('tipo', '')).capitalize()}"

            for p in e.get('posiciones', []):
                p_n = p.get('pos')
                pos_to_eje[p_n] = t_lbl
                lado = 'Izq' if p.get('lado') == 'izq' else 'Der' if p.get('lado') == 'der' else ''
                rol_str = normalizar_rol_pdf(p.get('rol'))
                pos_to_rol_desc[p_n] = f"{lado} · {rol_str}".strip(' ·')
                pos_to_info_esq[p_n] = {
                    'eje': e_num,
                    'lado': p.get('lado', ''),
                    'rol': p.get('rol', '')
                }

    ejes_orden = []
    for f in filas:
        p_num = int(f.get('posicion', 0))
        eje_lbl = pos_to_eje.get(p_num, 'Eje Principal')
        if eje_lbl not in ejes_orden:
            ejes_orden.append(eje_lbl)

    style_eje_subhead = ParagraphStyle('EjeSub', fontName='Helvetica-Bold', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#0F172A'))

    for eje_lbl in ejes_orden:
        data_llantas.append([
            Paragraph(f"<b>{html.escape(eje_lbl)}</b>", style_eje_subhead),
            "", "", "", "", "", "", "", "", "", "", ""
        ])
        filas_eje = [f for f in filas if pos_to_eje.get(int(f.get('posicion', 0)), 'Eje Principal') == eje_lbl]
        for f in filas_eje:
            p_n = int(f.get('posicion', 0))
            p_min = f.get('p_min')
            p_ext = f.get('prof_ext')
            p_cen = f.get('prof_cent')
            p_int = f.get('prof_int')

            es_cambio = (p_min is not None and p_min <= limite_retiro)
            novedad_texto = str(f.get('novedades') or '').strip()
            tiene_novedad_real = es_novedad_alerta(novedad_texto)

            if es_cambio:
                estado_txt = "Cambio sugerido"
                col_est = '#DC2626'
            elif tiene_novedad_real:
                estado_txt = "Con novedad"
                col_est = '#D97706'
            elif p_min is not None:
                estado_txt = "Registrada"
                col_est = '#16A34A'
            else:
                estado_txt = "Pendiente"
                col_est = '#94A3B8'

            st_pmin = ParagraphStyle('PMinCell', parent=style_cell_body, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#DC2626' if es_cambio else ('#64748B' if p_min is None else '#0F172A')))
            st_estado = ParagraphStyle('EstCell', parent=style_cell_body, fontName='Helvetica-Bold', textColor=colors.HexColor(col_est))

            marca_dis = f"{f.get('marca', '')} {f.get('diseno', '')}".strip()
            if not marca_dis or marca_dis.upper() in ('-', 'NAN', 'NONE'):
                marca_dis = "—"

            rol_lbl = pos_to_rol_desc.get(p_n, normalizar_rol_pdf(f.get('rol', '')))

            try:
                ext_val = float(p_ext) if p_ext is not None else None
            except (ValueError, TypeError):
                ext_val = None
            try:
                cen_val = float(p_cen) if p_cen is not None else None
            except (ValueError, TypeError):
                cen_val = None
            try:
                int_val = float(p_int) if p_int is not None else None
            except (ValueError, TypeError):
                int_val = None

            txt_ext = format_num_es(ext_val) if (ext_val is not None and ext_val > 0) else "—"
            txt_cen = format_num_es(cen_val) if (cen_val is not None and cen_val > 0) else "—"
            txt_int = format_num_es(int_val) if (int_val is not None and int_val > 0) else "—"
            txt_min = format_num_es(p_min)

            try:
                psi_raw = f.get('psi')
                if psi_raw is None or str(psi_raw).strip() == '':
                    psi_val = "—"
                else:
                    psi_flt = float(psi_raw)
                    psi_val = f"{psi_flt:.0f}" if psi_flt > 0 else "—"
            except Exception:
                psi_val = "—"

            dim_txt = str(f.get('dimension') or '').strip()
            if not dim_txt or dim_txt.upper() in ('-', 'NAN', 'NONE'):
                dim_txt = "—"

            num_int_txt = str(f.get('numero_interno') or '').strip()
            if not num_int_txt or num_int_txt.upper() in ('-', 'NAN', 'NONE'):
                num_int_txt = "—"

            data_llantas.append([
                Paragraph(f"<b>{p_n}</b>", style_cell_body),
                Paragraph(html.escape(rol_lbl), style_cell_body),
                Paragraph(html.escape(marca_dis), style_cell_body),
                Paragraph(html.escape(dim_txt), style_cell_body),
                Paragraph(html.escape(num_int_txt), style_cell_body),
                Paragraph(html.escape(str(f.get('vida') or 'Orig')), style_cell_body),
                Paragraph(txt_ext, style_cell_body),
                Paragraph(txt_cen, style_cell_body),
                Paragraph(txt_int, style_cell_body),
                Paragraph(txt_min, st_pmin),
                Paragraph(psi_val, style_cell_body),
                Paragraph(estado_txt, st_estado)
            ])

    t_llantas = Table(data_llantas, colWidths=[22, 55, 115, 68, 42, 45, 26, 26, 26, 28, 25, 62], repeatRows=1)
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
    elements.append(Paragraph("Profundidades en mm. PSI: presión registrada. — indica sin lectura o lectura cero.", style_subnota))

    # =========================================================================
    # SECCIÓN 6: NOVEDADES REGISTRADAS
    # =========================================================================
    elements.append(Paragraph("Novedades registradas", style_sec_tit))
    filas_con_nov = [f for f in filas if es_novedad_alerta(str(f.get('novedades') or '').strip())]
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
                Paragraph(html.escape(str(f.get('novedades')).strip()), style_cell_body)
            ])
    else:
        data_nov.append([
            Paragraph("-", style_cell_body),
            Paragraph("No se registraron novedades o anomalías mecánicas en las llantas inspeccionadas.", style_cell_body)
        ])

    pad_nov = 2.0 if not filas_con_nov else 2.5
    t_nov = Table(data_nov, colWidths=[40, 500], repeatRows=1)
    t_nov.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), pad_nov),
        ('BOTTOMPADDING', (0,0), (-1,-1), pad_nov),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_nov)
    elements.append(Spacer(1, 3 if not filas_con_nov else 4))

    # =========================================================================
    # SECCIÓN 7: EVIDENCIA FOTOGRÁFICA
    # =========================================================================
    llantas_enriquecidas = []
    for f in filas:
        p_n = int(f.get('posicion', 0))
        info_e = pos_to_info_esq.get(p_n, {})
        llantas_enriquecidas.append({
            'pos': p_n,
            'eje': info_e.get('eje', 1),
            'lado': info_e.get('lado', ''),
            'rol': info_e.get('rol', f.get('rol', '')),
            'novedad': str(f.get('novedades') or '').strip(),
            'foto_novedad': f.get('foto_novedad', '')
        })

    fotos_elementos = seccion_fotos(llantas_enriquecidas)
    if fotos_elementos:
        elements.extend(fotos_elementos)

    # =========================================================================
    # SECCIÓN 8: OBSERVACIONES DEL INSPECTOR
    # =========================================================================
    elements.append(Paragraph("Observaciones del inspector", style_sec_tit))
    obs_lines = []
    if n_cambios > 0:
        pos_cambios = [str(a['posicion']) for a in alertas_lista if a['tipo'] == 'Cambio']
        obs_lines.append(f"Se recomienda programar el retiro de la(s) llanta(s) en posición {', '.join(pos_cambios)} por encontrarse en o por debajo del límite de retiro ({format_num_es(limite_retiro)} mm).")
    if n_ali > 0:
        obs_lines.append("En el eje direccional se observa una diferencia de desgaste entre directores; se sugiere revisar alineación y balanceo preventivo.")
    if n_duales > 0:
        obs_lines.append("En los conjuntos duales se recomienda rotar o aparear llantas para evitar fatiga prematura por diferencia de radio rodante.")
    if n_nov > 0:
        obs_lines.append("Se identificaron novedades mecánicas reportadas; verificar componentes mecánicos asociados.")
    if not obs_lines:
        obs_lines.append("No se detectaron alertas de diagnóstico con las reglas configuradas.")

    style_par_obs = ParagraphStyle('ObsPar', fontName='Helvetica', fontSize=7.0, leading=9.5, textColor=colors.HexColor('#1E293B'))
    elements.append(Paragraph(" ".join(obs_lines), style_par_obs))
    elements.append(Spacer(1, 4))

    # =========================================================================
    # SECCIÓN 9: CRITERIOS DE DIAGNÓSTICO APLICADOS
    # =========================================================================
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

    # =========================================================================
    # SECCIÓN 10: FIRMAS
    # =========================================================================
    style_sub_firma = ParagraphStyle('FirmSub', fontName='Helvetica', fontSize=7.0, leading=9.0, textColor=colors.HexColor('#0F172A'), alignment=1)
    firma_data = [
        [
            Paragraph(f"__________________________________________<br/><b>Inspector · {html.escape(inspector_nombre)}</b>", style_sub_firma),
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

    # Construcción final con canvasmaker para paginación dinámica continua
    canvas_maker = obtener_canvas_reporte_vehiculo(num_informe, fecha_emision)
    doc.build(elements, canvasmaker=canvas_maker)
    buffer.seek(0)
    return buffer.getvalue()

def generar_pdf_plan_mantenimiento(placa, fecha=None):
    """
    Genera el archivo PDF oficial de Plan de Mantenimiento e Informe de Inspección
    de Vehículo unificando la consulta, límites, alertas y renderizado sin duplicación.
    """
    return renderizar_informe(construir_datos_informe(placa, fecha))

def generar_pdf_consolidado_jornada(cliente=None, subcliente=None, fecha=None, operacion=None, usuario=None):
    """
    Genera un informe PDF Consolidado de Flota con métricas globales, gráficos de resumen,
    estado de flota por eje y dimensión, y tabla de placas a intervenir.
    """
    df_insp = database.obtener_todas_inspecciones(usuario=usuario)
    if df_insp.empty:
        raise ValueError("No existen inspecciones registradas en el sistema.")

    if cliente and cliente != 'Todos':
        df_insp = df_insp[df_insp['cliente'].astype(str).str.upper().str.strip() == str(cliente).upper().strip()]
    if subcliente and subcliente != 'Todos':
        df_insp = df_insp[df_insp['subcliente'].astype(str).str.upper().str.strip() == str(subcliente).upper().strip()]
    if operacion and operacion != 'Todos':
        df_insp = df_insp[df_insp['tipo_operacion'].astype(str).str.upper().str.strip() == str(operacion).upper().strip()]
    if fecha:
        df_insp = df_insp[df_insp['fecha'].astype(str) == str(fecha)]

    if df_insp.empty:
        raise ValueError("No se encontraron inspecciones con los filtros seleccionados.")

    df_analisis = database.analizar_inspecciones_df(df_insp)

    # Métricas Globales
    total_vehiculos = df_analisis['Vehículo/Placa'].nunique() if not df_analisis.empty else 0
    total_llantas = len(df_insp)

    limite_def = database.obtener_limite_retiro_cliente(cliente if cliente else '') or 3.0
    
    # Cálculos llanta a llanta con dg.profundidad_minima
    df_insp['p_min'] = df_insp.apply(lambda r: dg.profundidad_minima(r.to_dict()), axis=1)
    llantas_retiro = len(df_insp[(df_insp['p_min'].notna()) & (df_insp['p_min'] <= limite_def)])
    llantas_proximo = len(df_insp[(df_insp['p_min'].notna()) & (df_insp['p_min'] > limite_def) & (df_insp['p_min'] <= limite_def + 2.0)])
    llantas_optimas = total_llantas - llantas_retiro - llantas_proximo

    pct_retiro = (llantas_retiro / total_llantas * 100) if total_llantas > 0 else 0
    pct_proximo = (llantas_proximo / total_llantas * 100) if total_llantas > 0 else 0
    pct_optimas = (llantas_optimas / total_llantas * 100) if total_llantas > 0 else 0

    veh_cambio = len(df_analisis[df_analisis['Plan_Cambio_Llanta'] == 'SÍ']) if not df_analisis.empty else 0
    veh_ali = len(df_analisis[df_analisis['Plan_Alineacion'] == 'SÍ']) if not df_analisis.empty else 0
    veh_dual = len(df_analisis[df_analisis['Plan_Dual_Mal_Apareado'] == 'SÍ']) if not df_analisis.empty else 0
    veh_rot_irr = len(df_analisis[df_analisis.get('Plan_Rotacion_Irregular', 'NO') == 'SÍ']) if not df_analisis.empty else 0
    veh_rot_esc = len(df_analisis[df_analisis.get('Plan_Rotacion_Escalonado', 'NO') == 'SÍ']) if not df_analisis.empty else 0
    veh_psi = len(df_analisis[df_analisis.get('Plan_Calibracion_PSI', 'NO') == 'SÍ']) if not df_analisis.empty else 0

    # Vehículos únicos que presentan al menos una alerta crítica (Cambio, Alineación o Dual)
    cond_alerta_critica = (
        (df_analisis['Plan_Cambio_Llanta'] == 'SÍ') |
        (df_analisis['Plan_Alineacion'] == 'SÍ') |
        (df_analisis['Plan_Dual_Mal_Apareado'] == 'SÍ')
    ) if not df_analisis.empty else []
    veh_con_alerta = int(df_analisis[cond_alerta_critica]['Vehículo/Placa'].nunique()) if not df_analisis.empty else 0

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=68,
        bottomMargin=32
    )

    styles = getSampleStyleSheet()

    style_titulo = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#0f172a'))
    style_subtitulo = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#475569'))
    style_seccion = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=colors.HexColor('#1e3a8a'), spaceBefore=8, spaceAfter=4)
    style_cell_header = ParagraphStyle('CellHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=colors.white, alignment=1)
    style_cell_body = ParagraphStyle('CellBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor('#1e293b'))
    style_cell_alert = ParagraphStyle('CellAlert', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=colors.HexColor('#b91c1c'))

    elements = []
    elements.append(Spacer(1, 2))

    # Tarjetas Resumen de Flota
    cliente_txt = cliente if cliente and cliente != 'Todos' else 'Consolidado General'
    partes_sede = []
    if subcliente and subcliente != 'Todos':
        partes_sede.append(f"Sede: {subcliente}")
    if operacion and operacion != 'Todos':
        partes_sede.append(f"Operación: {operacion}")
    sub_txt = " · ".join(partes_sede) if partes_sede else "Todas las Sedes y Operaciones"

    res_box = [
        [
            Paragraph(f"<b>Cliente / Flota:</b> {cliente_txt}", style_subtitulo),
            Paragraph(f"<b>Sede / Operación:</b> {sub_txt}", style_subtitulo),
            Paragraph(f"<b>Límite Retiro Aplicado:</b> {limite_def:.1f} mm", style_subtitulo)
        ],
        [
            Paragraph(f"<b>Vehículos Inspeccionados:</b> <font color='#2563eb' size=10><b>{total_vehiculos}</b></font>", style_subtitulo),
            Paragraph(f"<b>Total Llantas Medidas:</b> <font color='#2563eb' size=10><b>{total_llantas}</b></font>", style_subtitulo),
            Paragraph(f"<b>Vehículos con Alerta:</b> <font color='#b91c1c' size=10><b>{veh_con_alerta}</b></font>", style_subtitulo)
        ]
    ]
    t_res = Table(res_box, colWidths=[180, 180, 180])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_res)
    elements.append(Spacer(1, 8))

    # 1. ESTADO GLOBAL DE LAS LLANTAS (SEMÁFORO DE FLOTA)
    elements.append(Paragraph("1. Semáforo Global de Estado de Llantas", style_seccion))
    semaforo_data = [
        [
            Paragraph("<b>CONDICIÓN DE LA LLANTA</b>", style_cell_header),
            Paragraph("<b>CANTIDAD</b>", style_cell_header),
            Paragraph("<b>% FLOTA</b>", style_cell_header),
            Paragraph("<b>ACCIÓN TÉCNICA RECOMENDADA</b>", style_cell_header)
        ],
        [
            Paragraph("🔴 <b>Retiro Urgente (<= Límite)</b>", style_cell_alert),
            Paragraph(f"<b>{llantas_retiro}</b>", style_cell_alert),
            Paragraph(f"<b>{pct_retiro:.1f}%</b>", style_cell_alert),
            Paragraph("Programar desmontaje inmediato para evitar daños de carcasa o incidentes viales.", style_cell_body)
        ],
        [
            Paragraph("🟡 <b>Próximo a Cambio (+2.0 mm)</b>", style_cell_body),
            Paragraph(f"<b>{llantas_proximo}</b>", style_cell_body),
            Paragraph(f"<b>{pct_proximo:.1f}%</b>", style_cell_body),
            Paragraph("Monitorear en 15 a 30 días y alistar stock de reemplazo o reencauche.", style_cell_body)
        ],
        [
            Paragraph("🟢 <b>Condición Normal / Óptima</b>", style_cell_body),
            Paragraph(f"<b>{llantas_optimas}</b>", style_cell_body),
            Paragraph(f"<b>{pct_optimas:.1f}%</b>", style_cell_body),
            Paragraph("Mantener presiones recomendadas y rotación preventiva según kilometraje.", style_cell_body)
        ]
    ]
    t_sem = Table(semaforo_data, colWidths=[150, 60, 60, 270])
    t_sem.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#fee2e2')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#fef3c7')),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor('#f0fdf4')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_sem)
    elements.append(Spacer(1, 8))

    # 2. PLANES DE ACCIÓN REQUERIDOS EN LA FLOTA
    elements.append(Paragraph("2. Resumen Consolidado de Planes de Acción y Novedades", style_seccion))
    planes_data = [
        [
            Paragraph("<b>PLAN DE ACCIÓN TÉCNICO</b>", style_cell_header),
            Paragraph("<b>VEHÍCULOS AFECTADOS</b>", style_cell_header),
            Paragraph("<b>DETALLE Y ALCANCE OPERATIVO</b>", style_cell_header)
        ],
        [
            Paragraph("<b>Sugerencia Retiro / Cambio</b>", style_cell_body),
            Paragraph(f"<b>{veh_cambio}</b>", style_cell_alert if veh_cambio > 0 else style_cell_body),
            Paragraph(f"Vehículos con al menos una llanta en o por debajo de {limite_def:.1f} mm.", style_cell_body)
        ],
        [
            Paragraph("<b>Alineación y Geometría Direccional</b>", style_cell_body),
            Paragraph(f"<b>{veh_ali}</b>", style_cell_alert if veh_ali > 0 else style_cell_body),
            Paragraph("Vehículos con diferencia entre exterior e interior >= 2.0 mm en llantas direccionales.", style_cell_body)
        ],
        [
            Paragraph("<b>Emparejamiento / Dual Mal Apareado</b>", style_cell_body),
            Paragraph(f"<b>{veh_dual}</b>", style_cell_alert if veh_dual > 0 else style_cell_body),
            Paragraph("Vehículos con duales que superan 2.0 mm de diferencia o dimensiones heterogéneas.", style_cell_body)
        ],
        [
            Paragraph("<b>Rotación por Desgaste Irregular</b>", style_cell_body),
            Paragraph(f"<b>{veh_rot_irr}</b>", style_cell_alert if veh_rot_irr > 0 else style_cell_body),
            Paragraph("Llantas en tracción o eje libre con desgaste irregular o disparejo.", style_cell_body)
        ],
        [
            Paragraph("<b>Rotación por Desgaste Escalonado</b>", style_cell_body),
            Paragraph(f"<b>{veh_rot_esc}</b>", style_cell_alert if veh_rot_esc > 0 else style_cell_body),
            Paragraph("Llantas con diente de sierra / desgaste escalonado en eje de tracción.", style_cell_body)
        ],
        [
            Paragraph("<b>Calibración de Presión de Aire</b>", style_cell_body),
            Paragraph(f"<b>{veh_psi}</b>", style_cell_alert if veh_psi > 0 else style_cell_body),
            Paragraph("Posiciones con baja presión (< 90 PSI o novedad reportada).", style_cell_body)
        ]
    ]
    t_planes = Table(planes_data, colWidths=[180, 80, 280])
    t_planes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_planes)
    elements.append(Spacer(1, 8))

    # 3. LISTADO DETALLADO DE PLACAS A INTERVENIR
    elements.append(Paragraph(f"3. Matriz de Vehículos Inspeccionados y Placas a Intervenir ({total_vehiculos} Vehículos)", style_seccion))
    matriz_data = [
        [
            Paragraph("Vehículo", style_cell_header),
            Paragraph("Sede / Operación", style_cell_header),
            Paragraph("Llantas", style_cell_header),
            Paragraph("Cambio", style_cell_header),
            Paragraph("Alinear", style_cell_header),
            Paragraph("Dual", style_cell_header),
            Paragraph("Rotación", style_cell_header),
            Paragraph("Detalle de Alerta Principal", style_cell_header)
        ]
    ]

    for _, r in df_analisis.iterrows():
        p_cambio = r.get('Plan_Cambio_Llanta', 'NO')
        p_ali = r.get('Plan_Alineacion', 'NO')
        p_du = r.get('Plan_Dual_Mal_Apareado', 'NO')
        p_rot = "SÍ" if (r.get('Plan_Rotacion_Irregular') == 'SÍ' or r.get('Plan_Rotacion_Escalonado') == 'SÍ') else "NO"

        alertas_txt = []
        if p_cambio == 'SÍ': alertas_txt.append(f"Cambio: {r.get('Detalle_Cambio', '')}")
        if p_ali == 'SÍ': alertas_txt.append(f"Alinear: {r.get('Detalle_Alineacion', '')}")
        if p_du == 'SÍ': alertas_txt.append(f"Dual: {r.get('Detalle_Dual', '')}")
        if r.get('Recomendaciones_Dual') and r.get('Recomendaciones_Dual') != 'OK':
            alertas_txt.append(f"Recom: {r.get('Recomendaciones_Dual')}")

        det_rot = []
        d_irr = r.get('Detalle_Rotacion_Irregular', '')
        d_esc = r.get('Detalle_Rotacion_Escalonado', '')
        if r.get('Plan_Rotacion_Irregular') == 'SÍ' and d_irr and d_irr != 'OK':
            det_rot.append(f"Rotación irr: {d_irr}")
        if r.get('Plan_Rotacion_Escalonado') == 'SÍ' and d_esc and d_esc != 'OK':
            det_rot.append(f"Rotación esc: {d_esc}")

        if alertas_txt:
            texto_detalle = "; ".join(alertas_txt)
            style_detalle = style_cell_alert
        elif det_rot:
            texto_detalle = "Preventivo: " + "; ".join(det_rot)
            style_detalle = style_cell_body
        else:
            texto_detalle = "Sin novedades críticas"
            style_detalle = style_cell_body

        sede_val = str(r.get('Subcliente', '') or '').strip()
        op_val = str(r.get('Operación', '') or '').strip()
        sede_op_parts = []
        if sede_val and sede_val.lower() not in ('nan', 'none', '-'):
            sede_op_parts.append(f"<b>{sede_val}</b>")
        if op_val and op_val.lower() not in ('nan', 'none', '-'):
            sede_op_parts.append(f"<font color='#64748b'>{op_val}</font>")
        sede_op_html = "<br/>".join(sede_op_parts) if sede_op_parts else "-"

        matriz_data.append([
            Paragraph(f"<b>{r.get('Vehículo/Placa', '')}</b>", style_cell_body),
            Paragraph(sede_op_html, style_cell_body),
            Paragraph(str(r.get('Llantas Inspeccionadas', '')), style_cell_body),
            Paragraph(f"<b>{p_cambio}</b>", style_cell_alert if p_cambio == 'SÍ' else style_cell_body),
            Paragraph(f"<b>{p_ali}</b>", style_cell_alert if p_ali == 'SÍ' else style_cell_body),
            Paragraph(f"<b>{p_du}</b>", style_cell_alert if p_du == 'SÍ' else style_cell_body),
            Paragraph(f"<b>{p_rot}</b>", style_cell_alert if p_rot == 'SÍ' else style_cell_body),
            Paragraph(texto_detalle, style_detalle)
        ])

    t_matriz = Table(matriz_data, colWidths=[55, 65, 38, 42, 42, 38, 45, 215])
    t_matriz.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_matriz)
    elements.append(Spacer(1, 14))

    # 4. MATRIZ DE SEMÁFOROS POR POSICIÓN (POLÍTICA DE RETIRO POR CLIENTE, SEDE Y EJE)
    matriz_pos = database.calcular_matriz_semaforos_posicion(df_insp)
    if matriz_pos and matriz_pos.get('filas'):
        elements.append(Paragraph("4. Matriz de Semáforos por Posición (Desgaste vs Política Técnica)", style_seccion))
        leyenda_sem = (
            "<b>Umbrales Técnicos por Eje:</b> "
            "<font color='#b91c1c'><b>🔴 Retiro Inmediato (PB ≤ Límite)</b></font> · "
            "<font color='#b45309'><b>🟡 Próxima a Cambio (+2.0 mm)</b></font> · "
            "<font color='#15803d'><b>🟢 Estado Óptimo (&gt; Límite + 2mm)</b></font> · "
            "<font color='#64748b'><b>⚪ Sin Datos / Casco (PB ≤ 0)</b></font>"
        )
        elements.append(Paragraph(leyenda_sem, style_subtitulo))
        elements.append(Spacer(1, 4))

        pos_list = matriz_pos['posiciones']
        num_pos = len(pos_list)

        if num_pos <= 10:
            w_veh = 52
            w_tip = 58
            w_res = 65
            w_pos = (540 - w_veh - w_tip - w_res) / max(1, num_pos)
        elif num_pos <= 12:
            w_veh = 48
            w_tip = 52
            w_res = 60
            w_pos = (540 - w_veh - w_tip - w_res) / max(1, num_pos)
        else:
            w_veh = 44
            w_tip = 48
            w_res = 55
            w_pos = max(16.0, (540 - w_veh - w_tip - w_res) / max(1, num_pos))

        col_widths_sem = [w_veh, w_tip] + [w_pos] * num_pos + [w_res]

        style_sem_hdr = ParagraphStyle('SemHdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.white, alignment=1)
        style_sem_cell = ParagraphStyle('SemCell', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.5, leading=8, alignment=1)
        style_sem_text = ParagraphStyle('SemText', parent=styles['Normal'], fontName='Helvetica', fontSize=6.5, leading=8, textColor=colors.HexColor('#0f172a'))
        style_sem_res = ParagraphStyle('SemRes', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.5, leading=8, alignment=1)

        t_sem_rows = []
        hdr_row = [
            Paragraph("<b>Vehículo</b>", style_sem_hdr),
            Paragraph("<b>Tipología</b>", style_sem_hdr)
        ]
        for p in pos_list:
            hdr_row.append(Paragraph(f"<b>P{p}</b>", style_sem_hdr))
        hdr_row.append(Paragraph("<b>🔴/🟡/🟢</b>", style_sem_hdr))
        t_sem_rows.append(hdr_row)

        table_styles = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]

        for r_idx, fila in enumerate(matriz_pos['filas'], start=1):
            f_row = [
                Paragraph(f"<b>{fila['placa']}</b>", style_sem_text),
                Paragraph(f"<font size=5.5 color='#475569'>{fila['tipologia'][:16]}</font>", style_sem_text)
            ]
            for c_idx, p in enumerate(pos_list):
                col_pos_table = c_idx + 2
                if p in fila['posiciones']:
                    item = fila['posiciones'][p]
                    pb_val = item['pb']
                    c_col = item['color']

                    if c_col == 'rojo':
                        bg_c = colors.HexColor('#fee2e2')
                        txt_c = '#991b1b'
                    elif c_col == 'amarillo':
                        bg_c = colors.HexColor('#fef3c7')
                        txt_c = '#92400e'
                    elif c_col == 'verde':
                        bg_c = colors.HexColor('#dcfce7')
                        txt_c = '#166534'
                    else:
                        bg_c = colors.HexColor('#f1f5f9')
                        txt_c = '#64748b'

                    table_styles.append(('BACKGROUND', (col_pos_table, r_idx), (col_pos_table, r_idx), bg_c))
                    pb_str = f"{pb_val:.1f}" if pb_val > 0 else "0.0"
                    f_row.append(Paragraph(f"<font color='{txt_c}'><b>{pb_str}</b></font>", style_sem_cell))
                else:
                    f_row.append(Paragraph("<font color='#cbd5e1'>-</font>", style_sem_cell))

            c_rojo = fila['conteo']['rojo']
            c_amar = fila['conteo']['amarillo']
            c_verd = fila['conteo']['verde']
            f_row.append(Paragraph(f"<font color='#b91c1c'><b>{c_rojo}</b></font>/<font color='#b45309'><b>{c_amar}</b></font>/<font color='#15803d'><b>{c_verd}</b></font>", style_sem_res))
            t_sem_rows.append(f_row)

        tot_row_idx = len(t_sem_rows)
        foot_row = [
            Paragraph("<b>TOTALES</b>", style_sem_text),
            Paragraph("<b>(R/A/V)</b>", style_sem_hdr)
        ]
        for c_idx, p in enumerate(pos_list):
            t_p = matriz_pos['totales_posicion'].get(p, {'rojo': 0, 'amarillo': 0, 'verde': 0})
            foot_row.append(Paragraph(f"<font size=5><b><font color='#b91c1c'>{t_p['rojo']}</font>/<font color='#b45309'>{t_p['amarillo']}</font>/<font color='#15803d'>{t_p['verde']}</font></b></font>", style_sem_cell))

        glob = matriz_pos['resumen_global']
        foot_row.append(Paragraph(f"<b><font color='#b91c1c'>{glob['rojo']}</font>/<font color='#b45309'>{glob['amarillo']}</font>/<font color='#15803d'>{glob['verde']}</font></b>", style_sem_res))
        t_sem_rows.append(foot_row)

        table_styles.append(('BACKGROUND', (0, tot_row_idx), (-1, tot_row_idx), colors.HexColor('#e2e8f0')))
        table_styles.append(('LINEABOVE', (0, tot_row_idx), (-1, tot_row_idx), 1, colors.HexColor('#94a3b8')))

        t_matriz_pos = Table(t_sem_rows, colWidths=col_widths_sem, repeatRows=1)
        t_matriz_pos.setStyle(TableStyle(table_styles))
        elements.append(t_matriz_pos)
        elements.append(Spacer(1, 14))

    # Firmas
    firma_data = [
        [
            Paragraph("__________________________________________<br/><b>Director / Ingeniero de Gestión de Llantas</b>", style_subtitulo),
            Paragraph("__________________________________________<br/><b>Recibido por Jefe de Flota y Operaciones</b>", style_subtitulo)
        ]
    ]
    t_f = Table(firma_data, colWidths=[270, 270])
    t_f.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 10)]))
    elements.append(KeepTogether(t_f))

    cliente_canvas = cliente_txt
    if subcliente and subcliente != 'Todos':
        cliente_canvas += f" ({subcliente})"
    canvas_maker = obtener_canvas_consolidado_flota(fecha or 'Histórico General', cliente_canvas)
    doc.build(elements, canvasmaker=canvas_maker)
    buffer.seek(0)
    return buffer.getvalue()
