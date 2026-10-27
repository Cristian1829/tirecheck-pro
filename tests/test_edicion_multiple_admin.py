"""Pruebas para verificar que solo el Administrador puede hacer ediciones de múltiples registros en la pestaña Base de Inspecciones."""
import io
import pandas as pd
from fastapi.testclient import TestClient

import database
import server


def _cliente_con_token(username, rol):
    c = TestClient(server.app)
    c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(username, rol)}"})
    return c


def _crear_usuario(username, rol, cliente="FLOTA PRUEBAS", vistas="patio,basedatos"):
    with database.get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE username = ?", (username,))
        conn.execute(
            "INSERT INTO usuarios (username, password, nombre_completo, rol, cliente_asignado, vistas_permitidas) VALUES (?, ?, ?, ?, ?, ?)",
            (username, database.hash_password("12345"), username, rol, cliente, vistas)
        )
        conn.commit()


def test_solo_admin_puede_editar_multiples_registros(test_db):
    # 1. Crear 3 inspecciones de prueba
    id1 = database.insertar_inspeccion({
        "fecha": "2026-10-01", "cliente": "FLOTA PRUEBAS", "subcliente": "SEDE NORTE", "tipo_operacion": "URBANO",
        "placa": "AAA101", "posicion": 1, "kilometraje": 10000, "tipologia": "Cabezote (6x4)",
        "marca": "MICHELIN", "diseno": "X MULTI D", "dimension": "295/80R22.5", "vida": "Original",
        "prof_ext": 12, "prof_cent": 12, "prof_int": 12, "psi": 110, "prof_inicial": 18, "numero_interno": "N-101"
    })
    id2 = database.insertar_inspeccion({
        "fecha": "2026-10-01", "cliente": "FLOTA PRUEBAS", "subcliente": "SEDE NORTE", "tipo_operacion": "URBANO",
        "placa": "AAA102", "posicion": 1, "kilometraje": 20000, "tipologia": "Cabezote (6x4)",
        "marca": "MICHELIN", "diseno": "X MULTI D", "dimension": "295/80R22.5", "vida": "Original",
        "prof_ext": 11, "prof_cent": 11, "prof_int": 11, "psi": 110, "prof_inicial": 18, "numero_interno": "N-102"
    })
    id3 = database.insertar_inspeccion({
        "fecha": "2026-10-01", "cliente": "FLOTA PRUEBAS", "subcliente": "SEDE NORTE", "tipo_operacion": "URBANO",
        "placa": "AAA103", "posicion": 1, "kilometraje": 30000, "tipologia": "Cabezote (6x4)",
        "marca": "MICHELIN", "diseno": "X MULTI D", "dimension": "295/80R22.5", "vida": "Original",
        "prof_ext": 10, "prof_cent": 10, "prof_int": 10, "psi": 110, "prof_inicial": 18, "numero_interno": "N-103"
    })

    # 2. Crear usuarios con roles Jefatura, Inspector y Gerencia
    _crear_usuario("jefe_test", "jefatura", "FLOTA PRUEBAS", "patio,basedatos")
    _crear_usuario("insp_test", "inspector", "FLOTA PRUEBAS", "patio,basedatos")
    _crear_usuario("gere_test", "gerencia", "FLOTA PRUEBAS", "basedatos")

    payload_edicion = {
        "ids": [id1, id2],
        "cambios": {
            "subcliente": "SEDE SUR",
            "tipo_operacion": "INTERMUNICIPAL",
            "novedades": "MODIFICACIÓN EN LOTE TEST"
        }
    }

    # 3. Intentos de edición múltiple por roles no-admin DEBEN FALLAR con 403
    c_jefe = _cliente_con_token("jefe_test", "jefatura")
    r_jefe = c_jefe.put("/api/inspecciones/edicion-multiple", json=payload_edicion)
    assert r_jefe.status_code == 403
    assert "Solo el administrador" in r_jefe.json()["detail"]

    c_insp = _cliente_con_token("insp_test", "inspector")
    r_insp = c_insp.put("/api/inspecciones/edicion-multiple", json=payload_edicion)
    assert r_insp.status_code == 403

    c_gere = _cliente_con_token("gere_test", "gerencia")
    r_gere = c_gere.put("/api/inspecciones/edicion-multiple", json=payload_edicion)
    assert r_gere.status_code == 403

    # Verificar que los registros siguen intactos
    with database.get_connection() as conn:
        r1 = conn.execute("SELECT subcliente, tipo_operacion, novedades FROM inspecciones WHERE id = ?", (id1,)).fetchone()
        assert r1[0] == "SEDE NORTE"
        assert r1[1] == "URBANO"

    # 4. Edición múltiple por ADMINISTRADOR DEBE TENER ÉXITO (HTTP 200)
    c_admin = _cliente_con_token("admin", "admin")
    r_admin = c_admin.put("/api/inspecciones/edicion-multiple", json=payload_edicion)
    assert r_admin.status_code == 200
    res_data = r_admin.json()
    assert res_data["status"] == "ok"
    assert res_data["registros_actualizados"] == 2

    # Verificar que los registros 1 y 2 fueron actualizados y el 3 no fue tocado
    with database.get_connection() as conn:
        r1 = conn.execute("SELECT subcliente, tipo_operacion, novedades FROM inspecciones WHERE id = ?", (id1,)).fetchone()
        assert r1[0] == "SEDE SUR"
        assert r1[1] == "INTERMUNICIPAL"
        assert r1[2] == "MODIFICACIÓN EN LOTE TEST"

        r2 = conn.execute("SELECT subcliente, tipo_operacion, novedades FROM inspecciones WHERE id = ?", (id2,)).fetchone()
        assert r2[0] == "SEDE SUR"
        assert r2[1] == "INTERMUNICIPAL"

        r3 = conn.execute("SELECT subcliente, tipo_operacion, novedades FROM inspecciones WHERE id = ?", (id3,)).fetchone()
        assert r3[0] == "SEDE NORTE"
        assert r3[1] == "URBANO"


