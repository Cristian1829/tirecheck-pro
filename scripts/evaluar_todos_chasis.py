import os, sys
import pypdfium2

PROYECTO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROYECTO_DIR not in sys.path:
    sys.path.insert(0, PROYECTO_DIR)

import database, pdf_generator
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

ARTIFACTS_DIR = r"C:\Users\crist\.gemini\antigravity-ide\brain\c6d723f3-0d84-4040-a969-80008634f91f"

# Obtener todas las tipologías
with database.get_connection() as conn:
    c = conn.cursor()
    c.execute("SELECT nombre, cant_llantas, esquema_json FROM catalogo_tipologias ORDER BY cant_llantas ASC")
    tipologias = c.fetchall()

print(f"Total tipologías a evaluar: {len(tipologias)}")

styles = getSampleStyleSheet()

for t in tipologias:
    nombre, cant, esq_json = t[0], t[1], t[2]
    # Crear filas simuladas con datos completos
    filas_sim = []
    for p in range(1, cant + 1):
        filas_sim.append({
            'posicion': p,
            'prof_ext': 8.5 if p % 3 != 0 else 2.5,
            'prof_cent': 8.0,
            'prof_int': 8.2,
            'psi': 110,
            'novedades': 'Desgaste irregular' if p == 1 else '',
            'numero_interno': f'LL-{p}',
            'marca': 'MICHELIN'
        })
    
    # Dibujar diagrama
    drawing = pdf_generator.dibujar_diagrama_chasis_reportlab(nombre, filas_sim, limite_retiro=3.0, width=540)
    
    # Armar PDF rápido de 1 página
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elems = [
        Paragraph(f"<b>Tipología: {nombre} ({cant} llantas)</b>", styles['Normal']),
        Spacer(1, 10),
        drawing
    ]
    doc.build(elems)
    
    # Renderizar a imagen
    pdf_doc = pypdfium2.PdfDocument(buf.getvalue())
    page = pdf_doc[0]
    pix = page.render(scale=2.0)
    slug = nombre.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "").replace("+", "plus")
    img_name = f"chasis_{slug}.png"
    out_path = os.path.join(ARTIFACTS_DIR, img_name)
    pix.to_pil().save(out_path)
    print(f"OK: {nombre} -> {img_name}")

print("Evaluación de todas las tipologías completada.")
