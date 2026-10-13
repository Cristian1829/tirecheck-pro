import io
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Group
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

    # Mapear datos de inspección por posición
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

    # Separar ejes rodantes de repuesto
    ejes_rodantes = [e for e in esquema if e.get('eje') != 99 and (e.get('tipo') or '').lower() != 'repuesto']
    ejes_repuesto = [e for e in esquema if e.get('eje') == 99 or (e.get('tipo') or '').lower() == 'repuesto']

    num_ejes = len(ejes_rodantes)
    alto_eje = 42
    alto_header = 22
    alto_leyenda = 18
    alto_repuesto = 35 if ejes_repuesto else 0
    total_height = alto_header + (num_ejes * alto_eje) + alto_repuesto + alto_leyenda + 12

    d = Drawing(width, total_height)

    # Fondo decorativo técnico sutil
    d.add(Rect(0, 0, width, total_height, rx=6, ry=6, fillColor=colors.HexColor('#F8FAFC'), strokeColor=colors.HexColor('#CBD5E1'), strokeWidth=0.75))

    # Encabezado con orientación
    curr_y = total_height - 15
    d.add(String(15, curr_y, "DIAGRAMA TÉCNICO DE CHASIS", fontName="Helvetica-Bold", fontSize=8.5, fillColor=colors.HexColor('#1E293B')))
    d.add(String(width / 2, curr_y, "↑ FRENTE DEL VEHÍCULO", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor('#2563EB'), textAnchor="middle"))
    d.add(String(width - 80, curr_y, "DERECHA →", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))
    d.add(String(80, curr_y, "← IZQUIERDA", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

    curr_y -= 10
    d.add(Line(10, curr_y, width - 10, curr_y, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.75))

    # Renderizar cada eje
    w_llanta = 20
    h_llanta = 32
    cx_vehiculo = width / 2

    for idx, e in enumerate(ejes_rodantes):
        y_eje = curr_y - (idx * alto_eje) - 22
        eje_num = e.get('eje', idx + 1)
        tipo_lbl = str(e.get('tipo', '')).capitalize()
        if 'traccion' in tipo_lbl.lower(): tipo_lbl = 'Tracción'
        elif 'direccional' in tipo_lbl.lower(): tipo_lbl = 'Direccional'

        # Etiqueta de Eje a la izquierda
        d.add(String(15, y_eje - 2, f"Eje {eje_num}", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor('#1E293B')))
        d.add(String(15, y_eje - 10, tipo_lbl, fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor('#64748B')))

        # Posiciones en este eje
        posiciones = e.get('posiciones', [])
        izq = [p for p in posiciones if p.get('lado') == 'izq']
        der = [p for p in posiciones if p.get('lado') == 'der']

        # Tubo del eje
        x_min_tubo = cx_vehiculo - 145 if (len(izq) > 1 or len(der) > 1) else cx_vehiculo - 110
        x_max_tubo = cx_vehiculo + 145 if (len(izq) > 1 or len(der) > 1) else cx_vehiculo + 110
        d.add(Line(x_min_tubo, y_eje, x_max_tubo, y_eje, strokeColor=colors.HexColor('#94A3B8'), strokeWidth=2))
        
        # Cubo diferencial central
        d.add(Rect(cx_vehiculo - 10, y_eje - 5, 20, 10, rx=2, ry=2, fillColor=colors.HexColor('#CBD5E1'), strokeColor=colors.HexColor('#64748B'), strokeWidth=0.75))
        d.add(Circle(cx_vehiculo, y_eje, 2.5, fillColor=colors.HexColor('#475569'), strokeColor=colors.HexColor('#334155'), strokeWidth=0.5))

        # Distribuir llantas del lado izquierdo
        coords_izq = []
        if len(izq) == 1:
            coords_izq = [(cx_vehiculo - 110, izq[0])]
        elif len(izq) == 2:
            # Exterior más a la izquierda, Interior más al centro
            ext_p = next((p for p in izq if 'ext' in str(p.get('rol', '')).lower()), izq[0])
            int_p = next((p for p in izq if p != ext_p), izq[1])
            coords_izq = [(cx_vehiculo - 145, ext_p), (cx_vehiculo - 118, int_p)]

        # Distribuir llantas del lado derecho
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

            # Colores según diagnóstico y estado
            if not registrada:
                fill_tire = colors.HexColor('#E2E8F0')
                stroke_tire = colors.HexColor('#94A3B8')
                txt_color = colors.HexColor('#64748B')
            elif p_min > 0 and p_min <= limite_retiro:
                # Retiro Crítico
                fill_tire = colors.HexColor('#FEE2E2')
                stroke_tire = colors.HexColor('#DC2626')
                txt_color = colors.HexColor('#991B1B')
            elif novedades:
                # Con Novedad
                fill_tire = colors.HexColor('#FEF3C7')
                stroke_tire = colors.HexColor('#D97706')
                txt_color = colors.HexColor('#92400E')
            elif p_min > 0 and p_min <= limite_retiro + 2.0:
                # Próximo a retiro
                fill_tire = colors.HexColor('#FFEDD5')
                stroke_tire = colors.HexColor('#EA580C')
                txt_color = colors.HexColor('#9A3412')
            else:
                # Óptima / Registrada OK (Esmeralda sutil técnico)
                fill_tire = colors.HexColor('#DCFCE7')
                stroke_tire = colors.HexColor('#16A34A')
                txt_color = colors.HexColor('#14532D')

            # Dibujo de la silueta del neumático
            x_box = wx - (w_llanta / 2)
            y_box = y_eje - (h_llanta / 2)
            d.add(Rect(x_box, y_box, w_llanta, h_llanta, rx=3.5, ry=3.5, fillColor=fill_tire, strokeColor=stroke_tire, strokeWidth=1.2))

            # Surcos decorativos sutiles
            d.add(Line(x_box + 6, y_box + 2, x_box + 6, y_box + h_llanta - 2, strokeColor=stroke_tire, strokeWidth=0.6, strokeOpacity=0.5))
            d.add(Line(x_box + 14, y_box + 2, x_box + 14, y_box + h_llanta - 2, strokeColor=stroke_tire, strokeWidth=0.6, strokeOpacity=0.5))

            # Textos técnicos dentro y debajo de la llanta
            d.add(String(wx, y_box + h_llanta - 8, f"P{pos_num}", fontName="Helvetica-Bold", fontSize=7, fillColor=txt_color, textAnchor="middle"))
            if registrada:
                d.add(String(wx, y_box + h_llanta - 17, f"{p_min:.1f}m", fontName="Helvetica-Bold", fontSize=6.5, fillColor=txt_color, textAnchor="middle"))
                d.add(String(wx, y_box + 3, f"{psi:.0f}p", fontName="Helvetica", fontSize=6, fillColor=txt_color, textAnchor="middle"))
            else:
                d.add(String(wx, y_box + 10, "PEND", fontName="Helvetica", fontSize=5.5, fillColor=txt_color, textAnchor="middle"))

            # Rol debajo
            d.add(String(wx, y_box - 7, rol_txt, fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor('#64748B'), textAnchor="middle"))

    # Repuesto (si aplica)
    y_base_rep = 24
    if ejes_repuesto:
        p_rep = ejes_repuesto[0].get('posiciones', [{}])[0].get('pos', 99)
        info_rep = pos_map.get(p_rep, {})
        reg_rep = info_rep.get('registrada', False)
        p_min_rep = info_rep.get('p_min', 0.0)
        psi_rep = info_rep.get('psi', 0.0)
        d.add(String(cx_vehiculo - 70, y_base_rep + 12, "Soporte Repuesto:", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#475569')))
        
        col_rep = colors.HexColor('#DCFCE7') if (reg_rep and p_min_rep > limite_retiro) else colors.HexColor('#FEE2E2') if reg_rep else colors.HexColor('#E2E8F0')
        str_rep = colors.HexColor('#16A34A') if (reg_rep and p_min_rep > limite_retiro) else colors.HexColor('#DC2626') if reg_rep else colors.HexColor('#94A3B8')
        d.add(Rect(cx_vehiculo + 10, y_base_rep + 2, 24, 20, rx=2.5, ry=2.5, fillColor=col_rep, strokeColor=str_rep, strokeWidth=1))
        d.add(String(cx_vehiculo + 22, y_base_rep + 14, f"P{p_rep}", fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor('#1E293B'), textAnchor="middle"))
        if reg_rep:
            d.add(String(cx_vehiculo + 22, y_base_rep + 5, f"{p_min_rep:.1f}m", fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor('#1E293B'), textAnchor="middle"))
        y_base_rep += 20

    # Barra de Leyenda en la base
    d.add(Line(10, 16, width - 10, 16, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=0.5))
    
    # Items de Leyenda
    leg_x = 25
    # 1. Verde
    d.add(Rect(leg_x, 6, 8, 8, rx=1.5, ry=1.5, fillColor=colors.HexColor('#DCFCE7'), strokeColor=colors.HexColor('#16A34A'), strokeWidth=0.8))
    d.add(String(leg_x + 12, 7.5, f"Óptima (> {limite_retiro + 2.0:.1f} mm)", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor('#334155')))
    
    # 2. Naranja
    leg_x += 115
    d.add(Rect(leg_x, 6, 8, 8, rx=1.5, ry=1.5, fillColor=colors.HexColor('#FFEDD5'), strokeColor=colors.HexColor('#EA580C'), strokeWidth=0.8))
    d.add(String(leg_x + 12, 7.5, f"Próximo Retiro ({limite_retiro:.1f} - {limite_retiro + 2.0:.1f} mm)", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor('#334155')))
    
    # 3. Rojo
    leg_x += 150
    d.add(Rect(leg_x, 6, 8, 8, rx=1.5, ry=1.5, fillColor=colors.HexColor('#FEE2E2'), strokeColor=colors.HexColor('#DC2626'), strokeWidth=0.8))
    d.add(String(leg_x + 12, 7.5, f"Retiro / Cambio (<= {limite_retiro:.1f} mm)", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#991B1B')))

    # 4. Ámbar
    leg_x += 135
    d.add(Rect(leg_x, 6, 8, 8, rx=1.5, ry=1.5, fillColor=colors.HexColor('#FEF3C7'), strokeColor=colors.HexColor('#D97706'), strokeWidth=0.8))
    d.add(String(leg_x + 12, 7.5, "Alerta / Novedad Mecánica", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor('#92400E')))

    return d

print("Función de dibujo de chasis compilada exitosamente!")
