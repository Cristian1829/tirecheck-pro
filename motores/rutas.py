"""Rutas de Motores: página, acceso, órdenes, despachos, certificados, clientes, motores y archivos."""
import io
import os
import re
import time
import uuid
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import database
from motores import base, seguridad
from motores.archivos import TIPOS, ImagenInvalida, guardar_imagen, ruta_archivo, url_de
from motores.base import ahora, get_db
from motores.esquemas import (
    CambioClaveEntrada, CertificadoCalidadCreate, CertificadoCalidadResponse, ClienteCreate, ClienteResponse,
    ClienteUpdate, DashboardStats, EntregaSalidaCreate, EntregaSalidaResponse, LoginEntrada, MotorResponse,
    OrdenCreate, OrdenResponse, UsuarioCrear, UsuarioEditar, UsuarioRespuesta,
)
from motores.modelos import (
    CertificadoCalidad, Cliente, EntregaItem, EntregaSalida, MotorDetalle, Orden, Usuario,
)
from motores.pdf import generate_certificate_pdf, generate_entry_pdf, generate_exit_pdf

_PLANTILLA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "motores.html")
_USUARIO_VALIDO = re.compile(r"^[a-z0-9._-]{3,40}$")
_ID_CLIENTE_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,50}$")

PRESET_MAKES = ["Tirak", "Sky Climber", "Spider", "Tractel", "Blocstop"]
MODEL_TO_MAKE = {
    "SKYCLIMBER BALDOR 1000": "Sky Climber",
    "SKYCLIMBER COMPACT 1000": "Sky Climber",
    "SKYCLIMBER COMPACT 1250": "Sky Climber",
    "SKYCLIMBER LNX1000": "Sky Climber",
    "SPIDER Z-MAC 1000": "Spider",
    "TIRAK LE 501P": "Tirak",
    "TIRAK TE 401P": "Tirak",
    "TIRAK XE 500 P+": "Tirak",
    "TIRAK XE 500P": "Tirak",
    "TIRAK XE 501 P SAFWAY": "Tirak",
    "TIRAK XE 501 P+": "Tirak",
    "TIRAK XE 501 PA1": "Tirak",
    "TIRAK XE 600P": "Tirak",
}
PRESET_MODELS = sorted(MODEL_TO_MAKE)

router = APIRouter()  # página y acceso, sin sesión
api = APIRouter(prefix="/api/motores", dependencies=[Depends(seguridad.usuario_actual)])  # el resto exige sesión


def iniciar(directorio: str = None) -> None:
    base.configurar(directorio)
    seguridad.crear_admin_inicial()


def _limpio(texto) -> str:
    return (texto or "").strip()


def _mayus(texto) -> str:
    return _limpio(texto).upper()


def _imagen(data_url, prefijo: str, firma: bool = False):
    try:
        return guardar_imagen(data_url, prefijo, firma)
    except ImagenInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))


