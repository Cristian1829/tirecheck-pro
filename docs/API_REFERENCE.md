# Referencia de API RESTful - TireAnalyze Pro

Esta es la especificación técnica completa de los endpoints HTTP provistos por el backend FastAPI en [server.py](file:///c:/Users/crist/OneDrive/Documentos/Tyre/TireAnalyze_Pro_Proyecto/server.py).

---

## 1. Módulo de Autenticación y Sesión

### `POST /api/login`
Autentica un usuario contra la tabla `usuarios` de SQLite.
- **Request Body (JSON):**
  ```json
  {
    "username": "admin",
    "password": "admin123"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "ok",
    "usuario": {
      "id": 1,
      "username": "admin",
      "nombre_completo": "Administrador Principal",
      "rol": "admin",
      "cliente_asignado": ""
    }
  }
  ```
- **Errores:** `401 Unauthorized` si las credenciales son incorrectas o el usuario está inactivo.

---

## 2. Módulo de Inspecciones de Patio

### `GET /api/inspecciones`
Lista el historial de inspecciones registradas con opción de filtrado rápido.
- **Query Params:**
  - `q` (string, opcional): Término de búsqueda (filtra por coincidencia en placa o cliente).
- **Response (200 OK):** Array de objetos con las 23 columnas de la inspección.

### `POST /api/inspecciones`
Registra una nueva medición de rueda en el patio, evaluando los 6 candados de seguridad.
- **Request Body (JSON):**
  ```json
  {
    "fecha": "2026-10-09",
    "cliente": "TransCarga Nacional",
    "subcliente": "Sede Principal",
    "tipo_operacion": "Carga Seca",
    "placa": "ABC123",
    "posicion": 1,
    "kilometraje": 125000,
    "tipologia": "Tractor 6x4 (10 Llantas)",
    "marca": "Michelin",
    "diseno": "X Multi Z",
    "dimension": "295/80R22.5",
    "vida": "Nueva",
    "banda_reen": "",
    "prof_ext": 14.2,
    "prof_cent": 14.5,
    "prof_int": 14.1,
    "psi": 110.0,
    "novedades": "Desgaste regular normal",
    "precio": 1850000.0,
    "prof_inicial": 16.5,
    "km_montaje": 110000,
    "numero_interno": "LL-1001",
    "usuario_registro": "admin"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "ok",
    "id": 61,
    "message": "Inspección guardada exitosamente"
  }
  ```
- **Errores:** `400 Bad Request` si se infringe cualquiera de los 6 candados de seguridad (incluye detalle explícito del candado).

### `GET /api/inspecciones/{id}`
Obtiene el detalle completo de un registro por su ID primario.
- **Response (200 OK):** Diccionario con los datos del registro.
- **Errores:** `404 Not Found`.

### `PUT /api/inspecciones/{id}`
Actualiza los datos de una inspección previamente registrada, revalidando candados de seguridad.
- **Request Body (JSON):** Mismo esquema que en creación.
- **Response (200 OK):** `{"status": "ok", "id": 61, "message": "Inspección actualizada correctamente"}`.

### `DELETE /api/inspecciones/{id}`
Elimina físicamente un registro de la base de datos SQLite.
- **Response (200 OK):** `{"status": "ok", "id": 61, "message": "Inspección eliminada correctamente"}`.

---

## 3. Módulo de Archivos Excel

### `GET /api/inspecciones/plantilla-excel`
Descarga la plantilla oficial canónica para cargue masivo de inspecciones.
- **Response (200 OK):** Archivo binario Excel (.xlsx) con encabezado `Content-Disposition: attachment; filename=Plantilla_Cargue_Masivo_Inspecciones.xlsx`.

### `POST /api/inspecciones/importar-excel`
Importa masivamente inspecciones desde una hoja de cálculo Excel.
- **Content-Type:** `multipart/form-data` (campo `archivo`).
- **Response (200 OK):**
  ```json
  {
    "status": "ok",
    "importados": 15,
    "message": "Se importaron 15 inspecciones correctamente."
  }
  ```

### `GET /api/inspecciones/exportar-excel`
Genera y transmite en streaming un libro Excel con la totalidad de inspecciones en la base de datos.
- **Response (200 OK):** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

---

## 4. Módulo de Diagnóstico de Flota & Planes de Acción

### `GET /api/diagnostico`
Ejecuta los algoritmos de análisis sobre la flota de vehículos registrados.
- **Query Params:** `usuario` (opcional).
- **Response (200 OK):** Array de objetos con el diagnóstico por vehículo:
  ```json
  [
    {
      "Vehículo/Placa": "ABC123",
      "Cliente": "TransCarga Nacional",
      "Subcliente": "Sede Principal",
      "Operación": "Carga Seca",
      "Tipo": "Tractor 6x4",
      "Km": 125000,
      "Llantas Inspeccionadas": 10,
      "Limite_Retiro_mm": 3.0,
      "Plan_Cambio_Llanta": "NO",
      "Plan_Alineacion": "SÍ",
      "Plan_Dual_Mal_Apareado": "NO",
      "Detalle_Cambio": "OK",
      "Detalle_Alineacion": "Diferencia de 2.2 mm entre llantas direccionales (Pos 1: 12.0 mm, Pos 2: 9.8 mm)",
      "Detalle_Dual": "OK"
    }
  ]
  ```

### `GET /api/diagnostico/exportar-excel`
Genera un libro Excel con 2 hojas: `Planes_Accion` (resumen de alertas) y `Detalle_Inspecciones` (datos brutos).
- **Response (200 OK):** Archivo Excel descargable.

---

## 5. Módulo de Trazabilidad y KPIs de Llantas

### `GET /api/kpis-llantas`
Calcula métricas históricas de rendimiento, desgaste y costos para cada llanta rastreada.
- **Query Params (Filtros opcionales):**
  - `numero_interno`, `cliente`, `subcliente`, `tipo_operacion`, `marca`, `diseno`, `dimension`, `vida`, `banda_reen`.
- **Response (200 OK):** Array de objetos con métricas sanitizadas a tipos nativos:
  ```json
  [
    {
      "numero_interno": "LL-1001",
      "placa": "ABC123",
      "posicion": 1,
      "marca": "Michelin",
      "diseno": "X Multi Z",
      "dimension": "295/80R22.5",
      "prof_inicial": 16.5,
      "prof_actual_min": 14.1,
      "desgaste_mm": 2.4,
      "porcentaje_desgaste": 14.5,
      "km_rodados": 15000.0,
      "km_por_mm": 6250.0,
      "precio": 1850000.0,
      "cpk": 123.3333,
      "limite_retiro_mm": 3.0,
      "proyeccion_total_km": 84375.0,
      "cpk_proyectado": 21.9259,
      "km_restantes": 69375.0,
      "requiere_cambio": "NO"
    }
  ]
  ```

### `GET /api/kpis-llantas/exportar-excel`
Exporta las métricas calculadas a un archivo Excel descargable.

---

## 6. Módulo de Reportes Técnicos en PDF

### `GET /api/informe-pdf/{placa}`
Genera y transmite en formato binario el **Plan de Mantenimiento Vehicular** en PDF para una placa específica.
- **Headers de Respuesta:** `Content-Type: application/pdf`, `Content-Disposition: inline; filename=Plan_Mantenimiento_{placa}_{fecha}.pdf`.

### `GET /api/informe-pdf-consolidado`
Genera y transmite el informe técnico en PDF consolidado de toda la jornada para una flota o cliente.
- **Query Params:** `cliente`, `subcliente`, `fecha`.

---

## 7. Módulo de Catálogos y Parámetros Técnicos

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/operaciones` | `GET` | Lista todos los tipos de operación registrados. |
| `/api/operaciones` | `POST` | Registra una nueva operación (`{"nombre": "..."}`). |
| `/api/operaciones` | `DELETE` | Elimina una operación por query param `nombre`. |
| `/api/tipologias` | `GET` | Lista las tipologías configuradas y sus esquemas JSON. |
| `/api/tipologias` | `POST` | Registra una nueva tipología de vehículo. |
| `/api/modelos-llanta` | `GET` | Consulta el catálogo de modelos de llantas. |
| `/api/modelos-llanta` | `POST` | Añade un nuevo modelo con su profundidad de diseño. |
| `/api/configuraciones-clientes` | `GET` | Lista las políticas y límites de retiro por cliente. |
| `/api/configuraciones-clientes` | `POST` | Configura el límite en mm de retiro para un cliente. |
| `/api/limite-cliente` | `GET` | Retorna el límite en mm para un cliente (`?cliente=...`). |
| `/api/esquema` | `GET` | Retorna la distribución de ejes y ruedas de una tipología. |
| `/api/buscar-modelos` | `GET` | Búsqueda reactiva de sugerencias de catálogo en vivo. |

---

## 8. Módulo de Gestión de Usuarios

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/usuarios` | `GET` | Lista todos los usuarios registrados (oculta contraseñas). |
| `/api/usuarios` | `POST` | Crea un nuevo usuario con rol (`admin`, `inspector`, `auditor`). |
| `/api/usuarios/{username}` | `PUT` | Actualiza los datos de un usuario existente. |
| `/api/usuarios/{username}` | `DELETE` | Elimina un usuario (el usuario `admin` está protegido). |

---

## 9. Módulo de Servidor y Conectividad Remota

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/servidor/info` | `GET` | Retorna la IP local, URL del servidor y estado del túnel ngrok. |
| `/qr` | `GET` | Genera y transmite una imagen PNG con el código QR para acceso móvil. |
| `/api/ngrok/estado` | `GET` | Consulta si el túnel público HTTPS de ngrok se encuentra activo. |
| `/api/ngrok/toggle` | `POST` | Enciende o apaga el túnel público ngrok desde el navegador. |
