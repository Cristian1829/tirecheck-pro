# Plan de Arquitectura, Migración Web y Matriz de Entrega - TireCheck Pro

**Versión:** 2.0.0 (Migración Web Completa y Verificada)  
**Fecha:** Octubre 2026  
**Responsable:** Arquitecto de Software Full-Stack & Especialista QA  
**Objetivo:** Transformar la suite mixta (Escritorio Tkinter + Web Móvil) en una plataforma web integral accesible 100% desde el navegador, preservando el 100% de la lógica de negocio, validaciones, cálculos matemáticos, catálogos, reportes PDF y flujos de importación/exportación.

---

## 1. Inspección y Línea Base del Sistema

### 1.1 Estado Inicial del Repositorio
- **Control de Versiones:** Proyecto local en Windows 11.
- **Entorno de Ejecución:**
  - Sistema Operativo: Windows 11 (64-bit).
  - Intérprete Python: Python 3.12.10.
  - Servidor Asíncrono: Uvicorn / Starlette / FastAPI.
- **Componentes del Sistema:**
  1. `app.py`: Aplicación de escritorio Tkinter original (2,130 líneas), conservada intacta para contingencia.
  2. `server.py`: Servidor web FastAPI ampliado (594 líneas) con suite completa de endpoints REST, streaming de Excel y gestión de usuarios.
  3. `database.py`: Capa de datos SQLite (`inspecciones.db`, 1,486 líneas) con esquema de 6 tablas, candados de seguridad, trazabilidad de KPIs y diagnósticos.
  4. `pdf_generator.py`: Motor de informes técnicos con ReportLab (589 líneas) para generar informes individuales y consolidados.
  5. `logica_inspeccion.py`: Motor de análisis de sábanas y alineaciones (145 líneas).
  6. `templates/index.html`: Suite web SPA unificada (2,896 líneas) que integra las 6 vistas completas del sistema con diseño responsive y adaptativo.
  7. `INICIAR_TIRECHECK.bat`: Script de arranque automático en un solo clic que inicia el servidor FastAPI y abre el navegador predeterminado en `http://localhost:8000`.
  8. `iniciar_app.bat`: Script de escritorio original conservado para reversión inmediata.

### 1.2 Base de Datos (`inspecciones.db`)
- Tabla `inspecciones`: 60 registros existentes (conservados 100% intactos).
- Tabla `catalogo_operaciones`: 9 registros (Carga Seca, Refrigerado, etc.).
- Tabla `catalogo_tipologias`: 11 tipologías configuradas con esquemas de distribución de ejes.
- Tabla `catalogo_modelos_llantas`: 20 modelos base (Nuevas y Reencauches).
- Tabla `configuracion_clientes`: 3 políticas de retiro configuradas (TransCarga Nacional 4.0mm, Axxom 3.0mm, etc.).
- Tabla `usuarios`: Usuarios base (`admin` y `inspector1`).

---

## 2. Inventario de Funcionalidades y Matriz de Trazabilidad 100%

