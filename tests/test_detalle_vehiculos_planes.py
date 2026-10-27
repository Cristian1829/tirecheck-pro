import pytest
import database
import server

def test_deduplicacion_ultima_medicion_por_placa_posicion(test_db, auth_client):
    """
    1. Inserta para la placa WMK941 una lectura antigua en Pos 1 con 2.0 mm (2026-08-01)
    y una lectura más reciente en Pos 1 con 14.0 mm (2026-10-15).
    Verifica que Llantas Inspeccionadas == 1, Cant_Cambios == 0 y Plan_Cambio_Llanta == 'NO'.
    """
    with database.get_connection() as conn:
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi, fecha_registro)
            VALUES ('2026-08-01', 'CLIENTE PRUEBA', 'WMK941', 1, 'Cabezote (6x4)', 2.0, 2.0, 2.0, 100, '2026-08-01 10:00:00')
        """)
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi, fecha_registro)
            VALUES ('2026-10-15', 'CLIENTE PRUEBA', 'WMK941', 1, 'Cabezote (6x4)', 14.0, 14.0, 14.0, 100, '2026-10-15 10:00:00')
        """)

    res = auth_client.get("/api/diagnostico")
    assert res.status_code == 200
    data = res.json()
    veh = next((v for v in data if v["Vehículo/Placa"] == "WMK941"), None)
    assert veh is not None, "Vehículo WMK941 no encontrado en el diagnóstico"
    assert veh["Llantas Inspeccionadas"] == 1
    assert veh["Cant_Cambios"] == 0
    assert veh["Plan_Cambio_Llanta"] == "NO"

def test_regla_especial_par_direccional_y_proximas_cambio(test_db, auth_client):
    """
    2. Inserta en TAL620 Pos 1 con 2.5 mm (<= 3.0 mm límite) y Pos 2 con 11.0 mm y prof_inicial = 16.0 mm
    (16.0 - 11.0 = 5.0 mm >= 3.0 mm), más Pos 3 con 4.5 mm (en ventana Próxima a Cambio <= 5.0 mm).
    Verifica que el diagnóstico active la regla de Par Direccional en Detalle_Cambio y contabilice Cant_Proximas >= 1.
    """
    with database.get_connection() as conn:
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, prof_inicial, psi)
            VALUES ('2026-10-20', 'CLIENTE PRUEBA', 'TAL620', 1, 'Cabezote (6x4)', 2.5, 2.5, 2.5, 16.0, 100)
        """)
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, prof_inicial, psi)
            VALUES ('2026-10-20', 'CLIENTE PRUEBA', 'TAL620', 2, 'Cabezote (6x4)', 11.0, 11.0, 11.0, 16.0, 100)
        """)
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, prof_inicial, psi)
            VALUES ('2026-10-20', 'CLIENTE PRUEBA', 'TAL620', 3, 'Cabezote (6x4)', 4.5, 4.5, 4.5, 16.0, 100)
        """)

    res = auth_client.get("/api/diagnostico")
    assert res.status_code == 200
    data = res.json()
    veh = next((v for v in data if v["Vehículo/Placa"] == "TAL620"), None)
    assert veh is not None
    assert "Ajuste Par Direccional" in veh["Detalle_Cambio"]
    assert "Pos 2" in veh["Detalle_Cambio"]
    assert veh["Cant_Proximas"] >= 1
    assert veh["Plan_Cambio_Llanta"] == "SÍ"

def test_motor_auto_ajuste_interno_direccion_pachas_y_trailer(test_db, auth_client):
    """
    3. Inserta un vehículo donde Pos 2 (14.0 mm) > Pos 1 (12.0 mm) por 2.0 mm (>= 0.5 mm)
    y una pacha donde la llanta interior es más alta que la exterior (Pos 4 Int con 11.0 mm > Pos 3 Ext con 8.0 mm).
    Verifica que Badge_Rotacion == 'AUTO-AJUSTE' y que Detalle_Auto_Ajuste prescriba cruzar P1 ↔ P2 e invertir la pacha.
    """
    with database.get_connection() as conn:
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi)
            VALUES 
            ('2026-10-20', 'CLIENTE PRUEBA', 'AAJ100', 1, 'Cabezote (6x4)', 12.0, 12.0, 12.0, 100),
            ('2026-10-20', 'CLIENTE PRUEBA', 'AAJ100', 2, 'Cabezote (6x4)', 14.0, 14.0, 14.0, 100),
            ('2026-10-20', 'CLIENTE PRUEBA', 'AAJ100', 3, 'Cabezote (6x4)', 8.0, 8.0, 8.0, 100),
            ('2026-10-20', 'CLIENTE PRUEBA', 'AAJ100', 4, 'Cabezote (6x4)', 11.0, 11.0, 11.0, 100)
        """)

    res = auth_client.get("/api/diagnostico")
    assert res.status_code == 200
    data = res.json()
    veh = next((v for v in data if v["Vehículo/Placa"] == "AAJ100"), None)
    assert veh is not None
    assert veh["Badge_Rotacion"] == "AUTO-AJUSTE"
    assert "Cruzar P1 ↔ P2" in veh["Detalle_Auto_Ajuste"]
    assert "Invertir Pos 4 ↔ Pos 3" in veh["Detalle_Auto_Ajuste"]

