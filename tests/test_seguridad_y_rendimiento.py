import os
import sys
import pytest
from fastapi.testclient import TestClient

# Asegurar path de importación
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import server
import modulo_bodegas_taller


def test_aislamiento_multitenant_bodegas_mismo_numero_interno(test_db):
    """
    Verifica que llantas con el mismo número interno pertenecientes a clientes distintos
    tengan un ciclo de vida, inventario y hoja de vida completamente aislados (prevención IDOR).
    """
    # 1. Crear llanta LL-001 para CLIENTE_A
    res_a = database.crear_llanta_en_bodega({
        "cliente": "CLIENTE_A",
        "numero_interno": "LL-001",
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "GOODYEAR",
        "diseno": "KMAX",
        "dimension": "295/80R22.5",
        "prof_inicial": 18.0,
        "costo_compra": 1200000.0,
        "usuario_registro": "admin"
    })
    assert res_a.get("ok"), f"Fallo al crear llanta en CLIENTE_A: {res_a}"

    # 2. Crear llanta con el MISMO número interno LL-001 para CLIENTE_B
    res_b = database.crear_llanta_en_bodega({
        "cliente": "CLIENTE_B",
        "numero_interno": "LL-001",
        "ubicacion_bodega": "BODEGA_1_NUEVAS",
        "marca": "MICHELIN",
        "diseno": "XZE",
        "dimension": "295/80R22.5",
        "prof_inicial": 19.0,
        "costo_compra": 1500000.0,
        "usuario_registro": "admin"
    })
    assert res_b.get("ok"), f"Fallo al crear llanta en CLIENTE_B: {res_b}"

    # 3. Trasladar la llanta de CLIENTE_A a BODEGA_2_RECAMBIO
    mov_a = database.registrar_movimiento_bodega({
        "cliente": "CLIENTE_A",
        "numero_interno": "LL-001",
        "tipo_movimiento": "TRASLADO_INTERNO",
        "bodega_origen": "BODEGA_1_NUEVAS",
        "bodega_destino": "BODEGA_2_RECAMBIO",
        "usuario_registro": "inspector_a"
    })
    assert mov_a.get("ok"), f"Fallo movimiento en CLIENTE_A: {mov_a}"

    # 4. Despachar a planta de reencauche la llanta LL-001 de CLIENTE_A
    desp_a = database.despachar_lote_planta_reencauche({
        "cliente_propietario": "CLIENTE_A",
        "numeros_internos": ["LL-001"],
        "guia_remision_planta": "GUIA-101",
        "proveedor_planta": "Renovadora X",
        "usuario_responsable": "inspector_a"
    })
    assert desp_a.get("ok"), f"Fallo despacho en CLIENTE_A: {desp_a}"

    # 5. Consultar Hoja de Vida de LL-001 en CLIENTE_A -> Debe estar en Bodega_4_EnPlanta
    hv_a = database.obtener_hoja_vida_llanta("LL-001", "CLIENTE_A")
    assert hv_a.get("ok")
    assert hv_a["ficha_tecnica"]["marca"] == "GOODYEAR"
    assert hv_a["ficha_tecnica"]["cliente"] == "CLIENTE_A"
    assert hv_a["estado_actual"]["estado"] == "Bodega_4_EnPlanta"

    # 6. Consultar Hoja de Vida de LL-001 en CLIENTE_B -> DEBE SEGUIR INTACTA en En Stock - Nueva / BODEGA_1_NUEVAS
    hv_b = database.obtener_hoja_vida_llanta("LL-001", "CLIENTE_B")
    assert hv_b.get("ok")
    assert hv_b["ficha_tecnica"]["marca"] == "MICHELIN"
    assert hv_b["ficha_tecnica"]["cliente"] == "CLIENTE_B"
    assert hv_b["estado_actual"]["estado"] == "En Stock - Nueva"
    assert hv_b["estado_actual"]["ubicacion_bodega"] in ("BODEGA_1_NUEVAS", "Bodega_1_Nuevas")