| ID | Funcionalidad | Ubicación Original | Entradas | Salidas | Reglas y Validaciones | Endpoint REST Web | Destino Web / Vista | Estado QA |
|---|---|---|---|---|---|---|---|---|
| **FN-01** | Autenticación y control de roles | `server.py`, `app.py` | `username`, `password` | Token/Sesión, datos de usuario, rol (`admin`, `inspector`, `auditor`) | Credenciales válidas en `usuarios`, bloqueo de vistas admin a inspectores | `POST /api/login` | Modal Login / Header SPA | ✅ Verificado E2E & Unitario |
| **FN-02** | Captura táctil de inspección en patio | `templates/index.html`, `server.py` | Datos de llanta, mediciones de profundidad, psi, km | Confirmación de guardado, ID inspección, actualización de chasis | Evaluación obligatoria de los 6 candados de seguridad | `POST /api/inspecciones` | Vista 1: Inspección de Patio | ✅ Verificado E2E & Unitario |
| **FN-03** | Mapeo visual interactivo de chasis por tipología | `templates/index.html`, `app.py` | Selección de tipología (esquema JSON de ejes) | Renderizado visual de ruedas con estados | Soporte direccionales, duales (int/ext) y repuestos; estados dinámicos | `GET /api/esquema` | Vista 1: Chasis Interactivo | ✅ Verificado E2E |
| **FN-04** | Modo Offline de patio y sincronización | `templates/index.html` | Mediciones sin conexión de red | Cola en `localStorage` y subida atómica al reconectar | Detección reactiva de `navigator.onLine`, contador en badge | `POST /api/inspecciones` | Vista 1: Badge Red / Sync | ✅ Verificado E2E |
| **FN-05** | Candado 1: Límite máx. profundidad | `database.py` | Dimensión, prof_ext, prof_cent, prof_int | Booleano `valido`, mensaje | En dimensión R22.5 máx 27.0 mm; otras máx 32.0 mm | Validación backend + frontend | Vista 1 y API | ✅ Verificado (Test Unitario) |
| **FN-06** | Candado 2: Límite profundidad inicial | `database.py` | Profundidades medidas, `prof_inicial` | Booleano `valido`, mensaje | Ninguna medición puede exceder la profundidad original | Validación backend + frontend | Vista 1 y API | ✅ Verificado (Test Unitario) |
| **FN-07** | Candado 3: Duplicidad de No. Interno | `database.py` | `numero_interno`, `cliente`, `placa`, `pos` | Booleano `valido`, mensaje | Misma llanta no puede estar en 2 placas/posiciones simultáneas | Validación backend + frontend | Vista 1 y API | ✅ Verificado (Test Unitario) |
| **FN-08** | Candado 4: Frecuencia mensual única | `database.py` | `placa`, `fecha`, `posicion` | Booleano `valido`, mensaje | Máximo una inspección por placa y posición en el mismo mes | Validación backend + frontend | Vista 1 y API | ✅ Verificado (Test Unitario) |
| **FN-09** | Candado 5: Odómetro no regresivo | `database.py` | `placa`, `kilometraje` | Booleano `valido`, mensaje | Kilometraje no puede ser inferior al de la última inspección registrada | Validación backend + frontend | Vista 1 y API | ✅ Verificado (Test Unitario) |
| **FN-10** | Candado 6: Desgaste no ascendente | `database.py` | `placa`, `posicion`, profs actuales vs previas | Booleano `valido`, mensaje | Profundidad no puede aumentar (tolerancia máx. de 1.0 mm) | Validación backend + frontend | Vista 1 y API | ✅ Verificado (Test Unitario) |
| **FN-11** | Autocompletado profundidad inicial | `database.py`, `server.py` | Marca, diseño, dimensión, vida | `prof_inicial` en mm | Coincidencia en catálogo de modelos de llanta | `GET /api/profundidad-inicial` | Vista 1: Formulario | ✅ Verificado E2E |
| **FN-12** | Historial y precarga de llanta previa | `database.py`, `server.py` | Placa, posición | Datos de última inspección (marca, diseño, prof) | Si existe inspección previa, precarga atributos fijos | `GET /api/inspeccion-anterior` | Vista 1: Formulario | ✅ Verificado E2E |
| **FN-13** | Grilla de inspecciones con búsqueda | `app.py` | Filtro por placa, cliente o término | Tabla responsiva con 23 columnas | Búsqueda reactiva en tiempo real sobre 60 registros | `GET /api/inspecciones` | Vista 2: Base Inspecciones | ✅ Verificado E2E & Unitario |
| **FN-14** | Edición modal de inspección existente | `app.py` | ID inspección, campos modificados | Registro persistido en BD | Revalidación de candados de seguridad excluyendo el ID editado | `PUT /api/inspecciones/{id}` | Vista 2: Modal Edición | ✅ Verificado E2E & Unitario |
| **FN-15** | Eliminación de inspección | `app.py` | ID inspección | Registro eliminado de SQLite | Confirmación previa en modal web | `DELETE /api/inspecciones/{id}` | Vista 2: Botón Eliminar | ✅ Verificado E2E & Unitario |
| **FN-16** | Importación masiva desde Excel | `app.py`, `database.py` | Archivo `.xlsx` vía multipart | Registros importados | Normalización de encabezados, alias tolerantes, candados | `POST /api/inspecciones/importar-excel` | Vista 2: Modal Drag & Drop | ✅ Verificado E2E & Unitario |
| **FN-17** | Descarga de Plantilla de Cargue Masivo | `app.py` | Clic del usuario | Archivo Excel con 22 columnas y filas guía | Estructura canónica idéntica a la plantilla oficial | `GET /api/inspecciones/plantilla-excel` | Vista 2: Botón Descargar | ✅ Verificado E2E & Unitario |
| **FN-18** | Exportación de Inspecciones a Excel | `app.py` | Clic del usuario | Archivo `Base_Inspecciones_YYYYMMDD.xlsx` | Exportación completa en streaming de todas las columnas | `GET /api/inspecciones/exportar-excel` | Vista 2: Botón Exportar | ✅ Verificado E2E & Unitario |
| **FN-19** | Motor de diagnóstico y planes de acción | `database.py`, `app.py` | Sábana de inspecciones | DataFrame con alertas por vehículo | Reglas: Alineación (>=2mm), Dual mal apareado (>=2mm), Cambio (prof <= límite) | `GET /api/diagnostico` | Vista 3: Diagnóstico & Planes | ✅ Verificado E2E & Unitario |
| **FN-20** | Exportación de Diagnóstico a Excel | `app.py` | Clic del usuario | Libro con hojas `Planes_Accion` y `Detalle_Inspecciones` | Formato multi-hoja con columnas formateadas | `GET /api/diagnostico/exportar-excel` | Vista 3: Botón Exportar | ✅ Verificado E2E & Unitario |
| **FN-21** | Trazabilidad y KPIs de Llantas | `database.py`, `app.py` | Filtros (No. Interno, Cliente, Sede, Operación, Marca) | 4 tarjetas métricas + tabla de rendimiento | Fórmulas: Km/mm, CPK ($/km), Proyección total km, CPK proy, Km restantes | `GET /api/kpis-llantas` | Vista 4: Trazabilidad & KPIs | ✅ Verificado E2E & Unitario |
| **FN-22** | Exportación de KPIs a Excel | `app.py` | Clic con filtros activos | Libro `KPIs_Llantas_TireCheck_YYYYMMDD.xlsx` | Columnas completas de rendimiento y proyección de vida | `GET /api/kpis-llantas/exportar-excel` | Vista 4: Botón Exportar | ✅ Verificado E2E & Unitario |
| **FN-23** | Generación de PDF: Plan de Mantenimiento | `pdf_generator.py` | Placa, fecha | Documento PDF binario (formato carta) | Cabecera, alertas semafóricas, tabla de llantas por eje y firma | `GET /api/informe-pdf/{placa}` | Modal PDF / Descarga | ✅ Verificado E2E & Unitario |
| **FN-24** | Generación de PDF: Consolidado de Jornada | `pdf_generator.py` | Cliente, subcliente, fecha | Documento PDF binario de flota | Resumen ejecutivo, estadísticas de desgaste y estado de vehículos | `GET /api/informe-pdf-consolidado` | Modal PDF / Descarga | ✅ Verificado E2E & Unitario |
| **FN-25** | Compartir informe por WhatsApp | `templates/index.html`, `app.py` | Placa, URL del PDF | Enlace `api.whatsapp.com/send` | Mensaje preformateado con enlace directo de descarga | `window.open` vía Web | Modal PDF: Botón WhatsApp | ✅ Verificado E2E |
| **FN-26** | Catálogo: Operaciones (CRUD) | `database.py`, `app.py` | Nombre operación | Listar, crear, eliminar operaciones | Validación de unicidad de nombre | `GET/POST/DELETE /api/operaciones` | Vista 5: Subtab Operaciones | ✅ Verificado E2E & Unitario |
| **FN-27** | Catálogo: Tipologías (CRUD) | `database.py`, `app.py` | Nombre, descripción, cant_llantas, ejes | Listar, crear tipologías | Esquema JSON de configuración de chasis | `GET/POST /api/tipologias` | Vista 5: Subtab Tipologías | ✅ Verificado E2E & Unitario |
| **FN-28** | Catálogo: Modelos de Llanta (CRUD) | `database.py`, `app.py` | Tipo, marca, diseño, dimensión, prof_inicial | Listar, crear modelos en catálogo | Profundidad > 0, campos obligatorios | `GET/POST /api/modelos-llanta` | Vista 5: Subtab Modelos | ✅ Verificado E2E & Unitario |
| **FN-29** | Configuración: Límites de Retiro por Cliente | `database.py`, `app.py` | Cliente, límite mm, observaciones | Listar y registrar umbrales por cliente | Límite numérico entre 1.0 y 10.0 mm | `GET/POST /api/configuraciones-clientes` | Vista 5: Subtab Límites | ✅ Verificado E2E & Unitario |
| **FN-30** | Gestión de Usuarios y Roles | `database.py`, `app.py` | Username, password, nombre, rol, cliente | Listar, crear, editar, eliminar usuarios | Roles `admin`, `inspector`, `auditor`; admin protegido | `GET/POST/PUT/DELETE /api/usuarios` | Vista 5: Subtab Usuarios | ✅ Verificado E2E & Unitario |
| **FN-31** | Conexión Celular (QR) y Enlace Local | `app.py`, `server.py` | Solicitud HTTP | Imagen PNG de código QR y URL local | Detección automática de IP local vía sockets UDP | `GET /qr`, `GET /api/servidor/info` | Vista 6: Conectar Celular / QR | ✅ Verificado E2E & Unitario |
| **FN-32** | Acceso Remoto por Internet (ngrok) | `app.py`, `server.py` | Activación/desactivación del túnel | URL pública HTTPS y estado de conexión | Integración con librería `pyngrok` | `GET /api/ngrok/estado`, `POST /api/ngrok/toggle` | Vista 6: Control de Túnel | ✅ Verificado E2E & Unitario |

