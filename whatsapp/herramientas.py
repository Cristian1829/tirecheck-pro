"""Consultas que el asistente puede pedir. Todas trabajan con el usuario vinculado al celular y respetan sus
clientes y sedes, igual que la página web: el asistente nunca toca la base de datos directamente.

Cada herramienta devuelve un dict. Si genera un PDF, lo devuelve en la clave "_pdf" = (bytes, nombre_archivo);
el agente lo envía por WhatsApp y al modelo solo le cuenta que el archivo se envió.
"""
from datetime import datetime

import database
import pdf_generator

MAX_VEHICULOS_LISTA = 40

_ESTADOS = {"rojo": "Retiro inmediato (cambio ya)", "amarillo": "Próxima a cambio"}


# ---------- Permisos ----------

def _es_admin(usuario) -> bool:
    return str(usuario.get("rol", "")).strip().lower() in ("admin", "administrador") or \
        str(usuario.get("username", "")).strip().lower() == "admin"


def _clientes(usuario) -> list:
    return database.parsear_clientes_asignados(usuario.get("cliente_asignado"))


def _puede_ver_placa(usuario, placa):
    """(True, cliente, sede) si la placa existe y es de un cliente y sede del usuario."""
    cli, sede = database.cliente_sede_de_placa(placa)
    if not cli:
        return False, "", ""
    return database.usuario_puede_ver_sede(usuario, cli, sede), cli, sede


def _resolver_cliente(usuario, cliente):
    """Cliente pedido validado contra los del usuario. Con un solo cliente asignado, se usa ese."""
    clis = _clientes(usuario)
    pedido = str(cliente or "").strip().upper()
    if pedido:
        if not _es_admin(usuario) and pedido not in clis:
            raise PermissionError(f"No tiene acceso al cliente {pedido}.")
        return pedido
    return clis[0] if len(clis) == 1 else ""


def _validar_sede(usuario, cliente, sede):
    s = str(sede or "").strip().upper()
    if s and cliente and not database.usuario_puede_ver_sede(usuario, cliente, s):
        raise PermissionError(f"No tiene acceso a la sede {s}.")
    return s


def _fecha(valor):
    v = str(valor or "").strip()[:10]
    if not v:
        return ""
    datetime.strptime(v, "%Y-%m-%d")  # ValueError si no es AAAA-MM-DD
    return v


# ---------- Datos de inspección ----------

def _inspecciones(usuario, fecha_desde="", fecha_hasta="", cliente="", sede="", placa=""):
    df = database.filtrar_fechas_validas(database.obtener_todas_inspecciones(usuario=usuario["username"], incluir_fotos=False))
    if df.empty:
        return df
    desde, hasta = _fecha(fecha_desde), _fecha(fecha_hasta)
    if desde:
        df = df[df["fecha"].astype(str).str[:10] >= desde]
    if hasta:
        df = df[df["fecha"].astype(str).str[:10] <= hasta]
    if cliente:
        df = df[df["cliente"].astype(str).str.upper().str.strip() == cliente]
    if sede:
        df = df[df["subcliente"].astype(str).str.upper().str.strip() == sede]
    if placa:
        df = df[df["placa"].astype(str).str.upper().str.strip() == str(placa).strip().upper()]
    return df


def vehiculos_por_estado(usuario, estado="rojo", fecha_desde="", fecha_hasta="", cliente="", sede=""):
    estado = str(estado or "rojo").strip().lower()
    if estado not in _ESTADOS:
        return {"error": "estado debe ser 'rojo' (cambio inmediato) o 'amarillo' (próxima a cambio)"}
    cli = _resolver_cliente(usuario, cliente)
    sd = _validar_sede(usuario, cli, sede)
    matriz = database.calcular_matriz_semaforos_posicion(_inspecciones(usuario, fecha_desde, fecha_hasta, cli, sd))
    vehiculos = []
    for fila in matriz["filas"]:
        llantas = [{"posicion": pos, "profundidad_mm": d["pb"], "limite_mm": d["limite"], "eje": d["eje"]}
                   for pos, d in sorted(fila["posiciones"].items()) if d["color"] == estado]
        if llantas:
            vehiculos.append({"placa": fila["placa"], "cliente": fila["cliente"], "sede": fila["subcliente"],
                              "fecha_ultima_inspeccion": str(fila["fecha"])[:10], "llantas": llantas})
    vehiculos.sort(key=lambda v: (min(l["profundidad_mm"] for l in v["llantas"]), v["placa"]))
    return {
        "estado": _ESTADOS[estado],
        "criterio": "Última inspección de cada posición dentro del rango de fechas; profundidad mínima medida frente al límite de retiro del cliente.",
        "rango": {"desde": fecha_desde or "sin límite", "hasta": fecha_hasta or "sin límite"},
        "total_vehiculos": len(vehiculos),
        "total_llantas": sum(len(v["llantas"]) for v in vehiculos),
        "vehiculos": vehiculos[:MAX_VEHICULOS_LISTA],
        "lista_recortada": len(vehiculos) > MAX_VEHICULOS_LISTA,
    }


