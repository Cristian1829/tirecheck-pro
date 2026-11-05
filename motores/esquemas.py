"""Validación de lo que entra y sale de la API de Motores (documento, sección 4)."""
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from motores.archivos import url_de

Corto = Annotated[str, Field(max_length=200)]
Largo = Annotated[str, Field(max_length=2000)]
DataUrl = Annotated[str, Field(max_length=12_000_000)]


def _sin_zona(valor: Optional[datetime]) -> Optional[datetime]:
    """El navegador envía la hora local del taller; si llegara con zona, se conserva la hora escrita."""
    return valor.replace(tzinfo=None) if valor else valor


def _url(valor):
    return url_de(valor)


# ================= ACCESO =================
class LoginEntrada(BaseModel):
    username: Annotated[str, Field(max_length=200)]
    password: Annotated[str, Field(max_length=200)]


class CambioClaveEntrada(BaseModel):
    clave_actual: Annotated[str, Field(max_length=200)]
    clave_nueva: Annotated[str, Field(max_length=200)]


class UsuarioCrear(BaseModel):
    username: Annotated[str, Field(max_length=40)]
    nombre: Optional[Corto] = None
    rol: str = "tecnico"
    clave_nueva: Annotated[str, Field(max_length=200)]


class UsuarioEditar(BaseModel):
    nombre: Optional[Corto] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None
    clave_nueva: Optional[Annotated[str, Field(max_length=200)]] = None


class UsuarioRespuesta(BaseModel):
    id: int
    username: str
    nombre: Optional[str] = None
    rol: str
    activo: bool
    debe_cambiar_clave: bool
    model_config = ConfigDict(from_attributes=True)


# ================= CLIENTES =================
class ClienteBase(BaseModel):
    company_name: Corto
    contacto_principal: Optional[Corto] = None
    email: Optional[Corto] = None
    phone: Optional[Corto] = None
    address: Optional[Corto] = None


class ClienteCreate(ClienteBase):
    id: Optional[Annotated[str, Field(max_length=50)]] = None  # Si es null, el backend genera uno


class ClienteUpdate(BaseModel):
    company_name: Optional[Corto] = None
    contacto_principal: Optional[Corto] = None
    email: Optional[Corto] = None
    phone: Optional[Corto] = None
    address: Optional[Corto] = None