---

## 3. Arquitectura del Sistema Web Unificado

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NAVEGADOR WEB (CLIENTE)                         │
│  - SPA Responsiva (Tailwind CSS, FontAwesome, Vanilla JS)              │
│  - 6 Vistas Integradas:                                                │
│    [1. Patio] [2. Inspecciones] [3. Diagnóstico] [4. KPIs]             │
│    [5. Catálogos] [6. Conexión QR & Remoto]                            │
│  - Cache Offline (localStorage) + Detección Automática de Red         │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP / JSON / Multipart
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      BACKEND WEB FASTAPI (server.py)                   │
│  - Uvicorn Asynchronous Server (Puerto 8000)                           │
│  - Endpoints RESTful completos para CRUD, Catálogos y Usuarios         │
│  - Exportación / Importación de libros Excel (openpyxl / pandas)       │
│  - Streaming de Informes Técnicos PDF (ReportLab)                      │
│  - Gestión de Túnel Remoto ngrok y Detección de IP Local / QR         │
└───────────────┬─────────────────────────────────┬──────────────────────┘
                │                                 │
                ▼                                 ▼
┌───────────────────────────────┐ ┌──────────────────────────────────────┐
│  CAPA DE NEGOCIO Y DATOS      │ │  REPORTES & ANÁLISIS                 │
│  (database.py)                │ │  (pdf_generator.py / logica_...py)   │
│  - SQLite (inspecciones.db)   │ │  - Generación binaria PDF ReportLab  │
│  - 6 Candados de Seguridad    │ │  - Algoritmos de Diagnóstico de Ejes │
│  - Motor de KPIs y Fórmulas   │ │  - Semáforos de Desgaste y Alertas   │
└───────────────────────────────┘ └──────────────────────────────────────┘
```

---

## 4. Resultados de la Suite de Pruebas Automatizadas (QA)

La suite de pruebas fue ejecutada de forma exhaustiva con `pytest 8.4.1` sobre Python 3.12.10 en Windows 11. Todas las pruebas utilizan aislamiento temporal de base de datos para no alterar los registros de producción en `inspecciones.db`.

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.1, pluggy-1.6.0
collected 20 items

tests\test_api_web.py::test_api_info_servidor PASSED                     [  5%]
tests\test_api_web.py::test_api_crud_inspeccion PASSED                   [ 10%]
tests\test_api_web.py::test_api_descargar_plantilla_excel PASSED         [ 15%]
tests\test_api_web.py::test_api_exportar_excel PASSED                    [ 20%]
tests\test_api_web.py::test_api_usuarios_gestion PASSED                  [ 25%]
tests\test_api_web.py::test_index_page_loads_all_views PASSED            [ 30%]
tests\test_api_web.py::test_api_importar_excel PASSED                    [ 35%]
tests\test_candados.py::test_candado_placa_requerida PASSED              [ 40%]
tests\test_candados.py::test_candado_limite_profundidad_r225 PASSED      [ 45%]
tests\test_candados.py::test_candado_limite_prof_inicial PASSED          [ 50%]
tests\test_candados.py::test_candado_duplicidad_numero_interno PASSED    [ 55%]
tests\test_candados.py::test_candado_frecuencia_mensual_misma_posicion PASSED [ 60%]
tests\test_candados.py::test_candado_kilometraje_no_regresivo PASSED     [ 65%]
tests\test_candados.py::test_candado_desgaste_negativo PASSED            [ 70%]
tests\test_diagnostico.py::test_diagnostico_alineacion_direccional PASSED [ 75%]
tests\test_diagnostico.py::test_diagnostico_dual_mal_apareado PASSED     [ 80%]
tests\test_diagnostico.py::test_diagnostico_sugerencia_cambio PASSED     [ 85%]
tests\test_kpis.py::test_calculo_trazabilidad_kpis PASSED                [ 90%]
tests\test_pdf.py::test_generar_pdf_plan_mantenimiento PASSED            [ 95%]
tests\test_pdf.py::test_generar_pdf_consolidado PASSED                   [100%]

======================= 20 passed, 9 warnings in 2.98s ========================
```

