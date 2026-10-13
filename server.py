import io
import os
import socket
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

BOGOTA_TZ = ZoneInfo("America/Bogota")

def ahora_bogota():
    return datetime.now(BOGOTA_TZ)

import pandas as pd
from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import pdf_generator

app = FastAPI(title="TireCheck Pro - Sistema Integral Web & Móvil")

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
# RUTAS PRINCIPALES Y SERVIDOR
# ==========================================

@app.get("/", response_class=HTMLResponse)
def index():
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
        "app": "TireCheck Pro",
        "status": "online",
        "version": "2.0"
    }

# ==========================================
# RUTAS DE INSPECCIONES (CRUD & EXCEL)
# ==========================================

@app.get("/api/inspecciones")
def api_obtener_inspecciones(usuario: str = ""):
    df = database.obtener_todas_inspecciones(usuario=usuario if usuario else None)
    return df.to_dict(orient="records")

@app.get("/api/inspecciones/plantilla-excel")
def api_descargar_plantilla_excel():
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
def api_exportar_inspecciones_excel(usuario: str = ""):
    df = database.obtener_todas_inspecciones(usuario=usuario if usuario else None)
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
async def api_importar_excel(file: UploadFile = File(...)):
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
def api_obtener_inspeccion_por_id(inspeccion_id: int):
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
        cols = ['id', 'fecha', 'cliente', 'subcliente', 'tipo_operacion', 'placa', 'posicion', 'kilometraje',
                'tipologia', 'marca', 'diseno', 'dimension', 'vida', 'banda_reen', 'prof_ext', 'prof_cent', 'prof_int',
                'psi', 'novedades', 'precio', 'prof_inicial', 'km_montaje', 'numero_interno', 'usuario_registro', 'foto_novedad']
        return dict(zip(cols, row))

@app.post("/api/inspecciones")
def api_guardar_inspeccion(item: InspeccionItem):
    datos = item.model_dump()
    if not datos.get("fecha"):
        datos["fecha"] = ahora_bogota().strftime("%Y-%m-%d")

    # Validación de Candados de Seguridad
    val = database.validar_inspeccion_candados(datos)
    if not val.get('valido', True):
        raise HTTPException(status_code=400, detail=val.get('mensaje', 'Violación de regla de seguridad'))

    reg_id = database.insertar_inspeccion(datos)
    return {"status": "ok", "id": reg_id, "message": "Inspección guardada correctamente"}

@app.put("/api/inspecciones/{inspeccion_id}")
def api_actualizar_inspeccion(inspeccion_id: int, item: InspeccionItem):
    datos = item.model_dump()
    val = database.validar_inspeccion_candados(datos, excluir_id=inspeccion_id)
    if not val.get('valido', True):
        raise HTTPException(status_code=400, detail=val.get('mensaje', 'Violación de regla de seguridad'))

    ok = database.actualizar_inspeccion(inspeccion_id, datos)
    if not ok:
        raise HTTPException(status_code=404, detail="No se encontró el registro para actualizar")
    return {"status": "ok", "id": inspeccion_id, "message": "Inspección actualizada correctamente"}

@app.delete("/api/inspecciones/{inspeccion_id}")
def api_eliminar_inspeccion(inspeccion_id: int):
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
def api_diagnostico(usuario: str = ""):
    df = database.obtener_todas_inspecciones(usuario=usuario if usuario else None)
    analisis = database.analizar_inspecciones_df(df)
    return sanitizar_nativos(analisis.to_dict(orient="records"))

@app.get("/api/diagnostico/exportar-excel")
def api_exportar_diagnostico_excel(usuario: str = ""):
    df_insp = database.obtener_todas_inspecciones(usuario=usuario if usuario else None)
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
    usuario: str = ""
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
    usuario: str = ""
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
    data = database.obtener_trazabilidad_kpis_llanta(numero_interno, filtros)
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Trazabilidad_KPIs", index=False)
    f_str = ahora_bogota().strftime("%Y%m%d_%H%M")
    filename = f"KPIs_Llantas_TireCheck_{f_str}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==========================================
# RUTAS DE REPORTES PDF
# ==========================================

@app.get("/api/informe-pdf/{placa}")
def api_descargar_pdf_plan_mantenimiento(placa: str, fecha: str = ""):
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
def api_descargar_pdf_consolidado(cliente: str = "", subcliente: str = "", fecha: str = ""):
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
def api_posiciones(tipologia: str):
    posiciones = database.obtener_posiciones_por_tipologia(tipologia)
    return {"tipologia": tipologia, "posiciones": posiciones}

@app.get("/api/operaciones")
def api_obtener_operaciones():
    return database.obtener_todas_operaciones()

@app.post("/api/operaciones")
def api_crear_operacion(item: NuevaOperacionItem):
    nom = database.guardar_operacion(item.nombre)
    return {"status": "ok", "nombre": nom}

