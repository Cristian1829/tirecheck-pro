"""Conexión con WhatsApp Cloud API de Meta: firma del webhook, lectura de mensajes y envío de texto y PDF.

Todo lo que depende del proveedor está aquí: si algún día se cambia a otro proveedor, solo cambia este módulo.

Variables de entorno:
  WHATSAPP_TOKEN         token permanente del usuario del sistema (Meta Business)
  WHATSAPP_PHONE_ID      identificador del número (Phone Number ID)
  WHATSAPP_APP_SECRET    clave secreta de la app de Meta (firma de los webhooks)
  WHATSAPP_VERIFY_TOKEN  texto que se escribe en Meta al registrar el webhook
  WHATSAPP_API_VERSION   versión de la Graph API (por defecto v25.0)
"""
import hashlib
import hmac
import os

import requests

LIMITE_TEXTO = 4000  # WhatsApp admite 4096 caracteres por mensaje


def _cfg(nombre, defecto=""):
    return os.environ.get(nombre, defecto).strip()


def configurado() -> bool:
    return bool(_cfg("WHATSAPP_TOKEN") and _cfg("WHATSAPP_PHONE_ID"))


def _url(ruta):
    return f"https://graph.facebook.com/{_cfg('WHATSAPP_API_VERSION', 'v25.0')}/{_cfg('WHATSAPP_PHONE_ID')}/{ruta}"


def _cabeceras():
    return {"Authorization": f"Bearer {_cfg('WHATSAPP_TOKEN')}"}


def verificar_suscripcion(modo, token, reto):
    """Respuesta al GET con el que Meta confirma el webhook; None si el token no coincide."""
    esperado = _cfg("WHATSAPP_VERIFY_TOKEN")
    if modo == "subscribe" and esperado and hmac.compare_digest(str(token or ""), esperado):
        return str(reto or "")
    return None


def firma_valida(cuerpo: bytes, firma_cabecera) -> bool:
    """Meta firma cada webhook con la clave secreta de la app (cabecera X-Hub-Signature-256)."""
    secreto = _cfg("WHATSAPP_APP_SECRET")
    if not secreto or not firma_cabecera or not str(firma_cabecera).startswith("sha256="):
        return False
    esperado = hmac.new(secreto.encode("utf-8"), cuerpo or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(firma_cabecera)[7:], esperado)


def parsear_entrantes(payload) -> list:
    """Mensajes que trae el webhook: [{id, telefono, nombre, tipo, texto, numero_bot}]. Ignora estados de entrega."""
    mensajes = []
    for entrada in (payload or {}).get("entry", []) or []:
        for cambio in entrada.get("changes", []) or []:
            valor = cambio.get("value", {}) or {}
            numero_bot = "".join(ch for ch in str((valor.get("metadata") or {}).get("display_phone_number", "")) if ch.isdigit())
            nombres = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in valor.get("contacts", []) or []}
            for m in valor.get("messages", []) or []:
                tipo = m.get("type", "")
                texto = ""
                if tipo == "text":
                    texto = (m.get("text") or {}).get("body", "")
                elif tipo == "button":
                    texto = (m.get("button") or {}).get("text", "")
                elif tipo == "interactive":
                    inter = m.get("interactive") or {}
                    texto = (inter.get("button_reply") or inter.get("list_reply") or {}).get("title", "")
                mensajes.append({"id": m.get("id", ""), "telefono": m.get("from", ""),
                                 "nombre": nombres.get(m.get("from"), ""), "tipo": tipo, "texto": texto,
                                 "numero_bot": numero_bot})
    return mensajes


class ErrorMeta(Exception):
    pass


def _exigir_ok(r):
    """Si Meta rechaza la petición, el error lleva su motivo (p. ej. «número no permitido» o «token vencido»)."""
    if r.status_code >= 400:
        try:
            e = r.json().get("error", {})
            motivo = f"codigo {e.get('code')}: {e.get('message')} {(e.get('error_data') or {}).get('details', '')}".strip()
        except ValueError:
            motivo = r.text[:300]
        raise ErrorMeta(f"Meta respondió {r.status_code} ({motivo})")


def enviar_texto(telefono, texto):
    texto = str(texto or "").strip() or "…"
    trozos = [texto[i:i + LIMITE_TEXTO] for i in range(0, len(texto), LIMITE_TEXTO)]
    for trozo in trozos:
        r = requests.post(_url("messages"), headers=_cabeceras(), timeout=20, json={
            "messaging_product": "whatsapp", "to": str(telefono), "type": "text",
            "text": {"body": trozo, "preview_url": True}})
        _exigir_ok(r)


def enviar_documento(telefono, contenido: bytes, nombre_archivo, leyenda=""):
    """Sube el PDF a Meta y lo envía como documento."""
    subida = requests.post(_url("media"), headers=_cabeceras(), timeout=60,
                           data={"messaging_product": "whatsapp", "type": "application/pdf"},
                           files={"file": (nombre_archivo, contenido, "application/pdf")})
    _exigir_ok(subida)
    media_id = subida.json()["id"]
    documento = {"id": media_id, "filename": nombre_archivo}
    if leyenda:
        documento["caption"] = str(leyenda)[:1000]
    r = requests.post(_url("messages"), headers=_cabeceras(), timeout=20, json={
        "messaging_product": "whatsapp", "to": str(telefono), "type": "document", "document": documento})
    _exigir_ok(r)
