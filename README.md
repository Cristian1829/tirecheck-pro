# 🚛 TireAnalyze Pro - Suite Web Integral de Inspección y Diagnóstico de Llantas

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-32%2F32%20Passing-brightgreen.svg)](tests/)
[![Architecture](https://img.shields.io/badge/Architecture-100%25%20Web%20SPA-purple.svg)](docs/ARCHITECTURE.md)
[![Database](https://img.shields.io/badge/SQLite-data%2Finspecciones.db-blue.svg)](data/inspecciones.db)

**TireAnalyze Pro** es una plataforma integral accesible 100% desde el navegador para la inspección técnica de neumáticos en patio, control de flotas de carga pesada, diagnóstico predictivo (alineación, duales y retiro), trazabilidad histórica de llantas y cálculo de costos por kilómetro (CPK).

Diseñada con enfoque **Offline-First**, permite que los inspectores trabajen en patios o sótanos sin señal celular y sincronicen automáticamente sus datos al recuperar conexión.

---

## ⚡ Inicio Rápido (En 10 Segundos)

### En Windows:
Haz doble clic sobre:
```cmd
INICIAR_TIREANALYZE.bat
```
El script verificará las dependencias, iniciará el servidor FastAPI y **abrirá automáticamente tu navegador predeterminado en `http://localhost:8000`**.

### Desde Terminal:
```bash
pip install -r requirements.txt
python server.py
```
Abre en tu navegador: [http://localhost:8000](http://localhost:8000)

### 🔑 Credenciales del Sistema:
- **Administrador:** Usuario `admin` | Contraseña `admin123` (Acceso total, configuración y usuarios)
- **Inspector de Patio:** Usuario `inspector1` | Contraseña `1234` (Captura operativa en patio)

---

## 📚 Índice de Documentación Técnica

Para que cualquier persona o inteligencia artificial comprenda el sistema con máxima profundidad y rapidez, la documentación se encuentra organizada según los más altos estándares:

| Documento | Audiencia | Contenido |
|---|---|---|
| 🤖 [**AGENTS.md**](docs/AGENTS.md) | **IAs & Agentes** | Contexto denso, invariantes, reglas de no rotura, tipos de datos y guardrails. |
| 🏗️ [**ARCHITECTURE.md**](docs/ARCHITECTURE.md) | **Arquitectos & Devs** | Arquitectura en capas, diagramas C4, modelo entidad-relación SQLite y flujos. |
| 🔌 [**API_REFERENCE.md**](docs/API_REFERENCE.md) | **Integradores & Devs** | Especificación completa de los 25+ endpoints RESTful, payloads JSON y errores. |
| 📐 [**REGLAS_NEGOCIO.md**](docs/REGLAS_NEGOCIO.md) | **Ingenieros & QA** | Los 6 candados de seguridad, algoritmos predictivos y fórmulas matemáticas de CPK. |
| 🚚 [**CHASIS_INTERACTIVO.md**](docs/CHASIS_INTERACTIVO.md) | **Operaciones & Patio** | Guía visual y funcional del chasis por ejes, estados, ergonomía y esquemas JSON. |
| 📋 [**DOCUMENTACION_MIGRACION.md**](docs/DOCUMENTACION_MIGRACION.md) | **Auditoría & PM** | Matriz de trazabilidad 100%, inventario FN-01 a FN-32 y resultados reales de QA. |
| 🛠️ [**CONTRIBUTING.md**](docs/CONTRIBUTING.md) | **Desarrolladores** | Estándares de desarrollo, PEP 8, aislamiento de pruebas con pytest y checklist. |

---

## 🧭 Las 6 Vistas Integradas de la Suite Web

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BARRA DE NAVEGACIÓN SUPERIOR                    │
│  [📱 Patio] [📋 Inspecciones] [🔍 Diagnóstico] [📊 KPIs] [⚙️ Catálogos] [🌐 QR] │
└────────────────────────────────────────────────────────────────────────┘
```

1. 📱 **Inspección de Patio:**
   - Mapeo interactivo visual del chasis según su tipología (4x2, 6x4, 8x4, trailers).
   - Captura ergonómica de 3 surcos de profundidad (exterior, central, interior) y presión PSI.
   - Autocompletado inteligente de marcas y dimensiones según el catálogo.
   - **Modo Offline transparente:** Si se pierde la señal en patio, las inspecciones se guardan localmente y se suben atómicamente al reconectar.

2. 📋 **Base de Inspecciones:**
   - Grilla interactiva de 23 columnas con búsqueda instantánea por placa o cliente.
   - Edición de registros existentes mediante modal emergente.
   - Eliminación con confirmación de seguridad.
   - **Cargue masivo desde Excel:** Zona Drag & Drop con normalización automática de columnas.
   - Descarga de plantilla oficial y exportación completa de la base a Excel.

3. 🔍 **Diagnóstico & Planes de Acción:**
   - 5 tarjetas métricas de flota en vivo: Total Unidades, Cambios Inmediatos, Alineación, Duales Mal Apareados y Unidades en Norma.
   - Generación instantánea de reportes técnicos individuales en **PDF**.
   - Exportación de la matriz de diagnóstico a Excel en libro multi-hoja.

4. 📊 **Trazabilidad & KPIs de Llantas:**
   - Fórmulas de ingeniería: Km Rodados, Desgaste mm, Rendimiento Km/mm, Costo por Kilómetro (CPK $/km), Proyección Total de Vida y Km Restantes.
   - Filtros cruzados por número interno, cliente, sede, operación y marca.
   - Exportación completa de métricas a Excel.

5. ⚙️ **Catálogos & Configuración:**
   - Administración de Tipos de Operación (Carga Seca, Refrigerado, etc.).
   - Configuración de Tipologías de Vehículos y esquemas JSON de ejes.
   - Catálogo de Modelos de Llanta (Nuevas y Reencauches con profundidad original).
   - Límites de Retiro por Cliente (umbral en mm para alertas preventivas).
   - Administración de Usuarios, contraseñas y asignación de flotas.

6. 🌐 **Conectar Celular / QR & Acceso Remoto:**
   - Código QR dinámico generado en vivo para escaneo inmediato desde teléfonos.
   - Enlace directo por red local Wi-Fi (`http://IP_LOCAL:8000`).
   - Control de túnel público HTTPS de Internet (ngrok) con encendido/apagado en 1 clic.

---

## 🔒 Los 6 Candados de Seguridad Activos

Cada guardado, edición o importación masiva es validado transaccionalmente:
1. **Límite R22.5:** Profundidad máxima de 27.0 mm para rines de 22.5".
2. **Profundidad Inicial:** La profundidad medida no puede superar la profundidad de diseño de fábrica.
3. **Duplicidad de Llanta:** El mismo número interno no puede estar montado en dos placas o posiciones simultáneamente.
4. **Frecuencia Mensual Única:** Máximo una inspección por placa y posición en el mismo mes (`YYYY-MM`).
5. **Odómetro No Regresivo:** El kilometraje actual no puede ser menor al de la última inspección registrada.
6. **Desgaste No Ascendente:** La profundidad de una llanta no puede aumentar (tolerancia máxima de 1.0 mm).

---

## 🔄 Plan de Contingencia y Reversibilidad

Los archivos originales de la versión clásica de escritorio en Tkinter se conservan intactos en el repositorio:
- Para ejecutar la aplicación de escritorio en cualquier momento:
  ```cmd
  iniciar_app.bat
  ```
Ambas interfaces leen y escriben sobre la misma base de datos [data/inspecciones.db](file:///c:/Users/crist/OneDrive/Documentos/Tyre/TireCheck_Pro_Proyecto/data/inspecciones.db).

---

## 🧪 Pruebas Automatizadas (QA Testing)

Para ejecutar la suite de pruebas unitarias y de integración:
```bash
python -m pytest tests/ -v
```
*Total: 20 pruebas ejecutadas, 20 aprobadas (100% passing) con aislamiento de base de datos.*