@app.put("/api/operaciones")
def api_editar_operacion(item: EditarOperacionItem):
    ok = database.actualizar_operacion(item.nombre_antiguo, item.nombre_nuevo)
    return {"status": "ok" if ok else "error"}

@app.delete("/api/operaciones")
def api_eliminar_operacion(nombre: str):
    ok = database.eliminar_operacion(nombre)
    return {"status": "ok" if ok else "error"}

@app.get("/api/tipologias")
def api_obtener_tipologias():
    return database.obtener_todas_tipologias()

@app.post("/api/tipologias")
def api_crear_tipologia(item: NuevaTipologiaItem):
    nom = database.guardar_tipologia(item.nombre, item.descripcion, item.cant_llantas)
    return {"status": "ok", "nombre": nom}

@app.put("/api/tipologias")
def api_editar_tipologia(item: EditarTipologiaItem):
    ok = database.actualizar_tipologia(item.nombre_antiguo, item.nombre_nuevo, item.descripcion, item.cant_llantas)
    return {"status": "ok" if ok else "error"}

@app.delete("/api/tipologias")
def api_eliminar_tipologia(nombre: str):
    ok = database.eliminar_tipologia(nombre)
    return {"status": "ok" if ok else "error"}

@app.get("/api/esquema")
def api_esquema(tipologia: str):
    esquema = database.obtener_esquema_tipologia(tipologia)
    posiciones = database.obtener_posiciones_por_tipologia(tipologia)
    return {"tipologia": tipologia, "esquema": esquema, "posiciones": posiciones}

@app.get("/api/modelos-llanta")
def api_modelos_llanta():
    return database.obtener_catalogo_modelos()

@app.post("/api/modelos-llanta")
def api_guardar_modelo(item: ModeloLlantaItem):
    ok = database.guardar_modelo_llanta(item.tipo_llanta, item.marca, item.diseno, item.dimension, item.prof_inicial, item.descripcion)
    return {"status": "ok" if ok else "error"}

@app.get("/api/profundidad-inicial")
def api_buscar_profundidad(marca: str = "", diseno: str = "", dimension: str = "", vida: str = "Original"):
    prof = database.buscar_profundidad_inicial(marca, diseno, dimension, vida)
    return {"prof_inicial": prof}

@app.get("/api/buscar-modelos")
def api_buscar_modelos(query: str = ""):
    return database.buscar_modelos_llantas_filtro(query)

@app.get("/api/configuraciones-clientes")
def api_obtener_configuraciones_clientes():
    return database.obtener_todas_configuraciones_clientes()

@app.get("/api/limite-cliente")
def api_obtener_limite_cliente(cliente: str = ""):
    lim = database.obtener_limite_retiro_cliente(cliente)
    return {"cliente": cliente, "limite_retiro_mm": lim}

@app.post("/api/configuraciones-clientes")
def api_guardar_configuracion_cliente(item: LimiteClienteItem):
    ok = database.guardar_limite_retiro_cliente(item.cliente, item.limite_retiro_mm, item.observaciones)
    return {"status": "ok" if ok else "error"}

@app.get("/api/valores-campo")
def api_valores_campo(campo: str, cliente: str = "", usuario: str = "", marca: str = ""):
    if usuario and not cliente:
        usr_info = database.obtener_usuario_por_username(usuario)
        if usr_info and usr_info.get("rol") != "admin" and usr_info.get("cliente_asignado"):
            cliente = usr_info.get("cliente_asignado")
    return database.obtener_valores_unicos_campo(campo, cliente, filtro_marca=marca)

@app.get("/api/inspeccion-anterior")
def api_inspeccion_anterior(placa: str, posicion: int):
    prev = database.obtener_ultima_inspeccion_posicion(placa, posicion)
    return {"encontrado": True, "datos": prev} if prev else {"encontrado": False}

@app.get("/api/posiciones-inspeccionadas")
def api_posiciones_inspeccionadas(placa: str, fecha: str = ""):
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
def api_login(item: LoginItem):
    usr = database.autenticar_usuario(item.username, item.password)
    if not usr:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {"status": "ok", "usuario": usr}

@app.get("/api/usuarios")
def api_listar_usuarios():
    return database.listar_usuarios()

@app.post("/api/usuarios")
def api_crear_usuario(item: UsuarioItem):
    ok = database.crear_usuario(item.username, item.password, item.nombre_completo, item.rol, item.cliente_asignado)
    if not ok:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe o los datos son inválidos")
    return {"status": "ok", "username": item.username}

@app.put("/api/usuarios/{username}")
def api_actualizar_usuario(username: str, item: EditarUsuarioItem):
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

@app.delete("/api/usuarios/{username}")
def api_eliminar_usuario(username: str):
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
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=puerto, reload=False)
