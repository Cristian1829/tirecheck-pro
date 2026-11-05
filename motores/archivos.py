"""
Fotos, firmas y PDF de Motores. Viven fuera de /static y solo se entregan con sesión iniciada.

Del navegador solo se acepta una imagen en data URL: se valida y se vuelve a codificar. Nunca una ruta de archivo.
"""
import base64
import binascii
import io
import os
import re
import uuid

from PIL import Image, UnidentifiedImageError

from motores.base import dir_archivos

MAX_BYTES_IMAGEN = 8 * 1024 * 1024
MAX_PIXELES = 40_000_000
LADO_MAXIMO = 1600
_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg|webp);base64,", re.I)
_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,150}$")
TIPOS = {".jpg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}


class ImagenInvalida(ValueError):
    pass


def nombre_seguro(texto) -> str:
    """Parte de un nombre de archivo a partir de un texto del usuario (sin rutas ni caracteres raros)."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(texto or "")).strip("_")[:80] or "documento"


def guardar_imagen(data_url, prefijo: str, firma: bool = False):
    """Guarda la imagen y devuelve el nombre del archivo. None si no viene imagen; ImagenInvalida si no sirve."""
    if not data_url:
        return None
    m = _DATA_URL.match(str(data_url))
    if not m:
        raise ImagenInvalida("El archivo enviado no es una imagen PNG, JPG o WEBP.")
    try:
        crudo = base64.b64decode(str(data_url)[m.end():], validate=True)
    except (binascii.Error, ValueError):
        raise ImagenInvalida("La imagen enviada está dañada.")
    if len(crudo) > MAX_BYTES_IMAGEN:
        raise ImagenInvalida("La imagen supera el tamaño máximo de 8 MB.")
    try:
        with Image.open(io.BytesIO(crudo)) as img:
            if img.width * img.height > MAX_PIXELES:
                raise ImagenInvalida("La imagen tiene demasiados píxeles.")
            img.load()
            img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            # Volver a codificarla elimina metadatos (como la ubicación GPS de la foto) y cualquier contenido oculto
            if firma:
                nombre = f"{nombre_seguro(prefijo)}_{uuid.uuid4().hex[:12]}.png"
                img.convert("RGBA").save(os.path.join(dir_archivos(), nombre), "PNG")
            else:
                nombre = f"{nombre_seguro(prefijo)}_{uuid.uuid4().hex[:12]}.jpg"
                img.convert("RGB").save(os.path.join(dir_archivos(), nombre), "JPEG", quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ImagenInvalida("El archivo enviado no es una imagen válida.")
    return nombre


def ruta_archivo(nombre):
    """Ruta en disco de un archivo propio, o None si el nombre no es válido o el archivo no existe."""
    if not nombre or not _NOMBRE_VALIDO.match(str(nombre)):
        return None
    ruta = os.path.join(dir_archivos(), str(nombre))
    return ruta if os.path.isfile(ruta) else None


def url_de(nombre):
    """URL (con sesión) de un archivo guardado."""
    return f"/api/motores/archivos/{nombre}" if nombre else None
