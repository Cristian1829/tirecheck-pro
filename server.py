import io
import os
import socket
import tempfile
import time
import base64
import json
import hmac
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

try:
    BOGOTA_TZ = ZoneInfo("America/Bogota")
except Exception:
    from datetime import timezone, timedelta
    BOGOTA_TZ = timezone(timedelta(hours=-5))

def ahora_bogota():
    return datetime.now(BOGOTA_TZ)

import pandas as pd
from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import pdf_generator

app = FastAPI(title="TireAnalyze Pro - Sistema Integral Web & Móvil")

# Montar directorio de recursos estáticos (imágenes HD, CSS, logos)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================================
# MODELOS PYDANTIC
# ==========================================

class LoginItem(BaseModel):
    username: str
    password: str

class UsuarioItem(BaseModel):
    username: str
    password: str
    nombre_completo: str
    rol: str = "inspector"
    cliente_asignado: str = ""

class EditarUsuarioItem(BaseModel):
    nombre_completo: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    cliente_asignado: Optional[str] = None
    activo: Optional[bool] = None

class ResetPasswordItem(BaseModel):
    nueva_password: str

class InspeccionItem(BaseModel):
    fecha: str = ""
    cliente: str = ""
    subcliente: str = ""
    tipo_operacion: str = ""
    placa: str
    posicion: int
    kilometraje: float = 0.0
    tipologia: str = "Cabezote"
    marca: str = ""
    diseno: str = ""
    dimension: str = "295/80R22.5"
    vida: str = "Original"
    banda_reen: str = ""
    prof_ext: float = 0.0
    prof_cent: float = 0.0
    prof_int: float = 0.0
    psi: float = 100.0
    novedades: str = ""
    precio: float = 0.0
    prof_inicial: float = 0.0
    km_montaje: float = 0.0
    numero_interno: str = ""
    usuario_registro: str = ""
    foto_novedad: str = ""

class NuevaOperacionItem(BaseModel):
    nombre: str

class EditarOperacionItem(BaseModel):
    nombre_antiguo: str
    nombre_nuevo: str

class NuevaTipologiaItem(BaseModel):
    nombre: str
    descripcion: str = ""
    cant_llantas: int = 10

class EditarTipologiaItem(BaseModel):
    nombre_antiguo: str
    nombre_nuevo: str
    descripcion: str = ""
    cant_llantas: int = 10

class ModeloLlantaItem(BaseModel):
    tipo_llanta: str = "Nueva"
    marca: str
    diseno: str
    dimension: str
    prof_inicial: float
    descripcion: str = ""

class LimiteClienteItem(BaseModel):
    cliente: str
    limite_retiro_mm: float = 3.0
    observaciones: str = ""

# ==========================================
# SEGURIDAD Y TOKENS STATELESS (HMAC-SHA256)
# ==========================================

SECRET_KEY = os.environ.get("TIREANALYZE_SECRET_KEY", os.environ.get("TIRECHECK_SECRET_KEY", "tireanalyze-pro-super-secret-key-2026-production"))
TOKEN_EXPIRATION_SECONDS = 43200  # 12 horas

