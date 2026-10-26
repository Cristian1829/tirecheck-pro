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

# Misma regla que la app: "Normal sin Novedad", "OK", etc. no son alertas
es_novedad_alerta = database.es_novedad_alerta

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

def format_miles_es(val):
    """Entero con separador de miles colombiano: 246383 -> '246.383'."""
    try:
        return f"{float(val):,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return str(val)

# Decimales sueltos ("2.5mm", "dif 3.0 mm", "(2.2 vs 10.4)") pero no medidas de llanta como "R22.5"
_RE_DECIMAL_EN = re.compile(r'(?<![R/\d.,])(\d{1,3})\.(\d+)(?![\d.])')

def decimales_es(texto: str) -> str:
    """Pasa a coma decimal los textos que arma el motor de diagnóstico (en formato inglés)."""
    return _RE_DECIMAL_EN.sub(r'\1,\2', texto or '')

def punto_color(hex_color: str) -> str:
    """Punto de color para leyendas. Helvetica no tiene emojis (salen como cuadros), ZapfDingbats sí trae el círculo."""
    return f"<font name='ZapfDingbats' color='{hex_color}'>l</font>"

def normalizar_rol_pdf(rol):
    return dg._rol(rol)

def dibujar_diagrama_chasis_reportlab(tipologia, filas, limite_retiro=3.0, width=540, texto_limite=None):
    try:
        esquema = database.obtener_esquema_tipologia(tipologia)
    except Exception:
        esquema = None
    if not esquema:
        return Spacer(1, 5)
    return dg.dibujar_diagrama_chasis(esquema, filas, limite_retiro, width, texto_limite=texto_limite)

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

# Orden de prioridad de las secciones del diagnóstico (lo urgente primero)
GRUPOS_DIAGNOSTICO = [
    ('retiro', 'Retiros y reemplazos'),
    ('proximas', 'Próximas a cambio'),
    ('geometria', 'Alineación y duales'),
    ('rotacion', 'Rotaciones y auto-ajuste de posiciones'),
    ('presion', 'Presión de inflado'),
    ('novedades', 'Novedades reportadas por el inspector'),
    ('vehiculo', 'Configuración del vehículo'),
]
PSI_OBJETIVO = 100  # mismo valor que usa el motor de diagnóstico (rango aceptado ±10 %)


def _partes(texto):
    """Separa un detalle del motor ("a; b; c") y descarta los vacíos y el 'OK' de relleno."""
    t = str(texto or '').strip()
    if not t or t.upper() == 'OK':
        return []
    return [p.strip() for p in t.split(';') if p.strip()]


def _posiciones_en(texto):
    """'Invertir Pos 4 ↔ Pos 3' -> '4 y 3'."""
    nums = list(dict.fromkeys(re.findall(r'\bP(?:os(?:ición)?)?\s*(\d+)', texto, re.IGNORECASE)))
    if not nums:
        return '-'
    return nums[0] if len(nums) == 1 else ", ".join(nums[:-1]) + f" y {nums[-1]}"


def recomendaciones_motor(r_an, limite_retiro) -> list:
    """
    Traduce las recomendaciones del motor de diagnóstico (cruces de bodega, emparejamiento,
    auto-ajuste, rotaciones, presión y próximas a cambio) a filas claras para el informe:
    qué se encontró (detalle) y qué hacer (acción).
    """
    filas = []

    def agregar(grupo, tipo, color, posicion, detalle, accion):
        filas.append({'grupo': grupo, 'tipo': tipo, 'tipo_color': color, 'posicion': posicion,
                      'detalle': decimales_es(detalle), 'accion': decimales_es(accion)})

    # Ajuste del par direccional (se retira también la pareja para igualar alturas)
    for parte in _partes(r_an.get('Detalle_Cambio')):
        m = re.search(r'Ajuste Par Direccional: retirar también Pos (\d+) \(([\d.]+) mm\)', parte)
        if m:
            agregar('retiro', 'Ajuste par direccional', '#DC2626', m.group(1),
                    f"La pareja direccional sale por retiro; la Pos {m.group(1)} ({m.group(2)} mm) quedaría con altura distinta.",
                    f"Retirar también la Pos {m.group(1)} y enviarla a Bodega 2 (Recambio) para montar un par parejo.")

    # Cruces con Bodega 2 y emparejamiento de duales
    for parte in _partes(r_an.get('Recomendaciones_Dual')):
        m_b2 = re.search(r'Desmontar Pos (\d+) \(([\d.]+) mm\) y MONTAR llanta N° (\S+) \(([\d.]+) mm\)', parte)
        m_emp = re.search(r'Pos (\d+) en retiro \(([\d.]+) mm\) vs Pos (\d+) \(([\d.]+) mm\).*?entre ([\d.]+) y ([\d.]+) mm', parte)
        if m_b2:
            agregar('retiro', 'Reemplazo desde bodega', '#047857', m_b2.group(1),
                    f"El dual quedaría desparejo con la llanta actual ({m_b2.group(2)} mm).",
                    f"Desmontar la Pos {m_b2.group(1)} y montar la llanta N.º {m_b2.group(3)} ({m_b2.group(4)} mm) disponible en Bodega 2 (Recambio).")
        elif m_emp:
            agregar('retiro', 'Emparejamiento de dual', '#4338CA', m_emp.group(1),
                    f"La Pos {m_emp.group(1)} sale por retiro ({m_emp.group(2)} mm) y su pareja Pos {m_emp.group(3)} tiene {m_emp.group(4)} mm.",
                    f"Montar en la Pos {m_emp.group(1)} una llanta de {m_emp.group(5)} a {m_emp.group(6)} mm, o cambiar ambas para dejarlas parejas.")
        else:
            agregar('retiro', 'Recomendación de dual', '#4338CA', _posiciones_en(parte), parte, 'Aplicar la recomendación en el taller.')

    # Próximas a cambio (dentro de los 2 mm sobre el límite)
    for parte in _partes(r_an.get('Detalle_Proximas')):
        m = re.search(r'Pos (\d+) \(([\d.]+) mm\)', parte)
        if m:
            agregar('proximas', 'Próxima a cambio', '#D97706', m.group(1),
                    f"Remanente de {m.group(2)} mm, a menos de 2 mm del límite de retiro ({limite_retiro} mm).",
                    "Programar cambio o reencauche y volver a medir en 15 a 30 días.")

    # Auto-ajuste: cruces e inversiones de posiciones
    for parte in _partes(r_an.get('Detalle_Auto_Ajuste')):
        instruccion = parte.split(':', 1)[1].strip() if ':' in parte else parte
        if 'Dirección' in parte:
            motivo = "La llanta derecha del eje direccional tiene más remanente que la izquierda."
        elif 'Pacha' in parte:
            motivo = "En el dual, la llanta interior tiene más remanente que la exterior."
        else:
            motivo = "La altura de las llantas no respeta la jerarquía de ejes del tráiler."
        agregar('rotacion', 'Auto-ajuste de posiciones', '#1D4ED8', _posiciones_en(instruccion), motivo, instruccion + '.')

    for parte in _partes(r_an.get('Detalle_Rotacion_Equis')):
        m = re.search(r'^(Cruzar .*?) \(dif entre ejes ([\d.]+) mm\)', parte)
        if m:
            agregar('rotacion', 'Rotación entre ejes', '#1D4ED8', 'Tracción',
                    f"Diferencia de {m.group(2)} mm entre los ejes de tracción.", m.group(1) + '.')

    for parte in _partes(r_an.get('Detalle_Rotacion_Irregular')):
        m = re.search(r'Pos (\d+) \(dif ext/int ([\d.]+) mm\)', parte)
        detalle = (f"Diferencia de {m.group(2)} mm entre el hombro exterior y el interior." if m
                   else "El inspector reportó desgaste irregular.")
        agregar('rotacion', 'Desgaste irregular', '#1D4ED8', _posiciones_en(parte), detalle,
                "Rotar la llanta y revisar alineación y suspensión de esa posición.")

    for parte in _partes(r_an.get('Detalle_Rotacion_Escalonado')):
        agregar('rotacion', 'Desgaste escalonado', '#1D4ED8', _posiciones_en(parte),
                "Desgaste en diente de sierra en el eje de tracción.",
                "Rotar la llanta y revisar amortiguadores y balanceo.")

    # Presión fuera de rango
    for parte in _partes(r_an.get('Detalle_Calibracion_PSI')):
        # Formato del motor: "Pos 6 (84 PSI, baja; objetivo 100)" (objetivo según el eje y el cliente)
        m = re.search(r'Pos (\d+) \((\d+) PSI, (alta|baja)(?:; objetivo (\d+))?\)', parte)
        objetivo = m.group(4) if (m and m.group(4)) else str(PSI_OBJETIVO)
        if m and m.group(3) == 'alta':
            agregar('presion', 'Presión alta', '#0284C7', m.group(1),
                    f"{m.group(2)} PSI, por encima del rango del eje (objetivo {objetivo} PSI).",
                    f"Ajustar a {objetivo} PSI en frío.")
        elif m:
            agregar('presion', 'Presión baja', '#0284C7', m.group(1),
                    f"{m.group(2)} PSI, por debajo del rango del eje (objetivo {objetivo} PSI).",
                    f"Inflar a {objetivo} PSI en frío y revisar válvula y posibles fugas.")
        else:
            agregar('presion', 'Presión baja', '#0284C7', _posiciones_en(parte),
                    "El inspector reportó baja presión.",
                    "Medir e inflar a la presión objetivo del eje en frío y revisar válvula y posibles fugas.")

    return filas


