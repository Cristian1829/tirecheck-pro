"""Diagrama de chasis para el PDF (ReportLab). Reemplaza dibujar_diagrama_chasis_reportlab().

Principios para que nada se superponga:
  1. Toda la geometría sale de constantes; ninguna coordenada "calibrada a ojo".
  2. Cada llanta es una pila vertical con huecos fijos: llanta, medallón, rol, valor.
  3. El alto de fila se calcula a partir de esa pila (no es un número suelto).
  4. Los duales se dibujan juntos (hueco de 8 pt) y simétricos respecto al centro del vehículo.
  5. La leyenda se mide con stringWidth y se reparte sola; no usa posiciones fijas.
"""
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

# ------------------------------------------------------------------ colores
def _c(h): return colors.HexColor(h)
TINTA, GRIS, LINEA = _c("#0F172A"), _c("#64748B"), _c("#E2E8F0")
OK, AVISO, CRITICO, PEND = _c("#10B981"), _c("#D97706"), _c("#DC2626"), _c("#94A3B8")
LLANTA, LLANTA_BORDE, SURCO = _c("#1E293B"), _c("#0F172A"), _c("#475569")
TUBO, TUBO_BORDE, CUBO = _c("#CBD5E1"), _c("#94A3B8"), _c("#94A3B8")

# ------------------------------------------------------------------ geometría (puntos)
TIRE_W, TIRE_H = 18.0, 26.0
GAP_TIRE_BADGE = 3.5           # llanta -> medallón
BADGE_R = 5.0                  # radio del medallón
GAP_BADGE_ROL = 2.5            # medallón -> rol
ROL_FS, ROL_CAP = 5.6, 4.0     # tamaño y altura de mayúscula del rol
GAP_ROL_VAL = 2.2              # rol -> valor
VAL_FS, VAL_CAP, VAL_DESC = 7.0, 5.0, 1.6
PILA_H = (TIRE_H + GAP_TIRE_BADGE + 2 * BADGE_R + GAP_BADGE_ROL + ROL_CAP
          + GAP_ROL_VAL + VAL_CAP + VAL_DESC)          # alto real de una llanta con sus datos
PITCH = round(PILA_H + 3.0)    # alto de fila compactado (~15% ahorro vertical)
HEADER_H, LEGEND_H = 23.0, 28.0
# distancia horizontal de cada llanta al centro del vehículo
X_SEN, X_INT, X_EXT = 111.0, 98.0, 124.0               # duales: centros separados 26 pt (hueco de 8 pt)
MARGEN_X = 14.0

from database import es_novedad_alerta  # misma regla de novedades que la app y el informe

def profundidad_minima(fila):
    """Única definición de profundidad mínima (úsala también en KPIs y tabla)."""
    vals = []
    for k in ("prof_ext", "prof_cent", "prof_int"):
        try:
            v = float(fila.get(k))
        except (TypeError, ValueError):
            continue
        if v > 0:
            vals.append(v)
    return min(vals) if vals else None

def _num(v): return "—" if v is None else f"{v:.1f}".replace(".", ",")

def _rol(rol):
    r = str(rol or "").upper().strip()
    for clave, corto in (("DIR", "DIR"), ("EXT", "EXT"), ("INT", "INT"), ("REP", "REP")):
        if clave in r: return corto
    return "SEN" if ("SEN" in r or "LIB" in r) else r[:3]

def _tipo_eje(e):
    t = str(e.get("tipo", "")).lower()
    if "dir" in t: return "Direccional"
    if "trac" in t: return "Tracción"
    if "rem" in t or "trailer" in t or "tráiler" in t: return "Remolque"
    return "Libre"

def _llantas_del_eje(eje):
    """Devuelve [(desplazamiento_x_respecto_al_centro, posicion_dict)] ordenado de izquierda a derecha."""
    pos = eje.get("posiciones", [])
    izq = [p for p in pos if p.get("lado") == "izq"]
    der = [p for p in pos if p.get("lado") == "der"]
    res = []
    if len(izq) == 1: res.append((-X_SEN, izq[0]))
    elif len(izq) >= 2:
        ext = next((p for p in izq if "ext" in str(p.get("rol", "")).lower()), izq[0])
        itr = next((p for p in izq if p is not ext), izq[1])
        res += [(-X_EXT, ext), (-X_INT, itr)]
    if len(der) == 1: res.append((X_SEN, der[0]))
    elif len(der) >= 2:
        itr = next((p for p in der if "int" in str(p.get("rol", "")).lower()), der[0])
        ext = next((p for p in der if p is not itr), der[1])
        res += [(X_INT, itr), (X_EXT, ext)]
    return res

