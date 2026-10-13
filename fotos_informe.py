"""
Módulo de Procesamiento e Inserción de Evidencia Fotográfica en Reportes PDF
TireCheck Pro - Inspección Técnica Vehicular
"""

import base64
import html
import io
import json
import re
from typing import List, Dict, Any, Tuple, Optional

from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether

MAX_FOTOS_POR_POSICION = 6
MAX_FOTOS_POR_INFORME = 24
MAX_PX_LADO = 900
CALIDAD_JPEG = 75


def extraer_lista_fotos(campo_foto: Any) -> List[str]:
    """
    Normaliza el campo foto_novedad (string único, lista JSON o lista Python)
    a una lista de cadenas individuales.
    """
    if not campo_foto:
        return []
    if isinstance(campo_foto, list):
        return [str(x).strip() for x in campo_foto if str(x).strip()]
    if isinstance(campo_foto, str):
        s = campo_foto.strip()
        if not s:
            return []
        if s.startswith('[') and s.endswith(']'):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                try:
                    import ast
                    parsed = ast.literal_eval(s)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
        return [s]
    return []


def procesar_data_url_foto(item_foto: str) -> Tuple[Optional[io.BytesIO], Optional[Tuple[int, int]], Optional[str]]:
    """
    Valida y procesa una fotografía conforme a las directrices de seguridad y calidad:
    - Omitir y advertir si es enlace externo (previene SSRF).
    - Decodificar data URL en Base64.
    - Manejar excepciones en caso de imagen inválida o corrupta.
    - Corregir orientación EXIF.
    - Aplanar transparencias a RGB sobre fondo blanco.
    - Redimensionar proporcionalmente si excede 900 px.
    - Recomprimir a JPEG con calidad 75.

    Retorna: (BytesIO_JPEG, (ancho, alto), mensaje_nota)
    """
    s = (item_foto or '').strip()
    if not s:
        return None, None, None

    # 1. Regla de seguridad: enlaces externos NO se descargan (previene SSRF)
    if s.startswith(('http://', 'https://')):
        url_corta = s[:60] + ('...' if len(s) > 60 else '')
        return None, None, f"Enlace externo omitido por política de seguridad (SSRF): {url_corta}"

    # 2. Debe ser un data URL o base64 de imagen
    if s.startswith('data:'):
        match = re.match(r'^data:image/[a-zA-Z0-9\+\-\.]+;base64,(.+)$', s, re.DOTALL)
        if not match:
            return None, None, "Formato data URL no reconocido o no codificado en Base64."
        b64_str = match.group(1).strip()
    else:
        # Cadena Base64 directa
        b64_str = s

    # 3. Decodificación Base64
    try:
        raw_bytes = base64.b64decode(b64_str)
    except Exception as e:
        return None, None, f"Error decodificando imagen en Base64 ({e})."

    if len(raw_bytes) == 0:
        return None, None, "Contenido de imagen vacío."

    # 4. Carga y verificación con Pillow
    try:
        img_temp = Image.open(io.BytesIO(raw_bytes))
        img_temp.verify()  # Valida cabeceras e integridad
        # Reabrir porque verify() invalida el puntero interno
        img = Image.open(io.BytesIO(raw_bytes))
    except Exception as e:
        return None, None, f"Imagen inválida o archivo corrupto ({e})."

    # 5. Corrección de orientación EXIF
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # 6. Aplanar transparencias (RGBA/LA/P) sobre lienzo blanco
    try:
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            fondo_blanco = Image.new('RGB', img.size, (255, 255, 255))
            fondo_blanco.paste(img, mask=img.split()[3])
            img = fondo_blanco
        elif img.mode != 'RGB':
            img = img.convert('RGB')
    except Exception as e:
        return None, None, f"Error normalizando canales de color ({e})."

    # 7. Redimensionar si supera 900 px en su dimensión mayor
    w, h = img.size
    if max(w, h) > MAX_PX_LADO:
        img.thumbnail((MAX_PX_LADO, MAX_PX_LADO), Image.Resampling.LANCZOS)
        w, h = img.size

    # 8. Recompresión a JPEG con calidad 75
    out_buf = io.BytesIO()
    try:
        img.save(out_buf, format='JPEG', quality=CALIDAD_JPEG, optimize=True)
        out_buf.seek(0)
    except Exception as e:
        return None, None, f"Error recomprimiendo imagen JPEG ({e})."

    return out_buf, (w, h), None


def normalizar_lado_rol(lado: Any, rol: Any) -> str:
    """
    Construye una descripción amigable del lado y rol para el pie de foto.
    Ejemplos: 'Izq. EXT', 'Der. INT', 'Der. DIR', 'REPUESTO'.
    """
    l_str = str(lado or '').strip().lower()
    r_str = str(rol or '').strip().upper()

    if 'rep' in r_str or 'aux' in r_str or 'rep' in l_str:
        return "REPUESTO"

    prefix = "Izq." if l_str.startswith('izq') else "Der." if l_str.startswith('der') else ""
    if prefix and r_str:
        return f"{prefix} {r_str}"
    return prefix or r_str or "LLANTA"