def test_matriz_semaforo_posiciones_colores_exactos(test_db, auth_client):
    """
    4. Verifica que GET /api/diagnostico incluya Llantas_Posiciones con estados
    'ROJO' (<= 3.0), 'AMARILLO' (3.1-5.0) y 'VERDE' (> 5.0),
    y que ignore surcos en 0.0 mm cuando los otros surcos tienen lectura positiva.
    """
    with database.get_connection() as conn:
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi, numero_interno)
            VALUES 
            ('2026-10-20', 'CLIENTE PRUEBA', 'SEM001', 1, 'Camion 4x2', 2.2, 2.4, 2.5, 100, 'LL-01'),
            ('2026-10-20', 'CLIENTE PRUEBA', 'SEM001', 2, 'Camion 4x2', 4.0, 4.2, 4.1, 100, 'LL-02'),
            ('2026-10-20', 'CLIENTE PRUEBA', 'SEM001', 3, 'Camion 4x2', 0.0, 8.5, 8.5, 100, 'LL-03')
        """)

    res = auth_client.get("/api/diagnostico")
    assert res.status_code == 200
    data = res.json()
    veh = next((v for v in data if v["Vehículo/Placa"] == "SEM001"), None)
    assert veh is not None
    assert "Llantas_Posiciones" in veh

    pos_dict = {p["posicion"]: p for p in veh["Llantas_Posiciones"]}
    # Pos 1: min(2.2, 2.4, 2.5) = 2.2 <= 3.0 -> ROJO
    assert pos_dict[1]["semaforo"] == "ROJO"
    # Pos 2: min(4.0, 4.2, 4.1) = 4.0 (3.0 < 4.0 <= 5.0) -> AMARILLO
    assert pos_dict[2]["semaforo"] == "AMARILLO"
    # Pos 3: 0.0 ignorado porque 8.5 > 0 -> min(8.5, 8.5) = 8.5 > 5.0 -> VERDE
    assert pos_dict[3]["semaforo"] == "VERDE"
    assert pos_dict[3]["prof_min"] == 8.5

def test_filtro_rango_fechas_en_api_diagnostico(test_db, auth_client):
    """
    5. Verifica que GET /api/diagnostico?fecha_desde=2026-10-01&fecha_hasta=2026-10-31
    filtre correctamente las inspecciones dentro del periodo.
    """
    with database.get_connection() as conn:
        conn.execute("""
            INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi)
            VALUES 
            ('2026-09-15', 'CLIENTE PRUEBA', 'SEP001', 1, 'Camion 4x2', 10.0, 10.0, 10.0, 100),
            ('2026-10-15', 'CLIENTE PRUEBA', 'OCT001', 1, 'Camion 4x2', 10.0, 10.0, 10.0, 100),
            ('2026-11-05', 'CLIENTE PRUEBA', 'NOV001', 1, 'Camion 4x2', 10.0, 10.0, 10.0, 100)
        """)

    # Consulta solo octubre
    res = auth_client.get("/api/diagnostico?fecha_desde=2026-10-01&fecha_hasta=2026-10-31")
    assert res.status_code == 200
    placas_oct = [v["Vehículo/Placa"] for v in res.json()]
    assert "OCT001" in placas_oct
    assert "SEP001" not in placas_oct
    assert "NOV001" not in placas_oct


def test_posiciones_pendientes_en_diagnostico(test_db, auth_client):
    """
    6. Verifica que si un vehículo tiene posiciones pendientes según su tipología:
       - Se reporte Cant_Pendientes > 0 y la lista de Posiciones_Pendientes.
       - Se genere Detalle_Pendientes con el mensaje explícito.
       - En Bloques_Recomendaciones se incluya el bloque de tipo PENDIENTES.
       - Y para un vehículo con todas las posiciones inspeccionadas, Cant_Pendientes sea 0.
    """
    with database.get_connection() as conn:
        # Vehículo 1: COMPACTADOR 4 MANOS (12 llantas esperadas) pero solo 8 inspeccionadas
        for pos in range(1, 9):
            conn.execute("""
                INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi)
                VALUES ('2026-10-25', 'CIUDAD LIMPIA', 'CMP008', ?, 'COMPACTADOR 4 MANOS', 19.0, 19.0, 19.0, 100)
            """, (pos,))

        # Vehículo 2: COMPACTADOR 4 MANOS con las 12 posiciones inspeccionadas
        for pos in range(1, 13):
            conn.execute("""
                INSERT INTO inspecciones (fecha, cliente, placa, posicion, tipologia, prof_ext, prof_cent, prof_int, psi)
                VALUES ('2026-10-25', 'CIUDAD LIMPIA', 'CMP012', ?, 'COMPACTADOR 4 MANOS', 18.0, 18.0, 18.0, 100)
            """, (pos,))

    res = auth_client.get("/api/diagnostico")
    assert res.status_code == 200
    data = res.json()

    # Vehículo con 8 de 12 inspeccionadas
    veh8 = next((v for v in data if v["Vehículo/Placa"] == "CMP008"), None)
    assert veh8 is not None
    assert veh8["Llantas Inspeccionadas"] == 8
    assert veh8["Cant_Pendientes"] == 4
    assert veh8["Posiciones_Pendientes"] == [9, 10, 11, 12]
    assert "4 posiciones pendientes por inspeccionar" in veh8["Detalle_Pendientes"]
    assert "Pos 9, 10, 11, 12" in veh8["Detalle_Pendientes"]

    bloques8 = veh8.get("Bloques_Recomendaciones", [])
    bloque_pend8 = next((b for b in bloques8 if b.get("tipo") in ("PENDIENTE", "PENDIENTES")), None)
    assert bloque_pend8 is not None
    assert "4 posiciones pendientes por inspeccionar" in bloque_pend8["texto"]

    # Vehículo con 12 de 12 inspeccionadas
    veh12 = next((v for v in data if v["Vehículo/Placa"] == "CMP012"), None)
    assert veh12 is not None
    assert veh12["Llantas Inspeccionadas"] == 12
    assert veh12["Cant_Pendientes"] == 0
    assert veh12["Detalle_Pendientes"] == "OK"
    bloques12 = veh12.get("Bloques_Recomendaciones", [])
    bloque_pend12 = next((b for b in bloques12 if b.get("tipo") in ("PENDIENTE", "PENDIENTES")), None)
    assert bloque_pend12 is None

