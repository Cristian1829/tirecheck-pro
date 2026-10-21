import pytest
import sqlite3
import database

def test_migrar_restar_pext_ciudad_limpia(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_pext.db")
    monkeypatch.setattr(database, "DB_PATH", test_db)
    
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE inspecciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            placa TEXT,
            prof_ext REAL,
            prof_cent REAL,
            prof_int REAL
        )
    """)
    cur.execute("""
        CREATE TABLE llantas_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            numero_interno TEXT,
            prof_ext REAL,
            prof_cent REAL,
            prof_int REAL,
            prof_actual_min REAL
        )
    """)
    # Insert test data
    cur.execute("INSERT INTO inspecciones (cliente, placa, prof_ext, prof_cent, prof_int) VALUES ('CIUDAD LIMPIA BOGOTA', 'CL-01', 18.0, 16.0, 15.0)")
    cur.execute("INSERT INTO inspecciones (cliente, placa, prof_ext, prof_cent, prof_int) VALUES ('CIUDAD LIMPIA', 'CL-02', 12.0, 10.0, 9.0)")
    cur.execute("INSERT INTO inspecciones (cliente, placa, prof_ext, prof_cent, prof_int) VALUES ('OTRO CLIENTE', 'OT-01', 18.0, 16.0, 15.0)")
    
    cur.execute("INSERT INTO llantas_maestro (cliente, numero_interno, prof_ext, prof_cent, prof_int, prof_actual_min) VALUES ('CIUDAD LIMPIA BOGOTA', 'LL-01', 18.0, 16.0, 15.0, 15.0)")
    conn.commit()
    conn.close()

    # Ejecutar primera vez
    res1 = database.migrar_restar_pext_ciudad_limpia()
    assert res1["status"] == "ok"
    assert res1["inspecciones_actualizadas"] == 2
    assert res1["maestro_actualizadas"] == 1

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT prof_ext FROM inspecciones WHERE placa = 'CL-01'")
    assert cur.fetchone()[0] == 17.0, "18.0 debe haber bajado a 17.0"

    cur.execute("SELECT prof_ext FROM inspecciones WHERE placa = 'CL-02'")
    assert cur.fetchone()[0] == 11.0, "12.0 debe haber bajado a 11.0"

    cur.execute("SELECT prof_ext FROM inspecciones WHERE placa = 'OT-01'")
    assert cur.fetchone()[0] == 18.0, "Otro cliente no debe ser modificado"

    cur.execute("SELECT prof_ext FROM llantas_maestro WHERE numero_interno = 'LL-01'")
    assert cur.fetchone()[0] == 17.0

    conn.close()

    # Segunda ejecución: debe ser idempotente y no restar de nuevo
    res2 = database.migrar_restar_pext_ciudad_limpia()
    assert res2["status"] == "already_applied"

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT prof_ext FROM inspecciones WHERE placa = 'CL-01'")
    assert cur.fetchone()[0] == 17.0, "No debe restar dos veces en reinicios"
    conn.close()


def test_migrar_normalizar_cliente_ciudad_limpia_bogota(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_norm_cl.db")
    monkeypatch.setattr(database, "DB_PATH", test_db)
    
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE inspecciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            subcliente TEXT,
            placa TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE llantas_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            subcliente TEXT,
            numero_interno TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE padron_vehiculos_cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            subcliente TEXT,
            placa TEXT,
            UNIQUE(cliente, placa)
        )
    """)
    cur.execute("""
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            cliente_asignado TEXT
        )
    """)
    cur.execute("INSERT INTO inspecciones (cliente, subcliente, placa) VALUES ('CIUDAD LIMPIA BOGOTA', 'Compactador', '3032')")
    cur.execute("INSERT INTO inspecciones (cliente, subcliente, placa) VALUES ('CIUDAD LIMPIA', 'Norte', '3035')")
    cur.execute("INSERT INTO inspecciones (cliente, subcliente, placa) VALUES ('OTRO CLIENTE', 'Sede 1', '9999')")
    
    cur.execute("INSERT INTO llantas_maestro (cliente, subcliente, numero_interno) VALUES ('CIUDAD LIMPIA BOGOTA', 'Compactador', 'CL-01')")
    cur.execute("INSERT INTO padron_vehiculos_cliente (cliente, subcliente, placa) VALUES ('CIUDAD LIMPIA BOGOTA', 'Compactador', '3032')")
    cur.execute("INSERT INTO usuarios (username, cliente_asignado) VALUES ('inspector1', 'CIUDAD LIMPIA BOGOTA')")
    conn.commit()
    conn.close()

    res = database.migrar_normalizar_cliente_ciudad_limpia_bogota()
    assert res["status"] == "ok"
    assert res["inspecciones_actualizadas"] == 2
    assert res["maestro_actualizadas"] == 1
    assert res["padron_actualizadas"] == 1

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT cliente, subcliente FROM inspecciones WHERE placa = '3032'")
    row = cur.fetchone()
    assert row[0] == "CIUDAD LIMPIA"
    assert row[1] == "BOGOTA"

    cur.execute("SELECT cliente, subcliente FROM inspecciones WHERE placa = '3035'")
    row2 = cur.fetchone()
    assert row2[0] == "CIUDAD LIMPIA"
    assert row2[1] == "BOGOTA"

    cur.execute("SELECT cliente, subcliente FROM inspecciones WHERE placa = '9999'")
    row_otro = cur.fetchone()
    assert row_otro[0] == "OTRO CLIENTE"
    assert row_otro[1] == "Sede 1"

    cur.execute("SELECT cliente, subcliente FROM llantas_maestro WHERE numero_interno = 'CL-01'")
    row_ll = cur.fetchone()
    assert row_ll[0] == "CIUDAD LIMPIA"
    assert row_ll[1] == "BOGOTA"

    cur.execute("SELECT cliente_asignado FROM usuarios WHERE username = 'inspector1'")
    assert cur.fetchone()[0] == "CIUDAD LIMPIA"
    conn.close()

    # Idempotencia
    res2 = database.migrar_normalizar_cliente_ciudad_limpia_bogota()
    assert res2["status"] == "already_applied"

