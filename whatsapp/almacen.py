"""Tablas del chatbot de WhatsApp en la misma base SQLite de TireAnalyze.

- whatsapp_vinculos: qué usuario de TireAnalyze está detrás de cada celular.
- whatsapp_codigos: códigos de un solo uso del enlace de vinculación (vencen a los 10 minutos).
- whatsapp_historial: últimos mensajes de cada conversación, para que el asistente tenga contexto.
- whatsapp_mensajes_procesados: Meta puede reenviar un mismo mensaje; así no se responde dos veces.

Las tablas se crean al vuelo (CREATE TABLE IF NOT EXISTS) para que funcionen en cualquier base, incluidas las de pruebas.
"""
import secrets
import time

import database

VIGENCIA_CODIGO_S = 600
MENSAJES_HISTORIAL = 10


def _asegurar(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS whatsapp_vinculos (
                        telefono TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        sesion_version INTEGER NOT NULL DEFAULT 0,
                        creado REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS whatsapp_codigos (
                        codigo TEXT PRIMARY KEY,
                        telefono TEXT NOT NULL,
                        vence REAL NOT NULL,
                        usado INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS whatsapp_historial (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telefono TEXT NOT NULL,
                        rol TEXT NOT NULL,
                        contenido TEXT NOT NULL,
                        fecha REAL NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_historial_tel ON whatsapp_historial(telefono, id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS whatsapp_mensajes_procesados (
                        mensaje_id TEXT PRIMARY KEY,
                        fecha REAL NOT NULL)""")


def normalizar_telefono(telefono) -> str:
    return "".join(ch for ch in str(telefono or "") if ch.isdigit())


# ---------- Vínculos ----------

def obtener_vinculo(telefono):
    tel = normalizar_telefono(telefono)
    with database.get_connection() as conn:
        _asegurar(conn)
        fila = conn.execute("SELECT username, sesion_version FROM whatsapp_vinculos WHERE telefono = ?", (tel,)).fetchone()
    return {"telefono": tel, "username": fila[0], "sesion_version": int(fila[1] or 0)} if fila else None


def guardar_vinculo(telefono, username, sesion_version):
    tel = normalizar_telefono(telefono)
    with database.get_connection() as conn:
        _asegurar(conn)
        conn.execute("""INSERT INTO whatsapp_vinculos (telefono, username, sesion_version, creado) VALUES (?, ?, ?, ?)
                        ON CONFLICT(telefono) DO UPDATE SET username = excluded.username,
                            sesion_version = excluded.sesion_version, creado = excluded.creado""",
                     (tel, username, int(sesion_version or 0), time.time()))
        conn.execute("DELETE FROM whatsapp_historial WHERE telefono = ?", (tel,))


def borrar_vinculo(telefono):
    tel = normalizar_telefono(telefono)
    with database.get_connection() as conn:
        _asegurar(conn)
        conn.execute("DELETE FROM whatsapp_vinculos WHERE telefono = ?", (tel,))
        conn.execute("DELETE FROM whatsapp_historial WHERE telefono = ?", (tel,))


# ---------- Códigos de vinculación ----------

def crear_codigo(telefono) -> str:
    tel = normalizar_telefono(telefono)
    codigo = secrets.token_urlsafe(18)
    ahora = time.time()
    with database.get_connection() as conn:
        _asegurar(conn)
        conn.execute("DELETE FROM whatsapp_codigos WHERE vence < ? OR telefono = ?", (ahora, tel))
        conn.execute("INSERT INTO whatsapp_codigos (codigo, telefono, vence, usado) VALUES (?, ?, ?, 0)",
                     (codigo, tel, ahora + VIGENCIA_CODIGO_S))
    return codigo


def consumir_codigo(codigo):
    """Teléfono del código si está vigente y sin usar (y lo marca usado); None si no sirve."""
    cod = str(codigo or "").strip()
    if not cod:
        return None
    with database.get_connection() as conn:
        _asegurar(conn)
        fila = conn.execute("SELECT telefono, vence, usado FROM whatsapp_codigos WHERE codigo = ?", (cod,)).fetchone()
        if not fila or int(fila[2] or 0) or float(fila[1]) < time.time():
            return None
        cur = conn.execute("UPDATE whatsapp_codigos SET usado = 1 WHERE codigo = ? AND usado = 0", (cod,))
        if cur.rowcount != 1:
            return None
    return fila[0]


# ---------- Historial ----------

def historial(telefono) -> list:
    tel = normalizar_telefono(telefono)
    with database.get_connection() as conn:
        _asegurar(conn)
        filas = conn.execute("SELECT rol, contenido FROM whatsapp_historial WHERE telefono = ? ORDER BY id DESC LIMIT ?",
                             (tel, MENSAJES_HISTORIAL)).fetchall()
    return [{"rol": r, "contenido": c} for r, c in reversed(filas)]


def agregar_historial(telefono, rol, contenido):
    tel = normalizar_telefono(telefono)
    with database.get_connection() as conn:
        _asegurar(conn)
        conn.execute("INSERT INTO whatsapp_historial (telefono, rol, contenido, fecha) VALUES (?, ?, ?, ?)",
                     (tel, rol, str(contenido or "")[:4000], time.time()))
        # Solo se guardan los últimos mensajes de cada conversación
        conn.execute("""DELETE FROM whatsapp_historial WHERE telefono = ? AND id NOT IN
                        (SELECT id FROM whatsapp_historial WHERE telefono = ? ORDER BY id DESC LIMIT ?)""",
                     (tel, tel, MENSAJES_HISTORIAL))


# ---------- Mensajes ya atendidos ----------

def marcar_procesado(mensaje_id) -> bool:
    """True si es la primera vez que llega este mensaje; False si Meta lo está reenviando."""
    mid = str(mensaje_id or "").strip()
    if not mid:
        return True
    ahora = time.time()
    with database.get_connection() as conn:
        _asegurar(conn)
        conn.execute("DELETE FROM whatsapp_mensajes_procesados WHERE fecha < ?", (ahora - 3 * 86400,))
        cur = conn.execute("INSERT OR IGNORE INTO whatsapp_mensajes_procesados (mensaje_id, fecha) VALUES (?, ?)", (mid, ahora))
        return cur.rowcount == 1