class ClienteResponse(ClienteBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ================= MOTORES =================
class MotorBase(BaseModel):
    make: Annotated[str, Field(max_length=100)]
    model: Annotated[str, Field(max_length=100)]
    serial_number: Annotated[str, Field(max_length=100)]
    observaciones: Optional[Largo] = None


class MotorCreate(MotorBase):
    foto_ingreso_url: Optional[DataUrl] = None


class MotorResponse(MotorBase):
    id: int
    orden_id: int
    estado_motor: str
    foto_ingreso_url: Optional[str] = None
    foto_salida_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    _urls = field_validator("foto_ingreso_url", "foto_salida_url", mode="before")(_url)


# ================= ORDENES =================
class OrdenCreate(BaseModel):
    numero_orden: Optional[Annotated[str, Field(max_length=50)]] = None
    company_name: Corto
    date_in: Optional[datetime] = None
    dropoff_name: Optional[Corto] = "Customer"
    firma_dropoff: Optional[DataUrl] = None
    received_name: Optional[Corto] = "Marino Trejos"
    firma_received: Optional[DataUrl] = None
    notas: Optional[Largo] = None
    motores: Annotated[List[MotorCreate], Field(max_length=30)]

    _fecha = field_validator("date_in")(_sin_zona)


class OrdenResponse(BaseModel):
    id: int
    numero_orden: str
    company_name: str
    date_in: datetime
    date_out: Optional[datetime] = None
    estado_orden: str
    dropoff_name: Optional[str] = None
    firma_dropoff: Optional[str] = None
    received_name: Optional[str] = None
    firma_received: Optional[str] = None
    pdf_ingreso_url: Optional[str] = None
    notas: Optional[str] = None
    created_at: datetime
    motores: List[MotorResponse] = []
    model_config = ConfigDict(from_attributes=True)

    _urls = field_validator("firma_dropoff", "firma_received", "pdf_ingreso_url", mode="before")(_url)


# ================= ENTREGAS / SALIDAS =================
class EntregaItemCreate(BaseModel):
    motor_id: int
    foto_salida_url: Optional[DataUrl] = None


class EntregaItemResponse(BaseModel):
    id: int
    motor_id: int
    foto_salida_url: Optional[str] = None
    motor: Optional[MotorResponse] = None
    model_config = ConfigDict(from_attributes=True)

    _urls = field_validator("foto_salida_url", mode="before")(_url)


class EntregaSalidaCreate(BaseModel):
    orden_id: int
    tipo_entrega: Optional[str] = None  # lo decide el servidor según lo que quede en taller
    fecha_salida: Optional[datetime] = None
    entrega_empresa_name: Optional[Corto] = "Marino Trejos"
    firma_entrega_empresa: Optional[DataUrl] = None
    recibe_cliente_name: Optional[Corto] = "Customer"
    firma_recibe_cliente: Optional[DataUrl] = None
    notas: Optional[Largo] = None
    motores_despacho: Annotated[List[EntregaItemCreate], Field(max_length=30)]

    _fecha = field_validator("fecha_salida")(_sin_zona)


class EntregaSalidaResponse(BaseModel):
    id: int
    orden_id: int
    tipo_entrega: str
    fecha_salida: datetime
    entrega_empresa_name: Optional[str] = None
    firma_entrega_empresa: Optional[str] = None
    recibe_cliente_name: Optional[str] = None
    firma_recibe_cliente: Optional[str] = None
    pdf_salida_url: Optional[str] = None
    notas: Optional[str] = None
    items: List[EntregaItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

    _urls = field_validator("firma_entrega_empresa", "firma_recibe_cliente", "pdf_salida_url", mode="before")(_url)


# ================= CERTIFICADOS DE CALIDAD =================
class CertificadoCalidadCreate(BaseModel):
    motor_id: int
    test_certificate_no: Optional[Annotated[str, Field(max_length=100)]] = None
    test_date: Optional[datetime] = None
    next_service: Optional[datetime] = None
    voltage: Optional[Corto] = "220 / ONE PHASE"

    start_capacitor: Optional[Corto] = "100 uF"
    vr_start: Optional[Corto] = "330 V"
    run_capacitor: Optional[Corto] = "40 uF"
    vr_run: Optional[Corto] = "450 V"
    k1: Optional[Corto] = "1.8"
    k2: Optional[Corto] = "1.8"
    k3: Optional[Corto] = "2.1"

    # Un punto de seguridad que no se envía no está aprobado (en el documento venían en True)
    rectifier: bool = False
    brake_release_lever: bool = False
    brake_function: bool = False
    normal_noise: bool = False
    emergency_pin_descend: bool = False
    brake_disc: bool = False
    stirrup_adapter: bool = False
    rated_load_test: bool = False

    rated_load_capacity: Optional[Corto] = "1000"
    overload_test_pounds: Optional[Corto] = "1250 POUNDS (125%)"
    blocstop_model: Optional[Corto] = "BLOCSTOP BSO 1000"
    blocstop_serial: Optional[Corto] = None
    blocstop_rated_load: Optional[Corto] = "1000 POUNDS"
    blocstop_trigger_speed: Optional[Corto] = "Testing Pass"
    blocstop_load_test: Optional[Corto] = "1000 POUNDS Pass"
    blocstop_control_descent: Optional[Corto] = "Testing Pass"

    service_description: Optional[Largo] = "New warning labels, oil change, oil seal, brake gap adjustment, rated load test."
    certified_by: Optional[Corto] = "Marino Trejos | Cert#061821JV1"

    _fechas = field_validator("test_date", "next_service")(_sin_zona)


class CertificadoCalidadResponse(BaseModel):
    id: int
    motor_id: int
    test_certificate_no: str
    test_date: datetime
    next_service: datetime
    voltage: str

    start_capacitor: Optional[str] = None
    vr_start: Optional[str] = None
    run_capacitor: Optional[str] = None
    vr_run: Optional[str] = None
    k1: Optional[str] = None
    k2: Optional[str] = None
    k3: Optional[str] = None

    rectifier: bool
    brake_release_lever: bool
    brake_function: bool
    normal_noise: bool
    emergency_pin_descend: bool
    brake_disc: bool
    stirrup_adapter: bool
    rated_load_test: bool

    rated_load_capacity: Optional[str] = None
    overload_test_pounds: Optional[str] = None
    blocstop_model: Optional[str] = None
    blocstop_serial: Optional[str] = None
    blocstop_rated_load: Optional[str] = None
    blocstop_trigger_speed: Optional[str] = None
    blocstop_load_test: Optional[str] = None
    blocstop_control_descent: Optional[str] = None

    service_description: Optional[str] = None
    certified_by: str
    pdf_certificado_url: Optional[str] = None
    created_at: datetime
    motor: Optional[MotorResponse] = None
    model_config = ConfigDict(from_attributes=True)

    _urls = field_validator("pdf_certificado_url", mode="before")(_url)


# ================= DASHBOARD STATS =================
class DashboardStats(BaseModel):
    total_ordenes: int
    ordenes_en_taller: int
    ordenes_entregadas: int
    motores_en_taller: int
    motores_entregados: int
    certificados_emitidos: int