def test_bloqueo_descarga_pdf_placa_otro_cliente(test_db):
    """
    Verifica que un usuario asignado a CLIENTE_A no pueda descargar el PDF de informe
    técnico de un vehículo perteneciente a CLIENTE_B (HTTP 403 Forbidden).
    """
    # 1. Crear usuario inspector asignado exclusivamente a CLIENTE_A
    ok_user = database.crear_usuario(
        username="inspector_a",
        password="Password123*",
        nombre_completo="Inspector Flota A",
        rol="inspector",
        cliente_asignado="CLIENTE_A"
    )
    assert ok_user
    token_inspector_a = server.crear_token_acceso("inspector_a", "inspector")

    # 2. Registrar inspección del vehículo XYZ999 para CLIENTE_B
    database.insertar_inspeccion({
        "fecha": "2026-10-20",
        "cliente": "CLIENTE_B",
        "placa": "XYZ999",
        "posicion": 1,
        "kilometraje": 45000.0,
        "marca": "BRIDGESTONE",
        "diseno": "R268",
        "dimension": "295/80R22.5",
        "prof_ext": 9.0,
        "prof_cent": 9.0,
        "prof_int": 9.0,
        "psi": 105.0,
        "usuario_registro": "admin"
    })

    client = TestClient(server.app)

    # 3. Intentar descargar el PDF con el token del inspector de CLIENTE_A -> HTTP 403
    res_bloqueo = client.get(
        "/api/informe-pdf/XYZ999",
        headers={"Authorization": f"Bearer {token_inspector_a}"}
    )
    assert res_bloqueo.status_code == 403
    assert "No tiene permisos para descargar el informe de este vehículo" in res_bloqueo.json()["detail"]

    # 4. El usuario admin sí debe poder acceder
    token_admin = server.crear_token_acceso("admin", "admin")
    res_admin = client.get(
        "/api/informe-pdf/XYZ999",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.headers["content-type"] == "application/pdf"


def test_rendimiento_exclusiones_base64_y_sincronizacion_incremental(test_db):
    """
    Verifica que obtener_todas_inspecciones(incluir_fotos=False) no retorne las cadenas
    Base64 pesadas en memoria, que la bandera tiene_foto funcione y que la sincronización
    incremental funcione de manera específica y eficiente.
    """
    # 1. Insertar inspección con foto Base64 pesada (>10KB)
    foto_pesada = "data:image/jpeg;base64," + ("A" * 12000)
    insp_id = database.insertar_inspeccion({
        "fecha": "2026-10-22",
        "cliente": "FLOTA_DEMO",
        "subcliente": "BOGOTA",
        "tipo_operacion": "URBANO",
        "placa": "DEM123",
        "posicion": 1,
        "kilometraje": 30000.0,
        "marca": "PIRELLI",
        "diseno": "FG01",
        "dimension": "295/80R22.5",
        "prof_ext": 11.0,
        "prof_cent": 11.0,
        "prof_int": 11.0,
        "psi": 110.0,
        "numero_interno": "INT-555",
        "foto_novedad": foto_pesada,
        "novedades": "Desgaste parejo",
        "usuario_registro": "admin"
    })
    assert insp_id > 0

    # 2. Consultar sin fotos: el campo foto_novedad debe estar vacío y tiene_foto debe ser '1'
    df_sin_fotos = database.obtener_todas_inspecciones(incluir_fotos=False)
    assert not df_sin_fotos.empty
    reg_sin = df_sin_fotos[df_sin_fotos["id"] == insp_id].iloc[0]
    assert reg_sin["foto_novedad"] == ""
    assert str(reg_sin["tiene_foto"]).strip() == "1"

    # 3. Consultar con fotos: el campo foto_novedad debe contener la imagen Base64 completa
    df_con_fotos = database.obtener_todas_inspecciones(incluir_fotos=True)
    reg_con = df_con_fotos[df_con_fotos["id"] == insp_id].iloc[0]
    assert reg_con["foto_novedad"] == foto_pesada

    # 4. Probar sincronización incremental O(1) para ese cliente y número interno
    sincronizadas = database.sincronizar_maestro_desde_inspecciones(
        cliente_filtro="FLOTA_DEMO",
        numero_interno_filtro="INT-555"
    )
    assert sincronizadas >= 1

    # Verificar que se creó/actualizó en llantas_maestro
    with database.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT cliente, numero_interno, marca, placa_actual, posicion_actual 
            FROM llantas_maestro 
            WHERE UPPER(TRIM(cliente)) = 'FLOTA_DEMO' AND UPPER(TRIM(numero_interno)) = 'INT-555'
        """)
        row_m = c.fetchone()
        assert row_m is not None
        assert row_m[0] == "FLOTA_DEMO"
        assert row_m[1] == "INT-555"
        assert row_m[2] == "PIRELLI"
        assert row_m[3] == "DEM123"
        assert row_m[4] == 1

    # 5. Verificar que analizar_inspecciones_df procesa correctamente con Bodega 2 precargada
    analisis = database.analizar_inspecciones_df(df_sin_fotos)
    assert not analisis.empty
    assert "Plan_Dual_Mal_Apareado" in analisis.columns
    assert "Recomendaciones_Dual" in analisis.columns


def test_rate_limiting_login_fuerza_bruta(test_db):
    """
    Verifica que tras 8 intentos fallidos consecutivos de login en menos de 60 segundos,
    el endpoint /api/login bloquee las siguientes peticiones con HTTP 429 Too Many Requests.
    """
    server._login_attempts.clear()
    client = TestClient(server.app)

    # 8 intentos con credenciales incorrectas deben responder con 401
    for intento in range(1, 9):
        resp = client.post("/api/login", json={"username": "admin", "password": f"wrong_{intento}"})
        assert resp.status_code == 401, f"El intento {intento} debió retornar 401"
        assert resp.json()["detail"] == "Usuario o contraseña incorrectos"

    # El 9no intento debe ser bloqueado con HTTP 429
    resp_bloqueada = client.post("/api/login", json={"username": "admin", "password": "wrong_password"})
    assert resp_bloqueada.status_code == 429
    assert "Demasiados intentos fallidos. Intente de nuevo en 60 segundos." in resp_bloqueada.json()["detail"]

    # Incluso un intento con la contraseña correcta debe permanecer bloqueado
    resp_correcta_bloqueada = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert resp_correcta_bloqueada.status_code == 429

    # Limpiar el registro de rate limit y verificar que el login exitoso funcione y restablezca
    server._login_attempts.clear()
    resp_ok = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert resp_ok.status_code == 200
    assert "token" in resp_ok.json()
