"""Rutas del chatbot de WhatsApp.

- GET  /api/whatsapp/webhook   Meta confirma el webhook (hub.verify_token).
- POST /api/whatsapp/webhook   mensajes entrantes (firmados por Meta); se responden en segundo plano.
- POST /api/whatsapp/vincular  con la sesión de la página: une el celular del código con el usuario.
- GET  /whatsapp/vincular      página donde el cliente inicia sesión para vincular su celular.

Variables de entorno propias: URL_PUBLICA (o RAILWAY_PUBLIC_DOMAIN) para armar el enlace de vinculación y
WHATSAPP_ROLES (roles que pueden usar el bot; por defecto gerencia y jefatura).
"""
import json
import os
import time
from collections import defaultdict, deque

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

import database
from whatsapp import agente, almacen, proveedor_meta

_PLANTILLA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "vincular_whatsapp.html")
MAX_MENSAJES_POR_MINUTO = 20
_COMANDOS_SALIR = {"salir", "desvincular", "cerrar sesion", "cerrar sesión"}
_mensajes_recientes = defaultdict(deque)

AYUDA = ("Puedo ayudarte con:\n"
         "- Vehículos con llantas para *cambio inmediato* o *próximas a cambio* (por mes, sede o rango de fechas)\n"
         "- *Resumen* del estado de tu flota\n"
         "- Resultado de la *última inspección* de una placa\n"
         "- *Informe de inspección en PDF* de una placa\n"
         "- *Informe consolidado de flota en PDF*\n\n"
         "Ejemplo: _¿Qué carros de este mes tienen llantas para cambio inmediato?_\n"
         "Escribe *salir* para desvincular este celular.")


class VincularItem(BaseModel):
    codigo: str


def _roles_permitidos() -> set:
    return {r.strip().lower() for r in os.environ.get("WHATSAPP_ROLES", "gerencia,gerente,jefatura,jefe,jefe_llantas").split(",") if r.strip()}


def _url_publica() -> str:
    url = os.environ.get("URL_PUBLICA", "").strip().rstrip("/")
    if not url and os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        url = "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"].strip()
    return url


def motivo_rechazo_usuario(usr) -> str:
    """'' si el usuario puede usar el bot; si no, el motivo para mostrarle."""
    if not usr or not usr.get("activo"):
        return "Su usuario no existe o está inactivo."
    if usr.get("debe_cambiar_clave"):
        return "Debe cambiar su contraseña en TireCheck antes de usar el asistente."
    if str(usr.get("rol", "")).strip().lower() not in _roles_permitidos():
        return "Su tipo de usuario no tiene habilitado el asistente de WhatsApp."
    if not database.parsear_clientes_asignados(usr.get("cliente_asignado")):
        return "Su usuario no tiene un cliente asignado."
    return ""


def usuario_del_telefono(telefono):
    """Usuario vinculado y todavía válido. Si cambió la clave, cerró sesiones o lo desactivaron, el vínculo cae."""
    vinculo = almacen.obtener_vinculo(telefono)
    if not vinculo:
        return None
    usr = database.obtener_usuario_por_username(vinculo["username"])
    if motivo_rechazo_usuario(usr) or int(usr.get("sesion_version") or 0) != vinculo["sesion_version"]:
        almacen.borrar_vinculo(telefono)
        return None
    return usr


def _limite_superado(telefono) -> bool:
    ahora = time.time()
    cola = _mensajes_recientes[telefono]
    while cola and ahora - cola[0] > 60:
        cola.popleft()
    cola.append(ahora)
    return len(cola) > MAX_MENSAJES_POR_MINUTO


def _invitar_a_vincular(telefono):
    url = _url_publica()
    if not url:
        proveedor_meta.enviar_texto(telefono, "El asistente aún no está configurado (falta la dirección pública). Avise al administrador.")
        return
    codigo = almacen.crear_codigo(telefono)
    proveedor_meta.enviar_texto(telefono, (
        "¡Hola! Soy el asistente de *TireCheck Pro*.\n\n"
        "Para saber de qué flota eres, inicia sesión una sola vez con tu usuario y contraseña de TireCheck en este enlace "
        f"(vence en 10 minutos):\n{url}/whatsapp/vincular?c={codigo}\n\n"
        "Por seguridad, nunca escribas tu contraseña en este chat."))


