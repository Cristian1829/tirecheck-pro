# Arquitectura del Sistema - TireAnalyze Pro

Este documento describe la arquitectura técnica, el modelo de datos, los componentes de software y el flujo de información de la plataforma **TireAnalyze Pro**.

---

## 1. Visión General de la Arquitectura

TireAnalyze Pro sigue el patrón de **Arquitectura en Capas (Layered Architecture)** con separación estricta de responsabilidades entre la interfaz de usuario en el navegador (Single Page Application), el gateway de servicios RESTful asíncronos en FastAPI, y el motor de persistencia y lógica de negocio en SQLite.

```mermaid
graph TD
    subgraph Cliente ["Capa de Presentación (Navegador Web)"]
        UI["SPA Unificada (HTML5 + Tailwind CSS + JS)"]
        CHASIS["Motor de Chasis Interactivo SVG/HTML"]
        OFFLINE["Gestor de Cola Offline (localStorage)"]
    end

    subgraph Servidor ["Capa de Aplicación y Servicios (server.py)"]
        FASTAPI["FastAPI / Uvicorn Server"]
        ROUTERS["Controladores REST & Serializadores"]
        STREAMING["Motor de Streaming (Excel / PDF)"]
        NGROK["Controlador de Túnel Remoto (pyngrok)"]
    end

    subgraph Negocio ["Capa de Negocio y Lógica Técnica"]
        CANDADOS["Motor de 6 Candados de Seguridad (database.py)"]
        DIAG["Motor de Diagnóstico & Alineación (logica_inspeccion.py)"]
        KPIS["Calculador de Desgaste, Km/mm y CPK (database.py)"]
        REPORTES["Motor de Generación PDF (pdf_generator.py - ReportLab)"]
    end

    subgraph Persistencia ["Capa de Datos"]
        SQLITE[("Base de Datos SQLite (inspecciones.db)")]
    end

    UI -->|HTTP JSON / Multipart| FASTAPI
    OFFLINE -->|Sincronización Atómica| FASTAPI
    FASTAPI --> ROUTERS
    ROUTERS --> CANDADOS
    ROUTERS --> DIAG
    ROUTERS --> KPIS
    ROUTERS --> REPORTES
    ROUTERS --> STREAMING
    FASTAPI --> NGROK

    CANDADOS --> SQLITE
    DIAG --> SQLITE
    KPIS --> SQLITE
    REPORTES --> SQLITE
```

---

## 2. Modelo de Datos Relacional (SQLite)