def ordenar_por_grupo(alertas):
    """Ordena las alertas según GRUPOS_DIAGNOSTICO conservando el orden interno de cada grupo."""
    orden = {g: i for i, (g, _) in enumerate(GRUPOS_DIAGNOSTICO)}
    return sorted(alertas, key=lambda a: orden.get(a.get('grupo'), len(orden)))


ABREV_EJE = {'DIRECCIONAL': 'Dir', 'TRACCIÓN': 'Trac', 'LIBRE': 'Libre', 'REPUESTO': 'Rep'}


def minima_por_eje(filas) -> list:
    """[(eje, mínima, límite)] en orden de eje: la llanta más crítica de cada tipo de eje."""
    res = []
    for eje in ('DIRECCIONAL', 'TRACCIÓN', 'LIBRE', 'REPUESTO'):
        del_eje = [f for f in filas if f.get('eje') == eje and (f.get('p_min') or 0) > 0]
        if del_eje:
            critica = min(del_eje, key=lambda f: f['p_min'])
            res.append((eje, critica['p_min'], critica.get('limite_retiro')))
    return res


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

    limite_retiro = database.obtener_limite_retiro_cliente(cliente, subcliente) or 3.0

    # Límite de cada llanta según el eje de su posición (reglas por eje de Catálogos)
    lim_posicion = database.construir_resolver_limite_posicion()
    posiciones_veh = [int(f.get('posicion', 0) or 0) for f in filas]
    limites_por_eje = {}
    for f in filas:
        pos_f = int(f.get('posicion', 0) or 0)
        f['limite_retiro'] = lim_posicion(cliente, subcliente, tipologia, pos_f, posiciones_veh)
        f['eje'] = lim_posicion.tipo_eje(tipologia, pos_f, posiciones_veh)
        limites_por_eje.setdefault(f['eje'].capitalize(), f['limite_retiro'])
    # Texto del límite: uno solo si todos los ejes usan el mismo, o el detalle por eje
    if len(set(limites_por_eje.values())) <= 1:
        texto_limite = f"{format_num_es(next(iter(limites_por_eje.values()), limite_retiro))} mm"
    else:
        texto_limite = ", ".join(f"{eje.lower()} {format_num_es(v)} mm" for eje, v in limites_por_eje.items())

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
        if p_m is not None and p_m <= f['limite_retiro']:
            llantas_cambio.append((p, p_m, f['limite_retiro']))
    n_cambios = len(llantas_cambio)

    if n_cambios > 3:
        # Agrupación inteligente de alertas de cambio cuando son más de 3
        pos_cambio_str = ", ".join(str(p) for p, _, _ in llantas_cambio)
        pos_detalles = ", ".join(f"Posición {p}" for p, _, _ in llantas_cambio)
        alertas_lista.append({
            'grupo': 'retiro',
            'tipo': 'Cambio',
            'tipo_color': '#DC2626',
            'posicion': pos_cambio_str,
            'detalle': f"Retirar llantas en {pos_detalles} (remanente en o bajo el límite: {texto_limite}).",
            'accion': 'Retirar las llantas de estas posiciones y programar su cambio.'
        })
    else:
        for p, p_m, lim_p in llantas_cambio:
            alertas_lista.append({
                'grupo': 'retiro',
                'tipo': 'Cambio',
                'tipo_color': '#DC2626',
                'posicion': str(p),
                'detalle': f"Retirar llanta en Posición {p} (remanente {format_num_es(p_m)} mm <= {format_num_es(lim_p)} mm de límite).",
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

            es_trailer_tip = ('trailer' in tipologia.lower() or 'remolque' in tipologia.lower() or 'semirremolque' in tipologia.lower())
            tipo_ali = 'Alineación (Trailer / Eje libre)' if es_trailer_tip else 'Alineación Direccional'
            accion_ali = 'Alinear ejes de remolque y verificar bujes/tensores de suspensión.' if es_trailer_tip else 'Alinear y balancear eje direccional.'
            detalle_ali_fmt = f"{decimales_es(det_ali)} (desgaste irregular entre hombros en {'ejes de trailer / eje libre' if es_trailer_tip else 'eje direccional'})"

            alertas_lista.append({
                'grupo': 'geometria',
                'tipo': tipo_ali,
                'tipo_color': '#D97706',
                'posicion': pos_ali,
                'detalle': detalle_ali_fmt,
                'accion': accion_ali
            })
        if r_an.get('Plan_Dual_Mal_Apareado') == 'SÍ':
            alertas_lista.append({
                'grupo': 'geometria',
                'tipo': 'Dual mal apareado',
                'tipo_color': '#D97706',
                'posicion': 'Duales',
                'detalle': decimales_es(str(r_an.get('Detalle_Dual', 'Diferencia en conjunto dual mayor al umbral permitido.'))),
                'accion': 'Rotar y aparear.'
            })

    # 3. Novedades mecánicas registradas (filtrando observaciones benignas)
    for f in filas:
        nov = str(f.get('novedades') or '').strip()
        if es_novedad_alerta(nov):
            alertas_lista.append({
                'grupo': 'novedades',
                'tipo': 'Novedad mecánica',
                'tipo_color': '#D97706',
                'posicion': str(f.get('posicion')),
                'detalle': nov,
                'accion': 'Revisar componente y corregir condición.'
            })

    # 4. Alerta de Dimensiones Heterogéneas en el Vehículo (No recomendado)
    dims_map = {}
    for f in filas:
        p_n = int(f.get('posicion', 0))
        d_val = str(f.get('dimension') or '').strip().upper()
        if d_val and d_val not in ('NAN', 'NONE', '-', 'NULL', '0'):
            dims_map.setdefault(d_val, []).append(p_n)

    tiene_dims_distintas = len(dims_map) > 1
    if tiene_dims_distintas:
        partes_d = [f"{dim} (Pos {', '.join(str(p) for p in sorted(pos_list))})" for dim, pos_list in sorted(dims_map.items())]
        alertas_lista.append({
            'grupo': 'vehiculo',
            'tipo': 'Dimensiones mixtas',
            'tipo_color': '#DC2626',
            'posicion': 'Vehículo',
            'detalle': f"El vehículo monta llantas con diferentes dimensiones instaladas: {'; '.join(partes_d)}. No es recomendado mezclar dimensiones en una misma unidad ya que altera los radios de giro, desbalancea la carga y desgasta prematuramente componentes mecánicos.",
            'accion': 'Estandarizar todas las posiciones a una sola dimensión homologada según ficha técnica.'
        })

    # 5. Resto del plan del motor de diagnóstico: reemplazos, emparejamiento, auto-ajuste,
    #    rotaciones, presión y próximas a cambio (antes no salían en el informe)
    if not df_analisis.empty:
        alertas_lista.extend(recomendaciones_motor(df_analisis.iloc[0], limite_retiro))
    alertas_lista = ordenar_por_grupo(alertas_lista)

    n_ali = sum(1 for a in alertas_lista if 'Alineación' in a['tipo'])
    n_duales = sum(1 for a in alertas_lista if a['tipo'] == 'Dual mal apareado')
    n_nov = sum(1 for a in alertas_lista if a['tipo'] == 'Novedad mecánica')
    n_dims = sum(1 for a in alertas_lista if a['tipo'] == 'Dimensiones mixtas')
    n_otras = sum(1 for a in alertas_lista if a['grupo'] in ('retiro', 'proximas', 'rotacion', 'presion') and a['tipo'] != 'Cambio')
    # Los cambios cuentan por llanta aunque se agrupen en una sola fila
    total_alertas = n_cambios + n_ali + n_duales + n_nov + n_dims + n_otras

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
        'texto_limite': texto_limite,
        'esquema': esquema,
        'filas': filas,
        'total_auditadas': total_auditadas,
        'total_posiciones': total_posiciones,
        'posiciones_pendientes': posiciones_pendientes,
        'p_min_global': p_min_global,
        'pos_min_global': pos_min_global,
        'p_prom_global': p_prom_global,
        'minima_por_eje': minima_por_eje(filas),
        'alertas_lista': alertas_lista,
        'n_cambios': n_cambios,
        'n_ali': n_ali,
        'n_duales': n_duales,
        'n_nov': n_nov,
        'n_dims': n_dims,
        'n_otras': n_otras,
        'tiene_dims_distintas': tiene_dims_distintas,
        'dims_map': dims_map,
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
    texto_limite = datos.get('texto_limite') or f"{format_num_es(limite_retiro)} mm"
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
        [celda_meta("FECHA DE INSPECCIÓN", fecha_insp_fmt), celda_meta("INSPECTOR", inspector_nombre), celda_meta("LÍMITE DE RETIRO DEL CLIENTE", texto_limite)]
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
    # Mínima por eje (la llanta más crítica de cada eje) en lugar del promedio de mínimas
    partes_eje = []
    for eje, minima, lim_e in datos.get('minima_por_eje', []):
        color_e = '#DC2626' if (lim_e is not None and minima <= lim_e) else '#0F172A'
        partes_eje.append(f"<font color='{color_e}'>{ABREV_EJE.get(eje, eje)} {format_num_es(minima)}</font>")
    txt_prom_glo = " · ".join(partes_eje) if partes_eje else "—"
    # Desglose por grupo, solo con los grupos que tienen alertas
    conteo_grupo = {}
    for a in alertas_lista:
        conteo_grupo[a['grupo']] = conteo_grupo.get(a['grupo'], 0) + 1
    conteo_grupo['retiro'] = conteo_grupo.get('retiro', 0) + n_cambios - sum(1 for a in alertas_lista if a['tipo'] == 'Cambio')
    etiquetas_grupo = {'retiro': 'retiro/reemplazo', 'proximas': 'próximas', 'geometria': 'alineación/duales',
                       'rotacion': 'rotaciones', 'presion': 'presión', 'novedades': 'novedades', 'vehiculo': 'configuración'}
    partes_desglose = [f"{conteo_grupo[g]} {etiquetas_grupo[g]}" for g, _ in GRUPOS_DIAGNOSTICO if conteo_grupo.get(g)]
    desglose_alertas_txt = "Alertas: " + (", ".join(partes_desglose) if partes_desglose else "ninguna")

    data_kpi = [
        [
            Paragraph(f"<font color='#0F172A'><b>{total_auditadas} de {total_posiciones}</b></font>", style_kpi_num),
            Paragraph(f"<font color='{col_kpi_min}'><b>{txt_pmin_glo}</b></font>", style_kpi_num),
            Paragraph(f"<b>{txt_prom_glo}</b>", ParagraphStyle('KpiEje', parent=style_kpi_num, fontSize=9.5 if len(partes_eje) > 2 else 11, leading=13)),
            Paragraph(f"<font color='{col_kpi_alerta}'><b>{total_alertas}</b></font>", style_kpi_num),
        ],
        [
            Paragraph("Posiciones inspeccionadas", style_kpi_lbl),
            Paragraph(f"Profundidad mínima (posición {pos_min_global})", style_kpi_lbl),
            Paragraph("Profundidad mínima por eje (mm)", style_kpi_lbl),
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

    # Filas de título por grupo (retiros, próximas, alineación, rotaciones, presión...)
    style_grupo = ParagraphStyle('GrupoDiag', parent=style_cell_body, fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#0F172A'))
    filas_grupo = []
    nombres_grupo = dict(GRUPOS_DIAGNOSTICO)
    if alertas_lista:
        grupo_actual = None
        for a in alertas_lista:
            if a.get('grupo') != grupo_actual:
                grupo_actual = a.get('grupo')
                filas_grupo.append(len(data_diag))
                n_grupo = sum(1 for x in alertas_lista if x.get('grupo') == grupo_actual)
                data_diag.append([Paragraph(f"{nombres_grupo.get(grupo_actual, 'Otras acciones')} ({n_grupo})", style_grupo), '', '', ''])
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

    t_diag = Table(data_diag, colWidths=[95, 45, 225, 175], repeatRows=1)
    estilo_diag = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]
    for idx in filas_grupo:
        estilo_diag += [
            ('SPAN', (0, idx), (-1, idx)),
            ('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#E2E8F0')),
            ('LINEABOVE', (0, idx), (-1, idx), 0.8, colors.HexColor('#94A3B8')),
        ]
    t_diag.setStyle(TableStyle(estilo_diag))
    elements.append(t_diag)
    elements.append(Spacer(1, 4))

    # =========================================================================
    # SECCIÓN 4: DISTRIBUCIÓN POR EJES (DIAGRAMA CHASIS VECTORIAL)
    # =========================================================================
    tit_chasis = Paragraph("Distribución por ejes", style_sec_tit)
    drawing_chasis = dibujar_diagrama_chasis_reportlab(tipologia, filas, limite_retiro=limite_retiro, width=540, texto_limite=texto_limite)
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

            es_cambio = (p_min is not None and p_min <= (f.get('limite_retiro') or limite_retiro))
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
        obs_lines.append(f"Se recomienda programar el retiro de la(s) llanta(s) en posición {', '.join(pos_cambios)} por encontrarse en o por debajo del límite de retiro ({texto_limite}).")
    if n_ali > 0:
        es_trailer_tip = ('trailer' in tipologia.lower() or 'remolque' in tipologia.lower() or 'semirremolque' in tipologia.lower())
        if es_trailer_tip:
            obs_lines.append("En los ejes del trailer / eje libre se observa una diferencia de desgaste irregular entre hombros (exterior/interior); se sugiere alinear ejes del remolque y verificar bujes y tensores de suspensión.")
        else:
            obs_lines.append("En el eje direccional se observa una diferencia de desgaste entre directores; se sugiere revisar alineación y balanceo preventivo.")
    if n_duales > 0:
        obs_lines.append("En los conjuntos duales se recomienda rotar o aparear llantas para evitar fatiga prematura por diferencia de radio rodante.")
    if n_nov > 0:
        obs_lines.append("Se identificaron novedades mecánicas reportadas; verificar componentes mecánicos asociados.")
    if datos.get('tiene_dims_distintas'):
        dims_str = "; ".join(f"{d} en Pos {', '.join(str(p) for p in sorted(ps))}" for d, ps in sorted(datos.get('dims_map', {}).items()))
        obs_lines.append(f"Se identificó que el vehículo monta llantas con diferentes dimensiones ({dims_str}); esto NO es recomendado técnicamente por los fabricantes, ya que altera las relaciones de giro, sobrecarga componentes de transmisión y suspensión, y provoca desgaste acelerado e irregular. Se sugiere unificar a una única medida homologada.")
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
    <b>Cambio de llanta:</b> la profundidad mínima de una llanta es menor o igual al límite de retiro configurado para el cliente ({texto_limite}).<br/>
    <b>Alineación y geometría de ejes:</b> diferencia de 2,0 mm o más entre la profundidad exterior e interior en llantas direccionales o en ejes de trailer / eje libre.<br/>
    <b>Dual mal apareado:</b> diferencia de más de 2,5 mm entre la profundidad mínima de la llanta interior y la exterior del mismo lado, o dimensiones distintas en el par dual.<br/>
    <b>Dimensiones homogéneas:</b> No se recomienda utilizar llantas de diferentes dimensiones en una misma unidad; deben montarse llantas de medida idéntica por eje y configuración de flota.<br/>
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

def formatear_detalles_alertas_pdf(r, limite_def):
    """
    Genera un texto HTML con viñetas estructuradas y badges temáticos de alta legibilidad,
    evitando bloques monocromáticos rojos y facilitando la rápida interpretación técnica.
    """
    lineas = []

    # 1. Retiro Urgente / Límite
    p_cambio = r.get('Plan_Cambio_Llanta', 'NO')
    cant_cambios = int(r.get('Cant_Cambios', 0) or (1 if p_cambio == 'SÍ' else 0))
    det_camb = str(r.get('Detalle_Cambio', '') or '').strip()
    if p_cambio == 'SÍ' or (det_camb and det_camb != 'OK'):
        txt = det_camb if (det_camb and det_camb != 'OK') else f"Posiciones en o bajo límite ({format_num_es(limite_def)} mm)"
        lineas.append(f"• <b><font color='#b91c1c'>[RETIRO URGENTE]</font></b> <font color='#1e293b'>{txt}</font>")

    # 2. Próximas a Cambio (+2.0 mm)
    cant_prox = int(r.get('Cant_Proximas', 0) or 0)
    det_prox = str(r.get('Detalle_Proximas', '') or '').strip()
    if cant_prox > 0 or (det_prox and det_prox != 'OK'):
        txt = det_prox if (det_prox and det_prox != 'OK') else f"{cant_prox} llantas a monitorear (+2.0 mm)"
        lineas.append(f"• <b><font color='#b45309'>[PRÓXIMO CAMBIO]</font></b> <font color='#1e293b'>{txt}</font>")

    # 3. Alineación
    p_ali = r.get('Plan_Alineacion', 'NO')
    det_ali = str(r.get('Detalle_Alineacion', '') or '').strip()
    tipo_v = str(r.get('Tipo', '') or '').lower()
    is_trailer = ('trailer' in tipo_v or 'remolque' in tipo_v or 'semirremolque' in tipo_v)
    tag_ali = "[ALINEACIÓN TRAILER]" if is_trailer else "[ALINEACIÓN]"
    if p_ali == 'SÍ' or (det_ali and det_ali != 'OK'):
        txt = det_ali if (det_ali and det_ali != 'OK') else "Diferencia exterior vs interior >= 2.0 mm"
        lineas.append(f"• <b><font color='#c2410c'>{tag_ali}</font></b> <font color='#1e293b'>{txt}</font>")

    # 4. Dual Mal Apareado
    p_du = r.get('Plan_Dual_Mal_Apareado', 'NO')
    det_du = str(r.get('Detalle_Dual', '') or '').strip()
    if p_du == 'SÍ' or (det_du and det_du != 'OK'):
        txt = det_du if (det_du and det_du != 'OK') else "Diferencia milimétrica entre gemelas"
        lineas.append(f"• <b><font color='#7e22ce'>[DUAL DESPAREJADO]</font></b> <font color='#1e293b'>{txt}</font>")

    # 5. Dimensiones Heterogéneas en Unidad
    p_dims = r.get('Plan_Dimensiones_Heterogeneas', 'NO')
    det_dims = str(r.get('Detalle_Dimensiones_Heterogeneas', '') or '').strip()
    if p_dims == 'SÍ' or (det_dims and det_dims != 'OK'):
        txt = det_dims.replace(" - No recomendado mezclar", "").replace("No recomendado mezclar dimensiones en la unidad", "Mezcla de medidas no recomendada")
        lineas.append(f"• <b><font color='#92400e'>[DIMS MIXTAS]</font></b> <font color='#1e293b'>{txt}</font>")

    # 6. Cruces de Bodega y Recomendaciones de Duales
    recom_du = str(r.get('Recomendaciones_Dual', '') or '').strip()
    if recom_du and recom_du != 'OK':
        partes_recom = [p.strip() for p in recom_du.split(';') if p.strip()]
        for p_rec in partes_recom:
            if 'cruce bodega' in p_rec.lower():
                txt_b2 = p_rec.replace("Cruce Bodega 2: ", "").replace("Cruce Bodega 2:", "")
                lineas.append(f"• <b><font color='#047857'>[CRUCE BODEGA]</font></b> <font color='#1e293b'>{txt_b2}</font>")
            elif 'en retiro' in p_rec.lower() and 'se recomienda instalar' in p_rec.lower():
                m = re.search(r'Pos\s+(\d+)\s+en retiro.*?vs\s+Pos\s+(\d+).*?entre\s+([\d\.]+)\s+y\s+([\d\.]+)\s+mm', p_rec)
                if m:
                    lineas.append(
                        f"• <b><font color='#4338ca'>[EMPAREJAMIENTO]</font></b> <font color='#1e293b'>Reemplazo de Pos {m.group(1)} (en retiro): "
                        f"montar llanta de {format_num_es(m.group(3))} a {format_num_es(m.group(4))} mm para emparejar con Pos {m.group(2)}</font>"
                    )
                else:
                    lineas.append(f"• <b><font color='#4338ca'>[EMPAREJAMIENTO]</font></b> <font color='#1e293b'>{p_rec}</font>")
            else:
                lineas.append(f"• <b><font color='#475569'>[RECOMENDACIÓN]</font></b> <font color='#1e293b'>{p_rec}</font>")

    # 7. Auto-Ajuste Chasis
    det_auto = str(r.get('Detalle_Auto_Ajuste', '') or '').strip()
    if det_auto and det_auto != 'OK':
        partes_auto = [a.strip() for a in det_auto.split(';') if a.strip()]
        for a_txt in partes_auto:
            lineas.append(f"• <b><font color='#1d4ed8'>[AUTO-AJUSTE]</font></b> <font color='#1e293b'>{a_txt}</font>")

    # 8. Rotación Preventiva (Irregular / Escalonado / Equis)
    det_rot = []
    d_irr = str(r.get('Detalle_Rotacion_Irregular', '') or '').strip()
    d_esc = str(r.get('Detalle_Rotacion_Escalonado', '') or '').strip()
    if r.get('Plan_Rotacion_Irregular') == 'SÍ' and d_irr and d_irr != 'OK':
        det_rot.append(f"Irregular ({d_irr})")
    if r.get('Plan_Rotacion_Escalonado') == 'SÍ' and d_esc and d_esc != 'OK':
        det_rot.append(f"Escalonado ({d_esc})")
    if det_rot:
        lineas.append(f"• <b><font color='#2563eb'>[ROTACIÓN PREVENTIVA]</font></b> <font color='#1e293b'>{'; '.join(det_rot)}</font>")

    # 9. Calibración Presión PSI
    det_psi = str(r.get('Detalle_Calibracion_PSI', '') or '').strip()
    if r.get('Plan_Calibracion_PSI') == 'SÍ' or (det_psi and det_psi != 'OK'):
        txt = det_psi if (det_psi and det_psi != 'OK') else "Ajuste de presión según tabla operativa"
        lineas.append(f"• <b><font color='#0284c7'>[PRESIÓN PSI]</font></b> <font color='#1e293b'>{txt}</font>")

    # 10. Si no hay alertas
    if not lineas:
        lineas.append("• <b><font color='#15803d'>[VEHÍCULO OK]</font></b> <font color='#15803d'>Sin alertas activas en la inspección.</font>")

    return decimales_es("<br/>".join(lineas))

def generar_pdf_consolidado_jornada(cliente=None, subcliente=None, fecha=None, operacion=None, usuario=None, fecha_desde=None, fecha_hasta=None):
    """
    Genera un informe PDF Consolidado de Flota con métricas globales, gráficos de resumen,
    estado de flota por eje y dimensión, y tabla de placas a intervenir.
    """
    df_insp = database.obtener_todas_inspecciones(usuario=usuario, incluir_fotos=False)
    if df_insp.empty:
        raise ValueError("No existen inspecciones registradas en el sistema.")

    if cliente and cliente != 'Todos':
        df_insp = df_insp[df_insp['cliente'].astype(str).str.upper().str.strip() == str(cliente).upper().strip()]
    if subcliente and subcliente != 'Todos':
        df_insp = df_insp[df_insp['subcliente'].astype(str).str.upper().str.strip() == str(subcliente).upper().strip()]
    if operacion and operacion != 'Todos':
        df_insp = df_insp[df_insp['tipo_operacion'].astype(str).str.upper().str.strip() == str(operacion).upper().strip()]
    if fecha and fecha != 'Todos':
        df_insp = df_insp[df_insp['fecha'].astype(str) == str(fecha)]
    else:
        if fecha_desde and fecha_desde != 'Todos':
            df_insp = df_insp[df_insp['fecha'].astype(str).str.slice(0, 10) >= str(fecha_desde)]
        if fecha_hasta and fecha_hasta != 'Todos':
            df_insp = df_insp[df_insp['fecha'].astype(str).str.slice(0, 10) <= str(fecha_hasta)]

    df_insp = database.filtrar_fechas_validas(df_insp)
    if df_insp.empty:
        raise ValueError("No se encontraron inspecciones con los filtros seleccionados.")

    df_analisis = database.analizar_inspecciones_df(df_insp)
    # El semáforo cuenta cada llanta una vez (su última medición del período); antes sumaba todas las inspecciones
    df_insp = df_insp.sort_values(['fecha', 'id'], ascending=[False, False]).drop_duplicates(['placa', 'posicion']).copy()

    # Métricas Globales
    total_vehiculos = df_analisis['Vehículo/Placa'].nunique() if not df_analisis.empty else 0
    total_llantas = len(df_insp)

    limite_def = database.obtener_limite_retiro_cliente(cliente if cliente else '') or 3.0
    
    # Cálculos llanta a llanta con dg.profundidad_minima
    df_insp['p_min'] = df_insp.apply(lambda r: dg.profundidad_minima(r.to_dict()), axis=1)
    lim_posicion = database.construir_resolver_limite_posicion()
    posiciones_placa = df_insp.groupby('placa')['posicion'].apply(lambda x: [int(v or 0) for v in x]).to_dict()
    df_insp['lim_eje'] = df_insp.apply(lambda r: lim_posicion(r.get('cliente'), r.get('subcliente'), r.get('tipologia'),
                                                              int(r.get('posicion') or 0), posiciones_placa.get(r.get('placa'))), axis=1)
    df_insp['eje'] = df_insp.apply(lambda r: lim_posicion.tipo_eje(r.get('tipologia'), int(r.get('posicion') or 0),
                                                                   posiciones_placa.get(r.get('placa'))), axis=1)
    llantas_retiro = len(df_insp[(df_insp['p_min'].notna()) & (df_insp['p_min'] <= df_insp['lim_eje'])])
    llantas_proximo = len(df_insp[(df_insp['p_min'].notna()) & (df_insp['p_min'] > df_insp['lim_eje']) & (df_insp['p_min'] <= df_insp['lim_eje'] + 2.0)])
    llantas_optimas = total_llantas - llantas_retiro - llantas_proximo

    pct_retiro = (llantas_retiro / total_llantas * 100) if total_llantas > 0 else 0
    pct_proximo = (llantas_proximo / total_llantas * 100) if total_llantas > 0 else 0
    pct_optimas = (llantas_optimas / total_llantas * 100) if total_llantas > 0 else 0

    veh_cambio = len(df_analisis[df_analisis['Plan_Cambio_Llanta'] == 'SÍ']) if not df_analisis.empty else 0
    veh_ali = len(df_analisis[df_analisis['Plan_Alineacion'] == 'SÍ']) if not df_analisis.empty else 0
    veh_dual = len(df_analisis[df_analisis['Plan_Dual_Mal_Apareado'] == 'SÍ']) if not df_analisis.empty else 0
    veh_dims = len(df_analisis[df_analisis.get('Plan_Dimensiones_Heterogeneas', 'NO') == 'SÍ']) if not df_analisis.empty else 0
    veh_rot_irr = len(df_analisis[df_analisis.get('Plan_Rotacion_Irregular', 'NO') == 'SÍ']) if not df_analisis.empty else 0
    veh_rot_esc = len(df_analisis[df_analisis.get('Plan_Rotacion_Escalonado', 'NO') == 'SÍ']) if not df_analisis.empty else 0
    veh_psi = len(df_analisis[df_analisis.get('Plan_Calibracion_PSI', 'NO') == 'SÍ']) if not df_analisis.empty else 0

    # Vehículos únicos que presentan al menos una alerta crítica (Cambio, Alineación, Dual o Dimensiones heterogéneas)
    cond_alerta_critica = (
        (df_analisis['Plan_Cambio_Llanta'] == 'SÍ') |
        (df_analisis['Plan_Alineacion'] == 'SÍ') |
        (df_analisis['Plan_Dual_Mal_Apareado'] == 'SÍ') |
        (df_analisis.get('Plan_Dimensiones_Heterogeneas', 'NO') == 'SÍ')
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
    style_cell_center = ParagraphStyle('CellCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=6.5, leading=8, alignment=1, textColor=colors.HexColor('#1e293b'))
    style_cell_detalles = ParagraphStyle('CellDetalles', parent=styles['Normal'], fontName='Helvetica', fontSize=6.5, leading=8.5, textColor=colors.HexColor('#1e293b'))

    elements = []
    elements.append(Spacer(1, 2))

    # Tarjetas Resumen de Flota
    cliente_txt = cliente if cliente and cliente != 'Todos' else 'Consolidado General'
    partes_sede = []
    if subcliente and subcliente != 'Todos':
        partes_sede.append(f"Sede: {subcliente}")
    if operacion and operacion != 'Todos':
        partes_sede.append(f"Operación: {operacion}")
    sub_txt = " · ".join(partes_sede) if partes_sede else "Todas las sedes y operaciones"

    # El período va en su propia línea: antes salía bajo la etiqueta "Sede / Operación"
    if fecha and fecha != 'Todos':
        periodo_txt = formatear_fecha_ddmmyyyy(fecha)
    elif fecha_desde or fecha_hasta:
        periodo_txt = f"{formatear_fecha_ddmmyyyy(fecha_desde) or 'Inicio'} al {formatear_fecha_ddmmyyyy(fecha_hasta) or 'Hoy'}"
    else:
        periodo_txt = "Histórico general"

    res_box = [
        [
            Paragraph(f"<b>Cliente / Flota:</b> {cliente_txt}", style_subtitulo),
            Paragraph(f"<b>Sede / Operación:</b> {sub_txt}<br/><b>Período:</b> {periodo_txt}", style_subtitulo),
            Paragraph(f"<b>Límite Retiro Aplicado:</b> {format_num_es(limite_def)} mm", style_subtitulo)
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
            Paragraph(f"{punto_color('#dc2626')} <b>Retiro Urgente (≤ Límite)</b>", style_cell_alert),
            Paragraph(f"<b>{llantas_retiro}</b>", style_cell_alert),
            Paragraph(f"<b>{format_num_es(pct_retiro)}%</b>", style_cell_alert),
            Paragraph("Programar desmontaje inmediato para proteger la llanta reencauchable y evitar incidentes viales.", style_cell_body)
        ],
        [
            Paragraph(f"{punto_color('#d97706')} <b>Próximo a Cambio (+2,0 mm)</b>", style_cell_body),
            Paragraph(f"<b>{llantas_proximo}</b>", style_cell_body),
            Paragraph(f"<b>{format_num_es(pct_proximo)}%</b>", style_cell_body),
            Paragraph("Monitorear en 15 a 30 días y alistar stock de reemplazo o reencauche.", style_cell_body)
        ],
        [
            Paragraph(f"{punto_color('#16a34a')} <b>Condición Normal / Óptima</b>", style_cell_body),
            Paragraph(f"<b>{llantas_optimas}</b>", style_cell_body),
            Paragraph(f"<b>{format_num_es(pct_optimas)}%</b>", style_cell_body),
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

    # 2. ESTADO POR EJE: cada eje con su límite asignado y su llanta más crítica (mínima)
    elements.append(Paragraph("2. Estado por Eje", style_seccion))
    filas_eje = [[Paragraph(f"<b>{t}</b>", style_cell_header) for t in
                  ("EJE", "LLANTAS", "EN RETIRO", "PRÓXIMAS", "MÍNIMA (LLANTA MÁS CRÍTICA)", "LÍMITE APLICADO")]]
    nombres_eje = {'DIRECCIONAL': 'Direccional', 'TRACCIÓN': 'Tracción', 'LIBRE': 'Libre / Arrastre', 'REPUESTO': 'Repuesto', 'TODOS': 'Sin eje definido'}
    for eje_k in ('DIRECCIONAL', 'TRACCIÓN', 'LIBRE', 'REPUESTO', 'TODOS'):
        d_e = df_insp[df_insp['eje'] == eje_k]
        if d_e.empty:
            continue
        medidas = d_e[d_e['p_min'].notna() & (d_e['p_min'] > 0)]
        en_retiro = int((medidas['p_min'] <= medidas['lim_eje']).sum())
        proximas = int(((medidas['p_min'] > medidas['lim_eje']) & (medidas['p_min'] <= medidas['lim_eje'] + 2.0)).sum())
        if not medidas.empty:
            critica = medidas.loc[medidas['p_min'].idxmin()]
            txt_min = f"{format_num_es(critica['p_min'])} mm · {critica['placa']} Pos {int(critica['posicion'])}"
        else:
            txt_min = "—"
        lims = sorted(set(round(float(v), 1) for v in d_e['lim_eje']))
        txt_lim = f"{format_num_es(lims[0])} mm" if len(lims) == 1 else f"{format_num_es(lims[0])} a {format_num_es(lims[-1])} mm"
        filas_eje.append([
            Paragraph(f"<b>{nombres_eje[eje_k]}</b>", style_cell_body),
            Paragraph(str(len(d_e)), style_cell_body),
            Paragraph(f"<b>{en_retiro}</b>", style_cell_alert if en_retiro else style_cell_body),
            Paragraph(str(proximas), style_cell_body),
            Paragraph(txt_min, style_cell_alert if en_retiro else style_cell_body),
            Paragraph(txt_lim, style_cell_body),
        ])
    t_ejes = Table(filas_eje, colWidths=[95, 50, 60, 60, 175, 100])
    t_ejes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_ejes)
    elements.append(Spacer(1, 8))

    # 3. PLANES DE ACCIÓN REQUERIDOS EN LA FLOTA
    elements.append(Paragraph("3. Resumen Consolidado de Planes de Acción y Novedades", style_seccion))
    planes_data = [
        [
            Paragraph("<b>PLAN DE ACCIÓN TÉCNICO</b>", style_cell_header),
            Paragraph("<b>VEHÍCULOS AFECTADOS</b>", style_cell_header),
            Paragraph("<b>DETALLE Y ALCANCE OPERATIVO</b>", style_cell_header)
        ],
        [
            Paragraph("<b>Sugerencia Retiro / Cambio</b>", style_cell_body),
            Paragraph(f"<b>{veh_cambio}</b>", style_cell_alert if veh_cambio > 0 else style_cell_body),
            Paragraph(f"Vehículos con al menos una llanta en o por debajo de {format_num_es(limite_def)} mm.", style_cell_body)
        ],
        [
            Paragraph("<b>Alineación y Geometría de Ejes</b>", style_cell_body),
            Paragraph(f"<b>{veh_ali}</b>", style_cell_alert if veh_ali > 0 else style_cell_body),
            Paragraph("Vehículos con diferencia entre exterior e interior ≥ 2,0 mm en llantas direccionales o en ejes de trailer / eje libre.", style_cell_body)
        ],
        [
            Paragraph("<b>Emparejamiento / Dual Mal Apareado</b>", style_cell_body),
            Paragraph(f"<b>{veh_dual}</b>", style_cell_alert if veh_dual > 0 else style_cell_body),
            Paragraph("Vehículos con duales que superan 2,5 mm de diferencia o con dimensiones distintas en el par.", style_cell_body)
        ],
        [
            Paragraph("<b>Dimensiones Heterogéneas en Unidad</b>", style_cell_body),
            Paragraph(f"<b>{veh_dims}</b>", style_cell_alert if veh_dims > 0 else style_cell_body),
            Paragraph("Vehículos con diferentes dimensiones de llantas montadas en la misma unidad (no recomendado).", style_cell_body)
        ],
        [
            Paragraph("<b>Rotación por Desgaste Irregular</b>", style_cell_body),
            Paragraph(f"<b>{veh_rot_irr}</b>", style_cell_alert if veh_rot_irr > 0 else style_cell_body),
            Paragraph("Vehículos con llantas de tracción o eje libre con desgaste irregular o disparejo.", style_cell_body)
        ],
        [
            Paragraph("<b>Rotación por Desgaste Escalonado</b>", style_cell_body),
            Paragraph(f"<b>{veh_rot_esc}</b>", style_cell_alert if veh_rot_esc > 0 else style_cell_body),
            Paragraph("Vehículos con llantas con diente de sierra / desgaste escalonado en eje de tracción.", style_cell_body)
        ],
        [
            Paragraph("<b>Calibración de Presión de Aire</b>", style_cell_body),
            Paragraph(f"<b>{veh_psi}</b>", style_cell_alert if veh_psi > 0 else style_cell_body),
            Paragraph("Vehículos con alguna llanta fuera de la tolerancia de la presión objetivo de su eje (baja o alta) o con baja presión reportada.", style_cell_body)
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

    # 3. LISTADO DETALLADO DE VEHÍCULOS Y PLANES DE ACCIÓN
    elements.append(Paragraph(f"4. Detalle de Vehículos y Planes de Acción de Mantenimiento ({total_vehiculos} Unidades)", style_seccion))
    matriz_data = [
        [
            Paragraph("<b>Vehículo</b>", style_cell_header),
            Paragraph("<b>Tipología / Sede</b>", style_cell_header),
            Paragraph("<b>Llantas</b>", style_cell_header),
            Paragraph("<b>Cambio YA</b>", style_cell_header),
            Paragraph("<b>Próximas</b>", style_cell_header),
            Paragraph("<b>Alinear</b>", style_cell_header),
            Paragraph("<b>Dual</b>", style_cell_header),
            Paragraph("<b>Rotación</b>", style_cell_header),
            Paragraph("<b>Detalles de Alertas & Planes de Acción</b>", style_cell_header)
        ]
    ]

    for _, r in df_analisis.iterrows():
        p_cambio = r.get('Plan_Cambio_Llanta', 'NO')
        p_ali = r.get('Plan_Alineacion', 'NO')
        p_du = r.get('Plan_Dual_Mal_Apareado', 'NO')
        p_dims = r.get('Plan_Dimensiones_Heterogeneas', 'NO')
        p_rot = r.get('Plan_Rotacion', "SÍ" if (r.get('Plan_Rotacion_Irregular') == 'SÍ' or r.get('Plan_Rotacion_Escalonado') == 'SÍ') else "NO")
        badge_rot = r.get('Badge_Rotacion', 'SÍ' if p_rot == 'SÍ' else 'OK')

        cant_cambios = int(r.get('Cant_Cambios', 0) or (1 if p_cambio == 'SÍ' else 0))
        cant_prox = int(r.get('Cant_Proximas', 0) or 0)

        tipo_v = str(r.get('Tipo', '') or '').strip()

        # Generar detalles estructurados y con badges temáticos coloreados (texto en grafito oscuro)
        texto_detalles_html = formatear_detalles_alertas_pdf(r, limite_def)

        # Formateo Celda 1: Placa + Fecha + Km
        placa_txt = str(r.get('Vehículo/Placa', '') or '')
        fecha_txt = str(r.get('Fecha', '') or '')
        km_val = r.get('Km', 0)
        partes_veh = [f"<b>{placa_txt}</b>"]
        if fecha_txt:
            partes_veh.append(f"<font color='#64748b' size=5.5>{formatear_fecha_ddmmyyyy(fecha_txt)}</font>")
        try:
            km_num = float(km_val)
            if km_num > 0:
                partes_veh.append(f"<font color='#94a3b8' size=5.5>{format_miles_es(km_num)} km</font>")
        except Exception:
            pass
        celda_veh_html = "<br/>".join(partes_veh)

        # Formateo Celda 2: Tipología + Sede / Operación
        sede_val = str(r.get('Subcliente', '') or '').strip()
        op_val = str(r.get('Operación', '') or '').strip()
        partes_tipo = []
        if tipo_v and tipo_v.lower() not in ('nan', 'none', '-'):
            partes_tipo.append(f"<b>{tipo_v}</b>")
        if sede_val and sede_val.lower() not in ('nan', 'none', '-'):
            partes_tipo.append(f"<font color='#475569' size=5.5>{sede_val}</font>")
        if op_val and op_val.lower() not in ('nan', 'none', '-'):
            partes_tipo.append(f"<font color='#94a3b8' size=5>{op_val}</font>")
        celda_tipo_html = "<br/>".join(partes_tipo) if partes_tipo else "-"

        # Formateo Celdas de Acción
        llantas_num = str(r.get('Llantas Inspeccionadas', '') or '')
        cambio_html = f"<font color='#b91c1c'><b>URGENTE<br/>({cant_cambios})</b></font>" if cant_cambios > 0 else "<font color='#15803d'>OK</font>"
        proximas_html = f"<font color='#b45309'><b>PRÓXIMA<br/>({cant_prox})</b></font>" if cant_prox > 0 else "<font color='#94a3b8'>0</font>"
        ali_html = "<font color='#c2410c'><b>SÍ</b></font>" if p_ali == 'SÍ' else "<font color='#15803d'>OK</font>"
        dual_html = "<font color='#7e22ce'><b>SÍ</b></font>" if p_du == 'SÍ' else "<font color='#15803d'>OK</font>"
        if badge_rot == 'AUTO-AJUSTE':
            rot_html = "<font color='#4338ca'><b>AUTO-AJUSTE</b></font>"
        elif p_rot == 'SÍ':
            rot_html = "<font color='#1d4ed8'><b>SÍ</b></font>"
        else:
            rot_html = "<font color='#15803d'>OK</font>"

        matriz_data.append([
            Paragraph(celda_veh_html, style_cell_body),
            Paragraph(celda_tipo_html, style_cell_body),
            Paragraph(f"<b>{llantas_num}</b>", style_cell_center),
            Paragraph(cambio_html, style_cell_center),
            Paragraph(proximas_html, style_cell_center),
            Paragraph(ali_html, style_cell_center),
            Paragraph(dual_html, style_cell_center),
            Paragraph(rot_html, style_cell_center),
            Paragraph(texto_detalles_html, style_cell_detalles)
        ])

    t_matriz = Table(matriz_data, colWidths=[50, 58, 24, 34, 34, 30, 28, 34, 248], repeatRows=1)
    table_style_commands = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 2.5),
        ('RIGHTPADDING', (0,0), (-1,-1), 2.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]
    for idx_fila, r in enumerate(df_analisis.to_dict('records'), start=1):
        c_camb = int(r.get('Cant_Cambios', 0) or (1 if r.get('Plan_Cambio_Llanta') == 'SÍ' else 0))
        if c_camb > 0:
            table_style_commands.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#fff1f2')))
        elif idx_fila % 2 == 0:
            table_style_commands.append(('BACKGROUND', (0, idx_fila), (-1, idx_fila), colors.HexColor('#f8fafc')))
    t_matriz.setStyle(TableStyle(table_style_commands))
    elements.append(t_matriz)
    elements.append(Spacer(1, 14))

    # 4. MATRIZ DE SEMÁFOROS POR POSICIÓN (POLÍTICA DE RETIRO POR CLIENTE, SEDE Y EJE)
    matriz_pos = database.calcular_matriz_semaforos_posicion(df_insp)
    if matriz_pos and matriz_pos.get('filas'):
        elements.append(Paragraph("5. Matriz de Semáforos por Posición (Desgaste vs Política Técnica)", style_seccion))
        leyenda_sem = (
            "<b>Umbrales Técnicos por Eje:</b> "
            f"{punto_color('#dc2626')} <font color='#b91c1c'><b>Retiro Inmediato (PB ≤ Límite)</b></font> · "
            f"{punto_color('#d97706')} <font color='#b45309'><b>Próxima a Cambio (+2,0 mm)</b></font> · "
            f"{punto_color('#16a34a')} <font color='#15803d'><b>Estado Óptimo (&gt; Límite + 2 mm)</b></font> · "
            f"{punto_color('#94a3b8')} <font color='#64748b'><b>Sin Datos (PB ≤ 0)</b></font>"
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
        hdr_row.append(Paragraph("<b>Retiro / Próx. / Ópt.</b>", style_sem_hdr))
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
                    pb_str = format_num_es(pb_val) if pb_val > 0 else "0,0"
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
            Paragraph("<font color='#475569'><b>Ret. / Próx. / Ópt.</b></font>", style_sem_text)
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
    canvas_maker = obtener_canvas_consolidado_flota(periodo_txt, cliente_canvas)
    doc.build(elements, canvasmaker=canvas_maker)
    buffer.seek(0)
    return buffer.getvalue()


# =============================================================================
# REPORTES PDF: DESPACHO A PLANTA Y ACTA DE CHATARRIZACIÓN FVU
# =============================================================================

def generar_pdf_despacho_planta(datos: dict) -> bytes:
    """
    Genera la Planilla Oficial de Despacho de Carcasas a Planta Renovadora (Bodega 3 -> Bodega 4).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DispatchTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0f172a'),
        alignment=1
    )
    sub_style = ParagraphStyle(
        'DispatchSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    th_style = ParagraphStyle(
        'DispatchTH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1
    )
    td_style = ParagraphStyle(
        'DispatchTD',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )
    td_center = ParagraphStyle(
        'DispatchTDC',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1e293b'),
        alignment=1
    )

    elements = []

    # Encabezado
    guia = datos.get('guia_remision', 'GUIA-SIN-NUMERO')
    cliente = datos.get('cliente', 'CLIENTE GENERAL')
    proveedor = datos.get('proveedor_planta', 'Planta Renovadora')
    transportador = datos.get('transportador', 'Transporte Propio')
    fecha_envio = datos.get('fecha_envio', datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d'))
    fecha_comp = datos.get('fecha_compromiso', 'Por definir')

    elements.append(Paragraph("<b>TIREANALYZE PRO — GESTIÓN TÉCNICA DE FLOTAS</b>", sub_style))
    elements.append(Paragraph("<b>ORDEN DE DESPACHO A PLANTA RENOVADORA</b>", title_style))
    elements.append(Paragraph(f"Guía Oficial de Custodia: <b>{guia}</b> | Fecha de Envío: <b>{fecha_envio}</b>", sub_style))
    elements.append(Spacer(1, 14))

    # Metadatos del envío
    info_data = [
        [
            Paragraph(f"<b>Cliente / Flota:</b> {cliente}", td_style),
            Paragraph(f"<b>Planta Reencauchadora:</b> {proveedor}", td_style)
        ],
        [
            Paragraph(f"<b>Transportador:</b> {transportador}", td_style),
            Paragraph(f"<b>Fecha Compromiso Entrega:</b> {fecha_comp}", td_style)
        ]
    ]
    t_info = Table(info_data, colWidths=[270, 270])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 14))

    # Tabla de Llantas Despachadas
    llantas = datos.get('llantas', [])
    rows = [
        [
            Paragraph("<b>#</b>", th_style),
            Paragraph("<b>No. Interno</b>", th_style),
            Paragraph("<b>Marca / Carcasa</b>", th_style),
            Paragraph("<b>Diseño Orig.</b>", th_style),
            Paragraph("<b>Dimensión</b>", th_style),
            Paragraph("<b>Prof. Actual</b>", th_style),
            Paragraph("<b>Ciclo</b>", th_style),
            Paragraph("<b>Observaciones / Banda Sugerida</b>", th_style)
        ]
    ]

    for idx, item in enumerate(llantas, 1):
        num = item.get('numero_interno', '')
        marca = item.get('marca_origen') or item.get('marca', '')
        diseno = item.get('diseno_origen') or item.get('diseno', '')
        dim = item.get('dimension', '295/80R22.5')
        p_act = item.get('prof_actual_min', 0.0)
        ciclo = item.get('ciclo_actual', 1)
        obs = item.get('observaciones', 'Inspección de carcasa OK')

        rows.append([
            Paragraph(str(idx), td_center),
            Paragraph(f"<b>{num}</b>", td_center),
            Paragraph(str(marca), td_style),
            Paragraph(str(diseno), td_style),
            Paragraph(str(dim), td_center),
            Paragraph(f"{float(p_act):.1f} mm", td_center),
            Paragraph(f"R{ciclo-1}" if ciclo > 1 else "Orig.", td_center),
            Paragraph(str(obs), td_style)
        ])

    if len(rows) == 1:
        rows.append([Paragraph("No se seleccionaron llantas", td_style)] * 8)

    t_llantas = Table(rows, colWidths=[24, 75, 75, 75, 75, 55, 45, 116])
    t_llantas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_llantas)
    elements.append(Spacer(1, 24))

    # Firmas de Entrega y Recepción
    firmas = [
        [
            Paragraph("______________________________________<br/><b>Entregado por (Patio / Taller)</b><br/>Nombre:<br/>C.C.:", td_style),
            Paragraph("______________________________________<br/><b>Transportador / Custodia</b><br/>Nombre:<br/>C.C. / Placa:", td_style),
            Paragraph("______________________________________<br/><b>Recibido en Planta Reencauchadora</b><br/>Firma y Sello:<br/>Fecha:", td_style)
        ]
    ]
    t_firmas = Table(firmas, colWidths=[180, 180, 180])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 8)
    ]))
    elements.append(KeepTogether(t_firmas))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generar_pdf_acta_chatarrizacion(datos: dict) -> bytes:
    """
    Genera el Acta Oficial de Chatarrización y Disposición Final (FVU - Bodega 7).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ActaTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#b91c1c'),
        alignment=1
    )
    sub_style = ParagraphStyle(
        'ActaSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    td_style = ParagraphStyle(
        'ActaTD',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b')
    )
    alert_box_style = ParagraphStyle(
        'ActaAlert',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#991b1b'),
        alignment=1
    )

    elements = []

    num = datos.get('numero_interno', 'S/N')
    cliente = datos.get('cliente', 'CLIENTE GENERAL')
    acta = datos.get('numero_acta', f"ACTA-FVU-{datetime.now(BOGOTA_TZ).strftime('%Y%m')}-{num}")
    fecha = datos.get('fecha_baja', datetime.now(BOGOTA_TZ).strftime('%Y-%m-%d'))
    marca = datos.get('marca', 'GENERICA')
    diseno = datos.get('diseno', 'ESTANDAR')
    dim = datos.get('dimension', '295/80R22.5')
    prof_ret = float(datos.get('prof_retiro', 0.0))
    lim_ret = float(datos.get('limite_retiro', 3.0))
    mm_desp = float(datos.get('mm_desperdiciados', 0.0))
    dinero_perd = float(datos.get('dinero_perdido', 0.0))
    motivo = datos.get('motivo_baja', 'Desgaste Irregular / Falla de Carcasa')

    elements.append(Paragraph("<b>TIREANALYZE PRO — GESTIÓN TÉCNICA Y AUDITORÍA DE FLOTAS</b>", sub_style))
    elements.append(Paragraph("<b>ACTA TÉCNICA DE DISPOSICIÓN FINAL Y CHATARRIZACIÓN (FVU)</b>", title_style))
    elements.append(Paragraph(f"Consecutivo: <b>{acta}</b> | Fecha de Disposición: <b>{fecha}</b>", sub_style))
    elements.append(Spacer(1, 14))

    # Cuadro de Pérdida Financiera
    cuadro_alerta = [
        [
            Paragraph(f"⚠️ AUDITORÍA DE RENDIMIENTO: <b>{mm_desp:.1f} mm Desperdiciados</b> | Pérdida Económica Estimada: <b>${dinero_perd:,.0f} COP</b>", alert_box_style)
        ]
    ]
    t_alert = Table(cuadro_alerta, colWidths=[540])
    t_alert.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fef2f2')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#f87171')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_alert)
    elements.append(Spacer(1, 14))

    # Ficha Técnica
    tabla_datos = [
        [
            Paragraph(f"<b>Cliente Propietario:</b> {cliente}", td_style),
            Paragraph(f"<b>No. Interno / Serial:</b> <b>{num}</b>", td_style)
        ],
        [
            Paragraph(f"<b>Marca Carcasa:</b> {marca}", td_style),
            Paragraph(f"<b>Diseño Original:</b> {diseno}", td_style)
        ],
        [
            Paragraph(f"<b>Dimensión Técnica:</b> {dim}", td_style),
            Paragraph(f"<b>Límite Retiro Flota:</b> {lim_ret:.1f} mm", td_style)
        ],
        [
            Paragraph(f"<b>Profundidad Final Retiro:</b> {prof_ret:.1f} mm", td_style),
            Paragraph(f"<b>Milímetros Remanentes:</b> {mm_desp:.1f} mm", td_style)
        ],
        [
            Paragraph(f"<b>Causa Raíz de Desecho:</b><br/>{motivo}", td_style),
            Paragraph(f"<b>Destino Final:</b><br/>Bodega 7 FVU / Chatarrización Ambiental", td_style)
        ]
    ]
    t_detalles = Table(tabla_datos, colWidths=[270, 270])
    t_detalles.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_detalles)
    elements.append(Spacer(1, 14))

    declaracion_texto = (
        "<b>CERTIFICACIÓN AMBIENTAL Y TÉCNICA:</b> Por medio de la presente acta se certifica que la carcasa "
        "referenciada ha cumplido su ciclo de servicio o presenta daño estructural no reparable según los "
        "estándares de seguridad vial. Queda inhabilitada definitivamente para rodar y autorizada para su "
        "reciclaje, trituración o disposición final con gestor ambiental autorizado."
    )
    elements.append(Paragraph(declaracion_texto, td_style))
    elements.append(Spacer(1, 28))

    # Firmas
    firmas = [
        [
            Paragraph("______________________________________<br/><b>Inspector Técnico de Llantas</b><br/>Responsable de Inspección", td_style),
            Paragraph("______________________________________<br/><b>Jefe de Patio / Mantenimiento</b><br/>Aprobación de Baja", td_style),
            Paragraph("______________________________________<br/><b>Gestor Ambiental / Chatarrizador</b><br/>Recepción Disposición Final", td_style)
        ]
    ]
    t_firmas = Table(firmas, colWidths=[180, 180, 180])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 8)
    ]))
    elements.append(KeepTogether(t_firmas))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

