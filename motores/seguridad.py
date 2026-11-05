"""
Login de Motores, con el mismo nivel del de TireAnalyze: reutiliza su cifrado y su política de claves (database.py),
pero con cuentas, cookie y clave de firma propias. Un token de llantas no sirve aquí, ni al revés.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

import database
from motores.base import dir_datos, get_db, nueva_sesion
from motores.modelos import IntentoIngreso, SesionRevocada, Usuario

COOKIE = "motores_token"
DURACION_TOKEN = 604800  # 7 días, como en TireAnalyze
MAX_FALLOS_IP, VENTANA_FALLOS_IP = 8, 60.0
MAX_FALLOS_USUARIO, VENTANA_FALLOS_USUARIO = 10, 15 * 60.0
RUTAS_DE_SESION = ("/api/motores/me", "/api/motores/logout", "/api/motores/mi-cuenta/cambiar-clave")

intentos_ip: dict = {}  # ip -> marcas de tiempo de claves incorrectas del último minuto
_secreto = {}


def _obtener_secreto() -> bytes:
    """Clave de firma exclusiva de Motores: variable MOTORES_SECRET_KEY o archivo propio en el volumen."""
    carpeta = dir_datos()
    if carpeta in _secreto:
        return _secreto[carpeta]
    clave = (os.environ.get("MOTORES_SECRET_KEY") or "").strip()
    if not clave:
        archivo = os.path.join(carpeta, ".secret_key")
        try:
            if os.path.exists(archivo):
                with open(archivo, "r", encoding="utf-8") as f:
                    clave = f.read().strip()
            if not clave:
                clave = secrets.token_hex(32)
                with open(archivo, "w", encoding="utf-8") as f:
                    f.write(clave)
        except OSError as e:
            # Nunca una clave fija. Una al azar dura mientras el servidor esté encendido.
            print(f"[MOTORES] No se pudo guardar la clave secreta ({e}); las sesiones se cerrarán al reiniciar.")
            clave = clave or secrets.token_hex(32)
    _secreto[carpeta] = hashlib.sha256(b"motores-sesion-v1:" + clave.encode("utf-8")).digest()
    return _secreto[carpeta]


def _firmar(payload_b64: str) -> str:
    return hmac.new(_obtener_secreto(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def crear_token(usuario: Usuario) -> str:
    payload = {
        "app": "motores",
        "sub": usuario.username,
        "exp": int(time.time()) + DURACION_TOKEN,
        "ver": int(usuario.sesion_version or 0),
        "jti": secrets.token_urlsafe(12),
    }
    cuerpo = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{cuerpo}.{_firmar(cuerpo)}"


def verificar_token(token) -> Optional[dict]:
    if not token or not isinstance(token, str):
        return None
    partes = token.strip().split(".")
    if len(partes) != 2 or not hmac.compare_digest(partes[1], _firmar(partes[0])):
        return None
    try:
        relleno = "=" * ((4 - len(partes[0]) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(partes[0] + relleno).decode("utf-8"))
    except Exception:
        return None
    if payload.get("app") != "motores" or payload.get("exp", 0) < int(time.time()):
        return None
    return payload


def ip_cliente(request: Request) -> str:
    """En Railway la IP real llega en X-Real-IP; si no, en la última entrada de X-Forwarded-For."""
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    reenviada = (request.headers.get("x-forwarded-for") or "").strip()
    if reenviada:
        return reenviada.split(",")[-1].strip()
    return request.client.host if request.client else "127.0.0.1"


def es_https(request: Request) -> bool:
    return request.url.scheme == "https" or (request.headers.get("x-forwarded-proto") or "").lower() == "https"


def entregar_sesion(request: Request, response: Response, usuario: Usuario) -> None:
    response.set_cookie(
        key=COOKIE,
        value=crear_token(usuario),
        httponly=True,
        samesite="lax",
        secure=es_https(request),
        max_age=DURACION_TOKEN,
    )


def fallos_recientes(db: Session, username: str) -> int:
    desde = int(time.time() - VENTANA_FALLOS_USUARIO)
    return db.query(IntentoIngreso).filter(
        IntentoIngreso.username == username,
        IntentoIngreso.exito == False,  # noqa: E712
        IntentoIngreso.momento >= desde,
    ).count()


def registrar_intento(db: Session, username: str, ip: str, exito: bool, motivo: str = None) -> None:
    db.add(IntentoIngreso(username=username[:200], ip=(ip or "")[:64], exito=exito, motivo=motivo, momento=int(time.time())))
    db.commit()


def autenticar(db: Session, username: str, clave: str) -> Optional[Usuario]:
    usuario = db.query(Usuario).filter(Usuario.username == username).first()
    if not usuario or not usuario.activo:
        database.verificar_clave_ficticia(clave)  # mismo tiempo de respuesta que con un usuario real
        return None
    if not database.verify_password(clave, usuario.password_hash):
        return None
    if database.hash_desactualizado(usuario.password_hash):
        usuario.password_hash = database.hash_password(clave)
        db.commit()
    return usuario


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    payload = verificar_token(request.cookies.get(COOKIE))
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    usuario = db.query(Usuario).filter(Usuario.username == payload["sub"]).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    revocada = db.query(SesionRevocada).filter(SesionRevocada.jti == str(payload.get("jti"))).first()
    if revocada or int(payload.get("ver", 0) or 0) != int(usuario.sesion_version or 0):
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    if usuario.debe_cambiar_clave and request.url.path not in RUTAS_DE_SESION:
        raise HTTPException(status_code=403, detail="Debe cambiar su contraseña antes de continuar.",
                            headers={"X-Requiere-Cambio-Clave": "1"})
    return usuario


def solo_admin(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador de Motores puede hacer esto.")
    return usuario


def revocar(db: Session, payload: dict) -> None:
    if payload and payload.get("jti"):
        db.query(SesionRevocada).filter(SesionRevocada.exp < int(time.time())).delete()
        if not db.query(SesionRevocada).filter(SesionRevocada.jti == payload["jti"]).first():
            db.add(SesionRevocada(jti=payload["jti"], exp=int(payload.get("exp", 0))))
        db.commit()


def crear_admin_inicial() -> None:
    """
    Sin claves en el código: el primer administrador sale de MOTORES_ADMIN_USUARIO y MOTORES_ADMIN_CLAVE,
    solo si aún no hay usuarios, y debe cambiar la clave al primer ingreso.
    """
    db = nueva_sesion()
    try:
        if db.query(Usuario).count() > 0:
            return
        username = (os.environ.get("MOTORES_ADMIN_USUARIO") or "").strip().lower()
        clave = os.environ.get("MOTORES_ADMIN_CLAVE") or ""
        if not username or not clave:
            print("[MOTORES] Sin usuarios. Defina MOTORES_ADMIN_USUARIO y MOTORES_ADMIN_CLAVE para crear el primer administrador.")
            return
        error = database.validar_clave_nueva(clave, username)
        if error:
            print(f"[MOTORES] No se creó el primer administrador: {error}")
            return
        db.add(Usuario(username=username, nombre=username, password_hash=database.hash_password(clave),
                       rol="admin", activo=True, debe_cambiar_clave=True))
        db.commit()
        print(f"[MOTORES] Primer administrador creado: {username}")
    finally:
        db.close()
