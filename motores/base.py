"""Conexión a la base de datos propia de Motores y ubicación de sus archivos (en el volumen, nunca en /static)."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONA_TALLER = ZoneInfo(os.environ.get("MOTORES_TZ") or "America/New_York")  # el taller está en Brentwood, NY

Base = declarative_base()

_dir_datos = None
_engine = None
_Sesion = None


def ahora() -> datetime:
    """Hora del taller, sin zona (así se guarda y se imprime en los PDF)."""
    return datetime.now(ZONA_TALLER).replace(tzinfo=None)


def dir_datos() -> str:
    return _dir_datos


def dir_archivos() -> str:
    return os.path.join(_dir_datos, "archivos")


def dir_assets() -> str:
    """Logos, firma y sello opcionales. Si no están, los PDF salen con texto."""
    return os.path.join(_dir_datos, "assets")


def configurar(directorio: str = None) -> None:
    """Abre la base de datos en el directorio indicado y crea lo que falte."""
    global _dir_datos, _engine, _Sesion
    import motores.modelos  # noqa: F401  (registra las tablas)

    _dir_datos = directorio or os.environ.get("MOTORES_DATA_DIR") or os.path.join(_RAIZ, "data", "motores")
    os.makedirs(dir_archivos(), exist_ok=True)
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        "sqlite:///" + os.path.join(_dir_datos, "motores_control.db"),
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    _Sesion = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    Base.metadata.create_all(bind=_engine)


def nueva_sesion():
    return _Sesion()


def get_db():
    db = _Sesion()
    try:
        yield db
    finally:
        db.close()