def seccion_fotos(llantas: List[Dict[str, Any]]) -> List[Any]:
    """
    Genera la sección 'Evidencia fotográfica' para el informe PDF.
    
    Parámetros:
    - llantas: lista de diccionarios con keys: pos, eje, lado, rol, novedad, foto_novedad.
    
    Reglas estrictas aplicadas:
    - Si no hay fotos válidas, retorna lista vacía [] (no genera título ni sección).
    - Máximo 6 fotos por posición y 24 fotos por informe en total.
    - Cuadrícula de fotos balanceada (2 columnas de 265 pt c/u sobre ancho 540 pt).
    - Pie de foto con información detallada y texto de novedad con escape XML.
    - Notas de advertencia por enlaces externos (SSRF) o imágenes corruptas.
    """
    if not llantas:
        return []

    fotos_procesadas = []
    notas_auditoria = []
    total_fotos_global = 0

    for llanta in llantas:
        if total_fotos_global >= MAX_FOTOS_POR_INFORME:
            break

        pos = llanta.get('pos', '-')
        eje = llanta.get('eje', '-')
        lado = llanta.get('lado', '')
        rol = llanta.get('rol', '')
        novedad = str(llanta.get('novedad') or '').strip()
        campo_fotos = llanta.get('foto_novedad')

        lista_raw = extraer_lista_fotos(campo_fotos)
        if not lista_raw:
            continue

        if len(lista_raw) > MAX_FOTOS_POR_POSICION:
            notas_auditoria.append(
                f"Posición {pos}: se registraron {len(lista_raw)} fotos; se procesaron únicamente las primeras {MAX_FOTOS_POR_POSICION} por límite técnico."
            )
            lista_raw = lista_raw[:MAX_FOTOS_POR_POSICION]

        total_pos = len(lista_raw)
        lado_rol_txt = normalizar_lado_rol(lado, rol)

        for idx, item in enumerate(lista_raw, start=1):
            if total_fotos_global >= MAX_FOTOS_POR_INFORME:
                notas_auditoria.append(
                    f"Se alcanzó el límite máximo de {MAX_FOTOS_POR_INFORME} fotos por informe. Fotos adicionales fueron omitidas."
                )
                break

            buf_img, dims, nota_err = procesar_data_url_foto(item)
            if nota_err:
                notas_auditoria.append(f"Posición {pos} (Foto {idx} de {total_pos}): {nota_err}")
                continue

            if buf_img and dims:
                fotos_procesadas.append({
                    'buf': buf_img,
                    'dims': dims,
                    'pos': pos,
                    'eje': eje,
                    'lado_rol': lado_rol_txt,
                    'foto_idx': idx,
                    'foto_total': total_pos,
                    'novedad': novedad
                })
                total_fotos_global += 1

    # Regla 4: Si no hay fotos válidas ni notas, no debe aparecer la sección ni su título
    if not fotos_procesadas and not notas_auditoria:
        return []

    elements = []

    # Estilos tipográficos
    style_sec_tit = ParagraphStyle(
        'SecTitFotos',
        fontName='Helvetica-Bold',
        fontSize=10.0,
        leading=13.0,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=5
    )
    style_pie_tit = ParagraphStyle(
        'PieTitFoto',
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#0F172A'),
        alignment=0
    )
    style_pie_nov = ParagraphStyle(
        'PieNovFoto',
        fontName='Helvetica',
        fontSize=6.0,
        leading=8.0,
        textColor=colors.HexColor('#475569'),
        alignment=0
    )
    style_nota_adv = ParagraphStyle(
        'NotaAdvFoto',
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#D97706'),
        spaceBefore=2,
        spaceAfter=2
    )

    # Título de la sección
    elements.append(Paragraph("Evidencia fotográfica", style_sec_tit))

    # Construcción de celdas de cuadrícula (2 columnas)
    ancho_col = 265.0
    ancho_img = 255.0
    alto_max_img = 160.0

    celdas = []
    for f_info in fotos_procesadas:
        w_orig, h_orig = f_info['dims']
        ratio = h_orig / max(1, w_orig)
        alto_calc = min(alto_max_img, ancho_img * ratio)

        rl_img = RLImage(f_info['buf'], width=ancho_img, height=alto_calc)

        # Escape XML estricto en el texto del pie de foto
        pos_esc = html.escape(str(f_info['pos']))
        eje_esc = html.escape(str(f_info['eje']))
        lrol_esc = html.escape(f_info['lado_rol'])
        idx_esc = f_info['foto_idx']
        tot_esc = f_info['foto_total']
        nov_texto = f_info['novedad'] or "Novedad registrada"
        nov_esc = html.escape(nov_texto)

        txt_cabecera = f"Posición {pos_esc} · Eje {eje_esc} · {lrol_esc} · Foto {idx_esc} de {tot_esc}"
        p_tit = Paragraph(f"<b>{txt_cabecera}</b>", style_pie_tit)
        p_nov = Paragraph(f"Novedad: {nov_esc}", style_pie_nov)

        contenido_celda = [
            rl_img,
            Spacer(1, 2),
            p_tit,
            Spacer(1, 1),
            p_nov
        ]
        celdas.append(contenido_celda)

    # Agrupar en pares para tabla de 2 columnas
    filas_tabla = []
    for i in range(0, len(celdas), 2):
        col1 = celdas[i]
        col2 = celdas[i + 1] if (i + 1 < len(celdas)) else ""
        filas_tabla.append([col1, col2])

    if filas_tabla:
        t_fotos = Table(filas_tabla, colWidths=[ancho_col, ancho_col])
        t_fotos.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#F1F5F9')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FAFAFA')),
        ]))
        elements.append(t_fotos)
        elements.append(Spacer(1, 4))

    # Notas de auditoría (SSRF o imágenes no válidas)
    if notas_auditoria:
        for nota in notas_auditoria:
            elements.append(Paragraph(f"• <i>{html.escape(nota)}</i>", style_nota_adv))
        elements.append(Spacer(1, 4))

    return elements
