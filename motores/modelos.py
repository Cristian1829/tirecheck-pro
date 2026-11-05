"""Modelo de datos de Motores (documento, sección 3) más las cuentas propias de esta app."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from motores.base import Base, ahora

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(String(50), primary_key=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    contacto_principal = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True)
    phone = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=ahora)


class Orden(Base):
    __tablename__ = "ordenes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero_orden = Column(String(50), unique=True, index=True, nullable=False)
    company_name = Column(String(200), index=True, nullable=False)
    cliente_id = Column(String(50), ForeignKey("clientes.id"), nullable=True)
    date_in = Column(DateTime, default=ahora, nullable=False)
    date_out = Column(DateTime, nullable=True)
    estado_orden = Column(String(50), default="En Taller", nullable=False) 
    # Estados: "Pendiente", "En Taller", "Entregado Parcial", "Entregado Total"
    
    # Firmas y nombres de recepción/ingreso
    dropoff_name = Column(String(150), nullable=True)
    firma_dropoff = Column(Text, nullable=True) # Data URL o ruta de archivo
    received_name = Column(String(150), nullable=True)
    firma_received = Column(Text, nullable=True) # Data URL o ruta de archivo
    
    pdf_ingreso_url = Column(String(255), nullable=True)
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, default=ahora)

    # Relaciones
    motores = relationship("MotorDetalle", back_populates="orden", cascade="all, delete-orphan")
    entregas = relationship("EntregaSalida", back_populates="orden", cascade="all, delete-orphan")


class MotorDetalle(Base):
    __tablename__ = "motores_detalle"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id"), nullable=False)
    make = Column(String(100), nullable=False) # Ej: Tirak, Tractel, Sky Climber
    model = Column(String(100), nullable=False) # Ej: TIRAK LE 501P, XE 500P
    serial_number = Column(String(100), index=True, nullable=False)
    estado_motor = Column(String(50), default="En Taller", nullable=False) # "En Taller", "Entregado"
    
    foto_ingreso_url = Column(Text, nullable=True) # Ruta de imagen obligatoria al ingresar
    foto_salida_url = Column(Text, nullable=True) # Ruta de imagen obligatoria al despachar
    
    observaciones = Column(Text, nullable=True)
    created_at = Column(DateTime, default=ahora)

    # Relaciones
    orden = relationship("Orden", back_populates="motores")
    certificados = relationship("CertificadoCalidad", back_populates="motor", cascade="all, delete-orphan")
    entregas_asociadas = relationship("EntregaItem", back_populates="motor")


class EntregaSalida(Base):
    __tablename__ = "entregas_salida"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id"), nullable=False)
    tipo_entrega = Column(String(50), nullable=False) # "Parcial" o "Total"
    fecha_salida = Column(DateTime, default=ahora, nullable=False)
    
    firma_entrega_empresa = Column(Text, nullable=True)
    entrega_empresa_name = Column(String(150), nullable=True)
    firma_recibe_cliente = Column(Text, nullable=True)
    recibe_cliente_name = Column(String(150), nullable=True)
    
    pdf_salida_url = Column(String(255), nullable=True)
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, default=ahora)

    # Relaciones
    orden = relationship("Orden", back_populates="entregas")
    items = relationship("EntregaItem", back_populates="entrega", cascade="all, delete-orphan")


class EntregaItem(Base):
    __tablename__ = "entrega_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entrega_id = Column(Integer, ForeignKey("entregas_salida.id"), nullable=False)
    motor_id = Column(Integer, ForeignKey("motores_detalle.id"), nullable=False)
    foto_salida_url = Column(Text, nullable=True)

    entrega = relationship("EntregaSalida", back_populates="items")
    motor = relationship("MotorDetalle", back_populates="entregas_asociadas")


class CertificadoCalidad(Base):
    __tablename__ = "certificados_calidad"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    motor_id = Column(Integer, ForeignKey("motores_detalle.id"), nullable=False)
    test_certificate_no = Column(String(100), unique=True, index=True, nullable=False)
    test_date = Column(DateTime, default=ahora, nullable=False)
    next_service = Column(DateTime, nullable=False)
    voltage = Column(String(100), default="220 / ONE PHASE", nullable=False)
    
    # Campos eléctricos
    start_capacitor = Column(String(50), default="100 uF", nullable=True)
    vr_start = Column(String(50), default="330 V", nullable=True)
    run_capacitor = Column(String(50), default="40 uF", nullable=True)
    vr_run = Column(String(50), default="450 V", nullable=True)
    k1 = Column(String(50), default="1.8", nullable=True)
    k2 = Column(String(50), default="1.8", nullable=True)
    k3 = Column(String(50), default="2.1", nullable=True)
    
    # Inspecciones (Checks booleanos)
    rectifier = Column(Boolean, default=False)
    brake_release_lever = Column(Boolean, default=False)
    brake_function = Column(Boolean, default=False)
    normal_noise = Column(Boolean, default=False)
    emergency_pin_descend = Column(Boolean, default=False)
    brake_disc = Column(Boolean, default=False)
    stirrup_adapter = Column(Boolean, default=False)
    rated_load_test = Column(Boolean, default=False)
    
    # Pruebas de carga / Blocstop / Sky-Lock
    rated_load_capacity = Column(String(50), default="1000", nullable=True)
    overload_test_pounds = Column(String(50), default="1250 POUNDS (125%)", nullable=True)
    blocstop_model = Column(String(100), default="BLOCSTOP BSO 1000", nullable=True)
    blocstop_serial = Column(String(100), nullable=True)
    blocstop_rated_load = Column(String(50), default="1000 POUNDS", nullable=True)
    blocstop_trigger_speed = Column(String(50), default="Testing Pass", nullable=True)
    blocstop_load_test = Column(String(50), default="1000 POUNDS Pass", nullable=True)
    blocstop_control_descent = Column(String(50), default="Testing Pass", nullable=True)
    
    # Descripción y firma técnica
    service_description = Column(Text, default="New warning labels, oil change, oil seal, brake gap adjustment, rated load test.", nullable=True)
    certified_by = Column(String(150), default="Marino Trejos | Cert#061821JV1", nullable=False)
    
    pdf_certificado_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=ahora)

    motor = relationship("MotorDetalle", back_populates="certificados")



class Usuario(Base):
    """Cuentas de Motores. Son independientes de los usuarios de TireAnalyze."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(40), unique=True, index=True, nullable=False)
    nombre = Column(String(150), nullable=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), default="tecnico", nullable=False)  # "admin" o "tecnico"
    activo = Column(Boolean, default=True, nullable=False)
    debe_cambiar_clave = Column(Boolean, default=True, nullable=False)
    sesion_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=ahora)


class SesionRevocada(Base):
    __tablename__ = "sesiones_revocadas"

    jti = Column(String(40), primary_key=True)
    exp = Column(Integer, nullable=False)


class IntentoIngreso(Base):
    __tablename__ = "intentos_ingreso"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(200), index=True, nullable=False)
    ip = Column(String(64), nullable=True)
    exito = Column(Boolean, default=False, nullable=False)
    motivo = Column(String(40), nullable=True)
    momento = Column(Integer, index=True, nullable=False)  # segundos desde 1970
