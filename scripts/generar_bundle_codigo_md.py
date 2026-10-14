import os
import re
import sqlite3
import datetime
import shutil
from pathlib import Path

# Directorio raíz del proyecto
PROYECTO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE_1 = PROYECTO_DIR / "CODIGO_COMPLETO_PROYECTO.md"
OUTPUT_FILE_2 = PROYECTO_DIR.parent / "CODIGO_COMPLETO_PROYECTO.md"

# Lista canónica de los 40 archivos de código y documentación del proyecto
FILES_SPEC = [
    # 1. Configuración, Entorno y Despliegue en la Nube
    ("requirements.txt", "1. Configuración, Entorno y Despliegue en la Nube", "text", "Dependencias de paquetes Python (FastAPI, uvicorn, reportlab, pandas, etc.)"),
    (".gitignore", "1. Configuración, Entorno y Despliegue en la Nube", "gitignore", "Reglas de exclusión de Git"),
    (".dockerignore", "1. Configuración, Entorno y Despliegue en la Nube", "gitignore", "Reglas de exclusión para compilación de imagen Docker"),
    ("Dockerfile", "1. Configuración, Entorno y Despliegue en la Nube", "dockerfile", "Definición estandarizada del contenedor Docker para producción/cloud"),
    ("render.yaml", "1. Configuración, Entorno y Despliegue en la Nube", "yaml", "Blueprint de infraestructura como código para despliegue automático en Render.com"),
    ("INICIAR_TIRECHECK.bat", "1. Configuración, Entorno y Despliegue en la Nube", "bat", "Script de arranque automático para Windows: verificación de entorno, servidor uvicorn y apertura de navegador"),
    ("iniciar_app.bat", "1. Configuración, Entorno y Despliegue en la Nube", "bat", "Script de arranque directo sin dependencias"),

    # 2. Documentación Técnica y Arquitectura
    ("README.md", "2. Arquitectura y Documentación Técnica", "markdown", "Documento general del repositorio, resumen de arquitectura y guía de inicio"),
    ("docs/GUIA_DESPLIEGUE_RENDER.md", "2. Arquitectura y Documentación Técnica", "markdown", "Guía paso a paso para desplegar TireAnalyze Pro en Render.com de forma 100% gratuita"),
    ("docs/AGENTS.md", "2. Arquitectura y Documentación Técnica", "markdown", "Guía especializada para Agentes de IA: invariantes del sistema, reglas críticas y no regresión"),
    ("docs/ARCHITECTURE.md", "2. Arquitectura y Documentación Técnica", "markdown", "Arquitectura en capas, diagrama C4, flujos de inspección y persistencia de datos"),
    ("docs/API_REFERENCE.md", "2. Arquitectura y Documentación Técnica", "markdown", "Especificación técnica de los endpoints RESTful de FastAPI"),
    ("docs/REGLAS_NEGOCIO.md", "2. Arquitectura y Documentación Técnica", "markdown", "Reglas de negocio, los 6 candados operativos y algoritmos predictivos"),
    ("docs/CHASIS_INTERACTIVO.md", "2. Arquitectura y Documentación Técnica", "markdown", "Especificación del componente interactivo de chasis por ejes y esquemas JSON"),
    ("docs/DOCUMENTACION_MIGRACION.md", "2. Arquitectura y Documentación Técnica", "markdown", "Trazabilidad de migración de escritorio Tkinter a plataforma Web SPA"),
    ("docs/CONTRIBUTING.md", "2. Arquitectura y Documentación Técnica", "markdown", "Guía de contribución, buenas prácticas, PEP 8 y checklist de testing"),

    # 3. Núcleo Backend & API REST
    ("server.py", "3. Núcleo Backend & API REST", "python", "Servidor FastAPI principal: endpoints REST, autenticación, subida de archivos, integración ngrok y serving estático"),
    ("database.py", "3. Núcleo Backend & API REST", "python", "Capa de persistencia SQLite: DDL, migraciones automáticas, CRUD de inspecciones, diagnósticos, KPIs y catálogos"),
    ("logica_inspeccion.py", "3. Núcleo Backend & API REST", "python", "Módulo de lógica pura: validación de los 6 candados, reglas de diagnóstico y estados"),
    ("pdf_generator.py", "3. Núcleo Backend & API REST", "python", "Motor de generación de informes técnicos PDF (ReportLab): diagramas de chasis, tabla de mediciones y evidencias"),
    ("fotos_informe.py", "3. Núcleo Backend & API REST", "python", "Gestor de fotografías de inspección: redimensionamiento, compresión y renderizado en grid para el PDF"),
    ("app.py", "3. Núcleo Backend & API REST", "python", "Aplicación de escritorio Tkinter con servidor FastAPI/uvicorn integrado en hilo secundario"),

    # 4. Frontend Web SPA & Plantillas
    ("templates/index.html", "4. Frontend Web SPA & Plantillas", "html", "Aplicación Web SPA integral: HTML5, CSS Glassmorphism y JavaScript modular (Patio, Base, Diagnósticos, KPIs, Catálogos, Modo Offline)"),
    ("templates/preview_chasis.html", "4. Frontend Web SPA & Plantillas", "html", "Visor interactivo y banco de pruebas de renderizado de tipologías de chasis"),

    # 5. Suite de Pruebas Automatizadas (Pytest)
    ("tests/conftest.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Configuración de fixtures y base de datos SQLite en memoria para tests aislados"),
    ("tests/test_api_web.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas de endpoints RESTful y respuestas HTTP de FastAPI"),
    ("tests/test_automatizacion_placa_llanta.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas de vinculación placa-esquema, autocompletado multi-tenant de llantas y rotación intermensual"),
    ("tests/test_candados.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas unitarias de los 6 candados operativos de captura en patio"),
    ("tests/test_diagnostico.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas unitarias de diagnósticos automáticos (alineación, duales y retiro)"),
    ("tests/test_diagrama_chasis.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas del generador vectorial de diagramas de chasis en PDF"),
    ("tests/test_kpis.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas de cálculo de desgaste mm, rendimiento km/mm y CPK"),
    ("tests/test_pdf.py", "5. Suite de Pruebas Automatizadas (Pytest)", "python", "Pruebas de generación y estructura de informes técnicos PDF"),

    # 6. Scripts de Auditoría, Pruebas y Diagnóstico
    ("scripts/README.md", "6. Scripts de Auditoría, Soporte y Diagnóstico", "markdown", "Documentación del directorio de scripts auxiliares"),
    ("scripts/evaluar_todos_chasis.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Auditoría exhaustiva de renderizado para todas las tipologías de vehículos"),
    ("scripts/probar_chasis_ee3123.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Validación específica para chasis de vehículo placa EE3123"),
    ("scripts/test_pdf_chasis.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Verificación de dibujo vectorial de chasis en el informe PDF"),
    ("scripts/verificar_casos_fotos_pdf.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Auditoría de alineación de cuadrícula de fotos en página 2 del PDF"),
    ("scripts/verificar_informe_y_color_sutil.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Verificación de estilos, contrastes y jerarquía visual en PDF"),
    ("scripts/patch_db_kpis_tip.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Script de migración y parche de campos de KPIs y tipologías"),
    ("scripts/auditar_index_produccion.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Auditoría estática de sintaxis y consistencia de index.html"),
    ("scripts/auditar_preview.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Verificación de visualización en preview_chasis.html"),
    ("scripts/auditar_repuesto.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Auditoría de asignación y cálculo de llanta de repuesto"),
    ("scripts/check_js.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Validador sintáctico de los bloques <script> de index.html"),
    ("scripts/test_nuevo_informe_base.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Pruebas de renderizado comparativo del informe técnico"),
    ("scripts/generar_y_capturar_nuevo_pdf.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Pipeline automatizado de generación de PDF y renderizado a PNG para regresión visual"),
    ("scripts/capturar_banners_hd.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Pipeline de auditoría y captura de pantalla en HD (Desktop, Tablet, Mobile) para el nuevo banner"),
    ("scripts/test_read.py", "6. Scripts de Auditoría, Soporte y Diagnóstico", "python", "Script básico de lectura y diagnóstico de datos")
]