def atender_mensaje(mensaje):
    """Responde un mensaje entrante. Se ejecuta en segundo plano: nunca debe lanzar."""
    tel = almacen.normalizar_telefono(mensaje.get("telefono"))
    try:
        if not tel or not almacen.marcar_procesado(mensaje.get("id")):
            return
        print(f"[WHATSAPP] Mensaje recibido de ...{tel[-4:]} (tipo {mensaje.get('tipo')})")
        if _limite_superado(tel):
            return
        usr = usuario_del_telefono(tel)
        if not usr:
            _invitar_a_vincular(tel)
            return
        texto = str(mensaje.get("texto") or "").strip()
        if not texto:
            proveedor_meta.enviar_texto(tel, "Por ahora solo entiendo mensajes de texto. " + AYUDA)
            return
        if texto.lower() in _COMANDOS_SALIR:
            almacen.borrar_vinculo(tel)
            proveedor_meta.enviar_texto(tel, "Listo, este celular quedó desvinculado de TireCheck. Escríbeme cuando quieras volver a vincularlo.")
            return
        if texto.lower() in {"ayuda", "menu", "menú", "?"}:
            proveedor_meta.enviar_texto(tel, AYUDA)
            return
        if not agente.configurado():
            proveedor_meta.enviar_texto(tel, "El asistente aún no está configurado (falta la clave de IA). Avise al administrador.")
            return

        respuesta, pdfs = agente.responder(usr, almacen.historial(tel), texto)
        for contenido, nombre, leyenda in pdfs:
            proveedor_meta.enviar_documento(tel, contenido, nombre, leyenda)
        proveedor_meta.enviar_texto(tel, respuesta)
        almacen.agregar_historial(tel, "usuario", texto)
        almacen.agregar_historial(tel, "asistente", respuesta)
    except Exception as e:
        print(f"[WHATSAPP] Error atendiendo un mensaje: {e!r}")
        try:
            proveedor_meta.enviar_texto(tel, "Tuve un problema procesando tu mensaje. Intenta de nuevo en un momento.")
        except Exception:
            pass


def crear_router(obtener_usuario_actual) -> APIRouter:
    """El servidor pasa su dependencia de sesión (evita importar server.py desde aquí)."""
    router = APIRouter()

    @router.get("/api/whatsapp/webhook")
    def verificar_webhook(request: Request):
        q = request.query_params
        reto = proveedor_meta.verificar_suscripcion(q.get("hub.mode"), q.get("hub.verify_token"), q.get("hub.challenge"))
        if reto is None:
            raise HTTPException(status_code=403, detail="Token de verificación inválido")
        return PlainTextResponse(reto)

    @router.post("/api/whatsapp/webhook")
    async def recibir_webhook(request: Request, tareas: BackgroundTasks):
        cuerpo = await request.body()
        if not proveedor_meta.firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
            raise HTTPException(status_code=401, detail="Firma inválida")
        try:
            payload = json.loads(cuerpo or b"{}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Cuerpo inválido")
        # Meta exige respuesta rápida: se contesta 200 y el mensaje se atiende en segundo plano
        for m in proveedor_meta.parsear_entrantes(payload):
            tareas.add_task(atender_mensaje, m)
        return {"status": "ok"}

    @router.post("/api/whatsapp/vincular")
    def vincular(item: VincularItem, tareas: BackgroundTasks, usuario_actual: dict = Depends(obtener_usuario_actual)):
        motivo = motivo_rechazo_usuario(usuario_actual)
        if motivo:
            raise HTTPException(status_code=403, detail=motivo)
        telefono = almacen.consumir_codigo(item.codigo)
        if not telefono:
            raise HTTPException(status_code=400, detail="El enlace venció o ya se usó. Escríbale de nuevo al WhatsApp para recibir uno nuevo.")
        almacen.guardar_vinculo(telefono, usuario_actual["username"], usuario_actual.get("sesion_version"))
        nombre = usuario_actual.get("nombre_completo") or usuario_actual["username"]
        if proveedor_meta.configurado():
            tareas.add_task(_confirmar_vinculo, telefono, nombre)
        return {"status": "ok", "mensaje": f"Listo, {nombre}. Ya puede volver a WhatsApp y hacer su consulta."}

    @router.get("/whatsapp/vincular", response_class=HTMLResponse)
    def pagina_vincular():
        with open(_PLANTILLA, encoding="utf-8") as f:
            return HTMLResponse(f.read(), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    return router


def _confirmar_vinculo(telefono, nombre):
    try:
        proveedor_meta.enviar_texto(telefono, f"✅ Quedaste vinculado como *{nombre}*.\n\n" + AYUDA)
    except Exception as e:
        print(f"[WHATSAPP] No se pudo confirmar la vinculación: {e!r}")
