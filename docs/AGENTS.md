# AI & Agent Context - TireCheck Pro

> **Nota para Agentes Autónomos e Inteligencias Artificiales:**  
> Este documento resume el contexto técnico, las invariantes arquitectónicas, los contratos de datos y las reglas críticas del repositorio para permitir lecturas, análisis y modificaciones seguras, rápidas y eficientes sin degradar la funcionalidad existente.

---

## 1. Resumen Ejecutivo del Proyecto
- **Nombre:** TireCheck Pro
- **Propósito:** Suite web integral para inspección técnica de neumáticos en patio, control de flotas, diagnóstico predictivo (alineación, duales, retiro), trazabilidad histórica de llantas y cálculo de costos por kilómetro (CPK).
- **Tipo de Aplicación:** Single Page Application (SPA) responsiva servida por un backend RESTful asíncrono en Python.
- **Estado Actual:** 100% web, con modo offline en patio (`localStorage`) y soporte de escritorio para administración.

---

## 2. Pila Tecnológica (Tech Stack)

| Capa | Tecnología | Archivos Principales | Responsabilidad |
|---|---|---|---|
| **Frontend Web** | HTML5, Tailwind CSS (CDN), FontAwesome 6, Vanilla JS | `templates/index.html` | SPA de 6 módulos, renderizado de chasis dinámico, cola offline, modales y llamadas REST. |
| **Backend REST** | Python 3.12, FastAPI, Uvicorn, Starlette | `server.py` | API RESTful, validación con Pydantic, streaming de reportes PDF y libros Excel. |
| **Capa de Datos** | SQLite3, Pandas, NumPy | `database.py`, `inspecciones.db` | Esquema relacional de 6 tablas, transacciones, evaluación de 6 candados, motor de KPIs. |
| **Reportes Técnicos** | ReportLab | `pdf_generator.py` | Generación binaria en memoria de informes técnicos individuales y consolidados. |
| **Diagnóstico** | Pandas, NumPy | `logica_inspeccion.py`, `database.py` | Detección de sábanas, alineación directores, duales desparejados y límites de retiro. |
| **Testing** | Pytest, FastAPI TestClient | `tests/conftest.py`, `tests/` | 20 pruebas automatizadas con aislamiento de BD en archivo temporal. |

---

## 3. Mapa del Repositorio y Ubicación de Archivos

```
TireCheck_Pro_Proyecto/
├── INICIAR_TIRECHECK.bat               # Punto de entrada Windows: pip check + abre navegador + inicia FastAPI
├── iniciar_app.bat                   # Respaldo de contingencia para escritorio Tkinter
├── app.py                            # Aplicación de escritorio Tkinter original (conservada intacta)
├── server.py                         # Servidor FastAPI unificado con todos los endpoints REST
├── database.py                       # Capa de datos SQLite, 6 candados y motor de cálculo
├── pdf_generator.py                  # Generador de reportes PDF con ReportLab
├── logica_inspeccion.py              # Análisis de alineación y sábanas de desgaste
├── requirements.txt                  # Dependencias de Python
├── README.md                         # Guía rápida para humanos
├── .gitignore                        # Archivo de ignorados (WAL, SHM, pycache)
├── data/                             # Base de datos persistente y plantillas
│   ├── inspecciones.db               # Base de datos SQLite real (60 registros de producción)
│   └── plantillas/                   # Plantillas Excel de cargue masivo
├── docs/                             # Documentación técnica completa
│   ├── AGENTS.md                     # Este documento de contexto para IA
│   ├── ARCHITECTURE.md               # Arquitectura técnica detallada y diagramas C4
│   ├── API_REFERENCE.md              # Especificación exhaustiva de endpoints REST
│   ├── REGLAS_NEGOCIO.md             # Candados de seguridad, algoritmos y fórmulas
│   ├── CHASIS_INTERACTIVO.md         # Guía visual y funcional del chasis interactivo
│   ├── DOCUMENTACION_MIGRACION.md    # Matriz de trazabilidad al 100% y auditoría
│   └── CONTRIBUTING.md               # Guía de desarrollo y estándares de código
├── templates/
│   └── index.html                    # SPA Web unificada con las 6 vistas
├── tests/                            # Suite automatizada (pytest)
│   ├── conftest.py                   # Fixture que aísla database.DB_PATH a un archivo temporal
│   ├── test_candados.py              # Validación de los 6 candados de seguridad
│   ├── test_diagnostico.py           # Validación de reglas de alineación y duales
│   ├── test_kpis.py                  # Fórmulas de Km/mm, CPK y proyecciones
│   ├── test_pdf.py                   # Generación binaria de PDFs ReportLab
│   └── test_api_web.py               # Endpoints REST, carga de vistas, streaming Excel
└── scripts/                          # Utilidades y scripts auxiliares
```

