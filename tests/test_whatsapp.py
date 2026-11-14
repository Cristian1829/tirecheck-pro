"""Chatbot de WhatsApp: vinculación del celular, firma del webhook, permisos por sede de las consultas y PDF."""
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import database
import server
from whatsapp import agente, almacen, herramientas, proveedor_meta, rutas

CLI = "FLOTA WA"
SECRETO = "secreto-de-prueba"
TEL = "573001112233"


@pytest.fixture
def entorno(test_db, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", SECRETO)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verificar-123")
    monkeypatch.setenv("WHATSAPP_TOKEN", "token")
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "123")
    monkeypatch.setenv("URL_PUBLICA", "https://tirecheck.ejemplo.com")
    monkeypatch.setenv("GEMINI_API_KEY", "clave")
    rutas._mensajes_recientes.clear()
    enviados = {"textos": [], "documentos": []}
    monkeypatch.setattr(proveedor_meta, "enviar_texto", lambda tel, txt: enviados["textos"].append((tel, txt)))
    monkeypatch.setattr(proveedor_meta, "enviar_documento",
                        lambda tel, pdf, nombre, leyenda="": enviados["documentos"].append((tel, pdf, nombre)))
    _sembrar()
    return enviados


def _insp(placa, sede, prof, pos=1):
    database.insertar_inspeccion({
        "fecha": "2026-11-05", "cliente": CLI, "subcliente": sede, "placa": placa, "posicion": pos,
        "numero_interno": f"{placa}-{pos}", "marca": "MICHELIN", "diseno": "XZE", "dimension": "295/80R22.5",
        "vida": "Original", "kilometraje": 60000, "km_montaje": 10000, "prof_ext": prof, "prof_cent": prof, "prof_int": prof,
        "prof_inicial": 16, "precio": 1200000, "psi": 100, "tipologia": "Cabezote (6x4)"})


def _sembrar():
    database.crear_o_actualizar_cliente({"cliente": CLI, "tipo_licencia": "PRO", "limite_retiro_mm": 3.0,
                                         "subclientes": "NORTE, SUR"})
    for placa, sede in (("NOR001", "NORTE"), ("NOR002", "NORTE"), ("SUR001", "SUR")):
        database.guardar_vehiculo_padron(CLI, placa, "Cabezote (6x4)", sede)
    _insp("NOR001", "NORTE", 2.0)   # rojo
    _insp("NOR002", "NORTE", 9.0)   # verde
    _insp("SUR001", "SUR", 2.0)     # rojo, pero de otra sede
    database.crear_usuario("gerente_norte", "clave-de-prueba-123", "Gerente Norte", rol="gerencia",
                           cliente_asignado=CLI, vistas_permitidas="kpis,diagnostico", sedes_asignadas=f"{CLI}|NORTE")
    database.crear_usuario("insp_wa", "clave-de-prueba-123", "Inspector", rol="inspector", cliente_asignado=CLI)


def _usuario(nombre="gerente_norte"):
    return database.obtener_usuario_por_username(nombre)


def _cliente_api(usuario=None, rol="gerencia"):
    c = TestClient(server.app)
    if usuario:
        c.headers.update({"Authorization": f"Bearer {server.crear_token_acceso(usuario, rol)}"})
    return c


def _post_webhook(c, payload, secreto=SECRETO):
    cuerpo = json.dumps(payload).encode()
    firma = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return c.post("/api/whatsapp/webhook", content=cuerpo,
                  headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})


def _mensaje(texto, mid="wamid.1", tel=TEL):
    return {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": tel, "profile": {"name": "Cliente"}}],
        "messages": [{"id": mid, "from": tel, "type": "text", "text": {"body": texto}}]}}]}]}


# ---------- Consultas con permisos por sede ----------

def test_cambio_inmediato_solo_trae_vehiculos_de_las_sedes_del_usuario(entorno):
    r = herramientas.vehiculos_por_estado(_usuario(), "rojo")
    assert [v["placa"] for v in r["vehiculos"]] == ["NOR001"]
    llanta = r["vehiculos"][0]["llantas"][0]
    assert llanta["profundidad_mm"] == 2.0 and llanta["limite_mm"] == 3.0


def test_rango_de_fechas_sin_inspecciones_no_trae_vehiculos(entorno):
    r = herramientas.vehiculos_por_estado(_usuario(), "rojo", fecha_desde="2026-10-01", fecha_hasta="2026-10-31")
    assert r["total_vehiculos"] == 0


def test_no_puede_pedir_una_sede_ajena(entorno):
    r = herramientas.ejecutar("resumen_flota", {"sede": "SUR"}, _usuario())
    assert "error" in r and "SUR" in r["error"]


def test_informe_pdf_de_su_sede_y_no_de_otra(entorno):
    ok = herramientas.informe_inspeccion_pdf(_usuario(), "NOR001")
    pdf, nombre = ok["_pdf"]
    assert pdf[:4] == b"%PDF" and nombre.startswith("Informe_NOR001")
    assert "error" in herramientas.informe_inspeccion_pdf(_usuario(), "SUR001")
    assert "error" in herramientas.informe_inspeccion_pdf(_usuario(), "NOEXISTE")


def test_fecha_mal_escrita_devuelve_error_amable(entorno):
    r = herramientas.ejecutar("vehiculos_por_estado", {"estado": "rojo", "fecha_desde": "05/11/2026"}, _usuario())
    assert "AAAA-MM-DD" in r["error"]


# ---------- Vinculación ----------

