import sqlite3
import os

for path in ['data/inspecciones.db', 'seed_inspecciones.db', 'tirecheck.db']:
    if not os.path.exists(path):
        continue
    print(f"=== {path} ===")
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT cliente FROM inspecciones")
        rows = cur.fetchall()
        print("Clientes:", [r[0] for r in rows])
        
        cur.execute("SELECT id, fecha, cliente, subcliente, vehiculo, posicion, prof_ext, prof_cent, prof_int, prof_minima, semaforo FROM inspecciones WHERE UPPER(cliente) LIKE '%CIUDAD%LIMPIA%' LIMIT 10")
        sample = cur.fetchall()
        print(f"Total matching CIUDAD LIMPIA: {len(sample)}")
        for s in sample:
            print(s)
            
        cur.execute("SELECT count(*) FROM inspecciones WHERE UPPER(cliente) LIKE '%CIUDAD%LIMPIA%'")
        count = cur.fetchone()[0]
        print(f"Count total: {count}")
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()