def _estado(info, limite):
    """Prioridad: bajo límite (rojo) > desalineación / novedad (ámbar) > registrada (verde) > pendiente (gris)."""
    if not info.get("registrada"): return "pend", PEND
    pm = info.get("p_min")
    if pm is not None and pm <= limite: return "critico", CRITICO
    
    # Desgaste irregular por alineación (abs(prof_ext - prof_int) >= 2.0 mm)
    p_ext = info.get("prof_ext")
    p_int = info.get("prof_int")
    if p_ext is not None and p_int is not None:
        try:
            if abs(float(p_ext) - float(p_int)) >= 2.0:
                return "aviso", AVISO
        except (ValueError, TypeError):
            pass
            
    nov = info.get("novedades")
    if nov and es_novedad_alerta(nov): return "aviso", AVISO
    return "ok", OK

def _dibujar_llanta(d, x, y_top, pos, rol, info, limite):
    estado, color = _estado(info, limite)
    yb = y_top - TIRE_H
    es_pend = (estado == "pend")
    fill_llanta = _c("#F1F5F9") if es_pend else LLANTA
    stroke_llanta = _c("#94A3B8") if es_pend else LLANTA_BORDE
    stroke_surco = _c("#CBD5E1") if es_pend else SURCO

    d.add(Rect(x - TIRE_W / 2, yb, TIRE_W, TIRE_H, rx=3, ry=3, fillColor=fill_llanta, strokeColor=stroke_llanta, strokeWidth=.8))
    for gx in (x - TIRE_W / 2 + 5.5, x + TIRE_W / 2 - 5.5):
        d.add(Line(gx, yb + 3, gx, y_top - 3, strokeColor=stroke_surco, strokeWidth=.6))
    cy = yb - GAP_TIRE_BADGE - BADGE_R                                   # medallón
    d.add(Circle(x, cy, BADGE_R, fillColor=colors.white if estado in ("ok", "pend") else (_c("#FEE2E2") if estado == "critico" else _c("#FEF3C7")),
                 strokeColor=color, strokeWidth=1.1))
    d.add(String(x, cy - 2.0, str(pos), fontName="Helvetica-Bold", fontSize=5.8, fillColor=TINTA, textAnchor="middle"))
    y_rol = cy - BADGE_R - GAP_BADGE_ROL - ROL_CAP                       # rol
    d.add(String(x, y_rol, rol, fontName="Helvetica", fontSize=ROL_FS, fillColor=GRIS, textAnchor="middle"))
    y_val = y_rol - GAP_ROL_VAL - VAL_CAP                                # valor
    if not info.get("registrada"):
        d.add(String(x, y_val, "PEND", fontName="Helvetica", fontSize=5.6, fillColor=PEND, textAnchor="middle"))
    else:
        d.add(String(x, y_val, _num(info.get("p_min")), fontName="Helvetica-Bold", fontSize=VAL_FS,
                     fillColor=CRITICO if estado == "critico" else TINTA, textAnchor="middle"))