# ================= PÁGINA =================
@router.get("/motores", response_class=HTMLResponse)
@router.get("/motores/", response_class=HTMLResponse)
def pagina_motores(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    with open(_PLANTILLA, "r", encoding="utf-8") as f:
        return f.read()


# ================= ACCESO =================
def _usuario_publico(u: Usuario) -> dict:
    return UsuarioRespuesta.model_validate(u).model_dump()


@router.post("/api/motores/login")
def login(item: LoginEntrada, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = seguridad.ip_cliente(request)
    momento = time.time()
    intentos = [t for t in seguridad.intentos_ip.get(ip, []) if momento - t < seguridad.VENTANA_FALLOS_IP]
    seguridad.intentos_ip[ip] = intentos
    if len(intentos) >= seguridad.MAX_FALLOS_IP:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intente de nuevo en 60 segundos.")
    username = _limpio(item.username).lower()
    if username and seguridad.fallos_recientes(db, username) >= seguridad.MAX_FALLOS_USUARIO:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos con este usuario. Intente de nuevo en 15 minutos.")

    usuario = seguridad.autenticar(db, username, item.password)
    if not usuario:
        intentos.append(momento)
        if username:
            seguridad.registrar_intento(db, username, ip, False, "clave_incorrecta")
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    seguridad.intentos_ip[ip] = []
    seguridad.registrar_intento(db, username, ip, True)
    seguridad.entregar_sesion(request, response, usuario)
    return {"status": "ok", "usuario": _usuario_publico(usuario)}


@router.post("/api/motores/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    seguridad.revocar(db, seguridad.verificar_token(request.cookies.get(seguridad.COOKIE)))
    response.delete_cookie(key=seguridad.COOKIE)
    return {"status": "ok"}


@router.get("/api/motores/me")
def yo(usuario: Usuario = Depends(seguridad.usuario_actual)):
    return {"status": "ok", "usuario": _usuario_publico(usuario)}


@router.post("/api/motores/mi-cuenta/cambiar-clave")
def cambiar_clave(item: CambioClaveEntrada, request: Request, response: Response, db: Session = Depends(get_db),
                  usuario: Usuario = Depends(seguridad.usuario_actual)):
    if seguridad.fallos_recientes(db, usuario.username) >= seguridad.MAX_FALLOS_USUARIO:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos con este usuario. Intente de nuevo en 15 minutos.")
    if not database.verify_password(item.clave_actual, usuario.password_hash):
        seguridad.registrar_intento(db, usuario.username, seguridad.ip_cliente(request), False, "clave_incorrecta")
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    error = database.validar_clave_nueva(item.clave_nueva, usuario.username)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if item.clave_nueva.strip() == item.clave_actual.strip():
        raise HTTPException(status_code=400, detail="La contraseña nueva debe ser distinta de la actual.")
    usuario.password_hash = database.hash_password(item.clave_nueva.strip())
    usuario.debe_cambiar_clave = False
    usuario.sesion_version = int(usuario.sesion_version or 0) + 1  # cierra las demás sesiones
    db.commit()
    seguridad.entregar_sesion(request, response, usuario)
    return {"status": "ok", "usuario": _usuario_publico(usuario)}


# ================= USUARIOS (SOLO ADMINISTRADOR) =================
def _rol_valido(rol: str) -> str:
    if rol not in ("admin", "tecnico"):
        raise HTTPException(status_code=400, detail="El rol debe ser administrador o técnico.")
    return rol


@api.get("/usuarios", response_model=List[UsuarioRespuesta], dependencies=[Depends(seguridad.solo_admin)])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).order_by(Usuario.username.asc()).all()


@api.post("/usuarios", response_model=UsuarioRespuesta, dependencies=[Depends(seguridad.solo_admin)])
def crear_usuario(item: UsuarioCrear, db: Session = Depends(get_db)):
    username = _limpio(item.username).lower()
    if not _USUARIO_VALIDO.match(username):
        raise HTTPException(status_code=400, detail="El usuario debe tener de 3 a 40 letras, números, punto, guion o guion bajo.")
    if db.query(Usuario).filter(Usuario.username == username).first():
        raise HTTPException(status_code=400, detail="Ese usuario ya existe.")
    error = database.validar_clave_nueva(item.clave_nueva, username)
    if error:
        raise HTTPException(status_code=400, detail=error)
    nuevo = Usuario(username=username, nombre=_limpio(item.nombre) or username, rol=_rol_valido(item.rol),
                    password_hash=database.hash_password(item.clave_nueva.strip()), activo=True, debe_cambiar_clave=True)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@api.put("/usuarios/{usuario_id}", response_model=UsuarioRespuesta)
def editar_usuario(usuario_id: int, item: UsuarioEditar, db: Session = Depends(get_db),
                   admin: Usuario = Depends(seguridad.solo_admin)):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if u.id == admin.id and (item.activo is False or (item.rol and item.rol != "admin")):
        raise HTTPException(status_code=400, detail="No puede quitarse a sí mismo el acceso de administrador.")
    if item.nombre is not None:
        u.nombre = _limpio(item.nombre)
    if item.rol is not None:
        u.rol = _rol_valido(item.rol)
    if item.activo is not None:
        u.activo = item.activo
        if not item.activo:
            u.sesion_version = int(u.sesion_version or 0) + 1
    if item.clave_nueva:
        error = database.validar_clave_nueva(item.clave_nueva, u.username)
        if error:
            raise HTTPException(status_code=400, detail=error)
        u.password_hash = database.hash_password(item.clave_nueva.strip())
        u.debe_cambiar_clave = True
        u.sesion_version = int(u.sesion_version or 0) + 1
    db.commit()
    db.refresh(u)
    return u


# ================= ARCHIVOS (SOLO CON SESIÓN) =================
@api.get("/archivos/{nombre}")
def archivo(nombre: str):
    ruta = ruta_archivo(nombre)
    tipo = TIPOS.get(os.path.splitext(nombre)[1].lower())
    if not ruta or not tipo:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(ruta, media_type=tipo, filename=nombre, content_disposition_type="inline",
                        headers={"Cache-Control": "private, no-store"})


@api.get("/network-qr")
def network_qr(request: Request):
    """QR con la dirección de Motores, para abrirla desde un celular o tableta del taller."""
    import qrcode

    esquema = "https" if seguridad.es_https(request) else "http"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(f"{esquema}://{request.url.netloc}/motores")
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="#1e3a8a", back_color="white").save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


# ================= ÓRDENES (MÓDULO A) =================
def _siguiente_orden(db: Session) -> str:
    return f"ORD-{ahora().year}-{db.query(Orden).count() + 1:04d}"


@api.post("/orders/", response_model=OrdenResponse)
def crear_orden(orden_in: OrdenCreate, db: Session = Depends(get_db)):
    if not orden_in.motores:
        raise HTTPException(status_code=400, detail="Debe ingresar al menos un motor en la orden.")
    if not _limpio(orden_in.company_name):
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente.")
    for m in orden_in.motores:
        if not _limpio(m.make) or not _limpio(m.model) or not _limpio(m.serial_number):
            raise HTTPException(status_code=400, detail="Complete marca, modelo y serial de todos los motores.")
        if not m.foto_ingreso_url:
            raise HTTPException(status_code=400, detail=f"Falta la foto de ingreso del motor {_mayus(m.serial_number)}.")
    if not orden_in.firma_dropoff or not orden_in.firma_received:
        raise HTTPException(status_code=400, detail="Faltan firmas: se requieren la de quien entrega y la de quien recibe.")

    numero = _limpio(orden_in.numero_orden) or _siguiente_orden(db)
    if db.query(Orden).filter(Orden.numero_orden == numero).first():
        numero = f"{numero}-{db.query(Orden).count() + 1}"

    firma_dropoff = _imagen(orden_in.firma_dropoff, "firma_dropoff", firma=True)
    firma_received = _imagen(orden_in.firma_received, "firma_received", firma=True)
    fotos = [_imagen(m.foto_ingreso_url, "foto_in") for m in orden_in.motores]

    orden = Orden(
        numero_orden=numero,
        company_name=_mayus(orden_in.company_name),
        date_in=orden_in.date_in or ahora(),
        estado_orden="En Taller",
        dropoff_name=_mayus(orden_in.dropoff_name) or "CUSTOMER",
        firma_dropoff=firma_dropoff,
        received_name=_mayus(orden_in.received_name) or "MARINO TREJOS",
        firma_received=firma_received,
        notas=orden_in.notas,
    )
    db.add(orden)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Otro ingreso tomó ese número de orden. Intente guardar de nuevo.")
    for m, foto in zip(orden_in.motores, fotos):
        db.add(MotorDetalle(
            orden_id=orden.id,
            make=_mayus(m.make),
            model=_mayus(m.model),
            serial_number=_mayus(m.serial_number),
            estado_motor="En Taller",
            foto_ingreso_url=foto,
            observaciones=m.observaciones,
        ))
    db.commit()
    db.refresh(orden)

    try:
        orden.pdf_ingreso_url = generate_entry_pdf(orden)
        db.commit()
        db.refresh(orden)
    except Exception as e:
        print(f"[MOTORES] Error generando PDF de ingreso: {e}")
    return orden


@api.get("/orders/", response_model=List[OrdenResponse])
def listar_ordenes(estado: Optional[str] = None, search: Optional[str] = None, limit: int = Query(100, ge=1, le=500),
                   offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = db.query(Orden)
    if estado and estado != "Todos":
        q = q.filter(Orden.estado_orden == estado)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(Orden.numero_orden.ilike(s) | Orden.company_name.ilike(s))
    return q.order_by(Orden.id.desc()).offset(offset).limit(limit).all()


def _orden(db: Session, order_id: int) -> Orden:
    orden = db.query(Orden).filter(Orden.id == order_id).first()
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return orden


@api.get("/orders/{order_id}", response_model=OrdenResponse)
def ver_orden(order_id: int, db: Session = Depends(get_db)):
    return _orden(db, order_id)


@api.post("/orders/{order_id}/regenerate-pdf")
def regenerar_pdf_orden(order_id: int, db: Session = Depends(get_db)):
    orden = _orden(db, order_id)
    orden.pdf_ingreso_url = generate_entry_pdf(orden)
    db.commit()
    return {"pdf_url": url_de(orden.pdf_ingreso_url)}


# ================= DESPACHOS (MÓDULO B) =================
@api.post("/dispatches/", response_model=EntregaSalidaResponse)
def crear_despacho(d: EntregaSalidaCreate, db: Session = Depends(get_db)):
    orden = _orden(db, d.orden_id)
    if not d.motores_despacho:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un motor para despachar.")
    ids = [i.motor_id for i in d.motores_despacho]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Un motor aparece repetido en el despacho.")
    motores = {m.id: m for m in orden.motores}
    for item in d.motores_despacho:
        motor = motores.get(item.motor_id)
        if not motor:
            raise HTTPException(status_code=400, detail="Un motor seleccionado no pertenece a esta orden.")
        if motor.estado_motor != "En Taller":
            raise HTTPException(status_code=400, detail=f"El motor {motor.serial_number} ya fue entregado.")
        if not item.foto_salida_url:
            raise HTTPException(status_code=400, detail=f"Falta la foto de salida del motor {motor.serial_number}.")
    if not d.firma_entrega_empresa or not d.firma_recibe_cliente:
        raise HTTPException(status_code=400, detail="Faltan firmas: se requieren la del taller y la del cliente.")

    firma_empresa = _imagen(d.firma_entrega_empresa, "firma_despacho_taller", firma=True)
    firma_cliente = _imagen(d.firma_recibe_cliente, "firma_despacho_cliente", firma=True)
    fotos = [_imagen(i.foto_salida_url, "foto_out") for i in d.motores_despacho]
    fecha = d.fecha_salida or ahora()
    if orden.date_in and fecha < orden.date_in:
        raise HTTPException(status_code=400, detail="La fecha de salida no puede ser anterior a la fecha de ingreso de la orden.")

    entrega = EntregaSalida(
        orden_id=orden.id,
        tipo_entrega="Parcial",
        fecha_salida=fecha,
        entrega_empresa_name=_mayus(d.entrega_empresa_name) or "MARINO TREJOS",
        firma_entrega_empresa=firma_empresa,
        recibe_cliente_name=_mayus(d.recibe_cliente_name) or "CUSTOMER",
        firma_recibe_cliente=firma_cliente,
        notas=d.notas,
    )
    db.add(entrega)
    db.flush()
    for item, foto in zip(d.motores_despacho, fotos):
        motor = motores[item.motor_id]
        motor.estado_motor = "Entregado"
        motor.foto_salida_url = foto
        db.add(EntregaItem(entrega_id=entrega.id, motor_id=motor.id, foto_salida_url=foto))
    db.flush()

    if any(m.estado_motor == "En Taller" for m in orden.motores):
        orden.estado_orden = "Entregado Parcial"
        entrega.tipo_entrega = "Parcial"
    else:
        orden.estado_orden = "Entregado Total"
        orden.date_out = fecha
        entrega.tipo_entrega = "Total"
    db.commit()
    db.refresh(entrega)

    try:
        pdf = generate_exit_pdf(entrega)
        entrega.pdf_salida_url = pdf
        orden.pdf_ingreso_url = pdf  # el mismo PDF unificado queda actualizado en la orden
        db.commit()
        db.refresh(entrega)
    except Exception as e:
        print(f"[MOTORES] Error generando PDF de salida: {e}")
    return entrega


@api.get("/dispatches/", response_model=List[EntregaSalidaResponse])
def listar_despachos(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(EntregaSalida).order_by(EntregaSalida.id.desc()).limit(limit).all()


@api.get("/dispatches/order/{order_id}", response_model=List[EntregaSalidaResponse])
def despachos_de_orden(order_id: int, db: Session = Depends(get_db)):
    return db.query(EntregaSalida).filter(EntregaSalida.orden_id == order_id).order_by(EntregaSalida.id.desc()).all()


@api.get("/dispatches/{dispatch_id}", response_model=EntregaSalidaResponse)
def ver_despacho(dispatch_id: int, db: Session = Depends(get_db)):
    entrega = db.query(EntregaSalida).filter(EntregaSalida.id == dispatch_id).first()
    if not entrega:
        raise HTTPException(status_code=404, detail="Despacho no encontrado")
    return entrega


# ================= CERTIFICADOS (MÓDULO C) =================
def _siguiente_certificado(db: Session) -> str:
    # Consecutivo sobre los números automáticos: uno escrito a mano no le abre un hueco
    usados = [re.fullmatch(r"10010(\d{3,})", n or "") for (n,) in db.query(CertificadoCalidad.test_certificate_no).all()]
    return f"10010{max((int(m.group(1)) for m in usados if m), default=0) + 1:03d}"


@api.post("/certificates/", response_model=CertificadoCalidadResponse)
def crear_certificado(c: CertificadoCalidadCreate, db: Session = Depends(get_db)):
    motor = db.query(MotorDetalle).filter(MotorDetalle.id == c.motor_id).first()
    if not motor:
        raise HTTPException(status_code=404, detail="Motor no encontrado")
    numero = _limpio(c.test_certificate_no) or _siguiente_certificado(db)
    if db.query(CertificadoCalidad).filter(CertificadoCalidad.test_certificate_no == numero).first():
        # Es un número oficial: no se cambia en silencio
        raise HTTPException(status_code=400, detail=f"Ya existe un certificado con el número {numero}.")
    fecha = c.test_date or ahora()
    if c.next_service and c.next_service <= fecha:
        raise HTTPException(status_code=400, detail="El próximo servicio debe ser posterior a la fecha de prueba.")

    cert = CertificadoCalidad(
        motor_id=motor.id,
        test_certificate_no=numero,
        test_date=fecha,
        next_service=c.next_service or (fecha + timedelta(days=365)),
        voltage=c.voltage or "220 / ONE PHASE",
        start_capacitor=c.start_capacitor,
        vr_start=c.vr_start,
        run_capacitor=c.run_capacitor,
        vr_run=c.vr_run,
        k1=c.k1,
        k2=c.k2,
        k3=c.k3,
        rectifier=c.rectifier,
        brake_release_lever=c.brake_release_lever,
        brake_function=c.brake_function,
        normal_noise=c.normal_noise,
        emergency_pin_descend=c.emergency_pin_descend,
        brake_disc=c.brake_disc,
        stirrup_adapter=c.stirrup_adapter,
        rated_load_test=c.rated_load_test,
        rated_load_capacity=c.rated_load_capacity or "1000",
        overload_test_pounds=c.overload_test_pounds or "1250 POUNDS (125%)",
        blocstop_model=c.blocstop_model or "BLOCSTOP BSO 1000",
        blocstop_serial=c.blocstop_serial or f"BS-{motor.serial_number}",
        blocstop_rated_load=c.blocstop_rated_load or "1000 POUNDS",
        blocstop_trigger_speed=c.blocstop_trigger_speed or "Testing Pass",
        blocstop_load_test=c.blocstop_load_test or "1000 POUNDS Pass",
        blocstop_control_descent=c.blocstop_control_descent or "Testing Pass",
        service_description=c.service_description or "New warning labels, oil change, oil seal, brake gap adjustment, rated load test.",
        certified_by=c.certified_by or "Marino Trejos | Cert#061821JV1",
    )
    db.add(cert)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Otro certificado tomó ese número. Intente guardar de nuevo.")
    db.refresh(cert)

    try:
        cert.pdf_certificado_url = generate_certificate_pdf(cert)
        db.commit()
        db.refresh(cert)
    except Exception as e:
        print(f"[MOTORES] Error generando PDF de certificado: {e}")
    return cert


@api.get("/certificates/", response_model=List[CertificadoCalidadResponse])
def listar_certificados(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(CertificadoCalidad).order_by(CertificadoCalidad.id.desc()).limit(limit).all()


@api.get("/certificates/motor/{motor_id}", response_model=List[CertificadoCalidadResponse])
def certificados_de_motor(motor_id: int, db: Session = Depends(get_db)):
    return db.query(CertificadoCalidad).filter(CertificadoCalidad.motor_id == motor_id).order_by(CertificadoCalidad.id.desc()).all()


def _certificado(db: Session, cert_id: int) -> CertificadoCalidad:
    cert = db.query(CertificadoCalidad).filter(CertificadoCalidad.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificado no encontrado")
    return cert


@api.get("/certificates/{cert_id}", response_model=CertificadoCalidadResponse)
def ver_certificado(cert_id: int, db: Session = Depends(get_db)):
    return _certificado(db, cert_id)


@api.post("/certificates/{cert_id}/regenerate-pdf")
def regenerar_pdf_certificado(cert_id: int, db: Session = Depends(get_db)):
    cert = _certificado(db, cert_id)
    cert.pdf_certificado_url = generate_certificate_pdf(cert)
    db.commit()
    return {"pdf_url": url_de(cert.pdf_certificado_url)}


# ================= CLIENTES (MÓDULO D) =================
def _nombre_repetido(db: Session, nombre: str, excepto: str = None) -> bool:
    q = db.query(Cliente).filter(func.upper(Cliente.company_name) == nombre)
    if excepto:
        q = q.filter(Cliente.id != excepto)
    return q.first() is not None


@api.get("/clients/", response_model=List[ClienteResponse])
def listar_clientes(search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Cliente)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(
            Cliente.company_name.ilike(s) | Cliente.contacto_principal.ilike(s) | Cliente.email.ilike(s)
            | Cliente.phone.ilike(s) | Cliente.address.ilike(s)
        )
    return q.order_by(Cliente.company_name.asc()).all()


def _cliente(db: Session, client_id: str) -> Cliente:
    cliente = db.query(Cliente).filter(Cliente.id == client_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


@api.get("/clients/{client_id}", response_model=ClienteResponse)
def ver_cliente(client_id: str, db: Session = Depends(get_db)):
    return _cliente(db, client_id)


@api.post("/clients/", response_model=ClienteResponse)
def crear_cliente(c: ClienteCreate, db: Session = Depends(get_db)):
    nombre = _mayus(c.company_name)
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre de la empresa es obligatorio.")
    if _nombre_repetido(db, nombre):
        raise HTTPException(status_code=400, detail=f"El cliente '{nombre}' ya existe en el directorio.")
    cid = _limpio(c.id)
    if cid and not _ID_CLIENTE_VALIDO.match(cid):
        raise HTTPException(status_code=400, detail="El ID del cliente solo admite letras, números, guion y guion bajo.")
    if not cid or db.query(Cliente).filter(Cliente.id == cid).first():
        cid = uuid.uuid4().hex[:8]
    nuevo = Cliente(id=cid, company_name=nombre, contacto_principal=_mayus(c.contacto_principal) or None,
                    email=_limpio(c.email) or None, phone=_limpio(c.phone) or None, address=_limpio(c.address) or None)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@api.put("/clients/{client_id}", response_model=ClienteResponse)
def editar_cliente(client_id: str, c: ClienteUpdate, db: Session = Depends(get_db)):
    cliente = _cliente(db, client_id)
    if c.company_name is not None:
        nombre = _mayus(c.company_name)
        if not nombre:
            raise HTTPException(status_code=400, detail="El nombre de la empresa es obligatorio.")
        if _nombre_repetido(db, nombre, excepto=client_id):
            raise HTTPException(status_code=400, detail=f"El cliente '{nombre}' ya existe en el directorio.")
        cliente.company_name = nombre
    if c.contacto_principal is not None:
        cliente.contacto_principal = _mayus(c.contacto_principal) or None
    if c.email is not None:
        cliente.email = _limpio(c.email) or None
    if c.phone is not None:
        cliente.phone = _limpio(c.phone) or None
    if c.address is not None:
        cliente.address = _limpio(c.address) or None
    db.commit()
    db.refresh(cliente)
    return cliente


@api.delete("/clients/{client_id}")
def eliminar_cliente(client_id: str, db: Session = Depends(get_db)):
    db.delete(_cliente(db, client_id))
    db.commit()
    return {"status": "success"}


# ================= MOTORES, PRESETS Y MÉTRICAS (MÓDULO E) =================
@api.get("/motors/", response_model=List[MotorResponse])
def listar_motores(estado: Optional[str] = None, search: Optional[str] = None, orden_id: Optional[int] = None,
                   limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = db.query(MotorDetalle)
    if orden_id:
        q = q.filter(MotorDetalle.orden_id == orden_id)
    if estado and estado != "Todos":
        q = q.filter(MotorDetalle.estado_motor == estado)
    if search:
        s = f"%{search.strip()}%"
        q = q.join(Orden).filter(
            MotorDetalle.serial_number.ilike(s) | MotorDetalle.model.ilike(s) | MotorDetalle.make.ilike(s)
            | Orden.company_name.ilike(s) | Orden.numero_orden.ilike(s)
        )
    return q.order_by(MotorDetalle.id.desc()).offset(offset).limit(limit).all()


@api.get("/motors/common/presets")
def presets(db: Session = Depends(get_db)):
    clientes = sorted({_mayus(n) for (n,) in db.query(Cliente.company_name).all() if _limpio(n)})
    return {"makes": PRESET_MAKES, "models": PRESET_MODELS, "model_to_make": MODEL_TO_MAKE, "customers": clientes}


@api.get("/motors/dashboard/stats", response_model=DashboardStats)
def estadisticas(db: Session = Depends(get_db)):
    return DashboardStats(
        total_ordenes=db.query(Orden).count(),
        ordenes_en_taller=db.query(Orden).filter(Orden.estado_orden.in_(["Pendiente", "En Taller", "Entregado Parcial"])).count(),
        ordenes_entregadas=db.query(Orden).filter(Orden.estado_orden == "Entregado Total").count(),
        motores_en_taller=db.query(MotorDetalle).filter(MotorDetalle.estado_motor == "En Taller").count(),
        motores_entregados=db.query(MotorDetalle).filter(MotorDetalle.estado_motor == "Entregado").count(),
        certificados_emitidos=db.query(CertificadoCalidad).count(),
    )


@api.get("/motors/{motor_id}")
def ver_motor(motor_id: int, db: Session = Depends(get_db)):
    motor = db.query(MotorDetalle).filter(MotorDetalle.id == motor_id).first()
    if not motor:
        raise HTTPException(status_code=404, detail="Motor no encontrado")
    return {
        "id": motor.id,
        "orden_id": motor.orden_id,
        "numero_orden": motor.orden.numero_orden if motor.orden else "",
        "company_name": motor.orden.company_name if motor.orden else "",
        "make": motor.make,
        "model": motor.model,
        "serial_number": motor.serial_number,
        "estado_motor": motor.estado_motor,
        "foto_ingreso_url": url_de(motor.foto_ingreso_url),
        "foto_salida_url": url_de(motor.foto_salida_url),
        "observaciones": motor.observaciones,
        "date_in": motor.orden.date_in if motor.orden else None,
        "date_out": motor.orden.date_out if motor.orden else None,
        "certificados": [
            {
                "id": c.id,
                "test_certificate_no": c.test_certificate_no,
                "test_date": c.test_date,
                "next_service": c.next_service,
                "pdf_certificado_url": url_de(c.pdf_certificado_url),
                "certified_by": c.certified_by,
            }
            for c in motor.certificados
        ],
    }


router.include_router(api)