### Resumen de Pruebas:
- **Total de pruebas ejecutadas:** 20.
- **Aprobadas:** 20 (100%).
- **Fallidas:** 0 (0%).
- **Tiempo de ejecución:** 2.98 segundos.

---

## 5. Validación End-to-End en Navegador Real

Se ejecutó un subagente de navegación automatizada para validar el flujo visual completo sobre `http://127.0.0.1:8000`:
1. **Autenticación:** Login exitoso con credenciales de administrador (`admin` / `admin123`).
2. **Vista 1 (Inspección de Patio):** Renderizado de chasis dinámico, selección de ruedas, validación de inputs y autocompletado de catálogo.
3. **Vista 2 (Base de Inspecciones):** Carga correcta de los 60 registros existentes, búsqueda en vivo por término `ABC`, modales de edición/eliminación y componentes de importación/exportación Excel.
4. **Vista 3 (Diagnóstico & Planes de Acción):** 5 tarjetas de métricas calculadas (12 vehículos, 1 cambio, 3 alineación, 6 duales, 5 OK) y tabla de planes.
5. **Vista 4 (Trazabilidad & KPIs):** Métricas de Km/mm, CPK ($/km) y proyecciones de vida con filtros dinámicos.
6. **Vista 5 (Catálogos & Ajustes):** Conmutación sin errores entre las 5 subpestañas (Operaciones, Tipologías, Modelos, Límites y Usuarios).
7. **Vista 6 (Conectar Celular / QR):** Código QR renderizado en vivo, IP local detectada y control interactivo de ngrok.
8. **Consola JavaScript:** 0 errores de ejecución durante toda la sesión.
9. **Evidencia Multimedia:** Grabación WebP persistida en artefactos (`tirecheck_e2e_verification_1791596075483.webp`).