def dibujar_diagrama_chasis(esquema, filas, limite_retiro=3.0, width=540):
    """esquema: lista de ejes [{'eje','tipo','posiciones':[{'pos','lado','rol'}]}]; filas: inspecciones de la placa."""
    info = {}
    for f in filas:
        p = int(f.get("posicion", 0))
        nov = str(f.get("novedades") or "").strip()
        info[p] = {
            "registrada": True,
            "p_min": profundidad_minima(f),
            "prof_ext": f.get("prof_ext"),
            "prof_int": f.get("prof_int"),
            "novedades": nov
        }
    rodantes = [e for e in esquema if e.get("eje") != 99 and str(e.get("tipo", "")).lower() != "repuesto"]
    repuestos = [e for e in esquema if e.get("eje") == 99 or str(e.get("tipo", "")).lower() == "repuesto"]
    filas_dib = len(rodantes) + (1 if repuestos else 0)
    alto = HEADER_H + filas_dib * PITCH + LEGEND_H
    d = Drawing(width, alto)
    cx = width / 2.0
    d.add(Rect(0, 0, width, alto, rx=4, ry=4, fillColor=colors.white, strokeColor=LINEA, strokeWidth=.75))

    # encabezado: orientación (la flecha es una figura, no un carácter: Helvetica no trae "▲")
    y_h = alto - 13
    d.add(String(MARGEN_X + 4, y_h, "IZQUIERDA", fontName="Helvetica-Bold", fontSize=6.5, fillColor=GRIS))
    d.add(String(width - MARGEN_X - 4, y_h, "DERECHA", fontName="Helvetica-Bold", fontSize=6.5, fillColor=GRIS, textAnchor="end"))
    w_f = stringWidth("FRENTE", "Helvetica-Bold", 7)
    d.add(Polygon([cx - w_f / 2 - 13, y_h - .5, cx - w_f / 2 - 7, y_h - .5, cx - w_f / 2 - 10, y_h + 6],
                  fillColor=_c("#1E3A8A"), strokeColor=_c("#1E3A8A"), strokeWidth=.3))
    d.add(String(cx + 5, y_h, "FRENTE", fontName="Helvetica-Bold", fontSize=7, fillColor=_c("#1E3A8A"), textAnchor="middle"))
    d.add(Line(MARGEN_X, alto - HEADER_H + 2, width - MARGEN_X, alto - HEADER_H + 2, strokeColor=LINEA, strokeWidth=.6))

    def fila_eje(i, etiqueta, items):
        y_top = alto - HEADER_H - i * PITCH - 6                           # tope de las llantas de esta fila
        y_mid = y_top - TIRE_H / 2.0
        d.add(String(MARGEN_X + 2, y_mid - 2.5, etiqueta, fontName="Helvetica-Bold", fontSize=7, fillColor=TINTA))
        if len(items) > 1:                                                # tubo del eje: de la primera a la última llanta
            xs = [cx + dx for dx, _ in items]
            d.add(Line(min(xs), y_mid, max(xs), y_mid, strokeColor=TUBO, strokeWidth=1.8))
            d.add(Circle(cx, y_mid, 3.2, fillColor=CUBO, strokeColor=_c("#64748B"), strokeWidth=.6))
        for dx, p in items:
            _dibujar_llanta(d, cx + dx, y_top, p.get("pos"), _rol(p.get("rol")), info.get(p.get("pos"), {}), limite_retiro)
        if i < filas_dib - 1:
            d.add(Line(MARGEN_X, y_top - PITCH + 3.5 + TIRE_H - TIRE_H, width - MARGEN_X, y_top - PITCH + 3.5 + TIRE_H - TIRE_H,
                       strokeColor=_c("#F1F5F9"), strokeWidth=.5))

    for i, e in enumerate(rodantes):
        fila_eje(i, f"Eje {e.get('eje', i + 1)} · {_tipo_eje(e)}", _llantas_del_eje(e))
    if repuestos:
        pr = (repuestos[0].get("posiciones") or [{}])[0]
        fila_eje(len(rodantes), "Repuesto", [(0.0, {"pos": pr.get("pos", 99), "rol": "REP"})])

    # leyenda: se reparte sola según el ancho real del texto
    y_l = 17.0
    d.add(Line(MARGEN_X, LEGEND_H - 3, width - MARGEN_X, LEGEND_H - 3, strokeColor=LINEA, strokeWidth=.6))
    x = MARGEN_X + 4
    for etiqueta, col in (("Registrada", OK), ("Con novedad", AVISO), ("Bajo límite de retiro", CRITICO), ("Pendiente", PEND)):
        d.add(Circle(x + 3.6, y_l + 2.3, 3.6, fillColor=colors.white, strokeColor=col, strokeWidth=1.2))
        d.add(String(x + 11, y_l, etiqueta, fontName="Helvetica", fontSize=6.5, fillColor=_c("#334155")))
        x += 11 + stringWidth(etiqueta, "Helvetica", 6.5) + 16
    d.add(String(MARGEN_X + 4, 6.0, f"Valor bajo cada llanta: profundidad mínima (mm). Rojo: menor o igual al límite de retiro ({_num(limite_retiro)} mm).",
                 fontName="Helvetica", fontSize=6, fillColor=GRIS))
    return d