---

## 4. Invariantes Críticas y Reglas de No Romper (Guardrails)

### ⛔ 1. Preservación de la Base de Datos Real
- **Regla:** NUNCA ejecutes pruebas unitarias o scripts de prueba contra `inspecciones.db` real.
- **Mecanismo:** En `tests/conftest.py` existe el fixture `test_db` que redirige `database.DB_PATH` a un archivo `.db` temporal en `tempfile`. Al hacer pruebas manuales o automatizadas, usa siempre un entorno aislado.
- **Registros existentes:** Contiene 60 inspecciones históricas que deben ser leídas por la aplicación.

### ⛔ 2. Los 6 Candados de Seguridad Inquebrantables
Ubicados en `database.validar_inspeccion_candados()`:
1. **Dimensión R22.5:** Ninguna profundidad puede superar 27.0 mm (otras rines max 32.0 mm).
2. **Profundidad Inicial:** Las profundidades medidas no pueden superar la profundidad de diseño de fábrica (`prof_inicial`).
3. **Duplicidad de Llanta:** El mismo `numero_interno` no puede estar activo en 2 placas o posiciones distintas del mismo cliente.
4. **Frecuencia Mensual Única:** Máximo una inspección por placa y posición en el mismo mes calendario (`YYYY-MM`).
5. **Odómetro No Regresivo:** El kilometraje actual de la placa no puede ser menor al de su última inspección.
6. **Desgaste No Ascendente:** La profundidad de una llanta no puede aumentar respecto a su inspección anterior (tolerancia máxima de 1.0 mm).

### ⛔ 3. Serialización JSON en FastAPI (Tipos NumPy)
- **Problema conocido:** Pandas y SQLite en Python 3.12 retornan tipos `numpy.int64` y `numpy.float64`. Pydantic V2 / FastAPI `jsonable_encoder` lanza error si intenta serializarlos como dicts.
- **Solución implementada:** La función `sanitizar_nativos()` en `server.py` convierte recursivamente cualquier objeto con atributo `.item()` a tipos nativos de Python (`int`, `float`). TODO nuevo endpoint que devuelva datos de DataFrames o consultas complejas DEBE pasar por `sanitizar_nativos()`.

### ⛔ 4. Orden de Rutas en FastAPI
- Rutas fijas (ej. `/api/inspecciones/plantilla-excel`, `/exportar-excel`, `/importar-excel`) DEBEN definirse **ANTES** de la ruta con parámetro dinámico `/api/inspecciones/{inspeccion_id}`. De lo contrario, FastAPI intentará convertir `"plantilla-excel"` a `int` produciendo HTTP 422.

---

## 5. Mapeo de Vistas en la SPA (`templates/index.html`)

| Vista | ID en DOM | Función JS de Carga | Descripción |
|---|---|---|---|
| **1. Patio** | `#vista-patio` | `cargarCatalogos()` | Chasis interactivo, mediciones de remanente, PSI, autocompletado y cola offline. |
| **2. Base de Inspecciones** | `#vista-basedatos` | `cargarBaseInspecciones()` | Grilla de 23 columnas con búsqueda, edición, eliminación e importación/exportación Excel. |
| **3. Diagnóstico** | `#vista-diagnostico` | `cargarDiagnostico()` | 5 tarjetas métricas de flota, tabla de planes de acción, PDF individual y Excel multi-hoja. |
| **4. KPIs de Llantas** | `#vista-kpis` | `cargarKpis()` | 4 tarjetas de rendimiento, Km/mm, CPK, proyecciones de vida útil y exportación Excel. |
| **5. Catálogos** | `#vista-catalogos` | `cargarGestionCatalogos()` | Subpestañas para Operaciones, Tipologías, Modelos, Límites por Cliente y Usuarios. |
| **6. Conexión QR & Remoto** | `#vista-remoto` | `cargarInfoServidor()` | Generación de QR en vivo, IP de red local y control de túnel ngrok. |

---

## 6. Comandos Operativos para Agentes

```bash
# 1. Ejecutar la suite completa de pruebas
python -m pytest tests/ -v

# 2. Iniciar el servidor web de desarrollo
python server.py
# O alternativamente:
python -m uvicorn server:app --host 127.0.0.1 --port 8000

# 3. Comprobar la integridad de la base de datos
python -c "import database; print('Total inspecciones:', len(database.obtener_todas_inspecciones()))"
```

---

## 7. Credenciales por Defecto
- **Administrador:** `admin` / `admin123` (Acceso total, configuración y usuarios)
- **Inspector:** `inspector1` / `1234` (Acceso operativo para captura en patio)