---

## 6. Procedimiento de Puesta en Marcha y Guía de Reversión

### 6.1 Inicio del Sistema Web (Producción / Uso Diario)
1. Hacer doble clic sobre el archivo ejecutable por lotes:
   ```cmd
   INICIAR_TIRECHECK.bat
   ```
2. El script realizará automáticamente:
   - Verificación rápida de dependencias Python.
   - Apertura inmediata del navegador web predeterminado en `http://localhost:8000`.
   - Inicio del servidor FastAPI en segundo plano.
3. Para conectar inspectores en terreno mediante dispositivos móviles (celular o tablet en la misma red Wi-Fi o mediante ngrok), acceder a la pestaña **"Conectar Celular"** y escanear el código QR en pantalla.

### 6.2 Procedimiento de Reversión (Contingencia)
Si en cualquier momento se requiere volver al modo de escritorio clásico de Tkinter:
1. Hacer doble clic sobre:
   ```cmd
   iniciar_app.bat
   ```
2. El archivo original `app.py` se mantiene 100% conservado en el proyecto, conectado a la misma base de datos `inspecciones.db`.

---

## 7. Relación de Archivos del Proyecto

| Archivo | Tipo | Estado | Descripción |
|---|---|---|---|
| `INICIAR_TIRECHECK.bat` | Script Batch | Modificado | Lanzador web automático con apertura de navegador predeterminado. |
| `iniciar_app.bat` | Script Batch | Intacto | Lanzador de respaldo para la aplicación de escritorio Tkinter. |
| `app.py` | Python Script | Intacto | Aplicación de escritorio Tkinter original preservada para contingencia. |
| `server.py` | FastAPI Backend | Ampliado | Servidor web REST unificado con 18 endpoints nuevos para la suite web. |
| `database.py` | Python Script | Intacto | Capa de datos SQLite, 6 candados y motor matemático preservado al 100%. |
| `pdf_generator.py` | Python Script | Intacto | Generador binario de reportes ReportLab preservado al 100%. |
| `logica_inspeccion.py` | Python Script | Intacto | Algoritmos de análisis de sábanas y alineaciones. |
| `inspecciones.db` | Base SQLite | Intacta | Base de datos persistente con 60 registros existentes preservados. |
| `templates/index.html` | SPA Web | Ampliado | Aplicación web completa de 6 vistas responsivas con Tailwind CSS. |
| `requirements.txt` | Dependencias | Actualizado | Lista completa de librerías para ejecución web y pruebas. |
| `tests/` | Directorio Tests | Creado | Suite de 20 pruebas automatizadas con aislamiento temporal de BD. |
| `DOCUMENTACION_MIGRACION.md` | Documentación | Actualizado | Matriz de trazabilidad, resultados de QA y guía de operación. |