def resumen_flota(usuario, fecha_desde="", fecha_hasta="", cliente="", sede=""):
    cli = _resolver_cliente(usuario, cliente)
    sd = _validar_sede(usuario, cli, sede)
    matriz = database.calcular_matriz_semaforos_posicion(_inspecciones(usuario, fecha_desde, fecha_hasta, cli, sd))
    g = matriz["resumen_global"]
    por_sede = {}
    for fila in matriz["filas"]:
        k = f"{fila['cliente']} / {fila['subcliente'] or 'SIN SEDE'}"
        c = por_sede.setdefault(k, {"vehiculos": 0, "rojo": 0, "amarillo": 0, "verde": 0, "sin_datos": 0})
        c["vehiculos"] += 1
        for color in ("rojo", "amarillo", "verde"):
            c[color] += fila["conteo"][color]
        c["sin_datos"] += fila["conteo"]["gris"]
    return {
        "rango": {"desde": fecha_desde or "sin límite", "hasta": fecha_hasta or "sin límite"},
        "vehiculos_inspeccionados": g["total_vehiculos"], "llantas": g["total_llantas"],
        "llantas_retiro_inmediato": g["rojo"], "llantas_proximas_a_cambio": g["amarillo"],
        "llantas_estado_optimo": g["verde"], "llantas_sin_datos": g["gris"],
        "por_sede": por_sede,
    }


def ultima_inspeccion_vehiculo(usuario, placa, fecha=""):
    ok, _, _ = _puede_ver_placa(usuario, placa)
    if not ok:
        return {"error": f"No encontré el vehículo {str(placa).upper()} entre los vehículos a los que tiene acceso."}
    try:
        datos = pdf_generator.construir_datos_informe(placa, _fecha(fecha) or None)
    except ValueError as e:
        return {"error": str(e)}
    return {
        "placa": datos["placa"], "fecha": datos["fecha_insp"], "cliente": datos["cliente"],
        "tipologia": datos["tipologia"], "limite_retiro_mm": datos["limite_retiro"],
        "llantas_auditadas": datos["total_auditadas"], "posiciones_del_vehiculo": datos["total_posiciones"],
        "llantas_para_retiro": datos["n_cambios"], "llantas_con_novedad": datos["n_nov"],
        "alertas": [{k: a.get(k) for k in ("tipo", "posicion", "detalle", "accion")}
                    for a in datos["alertas_lista"][:25]],
    }


def mis_clientes_y_sedes(usuario):
    clis = _clientes(usuario)
    sedes = database.parsear_sedes_asignadas(usuario.get("sedes_asignadas"), clis)
    res = []
    with database.get_connection() as conn:
        for c in clis:
            filas = conn.execute("""SELECT UPPER(TRIM(IFNULL(subcliente, ''))), COUNT(*) FROM padron_vehiculos_cliente
                                    WHERE UPPER(TRIM(cliente)) = ? AND IFNULL(activo, 1) = 1 GROUP BY 1""", (c,)).fetchall()
            permitidas = sedes.get(c)
            por_sede = {s or "SIN SEDE": n for s, n in filas if not permitidas or s in permitidas}
            res.append({"cliente": c, "sedes": sorted(permitidas) if permitidas else "todas",
                        "vehiculos_activos_por_sede": por_sede})
    return {"usuario": usuario.get("nombre_completo") or usuario["username"], "clientes": res}


# ---------- PDF ----------

def informe_inspeccion_pdf(usuario, placa, fecha=""):
    ok, _, _ = _puede_ver_placa(usuario, placa)
    if not ok:
        return {"error": f"No encontré el vehículo {str(placa).upper()} entre los vehículos a los que tiene acceso."}
    try:
        pdf = pdf_generator.generar_pdf_plan_mantenimiento(placa, _fecha(fecha) or None)
    except ValueError as e:
        return {"error": str(e)}
    pl = str(placa).strip().upper()
    nombre = f"Informe_{pl}_{(_fecha(fecha) or datetime.now().strftime('%Y-%m-%d')).replace('-', '')}.pdf"
    return {"_pdf": (pdf, nombre), "leyenda": f"Informe de inspección {pl}"}