La persistencia se gestiona en [inspecciones.db](file:///c:/Users/crist/OneDrive/Documentos/Tyre/TireAnalyze_Pro_Proyecto/inspecciones.db) con un esquema normalizado de 6 tablas:

```mermaid
erDiagram
    inspecciones {
        INTEGER id PK
        TEXT fecha
        TEXT cliente
        TEXT subcliente
        TEXT tipo_operacion
        TEXT placa
        INTEGER posicion
        REAL kilometraje
        TEXT tipologia
        TEXT marca
        TEXT diseno
        TEXT dimension
        TEXT vida
        TEXT banda_reen
        REAL prof_ext
        REAL prof_cent
        REAL prof_int
        REAL psi
        TEXT novedades
        REAL precio
        REAL prof_inicial
        REAL km_montaje
        TEXT numero_interno
        TEXT usuario_registro
        TEXT foto_novedad
        TEXT fecha_creacion
    }

    catalogo_operaciones {
        INTEGER id PK
        TEXT nombre UK
        TEXT descripcion
    }

    catalogo_tipologias {
        INTEGER id PK
        TEXT nombre UK
        TEXT descripcion
        INTEGER cant_llantas
        TEXT esquema_json
    }

    catalogo_modelos_llantas {
        INTEGER id PK
        TEXT tipo_llanta
        TEXT marca
        TEXT diseno
        TEXT dimension
        REAL prof_inicial
        TEXT descripcion
    }

    configuracion_clientes {
        INTEGER id PK
        TEXT cliente UK
        REAL limite_retiro_mm
        TEXT observaciones
        TEXT fecha_actualizacion
    }

    usuarios {
        INTEGER id PK
        TEXT username UK
        TEXT password_hash
        TEXT nombre_completo
        TEXT rol
        TEXT cliente_asignado
        INTEGER activo
    }

    configuracion_clientes ||--o{ inspecciones : "aplica limite"
    catalogo_tipologias ||--o{ inspecciones : "define chasis"
    usuarios ||--o{ inspecciones : "registra inspeccion"
```

### Descripción de Tablas

1. **`inspecciones`:** Tabla central de hechos. Almacena cada medición de rueda efectuada, incluyendo fecha, cliente, vehículo, posición física, odómetro, presiones, 3 surcos de profundidad y atributos económicos (precio de llanta y km de montaje).
2. **`catalogo_operaciones`:** Segmentación operativa del negocio (ej. Carga Seca, Refrigerado, Líquidos, Paquetería).
3. **`catalogo_tipologias`:** Define la arquitectura de los vehículos (ej. 4x2, 6x4, 8x4, Remolques) y contiene en `esquema_json` la distribución física de ejes, tipo de eje (direccional, tracción, remolque) y posiciones asociadas.
4. **`catalogo_modelos_llantas`:** Base de conocimiento de llantas del mercado con sus profundidades originales de fábrica para control de desgaste y autocompletado reactivo.
5. **`configuracion_clientes`:** Permite parametrizar umbrales personalizados de retiro de llantas por cliente (ej. 3.0 mm estándar vs. 4.0 mm para cargas pesadas).
6. **`usuarios`:** Control de acceso y roles (`admin` con permisos globales, `inspector` para captura en patio y `auditor` para consulta).

---

## 3. Ciclo de Vida de una Inspección

```mermaid
sequenceDiagram
    autonumber
    actor Inspector as Inspector de Patio (Móvil)
    participant UI as Interfaz Web (SPA)
    participant Offline as Storage Local
    participant API as FastAPI (server.py)
    participant Candados as Motor de Candados
    participant DB as SQLite (inspecciones.db)

    Inspector->>UI: Ingresa Placa y selecciona Rueda en Chasis
    UI->>API: GET /api/inspeccion-anterior?placa=...&posicion=...
    API->>DB: Consulta último registro de la rueda
    DB-->>API: Datos históricos (marca, prof_inicial, km)
    API-->>UI: Precarga automática de campos fijos

    Inspector->>UI: Digita profundidades (ext, cent, int) y PSI
    UI->>UI: Validación local rápida (R22.5 <= 27mm, prof <= prof_inicial)

    alt Conexión Activa (Online)
        UI->>API: POST /api/inspecciones (Payload JSON)
        API->>Candados: Evaluar los 6 Candados de Seguridad
        alt Candado Fallido
            Candados-->>API: Error (ej. "Odómetro regresivo")
            API-->>UI: HTTP 400 Bad Request + Mensaje explicativo
            UI-->>Inspector: Alerta visual en pantalla (Toast rojo)
        else Candados Aprobados
            Candados->>DB: INSERT en tabla inspecciones
            DB-->>API: Confirmación de ID
            API-->>UI: HTTP 200 OK
            UI-->>Inspector: Feedback sonoro/visual + Avance a siguiente llanta
        end
    else Sin Conexión (Offline en Patio)
        UI->>Offline: Guardar en cola (tirecheck_offline_queue)
        UI-->>Inspector: Alerta: Guardado en MODO OFFLINE (Local)
        Note over UI, Offline: Al recuperar señal de red...
        UI->>API: POST /api/inspecciones por cada ítem encolado
        API->>DB: Inserción en lote tras validar candados
        UI->>Offline: Limpiar cola sincronizada
    end
```

---

## 4. Estrategia Offline-First

Para permitir que los inspectores técnicos trabajen en sótanos, patios remotos o zonas industriales sin cobertura celular:
1. **Detección de Red:** El frontend escucha continuamente los eventos nativos de JavaScript `window.addEventListener('online')` y `offline`, actualizando un indicador visual de estado de conectividad en el encabezado.
2. **Cola de Encolamiento Local:** Si `navigator.onLine === false` o la petición HTTP falla por timeout de red, el payload JSON se encapsula con una marca de tiempo y se almacena en `localStorage` bajo la clave `tirecheck_offline_queue`.
3. **Sincronización Transaccional:** En cuanto se restablece la conexión, el frontend vacía la cola enviando secuencialmente cada inspección al endpoint `POST /api/inspecciones`. Si una inspección ya había sido registrada previamente, el servidor responde informando duplicidad sin detener la sincronización de las demás.

---

## 5. Motor de Chasis Interactivo

El mapeo visual del chasis en [templates/index.html](file:///c:/Users/crist/OneDrive/Documentos/Tyre/TireAnalyze_Pro_Proyecto/templates/index.html) es completamente dinámico y reactivo:
- **Consulta de Esquema:** Al seleccionar una tipología en el formulario, se invoca `GET /api/esquema?tipologia=...`, que consulta el campo `esquema_json` de la base de datos.
- **Renderizado por Ejes:** Se crea la estructura visual de la viga central del chasis (`chassis-spine`), barras de suspensión según el tipo de eje (direccional, tracción o trailer) y las ruedas en sus lados izquierdo y derecho.
- **Micro-estados Visuales:**
  - `selected`: Rueda actualmente activa para captura (borde azul celeste y efecto de realce).
  - `inspected`: Rueda ya completada en la jornada actual (fondo con indicador verde check).
  - `tire-steer-left` / `tire-steer-right`: Inclinación visual direccional en ruedas delanteras.

---

## 6. Generación de Reportes Técnicos en Streaming

TireAnalyze Pro genera documentos PDF binarios en memoria mediante **ReportLab** a través de [pdf_generator.py](file:///c:/Users/crist/OneDrive/Documentos/Tyre/TireAnalyze_Pro_Proyecto/pdf_generator.py):
- **Plan de Mantenimiento Vehicular (`/api/informe-pdf/{placa}`):**
  - Encabezado corporativo, odómetro, cliente y fecha.
  - Semáforo general de estado del vehículo (Alerta Roja: cambio urgente, Amarilla: alineación/dual, Verde: en norma).
  - Diagrama de ruedas por eje con profundidades individuales, desgastes y presiones.
  - Matriz de acciones correctivas inmediatas y espacio para firma de auditoría.
- **Consolidado de Flota (`/api/informe-pdf-consolidado`):**
  - Resumen macro de la jornada para gerencia de flota.
  - Distribución porcentual de problemas encontrados (porcentaje de llantas en descarte, porcentaje con falla de presión).
  - Listado condensado de todas las unidades inspeccionadas con sus novedades.
