import sqlite3, os, sys, tempfile

PROYECTO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROYECTO_DIR not in sys.path:
    sys.path.insert(0, PROYECTO_DIR)

import database, pdf_generator
import pypdfium2

# Conectar a la base real para obtener la inspección de EE3123 y las tipologías
with database.get_connection() as conn_real:
    cur = conn_real.cursor()
    cur.execute("SELECT * FROM inspecciones WHERE placa = 'EE3123'")
    filas_insp = cur.fetchall()
    col_names = [d[0] for d in cur.description]
    
    cur.execute("SELECT * FROM catalogo_tipologias")
    tipos = cur.fetchall()
    cur.execute("SELECT * FROM usuarios")
    users = cur.fetchall()

# Crear DB temporal
fd, temp_db = tempfile.mkstemp(suffix='.db')
os.close(fd)
orig_db = database.DB_PATH
database.DB_PATH = temp_db
database.inicializar_bd()

with database.get_connection() as conn_temp:
    c = conn_temp.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_tipologias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            descripcion TEXT,
            cant_llantas INTEGER,
            esquema_json TEXT
        )
    """)
    for t in tipos:
        c.execute("INSERT OR REPLACE INTO catalogo_tipologias (nombre, descripcion, cant_llantas, esquema_json) VALUES (?, ?, ?, ?)", (t[1], t[2], t[3], t[4]))
    
    for u in users:
        c.execute("INSERT OR REPLACE INTO usuarios (username, password, nombre_completo, rol, cliente_asignado) VALUES (?, ?, ?, ?, ?)", (u[1], u[2], u[3], u[4], u[5]))

    # Insertar filas de EE3123
    placeholders = ', '.join(['?'] * len(col_names))
    cols_str = ', '.join(col_names)
    c.executemany(f"INSERT INTO inspecciones ({cols_str}) VALUES ({placeholders})", filas_insp)
    conn_temp.commit()

# Generar PDF
pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento('EE3123')
out_pdf = r"C:\Users\crist\.gemini\antigravity-ide\brain\c6d723f3-0d84-4040-a969-80008634f91f\test_EE3123_validado.pdf"
with open(out_pdf, 'wb') as f:
    f.write(pdf_bytes)

# Renderizar páginas a imágenes
doc = pypdfium2.PdfDocument(pdf_bytes)
print("EE3123 Páginas:", len(doc))
for i, page in enumerate(doc):
    pix = page.render(scale=2.0)
    img_path = rf"C:\Users\crist\.gemini\antigravity-ide\brain\c6d723f3-0d84-4040-a969-80008634f91f\test_EE3123_pag{i+1}.png"
    pix.to_pil().save(img_path)
    print(f"Página {i+1} guardada en {img_path}")

database.DB_PATH = orig_db
import gc
gc.collect()
try:
    if os.path.exists(temp_db):
        os.remove(temp_db)
except Exception:
    pass
print("Completado con éxito.")