def crear_token_acceso(username: str, rol: str) -> str:
    payload = {
        "sub": username,
        "rol": rol,
        "exp": int(time.time()) + TOKEN_EXPIRATION_SECONDS
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verificar_token(token: str) -> Optional[dict]:
    if not token or not isinstance(token, str):
        return None
    parts = token.strip().split('.')
    if len(parts) != 2:
        return None
    payload_b64, signature = parts
    expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        padding = '=' * ((4 - len(payload_b64) % 4) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes.decode('utf-8'))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

def obtener_usuario_actual(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "tireanalyze_token" in request.cookies:
        token = request.cookies.get("tireanalyze_token")
    elif "tirecheck_token" in request.cookies:
        token = request.cookies.get("tirecheck_token")
    elif "token" in request.query_params:
        token = request.query_params.get("token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    
    payload = verificar_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada")
    
    usr = database.obtener_usuario_por_username(payload["sub"])
    if not usr or not usr.get("activo"):
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    
    return usr

def requerir_admin(usuario_actual: dict = Depends(obtener_usuario_actual)) -> dict:
    if usuario_actual.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Se requieren permisos de administrador")
    return usuario_actual

# ==========================================
# RUTAS PRINCIPALES Y SERVIDOR
# ==========================================

@app.get("/", response_class=HTMLResponse)
def index(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/preview-chasis", response_class=HTMLResponse)
def preview_chasis():
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "preview_chasis.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/servidor/info")
def api_info_servidor():
    return {
        "app": "TireAnalyze Pro",
        "status": "online",
        "version": "2.0"
    }

# ==========================================
# RUTAS DE INSPECCIONES (CRUD & EXCEL)
# ==========================================

@app.get("/api/inspecciones")
def api_obtener_inspecciones(usuario: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin":
        filtro_u = usuario_actual["username"]
    else:
        filtro_u = usuario if usuario else None
    df = database.obtener_todas_inspecciones(usuario=filtro_u)
    return df.to_dict(orient="records")

@app.get("/api/inspecciones/plantilla-excel")
def api_descargar_plantilla_excel(usuario_actual: dict = Depends(obtener_usuario_actual)):
    _p_data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "plantillas", "Plantilla_Cargue_Masivo_Inspecciones.xlsx")
    _p_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Plantilla_Cargue_Masivo_Inspecciones.xlsx")
    plantilla_path = _p_data if os.path.exists(_p_data) else _p_root
    if os.path.exists(plantilla_path):
        with open(plantilla_path, "rb") as f:
            data = f.read()
    else:
        columnas = [
            'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'numero_interno',
            'posicion', 'kilometraje', 'tipologia', 'marca', 'diseno', 'dimension',
            'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int', 'psi',
            'novedades', 'precio', 'prof_inicial', 'km_montaje'
        ]
        datos_guia = [{
            'fecha': ahora_bogota().strftime('%Y-%m-%d'),
            'cliente': 'Axxom', 'subcliente': 'Principal', 'tipo_operacion': 'Carga Seca',
            'placa': 'ABC123', 'numero_interno': 'LL-001', 'posicion': 1, 'kilometraje': 120500,
            'tipologia': 'Cabezote (6x4)', 'marca': 'Michelin', 'diseno': 'X Multi Z',
            'dimension': '295/80R22.5', 'vida': 'Original', 'banda_reen': '',
            'prof_ext': 14.5, 'prof_cent': 14.2, 'prof_int': 14.4, 'psi': 110,
            'novedades': 'Buen estado', 'precio': 1650000, 'prof_inicial': 16.5, 'km_montaje': 80000
        }]
        df = pd.DataFrame(datos_guia, columns=columnas)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, sheet_name='Plantilla_Inspecciones')
        data = buf.getvalue()

    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Plantilla_Cargue_Masivo_Inspecciones.xlsx"}
    )

@app.get("/api/inspecciones/exportar-excel")
def api_exportar_inspecciones_excel(usuario: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin":
        filtro_u = usuario_actual["username"]
    else:
        filtro_u = usuario if usuario else None
    df = database.obtener_todas_inspecciones(usuario=filtro_u)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Inspecciones", index=False)
    f_str = ahora_bogota().strftime("%Y%m%d_%H%M")
    filename = f"Base_Inspecciones_{f_str}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/inspecciones/importar-excel")
async def api_importar_excel(file: UploadFile = File(...), usuario_actual: dict = Depends(obtener_usuario_actual)):
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Formato no soportado. El archivo debe ser Excel (.xlsx o .xls)")

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cant = database.cargar_excel_a_bd(tmp_path)
        return {"status": "ok", "registros_importados": cant, "message": f"Se importaron exitosamente {cant} registros a la base de datos."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar el archivo Excel: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@app.get("/api/inspecciones/{inspeccion_id}")
def api_obtener_inspeccion_por_id(inspeccion_id: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, fecha, cliente, subcliente, tipo_operacion, placa, posicion, kilometraje,
                   tipologia, marca, diseno, dimension, vida, banda_reen, prof_ext, prof_cent, prof_int,
                   psi, novedades, precio, prof_inicial, km_montaje, numero_interno, usuario_registro, foto_novedad
            FROM inspecciones WHERE id = ?
        """, (inspeccion_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Inspección no encontrada")
        
        # Validar permisos de inspector
        if usuario_actual.get("rol") != "admin":
            cli_asig = usuario_actual.get("cliente_asignado", "").strip()
            if cli_asig and row[2] and row[2].strip().lower() != cli_asig.lower():
                raise HTTPException(status_code=403, detail="No tiene permisos para ver inspecciones de este cliente")
        
        cols = ['id', 'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'posicion', 'kilometraje',
                'tipologia', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int',
                'psi', 'novedades', 'precio', 'prof_inicial', 'km_montaje', 'numero_interno', 'usuario_registro', 'foto_novedad']
        return dict(zip(cols, row))

@app.post("/api/inspecciones")
def api_guardar_inspeccion(item: InspeccionItem, usuario_actual: dict = Depends(obtener_usuario_actual)):
    datos = item.model_dump()
    if not datos.get("fecha"):
        datos["fecha"] = ahora_bogota().strftime("%Y-%m-%d")

    # Aislamiento por rol
    if usuario_actual.get("rol") != "admin":
        datos["usuario_registro"] = usuario_actual["username"]
        if usuario_actual.get("cliente_asignado"):
            datos["cliente"] = usuario_actual["cliente_asignado"]

    # Validación de Candados de Seguridad
    val = database.validar_inspeccion_candados(datos)
    if not val.get('valido', True):
        raise HTTPException(status_code=400, detail=val.get('mensaje', 'Violación de regla de seguridad'))

    reg_id = database.insertar_inspeccion(datos)
    return {"status": "ok", "id": reg_id, "message": "Inspección guardada correctamente"}

@app.put("/api/inspecciones/{inspeccion_id}")
def api_actualizar_inspeccion(inspeccion_id: int, item: InspeccionItem, usuario_actual: dict = Depends(obtener_usuario_actual)):
    datos = item.model_dump()
    
    # Validar permisos de inspector
    if usuario_actual.get("rol") != "admin":
        with database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cliente, usuario_registro FROM inspecciones WHERE id = ?", (inspeccion_id,))
            row_exist = cursor.fetchone()
            if not row_exist:
                raise HTTPException(status_code=404, detail="No se encontró el registro para actualizar")
            cli_asig = usuario_actual.get("cliente_asignado", "").strip()
            if cli_asig and row_exist[0] and row_exist[0].strip().lower() != cli_asig.lower():
                raise HTTPException(status_code=403, detail="No tiene permisos para modificar inspecciones de este cliente")
        datos["usuario_registro"] = usuario_actual["username"]
        if cli_asig:
            datos["cliente"] = cli_asig

    val = database.validar_inspeccion_candados(datos, excluir_id=inspeccion_id)
    if not val.get('valido', True):
        raise HTTPException(status_code=400, detail=val.get('mensaje', 'Violación de regla de seguridad'))

    ok = database.actualizar_inspeccion(inspeccion_id, datos)
    if not ok:
        raise HTTPException(status_code=404, detail="No se encontró el registro para actualizar")
    return {"status": "ok", "id": inspeccion_id, "message": "Inspección actualizada correctamente"}

@app.delete("/api/inspecciones/{inspeccion_id}")
def api_eliminar_inspeccion(inspeccion_id: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin":
        with database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cliente, usuario_registro FROM inspecciones WHERE id = ?", (inspeccion_id,))
            row_exist = cursor.fetchone()
            if not row_exist:
                raise HTTPException(status_code=404, detail="Inspección no encontrada")
            cli_asig = usuario_actual.get("cliente_asignado", "").strip()
            if cli_asig and row_exist[0] and row_exist[0].strip().lower() != cli_asig.lower():
                raise HTTPException(status_code=403, detail="No tiene permisos para eliminar inspecciones de este cliente")

    database.eliminar_inspeccion(inspeccion_id)
    return {"status": "ok", "id": inspeccion_id, "message": "Inspección eliminada correctamente"}

def sanitizar_nativos(obj):
    if isinstance(obj, list):
        return [sanitizar_nativos(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: sanitizar_nativos(v) for k, v in obj.items()}
    elif hasattr(obj, "item"):
        return obj.item()
    elif pd.isna(obj):
        return None
    return obj

# ==========================================
# RUTAS DE DIAGNÓSTICO Y PLANES DE ACCIÓN
# ==========================================

@app.get("/api/diagnostico")
def api_diagnostico(usuario: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin":
        filtro_u = usuario_actual["username"]
    else:
        filtro_u = usuario if usuario else None
    df = database.obtener_todas_inspecciones(usuario=filtro_u)
    analisis = database.analizar_inspecciones_df(df)
    return sanitizar_nativos(analisis.to_dict(orient="records"))

@app.get("/api/diagnostico/exportar-excel")
def api_exportar_diagnostico_excel(usuario: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin":
        filtro_u = usuario_actual["username"]
    else:
        filtro_u = usuario if usuario else None
    df_insp = database.obtener_todas_inspecciones(usuario=filtro_u)
    df_analisis = database.analizar_inspecciones_df(df_insp)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_analisis.to_excel(writer, sheet_name="Planes_Accion", index=False)
        if not df_insp.empty:
            df_insp.to_excel(writer, sheet_name="Detalle_Inspecciones", index=False)
    f_str = ahora_bogota().strftime("%Y%m%d_%H%M")
    filename = f"Diagnostico_Flota_{f_str}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==========================================
# RUTAS DE TRAZABILIDAD Y KPIS DE LLANTAS
# ==========================================

@app.get("/api/kpis-llantas")
def api_kpis_llantas(
    numero_interno: str = "",
    cliente: str = "",
    subcliente: str = "",
    tipo_operacion: str = "",
    marca: str = "",
    diseno: str = "",
    dimension: str = "",
    vida: str = "",
    banda_reen: str = "",
    usuario: str = "",
    usuario_actual: dict = Depends(obtener_usuario_actual)
):
    filtros = {
        'cliente': cliente,
        'subcliente': subcliente,
        'tipo_operacion': tipo_operacion,
        'marca': marca,
        'diseno': diseno,
        'dimension': dimension,
        'vida': vida,
        'banda_reen': banda_reen,
        'usuario': usuario
    }
    if usuario_actual.get("rol") != "admin":
        filtros['usuario'] = usuario_actual["username"]
        if usuario_actual.get("cliente_asignado"):
            filtros['cliente'] = usuario_actual["cliente_asignado"]

    raw = database.obtener_trazabilidad_kpis_llanta(numero_interno, filtros)
    return sanitizar_nativos(raw)

@app.get("/api/kpis-llantas/exportar-excel")
def api_exportar_kpis_excel(
    numero_interno: str = "",
    cliente: str = "",
    subcliente: str = "",
    tipo_operacion: str = "",
    marca: str = "",
    diseno: str = "",
    dimension: str = "",
    vida: str = "",
    banda_reen: str = "",
    usuario: str = "",
    usuario_actual: dict = Depends(obtener_usuario_actual)
):
    filtros = {
        'cliente': cliente,
        'subcliente': subcliente,
        'tipo_operacion': tipo_operacion,
        'marca': marca,
        'diseno': diseno,
        'dimension': dimension,
        'vida': vida,
        'banda_reen': banda_reen,
        'usuario': usuario
    }
    if usuario_actual.get("rol") != "admin":
        filtros['usuario'] = usuario_actual["username"]
        if usuario_actual.get("cliente_asignado"):
            filtros['cliente'] = usuario_actual["cliente_asignado"]

    data = database.obtener_trazabilidad_kpis_llanta(numero_interno, filtros)
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Trazabilidad_KPIs", index=False)
    f_str = ahora_bogota().strftime("%Y%m%d_%H%M")
    filename = f"KPIs_Llantas_TireAnalyze_{f_str}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==========================================
# RUTAS DE REPORTES PDF
# ==========================================

@app.get("/api/informe-pdf/{placa}")
def api_descargar_pdf_plan_mantenimiento(placa: str, fecha: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    try:
        pdf_bytes = pdf_generator.generar_pdf_plan_mantenimiento(placa, fecha if fecha else None)
        filename = f"Plan_Mantenimiento_{placa}_{ahora_bogota().strftime('%Y%m%d')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/informe-pdf-consolidado")
def api_descargar_pdf_consolidado(cliente: str = "", subcliente: str = "", fecha: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin" and usuario_actual.get("cliente_asignado"):
        cliente = usuario_actual["cliente_asignado"]
    try:
        pdf_bytes = pdf_generator.generar_pdf_consolidado_jornada(cliente, subcliente, fecha if fecha else None)
        c_tag = cliente.replace(" ", "_") if cliente else "General"
        filename = f"Consolidado_Flota_{c_tag}_{ahora_bogota().strftime('%Y%m%d')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# ==========================================
# RUTAS DE CATÁLOGOS Y CONFIGURACIONES
# ==========================================

@app.get("/api/posiciones")
def api_posiciones(tipologia: str, usuario_actual: dict = Depends(obtener_usuario_actual)):
    posiciones = database.obtener_posiciones_por_tipologia(tipologia)
    return {"tipologia": tipologia, "posiciones": posiciones}

@app.get("/api/operaciones")
def api_obtener_operaciones(usuario_actual: dict = Depends(obtener_usuario_actual)):
    return database.obtener_todas_operaciones()

@app.post("/api/operaciones")
def api_crear_operacion(item: NuevaOperacionItem, admin: dict = Depends(requerir_admin)):
    nom = database.guardar_operacion(item.nombre)
    return {"status": "ok", "nombre": nom}

@app.put("/api/operaciones")
def api_editar_operacion(item: EditarOperacionItem, admin: dict = Depends(requerir_admin)):
    ok = database.actualizar_operacion(item.nombre_antiguo, item.nombre_nuevo)
    return {"status": "ok" if ok else "error"}

@app.delete("/api/operaciones")
def api_eliminar_operacion(nombre: str, admin: dict = Depends(requerir_admin)):
    ok = database.eliminar_operacion(nombre)
    return {"status": "ok" if ok else "error"}

@app.get("/api/tipologias")
def api_obtener_tipologias(usuario_actual: dict = Depends(obtener_usuario_actual)):
    return database.obtener_todas_tipologias()

@app.post("/api/tipologias")
def api_crear_tipologia(item: NuevaTipologiaItem, admin: dict = Depends(requerir_admin)):
    nom = database.guardar_tipologia(item.nombre, item.descripcion, item.cant_llantas)
    return {"status": "ok", "nombre": nom}

@app.put("/api/tipologias")
def api_editar_tipologia(item: EditarTipologiaItem, admin: dict = Depends(requerir_admin)):
    ok = database.actualizar_tipologia(item.nombre_antiguo, item.nombre_nuevo, item.descripcion, item.cant_llantas)
    return {"status": "ok" if ok else "error"}

@app.delete("/api/tipologias")
def api_eliminar_tipologia(nombre: str, admin: dict = Depends(requerir_admin)):
    ok = database.eliminar_tipologia(nombre)
    return {"status": "ok" if ok else "error"}

@app.get("/api/esquema")
def api_esquema(tipologia: str, usuario_actual: dict = Depends(obtener_usuario_actual)):
    esquema = database.obtener_esquema_tipologia(tipologia)
    posiciones = database.obtener_posiciones_por_tipologia(tipologia)
    return {"tipologia": tipologia, "esquema": esquema, "posiciones": posiciones}

@app.get("/api/modelos-llanta")
def api_modelos_llanta(usuario_actual: dict = Depends(obtener_usuario_actual)):
    return database.obtener_catalogo_modelos()

@app.post("/api/modelos-llanta")
def api_guardar_modelo(item: ModeloLlantaItem, admin: dict = Depends(requerir_admin)):
    ok = database.guardar_modelo_llanta(item.tipo_llanta, item.marca, item.diseno, item.dimension, item.prof_inicial, item.descripcion)
    return {"status": "ok" if ok else "error"}

@app.get("/api/profundidad-inicial")
def api_buscar_profundidad(marca: str = "", diseno: str = "", dimension: str = "", vida: str = "Original", usuario_actual: dict = Depends(obtener_usuario_actual)):
    prof = database.buscar_profundidad_inicial(marca, diseno, dimension, vida)
    return {"prof_inicial": prof}

@app.get("/api/buscar-modelos")
def api_buscar_modelos(query: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    return database.buscar_modelos_llantas_filtro(query)

@app.get("/api/configuraciones-clientes")
def api_obtener_configuraciones_clientes(usuario_actual: dict = Depends(obtener_usuario_actual)):
    return database.obtener_todas_configuraciones_clientes()

@app.get("/api/limite-cliente")
def api_obtener_limite_cliente(cliente: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    lim = database.obtener_limite_retiro_cliente(cliente)
    return {"cliente": cliente, "limite_retiro_mm": lim}

@app.post("/api/configuraciones-clientes")
def api_guardar_configuracion_cliente(item: LimiteClienteItem, admin: dict = Depends(requerir_admin)):
    ok = database.guardar_limite_retiro_cliente(item.cliente, item.limite_retiro_mm, item.observaciones)
    return {"status": "ok" if ok else "error"}

@app.get("/api/valores-campo")
def api_valores_campo(campo: str, cliente: str = "", usuario: str = "", marca: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    if usuario_actual.get("rol") != "admin" and usuario_actual.get("cliente_asignado"):
        cliente = usuario_actual["cliente_asignado"]
    elif usuario and not cliente:
        usr_info = database.obtener_usuario_por_username(usuario)
        if usr_info and usr_info.get("rol") != "admin" and usr_info.get("cliente_asignado"):
            cliente = usr_info.get("cliente_asignado")
    return database.obtener_valores_unicos_campo(campo, cliente, filtro_marca=marca)

@app.get("/api/inspeccion-anterior")
def api_inspeccion_anterior(placa: str, posicion: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    prev = database.obtener_ultima_inspeccion_posicion(placa, posicion)
    return {"encontrado": True, "datos": prev} if prev else {"encontrado": False}

@app.get("/api/posiciones-inspeccionadas")
def api_posiciones_inspeccionadas(placa: str, fecha: str = "", usuario_actual: dict = Depends(obtener_usuario_actual)):
    det = database.obtener_posiciones_inspeccionadas_detalle(placa, fecha)
    return {
        "placa": placa,
        "posiciones": det["posiciones"],
        "posiciones_con_novedad": det["posiciones_con_novedad"],
        "novedades": det["novedades"]
    }

# ==========================================
# RUTAS DE AUTENTICACIÓN Y USUARIOS
# ==========================================

@app.post("/api/login")
def api_login(item: LoginItem, response: Response):
    usr = database.autenticar_usuario(item.username, item.password)
    if not usr:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = crear_token_acceso(usr["username"], usr["rol"])
    response.set_cookie(
        key="tireanalyze_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=TOKEN_EXPIRATION_SECONDS
    )
    response.set_cookie(
        key="tirecheck_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=TOKEN_EXPIRATION_SECONDS
    )
    return {"status": "ok", "token": token, "usuario": usr}

@app.post("/api/logout")
def api_logout(response: Response):
    response.delete_cookie(key="tireanalyze_token")
    response.delete_cookie(key="tirecheck_token")
    return {"status": "ok", "mensaje": "Sesión cerrada correctamente"}

@app.get("/api/usuarios")
def api_listar_usuarios(admin: dict = Depends(requerir_admin)):
    return database.listar_usuarios()

@app.post("/api/usuarios")
def api_crear_usuario(item: UsuarioItem, admin: dict = Depends(requerir_admin)):
    ok = database.crear_usuario(item.username, item.password, item.nombre_completo, item.rol, item.cliente_asignado)
    if not ok:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe o los datos son inválidos (contraseña mínima 4 caracteres)")
    return {"status": "ok", "username": item.username}

@app.put("/api/usuarios/{username}")
def api_actualizar_usuario(username: str, item: EditarUsuarioItem, admin: dict = Depends(requerir_admin)):
    if username.lower() == "admin":
        if item.activo is False:
            raise HTTPException(status_code=400, detail="No se puede desactivar al usuario administrador principal")
        if item.rol and item.rol.lower() != "admin":
            raise HTTPException(status_code=400, detail="No se puede degradar el rol del usuario administrador principal")
    ok = database.actualizar_usuario(
        username=username,
        nombre_completo=item.nombre_completo,
        password=item.password,
        rol=item.rol,
        cliente_asignado=item.cliente_asignado,
        activo=item.activo
    )
    if not ok:
        raise HTTPException(status_code=400, detail="No se pudo actualizar el usuario")
    return {"status": "ok", "username": username}

@app.post("/api/usuarios/{username}/reset-password")
def api_reset_password(username: str, item: ResetPasswordItem, admin: dict = Depends(requerir_admin)):
    if not item.nueva_password or len(item.nueva_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 4 caracteres")
    usr_existente = database.obtener_usuario_por_username(username)
    if not usr_existente:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    ok = database.restablecer_password_usuario(username, item.nueva_password)
    if not ok:
        raise HTTPException(status_code=400, detail="No se pudo restablecer la contraseña")
    return {"status": "ok", "message": f"Contraseña del usuario {username} restablecida correctamente"}

@app.delete("/api/usuarios/{username}")
def api_eliminar_usuario(username: str, admin: dict = Depends(requerir_admin)):
    if username.lower() == "admin":
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario administrador principal")
    ok = database.eliminar_usuario(username)
    if not ok:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"status": "ok", "username": username}

# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == "__main__":
    import uvicorn
    raw_port = os.environ.get("PORT", "8000")
    try:
        puerto = int(raw_port)
    except (ValueError, TypeError):
        puerto = 8000
    uvicorn.run("server:app", host="0.0.0.0", port=puerto, reload=False)