def test_solo_admin_puede_importar_excel(test_db):
    _crear_usuario("jefe_test", "jefatura", "FLOTA PRUEBAS", "patio,basedatos")

    df = pd.DataFrame([{
        'fecha': '2026-10-01',
        'cliente': 'FLOTA PRUEBAS',
        'subcliente': 'SEDE TEST',
        'tipo_operacion': 'CARGA',
        'placa': 'XLS-999',
        'numero_interno': 'LL-XLS',
        'posicion': 1,
        'kilometraje': 10000,
        'tipologia': 'Cabezote (6x4)',
        'marca': 'Michelin',
        'diseno': 'X Multi Z',
        'dimension': '295/80R22.5',
        'vida': 'Original',
        'prof_ext': 12.0,
        'prof_cent': 12.0,
        'prof_int': 12.0,
        'psi': 105,
        'prof_inicial': 16.0
    }])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    files = {'file': ('cargue_prueba.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}

    # 1. Jefatura intenta importar excel -> DEBE RETORNAR 403
    c_jefe = _cliente_con_token("jefe_test", "jefatura")
    res_jefe = c_jefe.post("/api/inspecciones/importar-excel", files=files)
    assert res_jefe.status_code == 403
    assert "Solo el administrador" in res_jefe.json()["detail"]

    # 2. Administrador importa excel -> DEBE TENER ÉXITO (HTTP 200)
    buf.seek(0)
    files_admin = {'file': ('cargue_prueba.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    c_admin = _cliente_con_token("admin", "admin")
    res_admin = c_admin.post("/api/inspecciones/importar-excel", files=files_admin)
    assert res_admin.status_code == 200
    assert res_admin.json()["status"] == "ok"
