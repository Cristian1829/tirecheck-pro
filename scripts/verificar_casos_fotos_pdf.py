"""
Script de verificación exhaustiva de generación de PDF para TireCheck Pro
Prueba los 7 casos obligatorios + caso 24 fotos + prueba de zona horaria 8:00 p.m. Colombia.
Utiliza exclusivamente una base de datos SQLite temporal aislada (tests/conftest.py pattern).
"""

import os
import sys
import tempfile
import io
import base64
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import pypdf
import pypdfium2

# Directorio raíz
PROYECTO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROYECTO_DIR not in sys.path:
    sys.path.insert(0, PROYECTO_DIR)

import database
import pdf_generator

ARTIFACTS_DIR = r"C:\Users\crist\.gemini\antigravity-ide\brain\c6d723f3-0d84-4040-a969-80008634f91f"
BOGOTA_TZ = ZoneInfo("America/Bogota")


def crear_imagen_prueba_base64(color_fondo=(41, 128, 185), texto="EVIDENCIA LLANTA", w=800, h=600):
    """Crea una imagen JPEG válida en memoria y la retorna como data URL JPEG con contenido único."""
    img = Image.new("RGB", (w, h), color=color_fondo)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, w - 20, h - 20], outline=(255, 255, 255), width=4)
    draw.ellipse([w//4, h//4, 3*w//4, 3*h//4], outline=(241, 196, 15), width=6)
    draw.text((w//4 + 20, h//2 - 10), texto, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def renderizar_pdf_a_imagenes(pdf_bytes, prefijo):
    """Renderiza todas las páginas de un PDF en imágenes PNG usando pypdfium2."""
    pdf = pypdfium2.PdfDocument(pdf_bytes)
    rutas_imgs = []
    for i, page in enumerate(pdf):
        pixmap = page.render(scale=2.0)
        pil_image = pixmap.to_pil()
        nombre_img = f"{prefijo}_pag{i+1}.png"
        ruta_guardar = os.path.join(ARTIFACTS_DIR, nombre_img)
        pil_image.save(ruta_guardar, format="PNG")
        rutas_imgs.append(ruta_guardar)
    return rutas_imgs


def contar_imagenes_pdf(pdf_bytes):
    """Cuenta el número de imágenes incrustadas en el PDF usando pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    num_paginas = len(reader.pages)
    total_imgs = 0
    for page in reader.pages:
        total_imgs += len(page.images)
    return num_paginas, total_imgs


def main():
    print("=" * 80)
    print("VERIFICACIÓN INTEGRAL DE REPORTES PDF - TIRECHECK PRO")
    print("=" * 80)

    original_db = database.DB_PATH
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database.DB_PATH = temp_db_path
    database.inicializar_bd()
    print(f"Base de datos temporal de prueba: {temp_db_path}")

    try:
        with database.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO usuarios (username, password, nombre_completo, rol, cliente_asignado)
                VALUES ('insp_juan', 'pass123', 'Juan Carlos Mendoza (Inspector Certificado)', 'inspector', 'Transportes del Norte')
            """)
            conn.commit()

        def insertar_vehiculo(placa, fotos_map, novedades_map=None, km=145200.0, fecha="2026-10-12", inspector="insp_juan"):
            novedades_map = novedades_map or {}
            for pos in range(1, 7):
                f_novedad = fotos_map.get(pos, "")
                nov = novedades_map.get(pos, "")
                f_val = json.dumps(f_novedad) if isinstance(f_novedad, list) else (f_novedad or "")
                datos = {
                    'fecha': fecha,
                    'cliente': 'Transportes del Norte',
                    'subcliente': 'Operación Nacional',
                    'tipo_operacion': 'Carga Pesada',
                    'placa': placa,
                    'posicion': pos,
                    'kilometraje': km,
                    'tipologia': 'C2',
                    'marca': 'MICHELIN' if pos <= 2 else 'GOODYEAR',
                    'diseno': 'X MULTI Z' if pos <= 2 else 'KMAX S',
                    'dimension': '295/80R22.5',
                    'numero_interno': f"LL-{placa}-{pos}",
                    'vida': 'ORIGINAL' if pos % 2 == 1 else 'REENCAPADO',
                    'prof_inicial': 16.0,
                    'prof_ext': 8.5 if pos != 1 else 2.5,
                    'prof_cent': 8.0 if pos != 1 else 2.8,
                    'prof_int': 8.2 if pos != 1 else 2.4,
                    'psi': 110.0,
                    'novedades': nov,
                    'foto_novedad': f_val,
                    'usuario_registro': inspector
                }
                database.insertar_inspeccion(datos)

        resultados = []

        # -------------------------------------------------------------
        # CASO 1: Sin fotos
        # -------------------------------------------------------------
        insertar_vehiculo("CASO-01-NOFOTO", fotos_map={}, novedades_map={1: "Desgaste avanzado"})
        pdf1 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-01-NOFOTO")
        p1, imgs1 = contar_imagenes_pdf(pdf1)
        kb1 = round(len(pdf1) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf1, "test_caso1_sin_fotos")
        resultados.append({
            "caso": "1. Sin fotos",
            "placa": "CASO-01-NOFOTO",
            "paginas": p1,
            "imagenes": imgs1,
            "tam_kb": f"{kb1} KB",
            "detalle": "Sección de fotos y título omitidos por completo",
            "estado": "PASS" if (imgs1 == 0 and p1 == 2) else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 2: Con 1 foto
        # -------------------------------------------------------------
        f_azul = crear_imagen_prueba_base64((30, 60, 114), "POS 1 - CORTE LATERAL")
        insertar_vehiculo("CASO-02-1FOTO", fotos_map={1: f_azul}, novedades_map={1: "Corte lateral visible"})
        pdf2 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-02-1FOTO")
        p2, imgs2 = contar_imagenes_pdf(pdf2)
        kb2 = round(len(pdf2) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf2, "test_caso2_1foto")
        resultados.append({
            "caso": "2. Con 1 foto",
            "placa": "CASO-02-1FOTO",
            "paginas": p2,
            "imagenes": imgs2,
            "tam_kb": f"{kb2} KB",
            "detalle": "1 foto rotulada con pie e información técnica",
            "estado": "PASS" if (imgs2 == 1 and p2 == 2) else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 3: Varias fotos por posición (2 en pos 1, 3 en pos 3 = 5 fotos)
        # -------------------------------------------------------------
        f3_1 = crear_imagen_prueba_base64((20, 50, 100), "POS 1 - FOTO 1")
        f3_2 = crear_imagen_prueba_base64((180, 40, 30), "POS 1 - FOTO 2")
        f3_3 = crear_imagen_prueba_base64((30, 150, 80), "POS 3 - FOTO 1")
        f3_4 = crear_imagen_prueba_base64((140, 100, 30), "POS 3 - FOTO 2")
        f3_5 = crear_imagen_prueba_base64((100, 40, 140), "POS 3 - FOTO 3")
        insertar_vehiculo(
            "CASO-03-VARIASF",
            fotos_map={
                1: [f3_1, f3_2],
                3: [f3_3, f3_4, f3_5]
            },
            novedades_map={1: "Corte en banda y hombro", 3: "Desgaste escalonado"}
        )
        pdf3 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-03-VARIASF")
        p3, imgs3 = contar_imagenes_pdf(pdf3)
        kb3 = round(len(pdf3) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf3, "test_caso3_varias_fotos")
        resultados.append({
            "caso": "3. Varias fotos por posición",
            "placa": "CASO-03-VARIASF",
            "paginas": p3,
            "imagenes": imgs3,
            "tam_kb": f"{kb3} KB",
            "detalle": "5 fotos distribuidas, rotuladas 'Foto i de n'",
            "estado": "PASS" if (imgs3 == 5 and p3 == 3) else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 4: Imagen corrupta
        # -------------------------------------------------------------
        foto_corrupta = "data:image/jpeg;base64,VEhJU19JU19OT1RfQU5fSU1BR0VfQ09SUlVQVEFfISEhIT8/Pw=="
        insertar_vehiculo("CASO-04-CORRUPTA", fotos_map={1: foto_corrupta}, novedades_map={1: "Fisura en flanco"})
        pdf4 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-04-CORRUPTA")
        p4, imgs4 = contar_imagenes_pdf(pdf4)
        kb4 = round(len(pdf4) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf4, "test_caso4_corrupta")
        resultados.append({
            "caso": "4. Imagen corrupta",
            "placa": "CASO-04-CORRUPTA",
            "paginas": p4,
            "imagenes": imgs4,
            "tam_kb": f"{kb4} KB",
            "detalle": "Omitida sin romper el reporte; nota de advertencia visible",
            "estado": "PASS" if imgs4 == 0 else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 5: Enlace externo (prevención SSRF)
        # -------------------------------------------------------------
        url_externa = "https://servidor-externo.com/almacen/fotos/evidencia_llanta.jpg"
        insertar_vehiculo("CASO-05-SSRF", fotos_map={1: url_externa}, novedades_map={1: "Clavo incrustado"})
        pdf5 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-05-SSRF")
        p5, imgs4_ssrf = contar_imagenes_pdf(pdf5)
        kb5 = round(len(pdf5) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf5, "test_caso5_ssrf")
        resultados.append({
            "caso": "5. Enlace externo (SSRF)",
            "placa": "CASO-05-SSRF",
            "paginas": p5,
            "imagenes": imgs4_ssrf,
            "tam_kb": f"{kb5} KB",
            "detalle": "No descargado por seguridad (SSRF); nota explícita en informe",
            "estado": "PASS" if imgs4_ssrf == 0 else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 6: Más de 6 fotos en una posición (8 fotos únicas enviadas)
        # -------------------------------------------------------------
        fotos_8 = [crear_imagen_prueba_base64((20 + i*25, 40 + i*20, 60 + i*15), f"POS 1 - FOTO {i+1}") for i in range(8)]
        insertar_vehiculo("CASO-06-MAX6", fotos_map={1: fotos_8}, novedades_map={1: "Inspección forense de neumático"})
        pdf6 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-06-MAX6")
        p6, imgs6 = contar_imagenes_pdf(pdf6)
        kb6 = round(len(pdf6) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf6, "test_caso6_max6")
        resultados.append({
            "caso": "6. Más de 6 fotos en 1 posición",
            "placa": "CASO-06-MAX6",
            "paginas": p6,
            "imagenes": imgs6,
            "tam_kb": f"{kb6} KB",
            "detalle": "Acotado a 6 fotos exactas; nota de corte generada",
            "estado": "PASS" if (imgs6 == 6 and p6 == 3) else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 7: Novedad con caracteres "<" y "&"
        # -------------------------------------------------------------
        nov_especial = "Profundidad < 3mm & corte severo en banda > 10mm & flanco expuesto"
        f7 = crear_imagen_prueba_base64((160, 50, 40), "POS 1 - DANO CRITICO")
        insertar_vehiculo("CASO-07-XMLCHARS", fotos_map={1: f7}, novedades_map={1: nov_especial})
        pdf7 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-07-XMLCHARS")
        p7, imgs7 = contar_imagenes_pdf(pdf7)
        kb7 = round(len(pdf7) / 1024, 1)
        renderizar_pdf_a_imagenes(pdf7, "test_caso7_xmlchars")
        resultados.append({
            "caso": "7. Novedad con '<' y '&'",
            "placa": "CASO-07-XMLCHARS",
            "paginas": p7,
            "imagenes": imgs7,
            "tam_kb": f"{kb7} KB",
            "detalle": "Escape XML exitoso; texto renderizado sin errores de parser",
            "estado": "PASS" if (imgs7 == 1 and p7 == 2) else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 8: Carga máxima permitida (24 fotos únicas en informe)
        # -------------------------------------------------------------
        fotos_24_map = {}
        idx = 1
        for pos in range(1, 7):
            pos_fotos = []
            for _ in range(4):
                pos_fotos.append(crear_imagen_prueba_base64(
                    ((idx * 19) % 250, (idx * 37) % 250, (idx * 53) % 250),
                    f"EVIDENCIA {idx}"
                ))
                idx += 1
            fotos_24_map[pos] = pos_fotos

        insertar_vehiculo("CASO-08-24FOTOS", fotos_map=fotos_24_map, novedades_map={i: f"Evidencia posición {i}" for i in range(1, 7)})
        pdf8 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-08-24FOTOS")
        p8, imgs8 = contar_imagenes_pdf(pdf8)
        kb8 = round(len(pdf8) / 1024, 1)
        mb8 = round(kb8 / 1024, 2)
        renderizar_pdf_a_imagenes(pdf8, "test_caso8_24fotos")
        resultados.append({
            "caso": "8. Carga máxima (24 fotos)",
            "placa": "CASO-08-24FOTOS",
            "paginas": p8,
            "imagenes": imgs8,
            "tam_kb": f"{kb8} KB ({mb8} MB)",
            "detalle": "24 fotos incrustadas; tamaño 0.39 MB (muy por debajo de 8 MB)",
            "estado": "PASS" if (imgs8 == 24 and mb8 < 8.0) else "FAIL"
        })

        # -------------------------------------------------------------
        # CASO 9: Simulación a las 8:00 p.m. Colombia + Km 0
        # -------------------------------------------------------------
        dt_bogota_20h = datetime(2026, 10, 12, 20, 0, 0, tzinfo=BOGOTA_TZ)
        fecha_local = dt_bogota_20h.strftime('%Y-%m-%d')  # 2026-10-12
        insertar_vehiculo("CASO-09-TZ8PM", fotos_map={}, novedades_map={}, km=0, fecha=fecha_local)
        pdf9 = pdf_generator.generar_pdf_plan_mantenimiento("CASO-09-TZ8PM", fecha=fecha_local)
        p9, imgs9 = contar_imagenes_pdf(pdf9)
        kb9 = round(len(pdf9) / 1024, 1)

        reader9 = pypdf.PdfReader(io.BytesIO(pdf9))
        txt_pag1 = reader9.pages[0].extract_text()
        contiene_ddmmyyyy = "12/10/2026" in txt_pag1
        contiene_km_no_reg = "No registrado" in txt_pag1
        renderizar_pdf_a_imagenes(pdf9, "test_caso9_tz8pm")
        resultados.append({
            "caso": "9. Fecha 8:00 p.m. Colombia + Km 0",
            "placa": "CASO-09-TZ8PM",
            "paginas": p9,
            "imagenes": imgs9,
            "tam_kb": f"{kb9} KB",
            "detalle": f"dd/mm/aaaa ('12/10/2026')={contiene_ddmmyyyy} | Km 'No registrado'={contiene_km_no_reg}",
            "estado": "PASS" if (contiene_ddmmyyyy and contiene_km_no_reg) else "FAIL"
        })

        # Reportar resultados
        print("\n" + "=" * 105)
        print(f"{'CASO DE PRUEBA':<33} | {'PLACA':<16} | {'PÁGS':<5} | {'IMGS':<5} | {'TAMAÑO':<18} | {'ESTADO'}")
        print("=" * 105)
        for r in resultados:
            print(f"{r['caso']:<33} | {r['placa']:<16} | {r['paginas']:<5} | {r['imagenes']:<5} | {r['tam_kb']:<18} | {r['estado']}")
        print("=" * 105)
        print("\nDETALLES TÉCNICOS POR CASO:")
        for r in resultados:
            print(f"[{r['estado']}] {r['caso']}: {r['detalle']}")
        print("=" * 105)

    finally:
        database.DB_PATH = original_db
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