def informe_consolidado_pdf(usuario, fecha_desde="", fecha_hasta="", cliente="", sede=""):
    cli = _resolver_cliente(usuario, cliente)
    if not cli:
        return {"error": "Indique de cuál cliente quiere el informe consolidado.", "clientes": _clientes(usuario)}
    sd = _validar_sede(usuario, cli, sede)
    try:
        pdf = pdf_generator.generar_pdf_consolidado_jornada(
            cliente=cli, subcliente=sd or None, fecha_desde=_fecha(fecha_desde) or None,
            fecha_hasta=_fecha(fecha_hasta) or None, usuario=usuario["username"])
    except ValueError as e:
        return {"error": str(e)}
    partes = ["Consolidado", cli.replace(" ", "_")] + ([sd.replace(" ", "_")] if sd else [])
    if fecha_desde or fecha_hasta:
        partes.append(f"{_fecha(fecha_desde).replace('-', '')}-{_fecha(fecha_hasta).replace('-', '')}")
    return {"_pdf": (pdf, "_".join(partes) + ".pdf"), "leyenda": f"Informe consolidado de flota {cli}" + (f" - {sd}" if sd else "")}


# ---------- Catálogo para el modelo ----------

_P_FECHAS = {
    "fecha_desde": {"type": "STRING", "description": "Fecha inicial AAAA-MM-DD (opcional)"},
    "fecha_hasta": {"type": "STRING", "description": "Fecha final AAAA-MM-DD (opcional)"},
    "cliente": {"type": "STRING", "description": "Cliente (opcional si el usuario solo tiene uno)"},
    "sede": {"type": "STRING", "description": "Sede o subcliente (opcional)"},
}

CATALOGO = {
    "vehiculos_por_estado": {
        "funcion": vehiculos_por_estado,
        "descripcion": "Lista los vehículos con llantas para cambio inmediato (estado 'rojo') o próximas a cambio "
                       "(estado 'amarillo'), con la posición, profundidad y límite de cada llanta. Sin fechas, es el "
                       "estado actual de la flota (última inspección de cada posición).",
        "parametros": {"estado": {"type": "STRING", "enum": ["rojo", "amarillo"],
                                  "description": "'rojo' = cambio inmediato, 'amarillo' = próxima a cambio"}, **_P_FECHAS},
        "requeridos": ["estado"],
    },
    "resumen_flota": {
        "funcion": resumen_flota,
        "descripcion": "Resumen del estado de la flota: vehículos inspeccionados y llantas en retiro inmediato, "
                       "próximas a cambio y en buen estado, en total y por sede.",
        "parametros": dict(_P_FECHAS), "requeridos": [],
    },
    "ultima_inspeccion_vehiculo": {
        "funcion": ultima_inspeccion_vehiculo,
        "descripcion": "Resultado de la última inspección (o la de una fecha) de un vehículo: llantas para retiro, "
                       "novedades y alertas por posición.",
        "parametros": {"placa": {"type": "STRING", "description": "Placa del vehículo"},
                       "fecha": {"type": "STRING", "description": "Fecha AAAA-MM-DD de la inspección (opcional)"}},
        "requeridos": ["placa"],
    },
    "mis_clientes_y_sedes": {
        "funcion": mis_clientes_y_sedes,
        "descripcion": "Clientes y sedes a los que tiene acceso el usuario y cuántos vehículos activos hay en cada sede.",
        "parametros": {}, "requeridos": [],
    },
    "informe_inspeccion_pdf": {
        "funcion": informe_inspeccion_pdf,
        "descripcion": "Genera y envía por WhatsApp el PDF del informe de inspección y plan de mantenimiento de un vehículo.",
        "parametros": {"placa": {"type": "STRING", "description": "Placa del vehículo"},
                       "fecha": {"type": "STRING", "description": "Fecha AAAA-MM-DD de la inspección (opcional; por defecto la última)"}},
        "requeridos": ["placa"],
    },
    "informe_consolidado_pdf": {
        "funcion": informe_consolidado_pdf,
        "descripcion": "Genera y envía por WhatsApp el PDF del informe consolidado de flota (métricas globales, estado "
                       "por eje y dimensión y placas a intervenir) de un cliente, opcionalmente por sede y rango de fechas.",
        "parametros": dict(_P_FECHAS), "requeridos": [],
    },
}


def ejecutar(nombre, argumentos, usuario) -> dict:
    """Ejecuta una herramienta del catálogo con el usuario vinculado. Nunca lanza: los errores vuelven como dict."""
    h = CATALOGO.get(nombre)
    if not h:
        return {"error": f"Herramienta desconocida: {nombre}"}
    args = {k: v for k, v in (argumentos or {}).items() if k in h["parametros"]}
    try:
        return h["funcion"](usuario, **args)
    except PermissionError as e:
        return {"error": str(e)}
    except ValueError:
        return {"error": "Fecha inválida: use el formato AAAA-MM-DD."}
    except Exception as e:  # el cliente recibe una respuesta amable; el detalle queda en el registro del servidor
        print(f"[WHATSAPP] Error en la herramienta {nombre}: {e!r}")
        return {"error": "No se pudo completar la consulta en este momento."}