def obtener_esquema_db():
    db_path = PROYECTO_DIR / "data" / "inspecciones.db"
    if not db_path.exists():
        return "-- Base de datos data/inspecciones.db no encontrada."
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cur.fetchall()
    conn.close()
    
    ddl_lines = []
    for name, sql in tables:
        if sql:
            ddl_lines.append(f"-- ========================================================")
            ddl_lines.append(f"-- TABLA: {name}")
            ddl_lines.append(f"-- ========================================================")
            ddl_lines.append(sql.strip() + ";\n")
    return "\n".join(ddl_lines)

def calcular_fence(contenido, lang):
    # Calcula el número de backticks necesarios para que ningún contenido interno cierre el bloque
    backticks = re.findall(r"`+", contenido)
    max_b = max([len(b) for b in backticks], default=0)
    fence_len = max(3, max_b + 1)
    fence = "`" * fence_len
    return f"{fence}{lang}\n{contenido.rstrip()}\n{fence}"

def slugify(text):
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s

def generar_documento():
    print("Iniciando compilación del código completo...")
    fecha_generacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Estadísticas previas
    total_archivos = len(FILES_SPEC)
    total_lineas = 0
    total_bytes = 0
    archivos_info = []

    for rel_path, categoria, lang, desc in FILES_SPEC:
        full_path = PROYECTO_DIR / rel_path
        if not full_path.exists():
            print(f"ALERTA: Archivo no encontrado: {rel_path}")
            continue
        content = full_path.read_text(encoding="utf-8", errors="replace")
        lines_count = len(content.splitlines())
        size_bytes = full_path.stat().st_size
        total_lineas += lines_count
        total_bytes += size_bytes
        archivos_info.append({
            "rel_path": rel_path,
            "categoria": categoria,
            "lang": lang,
            "desc": desc,
            "lines": lines_count,
            "bytes": size_bytes,
            "content": content
        })

    md = []
    # Encabezado principal
    md.append("# 🚛 TireAnalyze Pro — Código Completo del Proyecto para Análisis de IA")
    md.append("")
    md.append("> **Documento unificado que contiene el 100% del código fuente, arquitectura, esquemas de datos y suite de pruebas de TireAnalyze Pro.**")
    md.append("> Optimizado para ingesta directa por Modelos de Lenguaje (LLMs) y agentes inteligentes de desarrollo.")
    md.append("")
    md.append("## 📌 Metadatos del Repositorio")
    md.append("")
    md.append(f"- **Nombre del Sistema:** TireAnalyze Pro (Suite Web Integral de Inspección y Diagnóstico de Llantas)")
    md.append(f"- **Fecha de Generación:** `{fecha_generacion}`")
    md.append(f"- **Total de Archivos Incluidos:** `{total_archivos}` archivos de código y documentación")
    md.append(f"- **Líneas Totales de Código:** `{total_lineas:,}` líneas")
    md.append(f"- **Tamaño Total de Código Fuente:** `{total_bytes / 1024:.1f} KB` (`{total_bytes:,}` bytes)")
    md.append(f"- **Stack Principal:** Python 3.12 | FastAPI 0.115+ | SQLite 3 | ReportLab (PDF) | Vanilla HTML5/CSS/JS SPA | Tkinter (Desktop)")
    md.append("")
    md.append("---")
    md.append("")

    # Resumen Arquitectónico
    md.append("## 🏗️ Resumen Arquitectónico del Sistema")
    md.append("")
    md.append("TireAnalyze Pro es una plataforma **Offline-First** diseñada para la gestión técnica de neumáticos de flotas de transporte pesado:")
    md.append("")
    md.append("1. **Frontend Web SPA (`templates/index.html`):**")
    md.append("   - Sin dependencias de frameworks pesados (Vanilla JS, CSS personalizado con estética Glassmorphism moderna y modo oscuro/claro).")
    md.append("   - Soporte Offline transparente mediante caché de navegador y cola de sincronización diferida hacia SQLite.")
    md.append("   - Mapeo interactivo visual del chasis (4x2, 6x4, 8x4, remolques) por ejes, posiciones y llanta de repuesto.")
    md.append("   - Vistas integradas: Inspección de Patio, Base de Inspecciones, Diagnósticos & Planes de Acción, Trazabilidad & KPIs de Llantas, Catálogos & Configuración, y Módulo QR/Túnel Remoto.")
    md.append("")
    md.append("2. **Backend API REST (`server.py` & `database.py`):**")
    md.append("   - Framework FastAPI de alto rendimiento con validación tipada.")
    md.append("   - Persistencia relacional en SQLite con auto-migración de esquema (`data/inspecciones.db`).")
    md.append("   - Integración nativa con `pyngrok` y generador de códigos QR para conectar dispositivos móviles en patio en segundos.")
    md.append("")
    md.append("3. **Motor de Diagnóstico y Reglas de Negocio (`logica_inspeccion.py`):**")
    md.append("   - **6 Candados de Seguridad Operativos:** límite de desgaste crítico, presiones anormales (baja/alta), diferencia entre duales, desgastes irregulares (alineación) y semáforo de estado.")
    md.append("   - Fórmulas predictivas de Costo por Kilómetro (CPK), rendimiento proyectado y fechas estimadas de retiro.")
    md.append("")
    md.append("4. **Motor de Generación de Informes PDF (`pdf_generator.py` & `fotos_informe.py`):**")
    md.append("   - Reportes ejecutivos a dos páginas con ReportLab: página 1 con resumen de flota, ficha vehicular, diagrama vectorial de chasis y tabla de mediciones; página 2 con cuadrícula simétrica de fotos de novedades con sellos de posición y observación.")
    md.append("")
    md.append("---")
    md.append("")

    # Esquema de Base de Datos
    md.append("## 🗄️ Esquema Completo de Base de Datos SQLite (DDL)")
    md.append("")
    md.append("La base de datos reside en `data/inspecciones.db`. A continuación se presenta el DDL exacto extraído de `sqlite_master`:")
    md.append("")
    ddl_sql = obtener_esquema_db()
    md.append(calcular_fence(ddl_sql, "sql"))
    md.append("")
    md.append("---")
    md.append("")

    # Inventario de Archivos Binarios y Plantillas
    md.append("## 📦 Inventario de Activos Binarios y Plantillas Excel")
    md.append("")
    md.append("El proyecto incluye los siguientes archivos binarios estructurados de soporte:")
    md.append("")
    md.append("| Archivo | Tipo | Tamaño | Descripción / Contenido |")
    md.append("|---|---|---|---|")
    md.append("| `data/inspecciones.db` | Base de Datos SQLite | ~815 KB | Base de datos operacional activa con historial de inspecciones, usuarios y catálogos |")
    md.append("| `data/plantillas/Plantilla_Cargue_Masivo_Inspecciones.xlsx` | Excel (.xlsx) | 5.4 KB | Hoja `Plantilla_Inspecciones` con 22 columnas canónicas para importación masiva |")
    md.append("| `data/plantillas/plantilla_inspecciones_completa.xlsx` | Excel (.xlsx) | 5.5 KB | Hoja con 18 columnas estándar de inspección de flota |")
    md.append("| `data/plantillas/prueba_sabana.xlsx` | Excel (.xlsx) | 5.3 KB | Formato de prueba tipo sábana de patio con datos de medición |")
    md.append("| `static/img/logo_hd.svg` | Gráfico Vectorial SVG | ~86 KB | Logotipo oficial vectorial de TireAnalyze Pro en alta definición (264x150) |")
    md.append("| `static/img/pocillo_hd.svg` | Gráfico Vectorial SVG | ~119 KB | Ilustración técnica oficial vectorial del pocillo con vehículo en alta definición (200x276) |")
    md.append("")
    md.append("> **Nota sobre scripts temporales:** El archivo `scripts/temp_script.js` corresponde a un volcado de auditoría sintáctica generado por `scripts/check_js.py` para validar los bloques `<script>` de `templates/index.html`. El código fuente canónico se encuentra en `templates/index.html`.")
    md.append("")
    md.append("---")
    md.append("")

    # Tabla de Contenidos / Índice
    md.append("## 📑 Índice de Archivos de Código Fuente")
    md.append("")
    
    # Agrupar por categoría
    categorias = {}
    for info in archivos_info:
        cat = info["categoria"]
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(info)

    for cat_name, cat_files in categorias.items():
        md.append(f"### {cat_name}")
        md.append("")
        md.append("| Archivo | Lenguaje | Líneas | Tamaño | Propósito |")
        md.append("|---|---|---|---|---|")
        for f in cat_files:
            anchor = slugify(f"archivo-{f['rel_path']}")
            md.append(f"| [{f['rel_path']}](#{anchor}) | `{f['lang']}` | {f['lines']} | {f['bytes'] / 1024:.1f} KB | {f['desc']} |")
        md.append("")

    md.append("---")
    md.append("")

    # Volcado Completo de Código Fuente
    md.append("## 💻 Código Fuente Completo por Módulo")
    md.append("")

    for cat_name, cat_files in categorias.items():
        md.append(f"# {cat_name}")
        md.append("")
        for f in cat_files:
            anchor_title = f"Archivo: {f['rel_path']}"
            md.append(f"## {anchor_title}")
            md.append("")
            md.append(f"- **Ruta:** `{f['rel_path']}`")
            md.append(f"- **Descripción:** {f['desc']}")
            md.append(f"- **Métricas:** {f['lines']} líneas | {f['bytes']:,} bytes ({f['bytes'] / 1024:.1f} KB)")
            md.append(f"- **Lenguaje:** `{f['lang']}`")
            md.append("")
            md.append(calcular_fence(f['content'], f['lang']))
            md.append("")
            md.append("---")
            md.append("")

    final_content = "\n".join(md)
    print(f"Escribiendo archivo de salida en {OUTPUT_FILE_1}...")
    OUTPUT_FILE_1.write_text(final_content, encoding="utf-8")
    
    print(f"Copiando archivo a la raíz del workspace en {OUTPUT_FILE_2}...")
    shutil.copyfile(OUTPUT_FILE_1, OUTPUT_FILE_2)

    total_md_bytes = OUTPUT_FILE_1.stat().st_size
    total_md_lines = len(final_content.splitlines())
    print(f"¡ÉXITO TOTAL!")
    print(f"Archivo generado: {OUTPUT_FILE_1.name}")
    print(f"Tamaño final: {total_md_bytes / 1024:.1f} KB ({total_md_bytes:,} bytes)")
    print(f"Líneas totales del .md: {total_md_lines:,}")

if __name__ == "__main__":
    generar_documento()
