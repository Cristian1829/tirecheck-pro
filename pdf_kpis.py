"""Informe PDF de la suite de KPIs (vista Trazabilidad & KPIs).

Los gráficos llegan como imágenes capturadas en el navegador (los mismos Chart.js de la pantalla);
las cifras de las tablas se recalculan aquí con los mismos filtros. Cada indicador lleva un texto
que explica qué muestra. En licencia LIGHT solo salen las pestañas operativas (1, 2 y Tendencias).
"""
import base64
import html
import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from pdf_generator import ConsolidadoNumberedCanvas, ahora_bogota, format_miles_es, format_num_es

ANCHO = 540

_s_titulo = ParagraphStyle('KTit', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor('#0f172a'))
_s_texto = ParagraphStyle('KTxt', fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'))
_s_seccion = ParagraphStyle('KSec', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.white)
_s_kpi = ParagraphStyle('KKpi', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#1e3a8a'), spaceBefore=4)
_s_explica = ParagraphStyle('KExp', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#334155'))
_s_vacio = ParagraphStyle('KVac', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor('#94a3b8'))
_s_th = ParagraphStyle('KTh', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=colors.white, alignment=1)
_s_td = ParagraphStyle('KTd', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor('#1e293b'))
_s_td_c = ParagraphStyle('KTdC', parent=_s_td, alignment=1)
_s_cifra = ParagraphStyle('KCif', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#2563eb'), alignment=1)
_s_cifra_lbl = ParagraphStyle('KCifL', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor('#64748b'), alignment=1)


def _e(v):
    return html.escape(str(v if v is not None else ''))


def _pesos(v):
    return '—' if v is None else f"$ {format_miles_es(v)}"


def _cpk(v, u):
    return 'Sin dato' if v is None else f"$ {format_num_es(v, 1)} /{u}"


def _pct(v):
    return '—' if v is None else f"{format_num_es(v, 1)}%"


# ---------------------------------------------------------------------------
# Catálogo de indicadores: (clave de datos, título, explicación, canvas capturados)
# ---------------------------------------------------------------------------
SECCIONES = [
    (1, "1. Inspección & Parque", False, [
        ("kpi_01", "KPI 01 · Cumplimiento de inspección vs. parque vehicular",
         "Mide qué parte del parque activo del cliente fue inspeccionada. Compara los vehículos con al menos una "
         "inspección contra el padrón registrado; si no hay padrón cargado, el parque son los vehículos que ya se "
         "inspeccionaron alguna vez. Un cumplimiento bajo indica placas sin control de desgaste ni presión.", []),
        ("kpi_02", "KPI 02 · Volumen auditado mes a mes",
         "Las barras muestran cuántas llantas se midieron en cada corte y la línea cuántos vehículos se auditaron. "
         "Sirve para ver la constancia del programa de inspección: meses con caídas fuertes dejan la flota sin seguimiento.",
         ["canvasKpi02_volumen"]),
        ("kpi_03", "KPI 03 · Porcentaje de reencauche y unidades por ciclo",
         "Compara la proporción de llantas reencauchadas de la flota con la meta de reencauche del cliente y reparte "
         "las llantas por vida (Original, R1, R2, R3+). Un porcentaje por debajo de la meta indica que se están "
         "comprando llantas nuevas donde se podría reencauchar la carcasa.", ["canvasKpi03_pct", "canvasKpi03_ciclos"]),
        ("kpi_04", "KPI 04 · Composición de la flota",
         "Distribución de las llantas montadas por tipología de vehículo, marca y dimensión. Muestra de qué está "
         "hecha la flota hoy y sirve de base para negociar compras y estandarizar referencias.",
         ["canvasKpi04_tipologia", "canvasKpi04_marca", "canvasKpi04_dimension"]),
    ]),
    (2, "2. Mantenimiento & Pérdida", False, [
        ("kpi_05", "KPI 05 · Retiros y cambios inmediatos",
         "Llantas que ya llegaron al límite de retiro de su eje, con prioridad para el par direccional (posiciones 1 y 2). "
         "Cada llanta en esta lista debe desmontarse cuanto antes para no perder la carcasa reencauchable ni exponer la operación.",
         ["canvasKpi05_retiros"]),
        ("kpi_06", "KPI 06 · Alineación y costo de milímetros perdidos",
         "Llantas con diferencia entre hombros por encima de la tolerancia del cliente, señal de desalineación, y el "
         "valor en pesos del caucho perdido por ese desgaste irregular. Corregir la geometría a tiempo detiene la pérdida.",
         ["canvasKpi06_alineacion"]),
        ("kpi_07", "KPI 07 · Plan de rotaciones tándem",
         "Vehículos cuyos ejes en tándem tienen una diferencia de profundidad que justifica rotar llantas entre ejes "
         "para igualar el desgaste. Indica el esquema de rotación sugerido y si la condición es reincidente.", []),
        ("kpi_08", "KPI 08 · Duales mal apareados",
         "Pares de llantas duales con más de 3 mm de diferencia entre sí. La llanta más alta carga más peso y se desgasta "
         "o revienta antes; la gráfica muestra la frecuencia mensual de estos casos.", ["canvasKpi08_apareo"]),
        ("kpi_09", "KPI 09 · Estado de presiones y desperdicio de combustible",
         "Reparte las llantas medidas en rangos de presión frente a la presión objetivo del cliente y estima el combustible "
         "que se pierde por rodar subinfladas. Solo cuenta llantas con presión registrada.", ["canvasKpi09_psi"]),
        ("kpi_10", "KPI 10 · Pareto de novedades",
         "Ordena las novedades mecánicas de mayor a menor frecuencia con su porcentaje acumulado (regla 80/20). Las primeras "
         "barras concentran la mayoría de los problemas y son las que conviene atacar primero.", ["canvasKpi10_pareto"]),
        ("kpi_11", "KPI 11 · Impacto económico de las pérdidas",
         "Suma, por periodo, los milímetros perdidos por desalineación, desbalance y presión incorrecta y su equivalente en "
         "pesos. Muestra cuánto cuesta no corregir las novedades detectadas en las inspecciones.", ["canvasKpi11_impacto"]),
    ]),
    (3, "3. Producto & Proyecciones", True, [
        ("kpi_12", "KPI 12 · Desgaste de la flota",
         "Milímetros gastados, profundidad y porcentaje de desgaste de la llanta más crítica de la flota (la más gastada), "
         "y recorrido promedio de las llantas con profundidad inicial registrada. Muestra el peor caso que hay que atender.", []),
        ("kpi_13", "KPI 13 · Recorrido real vs. proyección al límite de retiro",
         "Compara lo que cada grupo de llantas ya rodó con lo que se proyecta que rodará hasta llegar al límite de retiro, "
         "según su ritmo de desgaste. La diferencia es el recorrido que aún queda por aprovechar.", ["canvasKpi13_comparativo"]),
        ("kpi_14", "KPI 14 · Proyección, rendimiento por milímetro y CPK proyectado",
         "Tres vistas del mismo grupo (marca, eje, tipología o periodo): recorrido proyectado total, recorrido por milímetro "
         "de caucho gastado y costo por kilómetro proyectado. Permite comparar referencias en rendimiento y en costo.",
         ["canvasKpi14_proy", "canvasKpi14_kmmm", "canvasKpi14_cpk"]),
        ("kpi_cpk", "Costo por kilómetro (CPK)",
         "Cuatro maneras de medir el costo: operativo (lo rodado hasta hoy), proyectado (hasta el límite de retiro), total por "
         "ciclo (Σ costo ÷ Σ recorrido de todas las vidas) y administrativo mensual (inversión en llantas instaladas sin recorrido "
         "÷ recorrido de la flota en el mes). Las llantas sin precio en la lista del cliente quedan fuera.", []),
        ("kpi_15", "KPI 15 · Potencial de llanta",
         "Rendimiento promedio de las llantas con al menos 1,5 mm de desgaste frente al mejor y al peor registro del grupo. "
         "La brecha con el máximo muestra cuánto rendimiento se podría ganar repitiendo las mejores condiciones de uso.",
         ["canvasKpi15_potencial"]),
        ("kpi_16", "KPI 16 · Proyección por rango de desgaste",
         "Agrupa las llantas en bandas de desgaste (0-40 %, 40-60 %, 60-80 %, 80-100 % y retiro) y muestra el rendimiento "
         "proyectado en cada una. Ayuda a ver si las proyecciones se mantienen a medida que la llanta envejece.",
         ["canvasKpi16_rangos"]),
    ]),
    (4, "4. Tablero de Bajas / FVU", True, [
        ("kpi_17", "KPI 17 · Indicadores globales de fin de vida útil",
         "Evolución mensual de las llantas dadas de baja (barras) y del índice de reencauchabilidad (línea), que relaciona "
         "las vidas logradas por carcasa. Un índice que cae indica carcasas que se pierden antes de aprovechar sus reencauches.",
         ["canvasKpi17_lineas"]),
        ("kpi_18", "KPI 18 · Participación de las bajas por marca, ciclo y causal",
         "Reparte las llantas dadas de baja por marca, por vida en la que salieron y por causa del daño. Sirve para detectar "
         "fallas prematuras repetidas en una referencia y sustentar reclamos de garantía.",
         ["canvasKpi18_marca", "canvasKpi18_ciclo", "canvasKpi18_causal"]),
        ("kpi_19", "KPI 19 · Profundidad de baja y dispersión",
         "Profundidad máxima, promedio y mínima con la que se retiraron las llantas, y su dispersión por milímetro. Retirar por "
         "encima del límite es caucho pagado y no usado; la gráfica cuantifica ese desperdicio.",
         ["canvasKpi19_lineas", "canvasKpi19_burbujas"]),
    ]),
    (5, "5. Balance de Bodegas (MRP)", True, [
        ("kpi_20", "KPI 20 · Planeación de necesidades de llantas (MRP)",
         "Por dimensión compara la necesidad bruta del horizonte (llantas que llegarán al retiro, reposición de bajas y stock de "
         "seguridad) con el inventario disponible en bodegas. La diferencia es la compra neta sugerida y su presupuesto estimado.",
         ["canvasKpi20_mrp"]),
    ]),
    (6, "6. Tendencias mensuales", False, [
        ("kpi_tendencias", "Tendencia de la flota mes a mes",
         "Foto de la flota al cierre de cada mes, con la última inspección de cada posición hasta ese mes: porcentaje de llantas "
         "con presión correcta, en límite de retiro y con alerta de alineación. Muestra si la gestión mejora o empeora en el tiempo.",
         ["canvasTendencias"]),
    ]),
]


def secciones_por_licencia(licencia):
    """Pestañas que se incluyen según la licencia efectiva del cliente."""
    es_full = str(licencia).upper() in ('FULL', 'PRO')
    return [s for s in SECCIONES if es_full or not s[2]]


def _leer_imagen(data_url):
    """(bytes, ancho, alto) de un data URL PNG/JPEG; None si no es una imagen válida."""
    try:
        crudo = base64.b64decode(str(data_url).split(',', 1)[-1])
        w, h = ImageReader(io.BytesIO(crudo)).getSize()
        return crudo, w, h
    except Exception:
        return None


def _imagen(data_url, ancho_max, alto_max):
    """Imagen desde un data URL (PNG/JPEG) ajustada a la caja sin deformarla."""
    leida = _leer_imagen(data_url)
    if not leida:
        return None
    crudo, w, h = leida
    escala = min(ancho_max / w, alto_max / h)
    return RLImage(io.BytesIO(crudo), width=w * escala, height=h * escala)


# Títulos de los gráficos que en pantalla comparten tarjeta y llevan su propio subtítulo
_s_subgraf = ParagraphStyle('KSubG', fontName='Helvetica-Bold', fontSize=7.5, leading=10,
                            textColor=colors.HexColor('#4338ca'), alignment=1)
SUBTITULOS = {
    'canvasKpi14_proy': "1. Recorrido proyectado al límite de retiro",
    'canvasKpi14_kmmm': "2. Rendimiento por milímetro de caucho",
    'canvasKpi14_cpk': "3. CPK proyectado ($ por unidad recorrida)",
}
# Barras con muchas etiquetas: siempre a todo el ancho, aunque la captura haya salido angosta
FILA_COMPLETA = set(SUBTITULOS)


def _bloque_graficos(ids, graficos):
    """Un gráfico solo o uno apaisado (capturado ancho) va en fila completa; los demás, de a dos por fila."""
    leidas = [(c, _leer_imagen(graficos[c])) for c in ids if graficos.get(c)]
    leidas = [(c, l) for c, l in leidas if l]
    if not leidas:
        return None
    solo = len(leidas) == 1

    def celda(c, ancho_max, alto_max):
        img = _imagen(graficos[c], ancho_max, alto_max)
        return [Paragraph(_e(SUBTITULOS[c]), _s_subgraf), img] if c in SUBTITULOS else img

    filas, completas, pendiente = [], [], []
    for c, (_, w, h) in leidas:
        if solo or w / h >= 2.2 or c in FILA_COMPLETA:
            completas.append(len(filas))
            filas.append([celda(c, ANCHO - 8, 240 if solo else 190), ''])
        else:
            pendiente.append(celda(c, ANCHO / 2 - 8, 190))
            if len(pendiente) == 2:
                filas.append(pendiente)
                pendiente = []
    if pendiente:
        filas.append(pendiente + [''])
    t = Table(filas, colWidths=[ANCHO / 2] * 2)
    estilo = [('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
              ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
              ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]
    estilo += [('SPAN', (0, i), (1, i)) for i in completas]
    t.setStyle(TableStyle(estilo))
    return t


def _tabla(encabezados, filas, anchos, vacio="Sin datos para los filtros seleccionados."):
    if not filas:
        return Paragraph(vacio, _s_vacio)
    datos = [[Paragraph(f"<b>{_e(h)}</b>", _s_th) for h in encabezados]]
    datos += [[Paragraph(_e(c), _s_td if i == 0 else _s_td_c) for i, c in enumerate(f)] for f in filas]
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    return t


def _cifras(pares):
    """Fila de tarjetas con cifras clave: [(etiqueta, valor), ...]."""
    ancho = ANCHO / len(pares)
    t = Table([[Paragraph(_e(v), _s_cifra) for _, v in pares], [Paragraph(_e(k), _s_cifra_lbl) for k, _ in pares]],
              colWidths=[ancho] * len(pares))
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#cbd5e1')),
        ('LINEAFTER', (0, 0), (-2, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


def _detalle(clave, d, u):
    """Cifras o tablas propias de cada indicador (además del gráfico)."""
    d = d or {}
    if clave == 'kpi_01':
        pct = d.get('porcentaje_cumplimiento')
        fuente = ("Sin padrón cargado: el parque son los vehículos ya inspeccionados alguna vez."
                  if d.get('fuente_padron') == 'vehiculos_inspeccionados' else "")
        out = [_cifras([("Cumplimiento", 'Sin padrón' if pct is None else _pct(pct)),
                        ("Vehículos inspeccionados / parque",
                         f"{format_miles_es(d.get('vehiculos_inspeccionados') or 0)} / {format_miles_es(d.get('total_padron_activo') or 0)}"),
                        ("Placas pendientes", format_miles_es(len(d.get('placas_pendientes') or [])))])]
        if fuente:
            out.append(Paragraph(fuente, _s_vacio))
        pend = d.get('placas_pendientes') or []
        if pend and d.get('parque_cargado'):
            # Parque cargado por el administrador: todos los que faltan, con datos para ubicarlos
            out.append(Paragraph("Medido contra el parque automotor cargado para el cliente.", _s_vacio))
            out.append(Spacer(1, 4))
            out.append(_tabla(["Placa / N° interno", "Sede", "Tipología", "Fabricante / línea", "Última inspección"],
                              [[p.get('placa') or '-', p.get('subcliente') or '-', p.get('tipologia') or '-',
                                ' '.join(x for x in (p.get('fabricante'), p.get('linea')) if x) or '-',
                                p.get('ultima_inspeccion') or 'Nunca'] for p in pend], [95, 90, 130, 140, 85]))
        elif pend:
            out.append(Spacer(1, 4))
            out.append(_tabla(["Placa pendiente", "Cliente / sede", "Tipología"],
                              [[p.get('placa') or '-', f"{p.get('cliente') or '-'}{' / ' + p['subcliente'] if p.get('subcliente') else ''}",
                                p.get('tipologia') or '-'] for p in pend[:25]], [120, 260, 160]))
            if len(pend) > 25:
                out.append(Paragraph(f"Se muestran 25 de {len(pend)} placas pendientes.", _s_vacio))
        return out
    if clave == 'kpi_07':
        rot = d.get('rotaciones_sugeridas') or []
        return [_tabla(["Placa", "Esquema sugerido", "Diferencia entre ejes", "Estado"],
                       [[r.get('placa') or '-', r.get('esquema') or '-', f"{format_num_es(r.get('delta_ejes_mm'))} mm",
                         r.get('estado') or '-'] for r in rot],
                       [110, 200, 120, 110], vacio="Desgaste equilibrado: no se requieren rotaciones en este corte.")]
    if clave == 'kpi_12':
        return [_cifras([("mm gastados (máx.)", f"{format_num_es(d.get('mm_gastados') or 0)} mm"),
                         ("Profundidad mínima", f"{format_num_es(d.get('profundidad_actual') or 0)} mm"),
                         ("% desgaste máx.", _pct(d.get('pct_desgaste') or 0)),
                         (f"Recorrido prom. ({u})", format_miles_es(d.get('km_recorridos') or 0))])]
    if clave == 'kpi_cpk':
        f = d.get('flota') or {}
        adm = [m for m in (d.get('administrativo') or []) if (m.get('km_flota') or 0) > 0]
        out = [_cifras([("CPK operativo", _cpk(f.get('cpk_operativo'), u)),
                        ("CPK proyectado", _cpk(f.get('cpk_proyectado'), u)),
                        ("CPK total por ciclo", _cpk(f.get('cpk_total'), u)),
                        ("CPK administrativo (último mes)", _cpk(adm[-1].get('cpk_administrativo') if adm else None, u))]),
               Paragraph(f"{f.get('llantas_con_cpk') or 0} vidas de llanta con CPK; {f.get('llantas_sin_precio') or 0} sin precio "
                         "(no entran al cálculo).", _s_vacio), Spacer(1, 4),
               _tabla(["Vida", "Llantas", "CPK operativo", "CPK proyectado"],
                      [[v.get('vida'), v.get('llantas'), _cpk(v.get('cpk_operativo'), u), _cpk(v.get('cpk_proyectado'), u)]
                       for v in d.get('por_vida') or []], [120, 100, 160, 160])]
        if d.get('administrativo'):
            out += [Spacer(1, 4), _tabla(["Mes", "Inversión instalada", f"Recorrido flota ({u})", "CPK administrativo"],
                                         [[m.get('mes'), _pesos(m.get('inversion')) if m.get('inversion') else '-',
                                           format_miles_es(m['km_flota']) if m.get('km_flota') else '-',
                                           _cpk(m.get('cpk_administrativo'), u)]
                                          for m in reversed(d['administrativo'])], [100, 150, 140, 150])]
        return out
    if clave == 'kpi_17':
        out = [_cifras([("Llantas dadas de baja", format_miles_es(d.get('cantidad_fvu') or 0)),
                        ("Índice de reencauchabilidad", format_num_es(d.get('indice_reencauchabilidad_ir') or 0, 2)),
                        ("% de bajas reencauchadas", _pct(d.get('pct_reencauche_fvu') or 0))])]
        if d.get('bajas_sin_fecha'):
            out.append(Paragraph(f"{format_miles_es(d['bajas_sin_fecha'])} de {format_miles_es(d.get('cantidad_fvu') or 0)} "
                                 "bajas no tienen fecha de baja registrada: cuentan en el total pero no aparecen en la "
                                 "gráfica mensual.", _s_vacio))
        return out
    if clave == 'kpi_20':
        m = d.get('matriz_mrp') or []
        return [_tabla(["Dimensión", "Demanda", "Reposición bajas", "Stock seg.", "Necesidad bruta", "Stock disponible",
                        "Compra neta", "Presupuesto"],
                       [[r.get('dimension') or '-', format_miles_es(r.get('demanda_flota') or 0),
                         format_miles_es(r.get('reposicion_bajas_fvu') or 0), format_miles_es(r.get('margen_seguridad') or 0),
                         format_miles_es(r.get('necesidad_bruta') or 0), format_miles_es(r.get('stock_disponible') or 0),
                         format_miles_es(r.get('compra_neta_sugerida') or 0), _pesos(r.get('presupuesto_estimado_cop') or 0)]
                        for r in m], [80, 55, 65, 55, 65, 65, 60, 95],
                       vacio="No hay inventario ni necesidades para los filtros seleccionados.")]
    if clave == 'kpi_tendencias':
        meses = (d.get('meses') or [])[::-1]
        if any(x.get('pct_cumplimiento_parque') is not None for x in meses):
            # Con parque cargado: % del parque inspeccionado en cada mes
            return [_tabla(["Mes", "Vehículos insp.", "% del parque", "Presión correcta", "En límite de retiro",
                            "Prof. mín. prom.", "Alerta alineación", "CPK operativo"],
                           [[x.get('mes'), x.get('vehiculos_inspeccionados'), _pct(x.get('pct_cumplimiento_parque')),
                             _pct(x.get('pct_presion_correcta')), _pct(x.get('pct_en_retiro')),
                             '—' if x.get('prof_minima_promedio') is None else f"{format_num_es(x['prof_minima_promedio'])} mm",
                             _pct(x.get('pct_alerta_alineacion')), _cpk(x.get('cpk_operativo'), u)] for x in meses],
                           [50, 55, 55, 65, 70, 65, 65, 115], vacio="Sin inspecciones en el periodo.")]
        return [_tabla(["Mes", "Vehículos insp.", "Presión correcta", "En límite de retiro", "Prof. mín. prom.",
                        "Alerta alineación", "CPK operativo"],
                       [[x.get('mes'), x.get('vehiculos_inspeccionados'), _pct(x.get('pct_presion_correcta')),
                         _pct(x.get('pct_en_retiro')),
                         '—' if x.get('prof_minima_promedio') is None else f"{format_num_es(x['prof_minima_promedio'])} mm",
                         _pct(x.get('pct_alerta_alineacion')), _cpk(x.get('cpk_operativo'), u)] for x in meses],
                       [60, 65, 75, 80, 75, 75, 110], vacio="Sin inspecciones en el periodo.")]
    return []


def _encabezado_seccion(titulo):
    t = Table([[Paragraph(_e(titulo), _s_seccion)]], colWidths=[ANCHO])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1e3a8a')),
                           ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                           ('LEFTPADDING', (0, 0), (-1, -1), 8)]))
    return t


def generar_pdf_kpis(datos: dict, graficos: dict, filtros: dict) -> bytes:
    """datos: salida de obtener_suite_completa_20_kpis; graficos: {id_canvas: data URL}; filtros: los de la pantalla."""
    graficos = graficos or {}
    licencia = datos.get('licencia', 'LIGHT')
    u = 'h' if datos.get('unidad') == 'horas' or str(filtros.get('unidad', '')).lower().startswith('hor') else 'km'

    class _Canvas(ConsolidadoNumberedCanvas):
        _titulo = "INFORME DE INDICADORES (KPIs) DE GESTIÓN DE LLANTAS"
        _fecha = ahora_bogota().strftime('%d/%m/%Y')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=68, bottomMargin=32,
                            title="Informe de KPIs - TireAnalyze Pro")
    el = [Paragraph("Informe de Indicadores de Gestión de Llantas", _s_titulo), Spacer(1, 4)]

    def f(k, todos):
        v = str(filtros.get(k) or '').strip()
        return v if v and v.upper() not in ('TODOS', 'TODAS') else todos

    lic_txt = 'FULL / PRO' if str(licencia).upper() in ('FULL', 'PRO') else 'LIGHT (operativa)'
    caja = [
        [Paragraph(f"<b>Cliente:</b> {_e(f('cliente', 'Todos los clientes'))}", _s_texto),
         Paragraph(f"<b>Sede:</b> {_e(f('subcliente', 'Todas las sedes'))}", _s_texto),
         Paragraph(f"<b>Operación:</b> {_e(f('tipo_operacion', 'Todas'))}", _s_texto)],
        [Paragraph(f"<b>Tipología:</b> {_e(f('tipologia', 'Todas'))}", _s_texto),
         Paragraph(f"<b>Marca:</b> {_e(f('marca', 'Todas'))}", _s_texto),
         Paragraph(f"<b>Dimensión:</b> {_e(f('dimension', 'Todas'))}", _s_texto)],
        [Paragraph(f"<b>Licencia:</b> {lic_txt}", _s_texto),
         Paragraph("<b>Base de cálculo:</b> " + ("Historial completo" if datos.get('base') == 'historial'
                                                  or filtros.get('base') == 'historial' else "Última inspección"), _s_texto),
         Paragraph("<b>Unidad:</b> " + ("Horas de motor" if u == 'h' else "Kilómetros"), _s_texto)],
    ]
    t = Table(caja, colWidths=[180] * 3)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                           ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                           ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                           ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    el += [t, Spacer(1, 8)]

    q = datos.get('calidad_datos') or {}
    excl = [f"{q[k]} {txt}" for k, txt in (('sin_psi', 'sin presión'), ('sin_prof_inicial', 'sin profundidad inicial'),
                                           ('sin_precio', 'sin precio'), ('sin_numero_interno', 'sin número interno'),
                                           ('sin_marca', 'sin marca'))
            if q.get(k)]
    if q.get('marca_es_banda'):
        excl.append(f"{q['marca_es_banda']} con marca de banda de reencauche en el campo marca "
                    f"({', '.join(q.get('marcas_banda_usadas') or [])})")
    if q.get('llantas') and excl:
        el.append(Spacer(1, 4))
        el.append(Paragraph(f"Calidad de datos: de {q['llantas']} llantas analizadas, {'; '.join(excl)}. Cada indicador "
                            "se calcula solo con las llantas que tienen el dato que necesita.", _s_vacio))

    # La primera pestaña arranca en la misma hoja de los filtros; las demás en hoja nueva
    for n_sec, (_, titulo_sec, _, kpis) in enumerate(secciones_por_licencia(licencia)):
        el.append(PageBreak() if n_sec else Spacer(1, 8))
        el.append(_encabezado_seccion(titulo_sec))
        el.append(Spacer(1, 6))
        for n_kpi, (clave, titulo, explica, canvas_ids) in enumerate(kpis):
            # El espacio va antes de cada indicador y no después: un espacio sobrante al final de una hoja llena
            # caía solo en la hoja siguiente y el salto de sección la dejaba en blanco
            if n_kpi:
                el.append(Spacer(1, 10))
            bloque = [Paragraph(_e(titulo), _s_kpi), Paragraph(_e(explica), _s_explica), Spacer(1, 4)]
            g = _bloque_graficos(canvas_ids, graficos)
            if g is not None:
                bloque.append(g)
            elif canvas_ids:
                bloque.append(Paragraph("Sin datos para graficar con los filtros seleccionados.", _s_vacio))
            detalle = _detalle(clave, datos.get(clave), u)
            if detalle and g is not None:
                bloque.append(Spacer(1, 4))
            bloque += detalle
            # El título y el gráfico van juntos; las tablas largas pueden partirse entre páginas
            el.append(KeepTogether(bloque[:4] if len(bloque) > 4 else bloque))
            el += bloque[4:]

    if str(licencia).upper() not in ('FULL', 'PRO'):
        el.append(Spacer(1, 6))
        el.append(Paragraph("Licencia LIGHT: este informe incluye los indicadores operativos. Las proyecciones, el CPK, el tablero "
                            "de bajas y el MRP de bodegas hacen parte de la licencia FULL / PRO.", _s_vacio))

    doc.build(el, canvasmaker=_Canvas)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Informe de Composición & Caracterización de Flota
# Lo arma con lo que muestra la pantalla (tarjetas, reglas de oro, gráficas y matriz ya filtradas),
# igual que el PDF de los KPI: las gráficas llegan capturadas del navegador.
# ---------------------------------------------------------------------------
GRAFICAS_COMPOSICION = [
    ("chartCompVidaEje", "Condición de vida por eje",
     "Proporción de llantas originales (nuevas) frente a reencauchadas en el eje seleccionado. Sirve para verificar la "
     "política de reencauche: en el eje direccional debería haber cero reencauches y en tracción y remolque la mayor "
     "parte de la flota debería estar renovada."),
    ("chartCompMarcas", "Participación por marca (top 7)",
     "Cuántas llantas de cada fabricante están montadas en la flota. Una flota concentrada en pocas marcas es más fácil "
     "de negociar, abastecer y comparar en rendimiento; muchas marcas con poca participación indican compras dispersas."),
    ("chartCompDimensiones", "Distribución por dimensión (top 6)",
     "Reparto de la flota por medida de llanta. Lo recomendado es que la medida principal concentre al menos el 70 % "
     "del inventario: menos medidas distintas significa menos stock de respaldo y más intercambiabilidad entre vehículos."),
    ("chartCompDisenos", "Diseños de rodamiento con mayor presencia (top 6)",
     "Los modelos o bandas más usados en la flota. Ayuda a ver si se está estandarizando el diseño por tipo de eje y a "
     "detectar diseños con muy pocas unidades que complican la rotación y el apareo de duales."),
]


_RE_SIN_FUENTE = re.compile(r'[^\u0000-ɏ‐-‧€≤≥×]')


def _sin_emojis(valor):
    """Texto de la pantalla sin emojis ni íconos: la fuente del PDF no los tiene y salían como cuadros (■)."""
    if isinstance(valor, dict):
        return {k: _sin_emojis(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sin_emojis(v) for v in valor]
    if isinstance(valor, str) and not valor.startswith('data:'):
        return re.sub(r'\s{2,}', ' ', _RE_SIN_FUENTE.sub('', valor)).strip()
    return valor


def generar_pdf_composicion(datos: dict) -> bytes:
    """datos: {filtros: {etiqueta: valor}, eje, tarjetas: [{etiqueta, valor, detalle}], reglas: [{titulo, estado, detalle}],
    graficos: {id_canvas: data URL}, matriz: {encabezados: [...], filas: [[...]]}}"""
    datos = _sin_emojis(datos or {})
    graficos = datos.get('graficos') or {}

    class _Canvas(ConsolidadoNumberedCanvas):
        _titulo = "INFORME DE COMPOSICIÓN Y CARACTERIZACIÓN DE FLOTA"
        _fecha = ahora_bogota().strftime('%d/%m/%Y')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=68, bottomMargin=32,
                            title="Composición de Flota - TireAnalyze Pro")
    el = [Paragraph("Composición y Caracterización de Flota", _s_titulo),
          Paragraph("Radiografía de la flota activa: ciclo de vida, tipo de eje, marcas, medidas y diseños, con las reglas "
                    "de oro de estandarización evaluadas sobre los filtros seleccionados.", _s_explica),
          Spacer(1, 6)]

    # Filtros aplicados (3 por fila)
    filtros = [(k, v) for k, v in (datos.get('filtros') or {}).items()]
    if filtros:
        celdas = [Paragraph(f"<b>{_e(k)}:</b> {_e(v)}", _s_texto) for k, v in filtros]
        celdas += [''] * (-len(celdas) % 3)
        t = Table([celdas[i:i + 3] for i in range(0, len(celdas), 3)], colWidths=[180] * 3)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                               ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                               ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                               ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        el += [t, Spacer(1, 8)]

    # Tarjetas resumen
    tarjetas = datos.get('tarjetas') or []
    if tarjetas:
        el.append(_encabezado_seccion("Resumen de la flota"))
        el.append(Spacer(1, 6))
        for i in range(0, len(tarjetas), 3):
            grupo = tarjetas[i:i + 3]
            el.append(_cifras([(f"{t.get('etiqueta', '')} · {t.get('detalle', '')}" if t.get('detalle') else t.get('etiqueta', ''),
                                t.get('valor', '—')) for t in grupo]))
            el.append(Spacer(1, 4))
        el.append(Spacer(1, 6))

    # Reglas de oro
    reglas = datos.get('reglas') or []
    if reglas:
        el.append(_encabezado_seccion("Reglas de oro de estandarización"))
        el.append(Spacer(1, 4))
        el.append(Paragraph("Cuatro controles de buenas prácticas sobre la flota filtrada: cero reencauches en el eje "
                            "direccional, nivel de renovación en tracción y remolque, concentración de medidas y homogeneidad "
                            "de los duales.", _s_explica))
        el.append(Spacer(1, 4))
        el.append(_tabla(["Regla", "Estado", "Resultado"],
                         [[r.get('titulo', ''), r.get('estado', ''), r.get('detalle', '')] for r in reglas],
                         [150, 90, 300]))
        el.append(Spacer(1, 10))

    # Gráficas, cada una con su explicación
    el.append(PageBreak())
    el.append(_encabezado_seccion("Gráficas de composición"))
    el.append(Spacer(1, 6))
    for n, (canvas_id, titulo, explica) in enumerate(GRAFICAS_COMPOSICION):
        if n:
            el.append(Spacer(1, 10))
        if canvas_id == "chartCompVidaEje" and datos.get('eje'):
            titulo = f"{titulo} — {datos['eje']}"
        g = _bloque_graficos([canvas_id], graficos)
        el.append(KeepTogether([Paragraph(_e(titulo), _s_kpi), Paragraph(_e(explica), _s_explica), Spacer(1, 4),
                                g if g is not None else Paragraph("Sin datos para graficar con los filtros seleccionados.",
                                                                  _s_vacio)]))

    # Matriz marca × diseño × medida
    matriz = datos.get('matriz') or {}
    filas = (matriz.get('filas') or [])[:200]
    encabezados = matriz.get('encabezados') or []
    if encabezados:
        el.append(PageBreak())
        el.append(_encabezado_seccion("Matriz de participación e inventario"))
        el.append(Spacer(1, 4))
        el.append(Paragraph("Desglose de las llantas en servicio por combinación de marca, diseño y medida, con cuántas son "
                            "originales y reencauchadas, su participación en la flota y la profundidad promedio. Las "
                            "combinaciones con muchas llantas y baja profundidad son las próximas compras o reencauches.",
                            _s_explica))
        el.append(Spacer(1, 4))
        n_col = len(encabezados)
        anchos = [ANCHO / n_col] * n_col
        el.append(_tabla(encabezados, [list(f)[:n_col] + [''] * (n_col - len(f)) for f in filas], anchos))
        if len(matriz.get('filas') or []) > 200:
            el.append(Paragraph(f"Se muestran 200 de {len(matriz['filas'])} combinaciones.", _s_vacio))

    doc.build(el, canvasmaker=_Canvas)
    return buffer.getvalue()