def test_vincular_con_codigo_valido_una_sola_vez(entorno):
    codigo = almacen.crear_codigo(TEL)
    c = _cliente_api("gerente_norte")
    r = c.post("/api/whatsapp/vincular", json={"codigo": codigo})
    assert r.status_code == 200, r.text
    assert almacen.obtener_vinculo(TEL)["username"] == "gerente_norte"
    assert c.post("/api/whatsapp/vincular", json={"codigo": codigo}).status_code == 400


def test_codigo_vencido_no_sirve(entorno):
    codigo = almacen.crear_codigo(TEL)
    with database.get_connection() as conn:
        conn.execute("UPDATE whatsapp_codigos SET vence = ? WHERE codigo = ?", (time.time() - 1, codigo))
    assert _cliente_api("gerente_norte").post("/api/whatsapp/vincular", json={"codigo": codigo}).status_code == 400
    assert almacen.obtener_vinculo(TEL) is None


def test_inspector_no_puede_vincular(entorno):
    codigo = almacen.crear_codigo(TEL)
    r = _cliente_api("insp_wa", "inspector").post("/api/whatsapp/vincular", json={"codigo": codigo})
    assert r.status_code == 403


def test_vincular_exige_sesion(entorno):
    assert _cliente_api().post("/api/whatsapp/vincular", json={"codigo": "x"}).status_code == 401


def test_cambio_de_clave_desvincula(entorno):
    almacen.guardar_vinculo(TEL, "gerente_norte", 0)
    assert rutas.usuario_del_telefono(TEL)["username"] == "gerente_norte"
    database.incrementar_version_sesion("gerente_norte")
    assert rutas.usuario_del_telefono(TEL) is None
    assert almacen.obtener_vinculo(TEL) is None


def test_pagina_de_vinculacion_se_sirve(entorno):
    r = _cliente_api().get("/whatsapp/vincular?c=abc")
    assert r.status_code == 200 and "Vincular su WhatsApp" in r.text


# ---------- Webhook ----------

def test_verificacion_del_webhook(entorno):
    c = _cliente_api()
    ok = c.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verificar-123", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    assert c.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "42"}).status_code == 403


def test_webhook_con_firma_invalida_se_rechaza(entorno):
    r = _post_webhook(_cliente_api(), _mensaje("hola"), secreto="otro")
    assert r.status_code == 401
    assert entorno["textos"] == []


def test_numero_sin_vincular_recibe_enlace(entorno):
    r = _post_webhook(_cliente_api(), _mensaje("hola"))
    assert r.status_code == 200
    (tel, texto), = entorno["textos"]
    assert tel == TEL and "https://tirecheck.ejemplo.com/whatsapp/vincular?c=" in texto


def test_mensaje_repetido_por_meta_se_atiende_una_vez(entorno):
    c = _cliente_api()
    _post_webhook(c, _mensaje("hola", mid="wamid.rep"))
    _post_webhook(c, _mensaje("hola", mid="wamid.rep"))
    assert len(entorno["textos"]) == 1


def test_numero_vinculado_recibe_respuesta_y_pdf(entorno, monkeypatch):
    almacen.guardar_vinculo(TEL, "gerente_norte", 0)
    vistos = {}

    def falso_responder(usuario, historial, mensaje):
        vistos["usuario"] = usuario["username"]
        return "Te envié el informe.", [(b"%PDF-falso", "Informe_NOR001.pdf", "Informe")]

    monkeypatch.setattr(agente, "responder", falso_responder)
    _post_webhook(_cliente_api(), _mensaje("mándame el informe de NOR001"))
    assert vistos["usuario"] == "gerente_norte"
    assert entorno["documentos"] == [(TEL, b"%PDF-falso", "Informe_NOR001.pdf")]
    assert entorno["textos"][-1] == (TEL, "Te envié el informe.")
    assert [h["rol"] for h in almacen.historial(TEL)] == ["usuario", "asistente"]


def test_salir_desvincula(entorno):
    almacen.guardar_vinculo(TEL, "gerente_norte", 0)
    _post_webhook(_cliente_api(), _mensaje("salir"))
    assert almacen.obtener_vinculo(TEL) is None


# ---------- Agente (Gemini simulado) ----------

class _RespuestaFalsa:
    def __init__(self, llamadas=None, texto=""):
        from google.genai import types
        self.function_calls = [types.FunctionCall(name=n, args=a) for n, a in (llamadas or [])]
        self.text = texto
        self.candidates = [types.Candidate(content=types.Content(
            role="model", parts=[types.Part(function_call=f) for f in self.function_calls] or [types.Part(text=texto)]))]


def test_agente_ejecuta_la_herramienta_con_el_usuario_vinculado(entorno, monkeypatch):
    respuestas = [_RespuestaFalsa([("vehiculos_por_estado", {"estado": "rojo"})]), _RespuestaFalsa(texto="NOR001 tiene cambio inmediato.")]
    recibidos = []

    class Modelos:
        def generate_content(self, model, contents, config):
            recibidos.append(contents[-1])
            return respuestas.pop(0)

    class Cliente:
        models = Modelos()

    monkeypatch.setattr(agente, "_cliente", lambda: Cliente())
    texto, pdfs = agente.responder(_usuario(), [], "¿qué carros tienen cambio inmediato?")
    assert texto == "NOR001 tiene cambio inmediato." and pdfs == []
    respuesta_herramienta = recibidos[1].parts[0].function_response.response
    assert [v["placa"] for v in respuesta_herramienta["vehiculos"]] == ["NOR001"]
