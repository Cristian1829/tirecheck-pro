"""PDF de Motores (documento, sección 5): Motors Form con 4 firmas y Test Certificate."""
import os
from xml.sax.saxutils import escape

from motores.base import ahora, dir_archivos, dir_assets
from motores.archivos import nombre_seguro, ruta_archivo

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import qrcode


# Logos de la empresa (públicos). La firma y el sello de certificación, si algún día se usan, van en dir_assets().
DIR_LOGOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "img", "motores")


ESTADOS_EN = {"Pendiente": "PENDING", "En Taller": "IN SHOP", "Entregado Parcial": "PARTIALLY DELIVERED", "Entregado Total": "FULLY DELIVERED"}


def esc(valor):
    """Texto del usuario listo para un Paragraph de ReportLab (que interpreta sus etiquetas)."""
    return escape(str(valor if valor is not None else ""))


def _paso(texto):
    """True si el resultado escrito por el técnico indica que la prueba pasó."""
    t = str(texto or "").upper()
    return "PASS" in t and "NOT" not in t and "FAIL" not in t


def create_qr_code(content, target_path):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1A365D", back_color="white")
    img.save(target_path)
    return target_path


# ==============================================================================
# FORMATO 1: MOTORS FORM - UNIFICADO DE INGRESO Y ENTREGA EN EL MISMO DOCUMENTO
# ==============================================================================
def generate_entry_pdf(orden):
    """
    Genera el formato unificado MOTORS FORM donde en el mismo documento
    se registran tanto la recepción (PHOTO IN / DROP OFF) como la entrega (PHOTO OUT / RECEIVED).
    """
    pdf_filename = f"Motors_Form_{nombre_seguro(orden.numero_orden)}.pdf"
    pdf_dir = dir_archivos()
    uploads_dir = dir_archivos()
    assets_dir = dir_assets()
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)
    
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        title=f"Motors Form {orden.numero_orden}",
        author="Marino Trejos Mechanic",
        leftMargin=24,
        rightMargin=24,
        topMargin=18,
        bottomMargin=18
    )
    
    styles = getSampleStyleSheet()
    
    title_corp = ParagraphStyle('CorpTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor('#0F172A'), alignment=1)
    corp_sub = ParagraphStyle('CorpSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#475569'), alignment=1)
    badge_title = ParagraphStyle('BadgeTitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#1E3A8A'), alignment=1)
    
    sec_banner_in = ParagraphStyle('SecBannerIn', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white)
    sec_banner_out = ParagraphStyle('SecBannerOut', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white)
    
    cell_b = ParagraphStyle('CB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    cell_n = ParagraphStyle('CN', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#334155'))
    cell_th = ParagraphStyle('CTH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)

    story = []
    
    # 1. ENCABEZADO OFICIAL CON NUEVOS LOGOS CORPORATIVOS DE MARINO TREJOS
    logo_horiz_path = os.path.join(DIR_LOGOS, "logo_marino_horizontal.png")
    logo_seal_path = os.path.join(DIR_LOGOS, "logo_motor_service_nyc.png")

    header_logo_left = Paragraph("<b>MARINO TREJOS MECHANIC</b>", cell_b)
    if os.path.exists(logo_horiz_path):
        try:
            header_logo_left = RLImage(logo_horiz_path, width=2.65*inch, height=0.551*inch)
        except Exception:
            pass

    header_seal_right = Paragraph("", cell_n)
    if os.path.exists(logo_seal_path):
        try:
            header_seal_right = RLImage(logo_seal_path, width=0.82*inch, height=0.82*inch)
        except Exception:
            pass

    right_subtable = Table([
        [
            Paragraph("<font size='7' color='#1E3A8A'><b>NYC MOTOR SERVICE &amp; REPAIR</b></font><br/><font size='7.5' color='#475569'>180 VANDERBILT AVE BRENTWOOD NY, 11717<br/>TEL: 631-6551478</font>", ParagraphStyle('HdrTxt', parent=styles['Normal'], alignment=2)),
            header_seal_right
        ]
    ], colWidths=[2.85*inch, 0.95*inch])
    right_subtable.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))

    header_table = Table([
        [header_logo_left, right_subtable]
    ], colWidths=[3.8*inch, 3.8*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceBefore=3, spaceAfter=5))
    
    # Título del Formulario
    story.append(Paragraph("MOTORS FORM (EQUIPMENT INTAKE &amp; DELIVERY RECEIPT)", badge_title))
    story.append(Spacer(1, 4))
    
    # Metadatos del Documento
    entregas = sorted(orden.entregas, key=lambda e: e.id)
    entregados_count = sum(1 for m in orden.motores if m.estado_motor == "Entregado")
    total_motores = len(orden.motores)
    ultima_entrega = entregas[-1] if entregas else None

    date_in_str = orden.date_in.strftime("%Y-%m-%d %H:%M") if orden.date_in else ahora().strftime("%Y-%m-%d %H:%M")
    
    if entregados_count == total_motores and total_motores > 0:
        estado_label = f"<font color='#16A34A'><b>FULLY DELIVERED</b></font> ({total_motores} motor{'s' if total_motores != 1 else ''})"
        date_out_str = orden.date_out.strftime("%Y-%m-%d %H:%M") if orden.date_out else (ultima_entrega.fecha_salida.strftime("%Y-%m-%d %H:%M") if ultima_entrega and ultima_entrega.fecha_salida else "DELIVERED")
    elif entregados_count > 0:
        estado_label = f"<font color='#D97706'><b>PARTIALLY DELIVERED</b></font> ({entregados_count} of {total_motores} dispatched)"
        date_out_str = f"PARTIAL: {ultima_entrega.fecha_salida.strftime('%Y-%m-%d %H:%M')}" if ultima_entrega and ultima_entrega.fecha_salida else "PENDING IN SHOP"
    else:
        estado_label = f"<font color='#2563EB'><b>IN SHOP</b></font> ({total_motores} motor{'s' if total_motores != 1 else ''})"
        date_out_str = "PENDING IN SHOP"
    
    qr_filename = f"qr_ord_unified_{orden.id}.png"
    qr_path = os.path.join(uploads_dir, qr_filename)
    create_qr_code(f"ORDER: {orden.numero_orden}\nCOMPANY: {orden.company_name}\nSTATUS: {ESTADOS_EN.get(orden.estado_orden, orden.estado_orden)}\nDATE IN: {date_in_str}\nDATE OUT: {date_out_str}", qr_path)
    qr_img = RLImage(qr_path, width=0.82*inch, height=0.82*inch)
    
    meta_data = [
        [
            Paragraph("<b>COMPANY'S NAME:</b>", cell_b), Paragraph(f"<b>{esc(str(orden.company_name).upper())}</b>", cell_b),
            Paragraph("<b>DATE IN:</b>", cell_b), Paragraph(date_in_str, cell_n),
            qr_img
        ],
        [
            Paragraph("<b>ORDER NUMBER:</b>", cell_b), Paragraph(f"<font color='#1E3A8A'><b>{esc(orden.numero_orden)}</b></font>", cell_b),
            Paragraph("<b>DATE OUT:</b>", cell_b), Paragraph(f"<font color='#0D9488'><b>{date_out_str}</b></font>", cell_b),
            ""
        ],
        [
            Paragraph("<b>ORDER STATUS:</b>", cell_b), Paragraph(estado_label, cell_b),
            Paragraph("<b>SERVICE TYPE:</b>", cell_b), Paragraph("Overhaul / Load Test / Certification", cell_n),
            ""
        ]
    ]
    meta_table = Table(meta_data, colWidths=[1.4*inch, 2.5*inch, 1.1*inch, 1.9*inch, 0.8*inch])
    meta_table.setStyle(TableStyle([
        ('SPAN', (4, 0), (4, 2)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (3, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (4, 0), (4, 2), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))

    # ==========================================
    # SECCIÓN 1: INGRESO / INTAKE (PHOTO IN)
    # ==========================================
    sec1_title = Table([[Paragraph("<b>1. INTAKE REGISTRATION</b>", sec_banner_in)]], colWidths=[7.6*inch])
    sec1_title.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E3A8A')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(sec1_title)
    
    in_headers = [
        Paragraph("<b>#</b>", cell_th),
        Paragraph("<b>MAKE</b>", cell_th),
        Paragraph("<b>MODEL</b>", cell_th),
        Paragraph("<b>SERIAL NUMBER</b>", cell_th),
        Paragraph("<b>PHOTO IN</b>", cell_th),
        Paragraph("<b>INTAKE NOTES</b>", cell_th)
    ]
    in_rows = [in_headers]
    for idx, m in enumerate(orden.motores, 1):
        photo_flowable = Paragraph("<i>No Photo</i>", cell_n)
        photo_path = ruta_archivo(m.foto_ingreso_url)
        if photo_path and os.path.exists(photo_path):
            try:
                photo_flowable = RLImage(photo_path, width=1.1*inch, height=0.62*inch)
            except Exception:
                pass
        
        row = [
            Paragraph(str(idx), cell_n),
            Paragraph(esc(str(m.make).upper()), cell_b),
            Paragraph(esc(str(m.model).upper()), cell_n),
            Paragraph(f"<b>{esc(str(m.serial_number).upper())}</b>", cell_b),
            photo_flowable,
            Paragraph(esc(m.observaciones or "Received at shop for service."), cell_n)
        ]
        in_rows.append(row)
        
    in_table = Table(in_rows, colWidths=[0.3*inch, 1.2*inch, 1.5*inch, 1.3*inch, 1.3*inch, 2.0*inch])
    in_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(in_table)
    story.append(Spacer(1, 4))
    
    # =======================================================
    # FIRMAS DE INGRESO (2 FIRMAS: CLIENTE DROP OFF + TALLER RECEIVED)
    # =======================================================
    marino_sig_path = os.path.join(assets_dir, "marino_signature.png")
    marino_stamp_path = os.path.join(assets_dir, "marino_stamp.png")

    # Firma 1: Drop Off (Cliente que entrega)
    sig_dropoff_img = Paragraph("<i>[ Signature Pending ]</i>", cell_n)
    sig_drop_path = ruta_archivo(orden.firma_dropoff)
    if sig_drop_path and os.path.exists(sig_drop_path):
        try:
            sig_dropoff_img = RLImage(sig_drop_path, width=1.6*inch, height=0.42*inch)
        except Exception:
            pass

    # Firma 2: Received by Shop (Equipo Marino Trejos que recibe)
    sig_received_in_img = Paragraph("<i>[ Signature Pending ]</i>", cell_n)
    sig_rec_in_path = ruta_archivo(orden.firma_received)
    if sig_rec_in_path and os.path.exists(sig_rec_in_path):
        try:
            sig_received_in_img = RLImage(sig_rec_in_path, width=1.6*inch, height=0.42*inch)
        except Exception:
            pass
    elif os.path.exists(marino_sig_path):
        try:
            sig_received_in_img = RLImage(marino_sig_path, width=1.6*inch, height=0.42*inch)
        except Exception:
            pass

    dropoff_str = esc(str(orden.dropoff_name or "CUSTOMER").upper())
    received_in_str = esc(str(orden.received_name or "MARINO TREJOS").upper())

    sig_in_data = [
        [
            Paragraph("<b>1.1 DROP OFF (CUSTOMER SIGNATURE)</b>", cell_b),
            Paragraph("<b>1.2 RECEIVED BY (MARINO TREJOS SHOP)</b>", cell_b)
        ],
        [
            sig_dropoff_img,
            sig_received_in_img
        ],
        [
            Paragraph(f"<b>Name / Rep:</b> {dropoff_str} &nbsp;|&nbsp; <b>Date In:</b> {date_in_str}", cell_n),
            Paragraph(f"<b>Received by:</b> {received_in_str} &nbsp;|&nbsp; <b>Date In:</b> {date_in_str}", cell_n)
        ]
    ]
    sig_in_table = Table(sig_in_data, colWidths=[3.8*inch, 3.8*inch])
    sig_in_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF2F7')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_in_table)
    story.append(Spacer(1, 6))

    # ==========================================
    # SECCIÓN 2: ENTREGA / DELIVERY (PHOTO OUT)
    # ==========================================
    sec2_title = Table([[Paragraph("<b>2. DISPATCH &amp; DELIVERY REGISTRATION</b>", sec_banner_out)]], colWidths=[7.6*inch])
    sec2_title.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0D9488')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(sec2_title)
    
    out_headers = [
        Paragraph("<b>#</b>", cell_th),
        Paragraph("<b>MAKE</b>", cell_th),
        Paragraph("<b>MODEL</b>", cell_th),
        Paragraph("<b>SERIAL NUMBER</b>", cell_th),
        Paragraph("<b>PHOTO OUT</b>", cell_th),
        Paragraph("<b>DELIVERY STATUS</b>", cell_th)
    ]
    out_rows = [out_headers]
    # En entregas parciales, los motores pendientes aparecen arriba y los entregados en la parte de abajo
    motores_para_salida = [m for m in orden.motores if m.estado_motor != "Entregado"] + [m for m in orden.motores if m.estado_motor == "Entregado"]
    entrega_de_motor = {item.motor_id: e for e in entregas for item in e.items}
    for idx, m in enumerate(motores_para_salida, 1):
        if m.estado_motor == "Entregado":
            entrega = entrega_de_motor.get(m.id)
            detalle = ""
            if entrega:
                fecha = entrega.fecha_salida.strftime("%Y-%m-%d %H:%M") if entrega.fecha_salida else ""
                detalle = f"<br/><font size='7' color='#15803D'>{fecha} &nbsp;|&nbsp; To: {esc(str(entrega.recibe_cliente_name or 'CUSTOMER').upper())}</font>"
            status_text = f"<font color='#16A34A'><b>DELIVERED</b></font><br/><font size='7' color='#15803D'>Inspected and tested</font>{detalle}"
            photo_flowable = Paragraph("<font color='#64748B'><i>Delivered (no photo)</i></font>", cell_n)
            photo_path = ruta_archivo(m.foto_salida_url)
            if photo_path and os.path.exists(photo_path):
                try:
                    photo_flowable = RLImage(photo_path, width=1.1*inch, height=0.62*inch)
                except Exception:
                    pass
        else:
            # Motor aún NO entregado (En taller)
            photo_flowable = Paragraph("<font color='#94A3B8'><i>Pending in shop</i></font>", cell_n)
            status_text = "<font color='#DC2626'><b>PENDING IN SHOP</b></font><br/><font size='7' color='#DC2626'><b>Not delivered yet</b></font>"

        row = [
            Paragraph(str(idx), cell_n),
            Paragraph(esc(str(m.make).upper()), cell_b),
            Paragraph(esc(str(m.model).upper()), cell_n),
            Paragraph(f"<b>{esc(str(m.serial_number).upper())}</b>", cell_b),
            photo_flowable,
            Paragraph(status_text, cell_n)
        ]
        out_rows.append(row)
        
    out_table = Table(out_rows, colWidths=[0.3*inch, 1.2*inch, 1.5*inch, 1.3*inch, 1.3*inch, 2.0*inch])
    out_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#134E4A')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(out_table)
    story.append(Spacer(1, 4))
    
    # =======================================================
    # FIRMAS DE SALIDA: UN BLOQUE POR ENTREGA (TALLER DELIVERED + CLIENTE RECEIVED)
    # =======================================================
    def _firma(nombre_archivo, pendiente):
        ruta = ruta_archivo(nombre_archivo)
        if ruta:
            try:
                return RLImage(ruta, width=1.6*inch, height=0.45*inch)
            except Exception:
                pass
        return Paragraph(f"<font color='#94A3B8'><i>[ {pendiente} ]</i></font>", cell_n)

    for n, entrega in enumerate(entregas or [None], 1):
        sufijo = f" - DISPATCH {n} OF {len(entregas)}" if len(entregas) > 1 else ""
        if entrega:
            fecha = entrega.fecha_salida.strftime("%Y-%m-%d %H:%M") if entrega.fecha_salida else "PENDING"
            nombre_taller = esc(str(entrega.entrega_empresa_name or "MARINO TREJOS").upper())
            nombre_cliente = esc(str(entrega.recibe_cliente_name or "CUSTOMER").upper())
            firma_taller = _firma(entrega.firma_entrega_empresa, "Delivery Pending")
            firma_cliente = _firma(entrega.firma_recibe_cliente, "Pickup Pending")
        else:
            fecha, nombre_taller, nombre_cliente = "PENDING", "PENDING", "PENDING"
            firma_taller = _firma(None, "Delivery Pending")
            firma_cliente = _firma(None, "Pickup Pending")
        sig_out_table = Table([
            [
                Paragraph(f"<b>2.1 DELIVERED BY (MARINO TREJOS SHOP){sufijo}</b>", cell_b),
                Paragraph(f"<b>2.2 RECEIVED BY (CUSTOMER){sufijo}</b>", cell_b)
            ],
            [firma_taller, firma_cliente],
            [
                Paragraph(f"<b>Delivered by:</b> {nombre_taller} &nbsp;|&nbsp; <b>Date:</b> {fecha}", cell_n),
                Paragraph(f"<b>Received by:</b> {nombre_cliente} &nbsp;|&nbsp; <b>Date:</b> {fecha}", cell_n)
            ]
        ], colWidths=[3.8*inch, 3.8*inch])
        sig_out_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDFA')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CCFBF1')),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#99F6E4')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCFBF1')),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(KeepTogether(sig_out_table))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 2))

    # Sello de Taller Marino Trejos al pie (Certificación Final y Sello Azul)
    stamp_mech = Paragraph("", cell_n)
    if os.path.exists(marino_stamp_path):
        try:
            stamp_mech = RLImage(marino_stamp_path, width=0.85*inch, height=0.85*inch)
        except Exception:
            pass
            
    footer_data = [
        [
            Paragraph("<font size='7.5' color='#64748B'>This unified document records the <b>required signatures</b> (customer drop-off and shop receipt, shop dispatch and customer pickup) to ensure the legal and technical traceability of the equipment by <b>Marino Trejos Mechanic</b>.</font>", cell_n),
            stamp_mech
        ]
    ]
    footer_table = Table(footer_data, colWidths=[6.6*inch, 1.0*inch])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(KeepTogether(footer_table))
    
    doc.build(story)
    return pdf_filename


# ==============================================================================
# ALIAS COMPATIBILIDAD: generate_exit_pdf ahora regenera el formato unificado
# ==============================================================================
def generate_exit_pdf(entrega):
    """
    Actualiza y retorna el PDF oficial unificado de la orden donde figura
    la recepción inicial y la entrega final recién firmada.
    """
    return generate_entry_pdf(entrega.orden)


# ==============================================================================
# FORMATO 2: TEST CERTIFICATE (CERTIFICADO DE CALIDAD PROFESIONAL ACTUALIZADO)
# ==============================================================================
def generate_certificate_pdf(cert):
    """
    Genera el Certificado de Calidad con el diseño oficial modernizado,
    incluyendo el logo oficial de Tractel, sellos, firma de Marino Trejos
    y los checks verdes oficiales de inspección.
    """
    motor = cert.motor
    orden = motor.orden if motor else None
    customer_name = orden.company_name if orden else "REGISTERED CUSTOMER"
    
    pdf_filename = f"Test_Certificate_{nombre_seguro(cert.test_certificate_no)}.pdf"
    pdf_dir = dir_archivos()
    uploads_dir = dir_archivos()
    assets_dir = dir_assets()
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)
    
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        title=f"Test Certificate {cert.test_certificate_no}",
        author="Marino Trejos Mechanic",
        leftMargin=30,
        rightMargin=30,
        topMargin=24,
        bottomMargin=24
    )
    
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('CertH1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#0F172A'), alignment=1)
    h2 = ParagraphStyle('CertH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#1E3A8A'), alignment=1)
    
    sec_title = ParagraphStyle('SecTitle', parent=styles['Heading3'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white)
    cell_b = ParagraphStyle('CB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    cell_n = ParagraphStyle('CN', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155'))
    
    story = []
    
    # 1. ENCABEZADO OFICIAL CON NUEVOS LOGOS CORPORATIVOS DE MARINO TREJOS
    logo_horiz_path = os.path.join(DIR_LOGOS, "logo_marino_horizontal.png")
    logo_seal_path = os.path.join(DIR_LOGOS, "logo_motor_service_nyc.png")

    header_logo_left = Paragraph("<b>MARINO TREJOS MECHANIC</b>", cell_b)
    if os.path.exists(logo_horiz_path):
        try:
            header_logo_left = RLImage(logo_horiz_path, width=2.65*inch, height=0.551*inch)
        except Exception:
            pass

    header_seal_right = Paragraph("", cell_n)
    if os.path.exists(logo_seal_path):
        try:
            header_seal_right = RLImage(logo_seal_path, width=0.82*inch, height=0.82*inch)
        except Exception:
            pass

    right_subtable = Table([
        [
            Paragraph("<font size='7' color='#1E3A8A'><b>NYC MOTOR SERVICE &amp; REPAIR</b></font><br/><font size='7.5' color='#475569'>180 VANDERBILT AVE BRENTWOOD NY, 11717<br/>TEL: 631-6551478</font>", ParagraphStyle('HdrTxtCert', parent=styles['Normal'], alignment=2)),
            header_seal_right
        ]
    ], colWidths=[2.85*inch, 0.95*inch])
    right_subtable.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))

    header_table = Table([
        [header_logo_left, right_subtable]
    ], colWidths=[3.8*inch, 3.8*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceBefore=3, spaceAfter=5))
    
    # Título del Certificado
    story.append(Paragraph("TEST CERTIFICATE", h1))
    story.append(Paragraph(f"No. {esc(cert.test_certificate_no)}", h2))
    story.append(Spacer(1, 4))
    
    # QR Code
    qr_filename = f"qr_cert_{cert.id}.png"
    qr_path = os.path.join(uploads_dir, qr_filename)
    test_date_str = cert.test_date.strftime("%Y-%m-%d") if cert.test_date else ""
    next_serv_str = cert.next_service.strftime("%Y-%m-%d") if cert.next_service else ""
    create_qr_code(
        f"TEST CERTIFICATE: No. {cert.test_certificate_no}\nCOMPANY: {customer_name}\nMODEL: {motor.make if motor else ''} {motor.model if motor else ''}\nSERIAL: {motor.serial_number if motor else ''}\nTEST DATE: {test_date_str}\nNEXT SERVICE: {next_serv_str}\nCERTIFIED BY: {cert.certified_by}",
        qr_path
    )
    qr_img = RLImage(qr_path, width=0.9*inch, height=0.9*inch)
    
    # Cuadro Cliente y Motor
    cust_data = [
        [
            Paragraph("<b>Company Name:</b>", cell_b), Paragraph(f"<b>{esc(str(customer_name).upper())}</b>", cell_b),
            Paragraph("<b>TEST CERTIFICATE:</b>", cell_b), Paragraph(f"<b>No. {esc(cert.test_certificate_no)}</b>", cell_b),
            qr_img
        ],
        [
            Paragraph("<b>MODEL:</b>", cell_b), Paragraph(esc(str(motor.model if motor else 'N/A').upper()), cell_n),
            Paragraph("<b>TEST DATE:</b>", cell_b), Paragraph(test_date_str, cell_n),
            ""
        ],
        [
            Paragraph("<b>SERIAL #:</b>", cell_b), Paragraph(f"<b>{esc(str(motor.serial_number if motor else 'N/A').upper())}</b>", cell_b),
            Paragraph("<b>NEXT SERVICE:</b>", cell_b), Paragraph(f"<font color='#DC2626'><b>{next_serv_str}</b></font>", cell_b),
            ""
        ]
    ]
    cust_table = Table(cust_data, colWidths=[1.3*inch, 2.4*inch, 1.4*inch, 1.6*inch, 0.9*inch])
    cust_table.setStyle(TableStyle([
        ('SPAN', (4, 0), (4, 2)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (3, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (4, 0), (4, 2), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(cust_table)
    story.append(Spacer(1, 6))

    # Resultado general: un certificado con puntos sin aprobar debe decirlo a simple vista
    aprobado = all([
        cert.rectifier, cert.brake_release_lever, cert.brake_function, cert.normal_noise,
        cert.emergency_pin_descend, cert.brake_disc, cert.stirrup_adapter, cert.rated_load_test,
        _paso(cert.blocstop_trigger_speed), _paso(cert.blocstop_load_test), _paso(cert.blocstop_control_descent),
    ])
    if not aprobado:
        aviso = Table([[Paragraph("<font color='white'><b>RESULT: ONE OR MORE ITEMS NOT PASSED</b></font>", cell_b)]], colWidths=[7.6*inch])
        aviso.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#DC2626')), ('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
        story.append(aviso)
        story.append(Spacer(1, 6))

    # Icono Check Verde Oficial
    check_icon_path = os.path.join(assets_dir, "check_icon.jpg")
    def get_check_cell(val):
        if val and os.path.exists(check_icon_path):
            try:
                return RLImage(check_icon_path, width=0.18*inch, height=0.18*inch)
            except Exception:
                pass
        if val:
            return Paragraph("<font color='#16A34A'><b>PASSED</b></font>", cell_b)
        return Paragraph("<font color='#DC2626'><b>NOT PASSED</b></font>", cell_b)

    # SECCIÓN: ELECTRIC BOX &amp; PARAMETERS
    elec_header = [Paragraph("<b>INSPECTION - ELECTRIC BOX</b>", sec_title), Paragraph(f"<b>VOLTAGE: {esc(cert.voltage)}</b>", sec_title)]
    elec_data = [
        elec_header,
        [
            Paragraph(f"<b>START CAPACITOR:</b> {esc(cert.start_capacitor or 'N/A')} (Vr: {esc(cert.vr_start or '330V')})", cell_n),
            Paragraph(f"<b>K1 RESISTANCE:</b> {esc(cert.k1 or '1.8')} OHM", cell_n)
        ],
        [
            Paragraph(f"<b>RUN CAPACITOR:</b> {esc(cert.run_capacitor or 'N/A')} (Vr: {esc(cert.vr_run or '450V')})", cell_n),
            Paragraph(f"<b>K2 RESISTANCE:</b> {esc(cert.k2 or '1.8')} OHM", cell_n)
        ],
        [
            Paragraph("<b>ELECTRIC BOX CONDITION:</b> Clean / Inspected OK", cell_n),
            Paragraph(f"<b>K3 RESISTANCE:</b> {esc(cert.k3 or '2.1')} OHM", cell_n)
        ]
    ]
    elec_table = Table(elec_data, colWidths=[3.8*inch, 3.8*inch])
    elec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#1E3A8A')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(elec_table)
    story.append(Spacer(1, 6))

    # SECCIÓN: INSPECTION CHECKLIST CON ICONOS VERDES OFICIALES
    chk_header = [Paragraph("<b>OPERATIONAL &amp; SAFETY INSPECTION CHECKLIST</b>", sec_title), Paragraph("<b>VERIFICATION</b>", sec_title)]
    chk_rows = [
        chk_header,
        [Paragraph("Rectifier Diodes &amp; Voltage Stability", cell_b), get_check_cell(cert.rectifier)],
        [Paragraph("Brake Release Lever Operation", cell_b), get_check_cell(cert.brake_release_lever)],
        [Paragraph("Brake Function &amp; Dynamic Stopping Distance", cell_b), get_check_cell(cert.brake_function)],
        [Paragraph("Normal Noise &amp; Smooth Gear Transmission", cell_b), get_check_cell(cert.normal_noise)],
        [Paragraph("Emergency Pin Descent Operation", cell_b), get_check_cell(cert.emergency_pin_descend)],
        [Paragraph("Brake Disc Wear &amp; Clearance Gap", cell_b), get_check_cell(cert.brake_disc)],
        [Paragraph("Stirrup Adapter &amp; Mounting Rigidity", cell_b), get_check_cell(cert.stirrup_adapter)],
        [Paragraph("Rated Load Full Hoist Test", cell_b), get_check_cell(cert.rated_load_test)],
    ]
    chk_table = Table(chk_rows, colWidths=[5.6*inch, 2.0*inch])
    chk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(chk_table)
    story.append(Spacer(1, 6))

    # SECCIÓN: RATED LOAD &amp; BLOCSTOP / SKY-LOCK
    load_bloc_header = [
        Paragraph(f"<b>TEST CERTIFICATE: No. {esc(cert.test_certificate_no)}<br/>At {esc(cert.rated_load_capacity or '1000')} Pounds (OVERLOAD 125% RATED LOAD)</b>", sec_title),
        Paragraph("<b>BLOCSTOP / SKY-LOCK SECONDARY SAFETY BRAKE</b>", sec_title)
    ]
    load_bloc_data = [
        load_bloc_header,
        [
            Paragraph(f"<b>X-T 300:</b> 875 POUNDS", cell_n),
            Paragraph(f"<b>Model:</b> {esc(cert.blocstop_model or 'N/A')} &nbsp;|&nbsp; <b>Serial #:</b> {esc(cert.blocstop_serial or 'N/A')}", cell_n)
        ],
        [
            Paragraph(f"<b>X-T 500:</b> 1250 POUNDS", cell_n),
            Paragraph(f"<b>Rated Load:</b> {esc(cert.blocstop_rated_load or '1000 POUNDS')}", cell_n)
        ],
        [
            Paragraph(f"<b>X-T 700:</b> 1850 POUNDS", cell_n),
            Table([[Paragraph("<b>Trigger Speed:</b>", cell_b), get_check_cell(_paso(cert.blocstop_trigger_speed))]], colWidths=[1.8*inch, 1.8*inch])
        ],
        [
            Paragraph(f"<b>Overload 125% Test:</b> {esc(cert.overload_test_pounds or '1250 POUNDS')} " + ("<font color='#16A34A'><b>PASSED</b></font>" if cert.rated_load_test else "<font color='#DC2626'><b>NOT PASSED</b></font>"), cell_b),
            Table([[Paragraph("<b>Load Test:</b>", cell_b), get_check_cell(_paso(cert.blocstop_load_test))]], colWidths=[1.8*inch, 1.8*inch])
        ],
        [
            Paragraph("<b>Dynamic Hoist Stability:</b> Verified Under Load", cell_n),
            Paragraph(f"<b>Load Test Result:</b> {esc(cert.blocstop_load_test or 'N/A')}", cell_n)
        ],
        [
            Paragraph("<b>Overheat Protection:</b> Normal", cell_n),
            Table([[Paragraph("<b>Testing Control Descent:</b>", cell_b), get_check_cell(_paso(cert.blocstop_control_descent))]], colWidths=[1.8*inch, 1.8*inch])
        ]
    ]
    load_bloc_table = Table(load_bloc_data, colWidths=[3.8*inch, 3.8*inch])
    load_bloc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F766E')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#0F766E')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(load_bloc_table)
    story.append(Spacer(1, 6))

    # SECCIÓN: SERVICE DESCRIPTION
    desc_header = [Paragraph("<b>SERVICE PERFORMED:</b>", sec_title)]
    desc_data = [
        desc_header,
        [Paragraph(esc(cert.service_description or "New warning labels, oil change, oil seal, brake gap adjustment, rated dynamic load test."), cell_n)]
    ]
    desc_table = Table(desc_data, colWidths=[7.6*inch])
    desc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#64748B')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(desc_table)
    story.append(Spacer(1, 6))

    # SECCIÓN: CERTIFIED BY - CON FIRMA DE MARINO TREJOS Y SELLO AZUL CIRCULAR ORIGINAL
    marino_sig_path = os.path.join(assets_dir, "marino_signature.png")
    marino_stamp_path = os.path.join(assets_dir, "marino_stamp.png")
    
    partes_cert = [p.strip() for p in str(cert.certified_by or "").split("|")]
    tecnico = esc(partes_cert[0])
    licencia = esc(partes_cert[1].upper()) if len(partes_cert) > 1 else ""
    sig_img = Paragraph(f"<b>{tecnico}</b>", cell_b)
    if os.path.exists(marino_sig_path):
        try:
            sig_img = RLImage(marino_sig_path, width=2.2*inch, height=0.65*inch)
        except Exception:
            pass

    stamp_img = Paragraph("", cell_n)
    if os.path.exists(marino_stamp_path):
        try:
            stamp_img = RLImage(marino_stamp_path, width=1.1*inch, height=1.1*inch)
        except Exception:
            pass

    cert_box_data = [
        [
            Paragraph(f"<b>CERTIFIED BY AUTHORIZED TECHNICIAN:</b><br/><br/><b>{tecnico}</b><br/><b>{licencia}</b><br/><font size='7.5' color='#64748B'>Certified Hoist, Rigging &amp; Safety Specialist</font>", cell_n),
            sig_img,
            stamp_img
        ]
    ]
    cert_box_table = Table(cert_box_data, colWidths=[3.2*inch, 2.8*inch, 1.6*inch])
    cert_box_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(KeepTogether(cert_box_table))
    
    doc.build(story)
    return pdf_filename

