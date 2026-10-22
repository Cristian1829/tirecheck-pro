# 🛞 Prompt para Antigravity IDE (AGY): Implementación Integral de las 7 Bodegas, Taller en Patio y Hoja de Vida del Neumático (Life Sheet)

> **INSTRUCCIÓN DIRECTA PARA EL AGENTE DE CÓDIGO (ANTIGRAVITY IDE):**
> Actúa como un Arquitecto Principal de Software Full-Stack (FastAPI + SQLite + Pandas + ReportLab + Chart.js + Tailwind CSS). Tu objetivo es desplegar en **TireAnalyze Pro** la especificación técnica completa de **Las 7 Bodegas Especializadas**, el **Panel de Taller en Patio (`#seccionTallerPatio`)**, los **9 Flujos Operativos** y la **Hoja de Vida Completa del Neumático (Life Sheet)** en `database.py`, `server.py`, `pdf_generator.py` y `templates/index.html`.

---

## 1. Reglas Inquebrantables (Guardrails)

1. **Aislamiento de Base de Datos en Tests:** NUNCA modifiques ni ejecutes pruebas destructivas sobre `data/inspecciones.db`. Todas las pruebas en `pytest` deben usar el fixture `test_db` de `tests/conftest.py`.
2. **Adaptación de DDL a SQLite Idempotente:** Convierte los tipos `SERIAL PRIMARY KEY`, `VARCHAR` y `NUMERIC` a sintaxis nativa SQLite (`INTEGER PRIMARY KEY AUTOINCREMENT`, `TEXT`, `REAL`) dentro de `inicializar_bd()` en `database.py`, usando `CREATE TABLE IF NOT EXISTS` y migración automática de columnas con `PRAGMA table_info`.
3. **Serialización JSON Segura y Autenticación:** Envuelve todas las respuestas de los nuevos endpoints en `server.py` con `sanitizar_nativos()` y protébelos con `Depends(obtener_usuario_actual)`, respetando el aislamiento multi-cliente (`cliente_asignado`).

---

## 2. Esquema Relacional y Topología de las 7 Bodegas en `database.py`

### 2.1 Estados Canónicos de Bodega (`estado_actual`)

Implementa la máquina de estados exacta con estos 8 valores permitidos en `llantas_maestro.estado_actual`:
* `'Bodega_1_Nuevas'`: Llantas 0 km con banda original de fábrica (stock compras, registra factura, precio unitario y proveedor).
* `'Bodega_2_Reutilizable'`: Stock de patio con profundidad remanente útil (desmontadas por rotación, nivelación de pachas o recién retornadas de reencauche/reparación, listas para montar).
* `'Bodega_3_Reencauche'`: En alistamiento de despacho a renovadora (desmontadas al llegar a milímetros de retiro con carcasa sana).
* `'Bodega_4_EnPlanta'`: En planta externa de renovado / en tránsito bajo custodia del proveedor reencauchador.
* `'Bodega_5_Reparacion'`: En vulcanizadora por pinchazo, fuga, sección o parche reparable.
* `'Bodega_6_Garantia'`: Garantías en trámite por falla prematura atribuible a fabricación.
* `'Bodega_7_FVU'`: Fin de Vida Útil / Chatarra / Desecho definitivo.
* `'Montada'`: Actualmente instalada y rodando en un vehículo (`placa_actual`, `posicion_actual`).

### 2.2 Creación de las 4 Tablas en `inicializar_bd()` (`database.py`)

Agrega en `inicializar_bd()` las siguientes 4 tablas relacionales y sus índices:

```sql
-- 1. TABLA MAESTRA DE LA CARCASA / LLANTA
CREATE TABLE IF NOT EXISTS llantas_maestro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_interno TEXT NOT NULL,
    numero_serie_dot TEXT DEFAULT '',
    marca_origen TEXT NOT NULL DEFAULT '',
    diseno_origen TEXT NOT NULL DEFAULT '',
    dimension TEXT NOT NULL DEFAULT '295/80R22.5',
    tipo_construccion TEXT DEFAULT 'Radial',
    indice_carga_velocidad TEXT DEFAULT '',
    precio_compra_inicial REAL DEFAULT 0.0,
    prof_inicial_nueva REAL DEFAULT 16.0,
    proveedor_factura TEXT DEFAULT '',

    -- Estado Actual en Flota
    estado_actual TEXT NOT NULL DEFAULT 'Bodega_1_Nuevas',
    placa_actual TEXT DEFAULT NULL,
    posicion_actual INTEGER DEFAULT 0,
    tipo_eje_actual TEXT DEFAULT '',
    prof_actual_min REAL DEFAULT 0.0,
    psi_actual REAL DEFAULT 100.0,
    km_montaje_actual REAL DEFAULT 0.0,

    -- Tracking Planta / Garantía / Taller
    proveedor_planta TEXT DEFAULT '',
    guia_remision_planta TEXT DEFAULT '',
    transportador_planta TEXT DEFAULT '',
    fecha_envio_planta TEXT DEFAULT NULL,
    fecha_compromiso_planta TEXT DEFAULT NULL,
    dictamen_garantia TEXT DEFAULT '',
    pct_reconocido_garantia REAL DEFAULT 0.0,
    valor_reconocido_garantia REAL DEFAULT 0.0,

    -- Métricas Consolidadas de Vida
    ciclo_actual INTEGER DEFAULT 1,
    km_acumulados_total REAL DEFAULT 0.0,
    costo_reencauches_total REAL DEFAULT 0.0,
    costo_reparaciones_total REAL DEFAULT 0.0,
    cpk_acumulado_global REAL DEFAULT 0.0,

    -- Propiedad y Ubicación
    cliente_propietario TEXT NOT NULL DEFAULT '',
    subcliente_sede TEXT DEFAULT 'Principal',
    fecha_alta TEXT DEFAULT CURRENT_DATE,
    fecha_ultimo_movimiento TEXT DEFAULT CURRENT_DATE,
    fecha_baja TEXT DEFAULT NULL,
    motivo_baja TEXT DEFAULT NULL,
    foto_baja TEXT DEFAULT '',
    mm_desperdiciados_fvu REAL DEFAULT 0.0,
    dinero_perdido_fvu REAL DEFAULT 0.0,
    UNIQUE(cliente_propietario, numero_interno)
);

-- 2. TABLA DE HISTÓRICO DE CICLOS DE VIDA (ORIGINAL, R1, R2, R3...)
CREATE TABLE IF NOT EXISTS llantas_ciclos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_interno TEXT NOT NULL,
    cliente_propietario TEXT NOT NULL DEFAULT '',
    numero_ciclo INTEGER NOT NULL DEFAULT 1,
    tipo_ciclo TEXT NOT NULL DEFAULT 'Original', -- 'Original', 'Reencauche 1', 'Reencauche 2'
    proveedor_banda TEXT DEFAULT '',
    diseno_banda TEXT DEFAULT '',
    prof_inicial_ciclo REAL NOT NULL DEFAULT 16.0,
    prof_final_ciclo REAL DEFAULT NULL,
    km_inicial_ciclo REAL DEFAULT 0.0,
    km_final_ciclo REAL DEFAULT NULL,
    km_recorridos_ciclo REAL DEFAULT 0.0,
    costo_ciclo REAL DEFAULT 0.0,
    cpk_ciclo REAL DEFAULT 0.0,
    factura_renovado TEXT DEFAULT '',
    fecha_inicio_ciclo TEXT DEFAULT CURRENT_DATE,
    fecha_fin_ciclo TEXT DEFAULT NULL,
    estado_ciclo TEXT DEFAULT 'En_Servicio' -- 'En_Servicio', 'Cerrado_Por_Retiro', 'Desechado'
);

-- 3. TABLA DE LOG DE MOVIMIENTOS Y TRANSACCIONES DE TALLER
CREATE TABLE IF NOT EXISTS llantas_movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_movimiento TEXT DEFAULT CURRENT_TIMESTAMP,
    numero_interno TEXT NOT NULL,
    cliente_propietario TEXT NOT NULL DEFAULT '',
    tipo_movimiento TEXT NOT NULL,
    -- 'COMPRA_INGRESO', 'MONTAJE', 'DESMONTE', 'ROTACION',
    -- 'ENVIO_REENCAUCHE', 'RETORNO_REENCAUCHE', 'ENVIO_REPARACION',
    -- 'RETORNO_REPARACION', 'RECLAMO_GARANTIA', 'BAJA_FVU'
    bodega_origen TEXT DEFAULT '',
    bodega_destino TEXT DEFAULT '',
    placa_origen TEXT DEFAULT '',
    posicion_origen INTEGER DEFAULT 0,
    placa_destino TEXT DEFAULT '',
    posicion_destino INTEGER DEFAULT 0,
    odometro_vehiculo REAL DEFAULT 0.0,
    profundidad_momento REAL DEFAULT 0.0,
    psi_momento REAL DEFAULT 0.0,
    costo_asociado REAL DEFAULT 0.0,
    motivo TEXT DEFAULT '',
    usuario_responsable TEXT NOT NULL DEFAULT 'admin'
);

-- 4. TABLA DE HISTÓRICO DE NOVEDADES FÍSICAS EN CARCASA
CREATE TABLE IF NOT EXISTS llantas_novedades_registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_deteccion TEXT DEFAULT CURRENT_DATE,
    numero_interno TEXT NOT NULL,
    cliente_propietario TEXT NOT NULL DEFAULT '',
    tipo_novedad TEXT NOT NULL,
    categoria_severidad TEXT DEFAULT 'Operativa', -- 'Permanente', 'Operativa'
    estado_novedad TEXT DEFAULT 'Activa',         -- 'Activa', 'Reparada', 'Condenatoria_FVU'
    placa TEXT DEFAULT '',
    posicion INTEGER DEFAULT 0,
    observacion TEXT DEFAULT '',
    foto_url TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_llantas_maestro_num ON llantas_maestro(numero_interno, cliente_propietario);
CREATE INDEX IF NOT EXISTS idx_llantas_maestro_estado ON llantas_maestro(cliente_propietario, estado_actual);
CREATE INDEX IF NOT EXISTS idx_llantas_maestro_placa_pos ON llantas_maestro(placa_actual, posicion_actual, estado_actual);
CREATE INDEX IF NOT EXISTS idx_llantas_ciclos_num ON llantas_ciclos(numero_interno, numero_ciclo);
CREATE INDEX IF NOT EXISTS idx_llantas_mov_num ON llantas_movimientos(numero_interno, fecha_movimiento DESC);
```

### 2.3 Backfill Automático desde `inspecciones` (`sincronizar_hoja_vida_desde_inspecciones`)

Crea en `database.py` una función que se ejecute al final de `inicializar_bd()` y al insertar/actualizar una inspección en patio:
* Si un `numero_interno` registrado en `inspecciones` aún no existe en `llantas_maestro`, crea automáticamente su registro maestro (`estado_actual = 'Montada'`, `placa_actual = placa`, `posicion_actual = posicion`), su ciclo inicial en `llantas_ciclos` (`numero_ciclo = 1` si `vida == 'ORIGINAL'` o `2` si es `'REENCAUCHE'`) y su movimiento inicial `'MONTAJE'`, además de registrar cualquier novedad no vacía en `llantas_novedades_registro`.
* Si ya existe en `llantas_maestro` y está `'Montada'`, actualiza su `prof_actual_min`, `psi_actual` y kilómetros acumulados según el odómetro más reciente.

---

## 3. Implementación de los 9 Flujos Operativos en `database.py`

Implementa en `database.py` las funciones transaccionales para cubrir los 9 flujos exactos de la especificación:

1. **Flujo 1 — Ingreso de Llantas Nuevas Individual o en Lote (`crear_llantas_stock(datos: dict) -> dict`):**
   * Soporta `modo = 'individual'` (`numero_interno`) o `modo = 'lote'` (`prefijo`, `numero_inicial`, `cantidad`, ej. `LL-1050` a `LL-1059`).
   * Valida que ningún `numero_interno` exista previamente para ese `cliente_propietario`.
   * Inserta cada llanta en `llantas_maestro` con `estado_actual = 'Bodega_1_Nuevas'`, `prof_actual_min = prof_inicial_nueva`, `ciclo_actual = 1`.
   * Crea el Ciclo 1 (`tipo_ciclo = 'Original'`, `banda = 'Banda Original Fábrica'`, `costo_ciclo = precio_compra_inicial`) en `llantas_ciclos` y el evento `'COMPRA_INGRESO'` en `llantas_movimientos`.

2. **Flujo 2 — Desmonte Directo desde Inspección de Patio o Bodegas (`desmontar_llanta_taller(datos: dict) -> dict`):**
   * Mapea alias cortos (`'reutilizable'` $\rightarrow$ `'Bodega_2_Reutilizable'`, `'reencauche'` $\rightarrow$ `'Bodega_3_Reencauche'`, `'planta'` $\rightarrow$ `'Bodega_4_EnPlanta'`, `'reparacion'` $\rightarrow$ `'Bodega_5_Reparacion'`, `'garantia'` $\rightarrow$ `'Bodega_6_Garantia'`, `'fvu'` / `'chatarra'` $\rightarrow$ `'Bodega_7_FVU'`) o el código canónico directo.
   * Si la llanta estaba `'Montada'`, calcula el recorrido del tramo:
     $$\Delta \text{Km} = \max(0.0,\; \text{odometro\_vehiculo} - \text{km\_montaje\_actual})$$
     $$\text{km\_acumulados\_total} = \text{km\_acumulados\_total} + \Delta \text{Km}$$
     $$\text{km\_recorridos\_ciclo} = \text{km\_recorridos\_ciclo} + \Delta \text{Km}$$
   * Libera la posición (`placa_actual = None`, `posicion_actual = 0`), actualiza `estado_actual = bodega_destino`, `prof_actual_min = profundidad`, `fecha_ultimo_movimiento = CURRENT_DATE` e inserta el evento `'DESMONTE'` en `llantas_movimientos`.
   * Si el destino es `'Bodega_7_FVU'`, aplica la lógica del **Flujo 8** (cálculo automático de `mm_desperdiciados_fvu` y `dinero_perdido_fvu`).

3. **Flujo 3 — Montaje Directo en Patio desde Stock o Nueva Directa (`montar_llanta_taller(datos: dict) -> dict`):**
   * Soporta **Opción A (Desde Stock B1/B2 por `llanta_id` o `numero_interno`)** y **Opción B (Llanta Nueva Directa en patio: si no existe en `llantas_maestro`, la da de alta primero y luego la monta)**.
   * **Candado Vial:** Si `es_posicion_direccional(tipologia, posicion)` es verdadero y la llanta tiene `ciclo_actual > 1`, bloquea el montaje con error claro.
   * **Desmonte automático de ocupante previa:** Si en `(cliente_propietario, placa, posicion)` ya hay otra llanta con `estado_actual == 'Montada'`, la desmonta automáticamente hacia `'Bodega_2_Reutilizable'` registrando su evento `'DESMONTE'`.
   * Actualiza la llanta entrante a `estado_actual = 'Montada'`, `placa_actual = placa`, `posicion_actual = posicion`, `km_montaje_actual = odometro_vehiculo`, registra `'MONTAJE'` en `llantas_movimientos` y retorna el objeto `llanta` (`numero_interno`, `marca`, `diseno`, `dimension`, `vida`, `prof_inicial`, `profundidad_actual`) para autocompletar el formulario de patio.

4. **Flujo 4 — Despacho en Lote a Planta de Reencauche (`despachar_lote_planta_reencauche(datos: dict) -> dict`):**
   * Recibe `numeros_internos: list[str]`, `proveedor_planta`, `guia_remision`, `transportador`, `fecha_compromiso`.
   * Actualiza todas las llantas seleccionadas de `'Bodega_3_Reencauche'` a `'Bodega_4_EnPlanta'` e inserta el evento `'ENVIO_REENCAUCHE'` en `llantas_movimientos`.

5. **Flujo 5 — Recepción desde Planta y Apertura de Nuevo Ciclo (`recepcionar_llanta_reencauchada(datos: dict) -> dict`):**
   * Cierra el ciclo activo en `llantas_ciclos` (`fecha_fin_ciclo`, `prof_final_ciclo`, `estado_ciclo = 'Cerrado_Por_Retiro'`, `cpk_ciclo = costo_ciclo / max(1.0, km_recorridos_ciclo)`).
   * Crea nuevo ciclo en `llantas_ciclos` con `numero_ciclo = ciclo_anterior + 1`, `tipo_ciclo = f"Reencauche {ciclo_anterior}"`, `proveedor_banda`, `diseno_banda`, `prof_inicial_ciclo = prof_banda_nueva`, `costo_ciclo = costo_factura_renovado`, `estado_ciclo = 'En_Servicio'`.
   * Actualiza `llantas_maestro`: `ciclo_actual = ciclo_anterior + 1`, `prof_actual_min = prof_banda_nueva`, `costo_reencauches_total += costo_factura_renovado`, `estado_actual = 'Bodega_2_Reutilizable'` e inserta `'RETORNO_REENCAUCHE'` en `llantas_movimientos`.

6. **Flujo 6 — Finalizar Reparación / Vulcanizado (`finalizar_reparacion_bodega5(datos: dict) -> dict`):**
   * Recibe `numero_interno`, `tipo_trabajo` (`Parche radial`, `Sección vulcanizada`, `Cambio de válvula`), `costo_reparacion`, `proveedor`.
   * Marca novedades activas de esa carcasa en `llantas_novedades_registro` como `'Reparada'`, suma `costo_reparaciones_total += costo_reparacion` (y al costo del ciclo activo), traslada la llanta a `'Bodega_2_Reutilizable'` e inserta `'RETORNO_REPARACION'`.

7. **Flujo 7 — Dictamen Técnico de Garantía (`procesar_dictamen_garantia_bodega6(datos: dict) -> dict`):**
   * Recibe `numero_interno`, `dictamen` (`'Aprobada'` o `'Rechazada'`), `pct_reconocido`, `valor_nota_credito`.
   * Actualiza `dictamen_garantia`, `pct_reconocido_garantia` y `valor_reconocido_garantia` en `llantas_maestro`, traslada la carcasa a `'Bodega_7_FVU'` recalculando `dinero_perdido_fvu` descontando la nota de crédito, e inserta `'RECLAMO_GARANTIA'`.

8. **Flujo 8 — Chatarrización y Cálculo Financiero FVU (`dar_baja_fvu_bodega7(datos: dict) -> dict`):**
   * Calcula:
     $$\text{mm\_desperdiciados\_fvu} = \max(0.0,\; \text{prof\_retiro} - \text{limite\_retiro})$$
     $$\text{dinero\_perdido\_fvu} = \max\left(0.0,\; \left(\text{mm\_desperdiciados\_fvu} \times \frac{\text{costo\_ciclo\_actual}}{\max(1.0,\; \text{prof\_inicial\_ciclo} - \text{limite\_retiro})}\right) - \text{valor\_reconocido\_garantia}\right)$$
   * Cierra el ciclo en `llantas_ciclos` como `'Desechado'`, pasa `estado_actual = 'Bodega_7_FVU'`, guarda `motivo_baja`, `fecha_baja = CURRENT_DATE` e inserta `'BAJA_FVU'`.

9. **Flujo 9 — Hoja de Vida Completa (`obtener_hoja_vida_llanta(numero_interno: str, cliente: str = "") -> dict`):**
   * Retorna exactamente el esquema JSON de la sección 4 del documento:
     * `numero_interno`, `dot`
     * `ficha_tecnica`: `{marca, diseno, dimension, precio_compra, fecha_alta, cliente}`
     * `estado_actual`: `{estado, placa, posicion, tipo_eje, prof_min_actual, psi_actual, ciclo_vida}`
     * `metricas_consolidadas`: `{km_totales, costo_total_invertido, cpk_global, rendimiento_km_mm, ahorro_generado_vs_nueva}`
     * `desglose_por_ciclos`: lista de ciclos con `{ciclo, tipo, prof_inicial, prof_final, km_recorridos, costo, cpk, banda}`
     * `historial_movimientos`: lista cronológica `{fecha, evento, detalle}`
     * `curva_desgaste`: puntos `{"fecha", "km", "prof_mm"}` combinando inspecciones y eventos de montaje/reencauche para graficar los dientes de sierra (`Original` $\rightarrow$ `R1` $\rightarrow$ `R2`).
     * `novedades_carcasa`: registros de `llantas_novedades_registro`.

---

## 4. Catálogo de Endpoints REST en `server.py` y Reportes PDF en `pdf_generator.py`

Agrega en `server.py` los siguientes endpoints autenticados:

1. **`GET /api/taller/posicion-info`**:
   * Query params: `placa`, `posicion`, `cliente`.
   * Retorna `{"placa": ..., "posicion": ..., "llanta_instalada": {...} | None, "stock_disponible": [...]}` filtrando en `stock_disponible` las llantas del cliente en `'Bodega_1_Nuevas'` y `'Bodega_2_Reutilizable'` (si la posición es direccional, excluye reencauchadas de `stock_disponible`).
2. **`POST /api/taller/desmontar`**:
   * Ejecuta `database.desmontar_llanta_taller(datos)` y retorna `{"status": "ok", "message": ..., "bodega_nombre": ...}`.
3. **`POST /api/taller/montar`**:
   * Ejecuta `database.montar_llanta_taller(datos)` y retorna `{"status": "ok", "message": ..., "llanta": {...}}`.
4. **`POST /api/llantas-crear-stock`** (y alias `POST /api/bodegas/ingreso-compra`):
   * Ejecuta `database.crear_llantas_stock(datos)` para ingreso individual o por lote consecutivo.
5. **`GET /api/bodegas/inventario`**:
   * Lista las llantas de `llantas_maestro` con cálculo de `dias_en_bodega`, filtrando por `cliente`, `subcliente`, `estado_actual` (`Todas` o cualquiera de las 7 bodegas / `Montada`), `dimension` y búsqueda `q`, más el resumen de conteo y valorización para las **8 tarjetas KPI superiores** (`Total Llantas`, `B1 Nuevas`, `B2 Reutilizables`, `B3 Reencauche`, `B4 En Planta`, `B5 Reparación`, `B6 Garantía`, `B7 Chatarra`).
6. **`POST /api/bodegas/despacho-planta`**: Ejecuta el Flujo 4 (Bodega 3 $\rightarrow$ Bodega 4).
7. **`POST /api/bodegas/retorno-reencauche`**: Ejecuta el Flujo 5 (Bodega 4 $\rightarrow$ Bodega 2).
8. **`POST /api/bodegas/finalizar-reparacion`**: Ejecuta el Flujo 6 (Bodega 5 $\rightarrow$ Bodega 2).
9. **`POST /api/bodegas/dictamen-garantia`**: Ejecuta el Flujo 7 (Bodega 6 $\rightarrow$ Bodega 7).
10. **`GET /api/llanta/hoja-vida/{numero_interno}`**: Retorna el JSON completo de la Hoja de Vida (Life Sheet).
11. **`GET /api/bodegas/pdf-despacho-planta`** y **`GET /api/bodegas/pdf-acta-chatarrizacion/{numero_interno}`**:
    * Implementa en `pdf_generator.py` la generación en ReportLab de la **Planilla Oficial de Despacho a Planta Renovadora** (con tabla de carcasas y firmas de entrega/transportador) y el **Acta Oficial de Chatarrización FVU** (con milímetros desperdiciados, pérdida económica y causa raíz).

---

## 5. Arquitectura de Pantalla y Controladores JS en `templates/index.html`

1. **Panel de Taller en la Pestaña de Inspección de Patio (`#seccionTallerPatio`):**
   * Ubícalo en `#vista-patio` justo debajo del diagrama interactivo del chasis.
   * Muestra el badge de la posición activa (`#badgeTallerPos`), el detalle de la llanta instalada (`#txtTallerLlantaActual`) y los dos botones de acción rápida: **`[ 🔧 Desmontar a Bodega ]`** (abre `#modalTallerDesmontar`) y **`[ 🛞 Montar Llanta ]`** (abre `#modalTallerMontar` con Pestaña A *"Llantas en Stock / Bodega"* y Pestaña B *"Montar Nueva / Directa"*).
   * Conecta `seleccionarPosicion(p)` para que invoque automáticamente `actualizarPanelTallerPosicion(p)` y sincronice la información de la rueda seleccionada.
   * Implementa las funciones exactas `actualizarPanelTallerPosicion(pos)`, `abrirModalDesmontarTaller()`, `ejecutarDesmontajeTallerPatio()` y `ejecutarMontajeTallerPatio()` (que autocompleta `numero_interno`, `marca`, `diseno`, `dimension`, `vida`, `prof_inicial`, `prof_ext`, `prof_cent`, `prof_int` al montar).

2. **Pestaña Principal del Módulo de Bodegas (`#vista-bodegas`):**
   * Agrega el botón de navegación `"Bodegas & Hoja de Vida"` en `.app-hd__nav`.
   * Incluye:
     * Cabecera con botón verde **`[ + Ingresar Llanta a Bodega ]`** (modal con radio `[ Individual ]` / `[ Lote Consecutivo ]`).
     * **8 Tarjetas KPI Resumen de Stock** (`Total Llantas`, `B1 Nuevas`, `B2 Reutilizables`, `B3 Reencauche`, `B4 En Planta`, `B5 Reparación`, `B6 Garantía`, `B7 Chatarra`).
     * Barra de filtros (`Cliente`, `Sede`, `Dimensión`, buscador `No. Interno / DOT`) y **Pestañas de Sub-Bodegas (Tabs)** con acciones contextuales en cada fila:
       * `[ 👁️ Hoja de Vida ]` en todas las filas.
       * `[ 🔧 Montar ]` en B1 y B2.
       * Checkboxes de selección + `[ 🚚 Despachar a Planta ]` en B3.
       * `[ ♻️ Recibir Renovada ]` en B4.
       * `[ 🛠️ Finalizar Reparación ]` en B5.
       * `[ 🛡️ Dictamen Garantía ]` en B6.
       * `[ 📄 Acta PDF ]` en B7.

3. **Modal de Hoja de Vida Completa (`#modalHojaVidaLlanta` / `abrirHojaVidaLlanta(numero_interno)`):**
   * Se abre desde el botón `[ 👁️ ]` en Bodegas o haciendo clic sobre cualquier `numero_interno` en **Base de Inspecciones** o **KPIs**.
   * Renderiza:
     * Encabezado con `numero_interno`, `DOT`, `Estado Actual`, `Marca`, `Diseño`, `Dimensión` y `Ciclo`.
     * 5 Tarjetas de Rendimiento (`Km Totales`, `Inversión`, `CPK Global`, `Rendimiento km/mm`, `Ahorro Reencauche vs Nueva`).
     * **Gráfico Interactivo Chart.js (`chartCurvaDesgasteHojaVida`):** Curva histórica de desgaste (`mm` vs `Km`) mostrando cada ciclo de vida.
     * **Tabla Comparativa de Ciclos de Vida** (`Original`, `Reencauche 1`, `Reencauche 2`...).
     * **Línea de Tiempo Cronológica Vertical (Timeline)** de movimientos y sección de **Novedades Físicas en Carcasa**.

---

## 6. Suite de Pruebas Automatizadas (`tests/test_bodegas_hoja_vida.py`)

Crea el archivo `tests/test_bodegas_hoja_vida.py` (usando `test_db` y `auth_client`) con estas 4 pruebas de extremo a extremo:

1. `test_ingreso_lote_bodega1_y_montaje_desmonte_patio`:
   * Crea un lote de 3 llantas (`LL-1050` a `LL-1052`) vía `POST /api/llantas-crear-stock`, consulta `GET /api/taller/posicion-info?placa=TPX067&posicion=3`, monta `LL-1050` vía `POST /api/taller/montar` verificando el autocompletado y luego la desmonta con `3.2 mm` hacia `'reencauche'` vía `POST /api/taller/desmontar`, comprobando que quede en `'Bodega_3_Reencauche'`.
2. `test_ciclo_completo_planta_reencauche_reparacion_y_garantia`:
   * Despacha `LL-1050` a `'Bodega_4_EnPlanta'`, la recibe renovada con banda `'Bandag BDL'` a `17.0 mm` y costo `$720.000` verificando que pase a `'Bodega_2_Reutilizable'` en `ciclo_actual == 2`. Prueba también el paso por `'Bodega_5_Reparacion'` (`+$120.000`) y un dictamen de garantía en `'Bodega_6_Garantia'`.
3. `test_endpoint_hoja_vida_json_exacto`:
   * Recrea el historial de `LL-1045` (`122.000 km` en `Original` a `$1.850.000` + `72.500 km` en `Reencauche 1` a `$720.000`) e invoca `GET /api/llanta/hoja-vida/LL-1045`, verificando `km_totales == 194500.0`, `costo_total_invertido == 2570000.0`, `len(desglose_por_ciclos) == 2` y los puntos de `curva_desgaste`.
4. `test_candado_direccional_y_desmonte_automatico_en_montaje`:
   * Verifica que una llanta reencauchada (`ciclo_actual == 2`) sea rechazada en Posición 1 direccional, pero permitida en Posición 3 de tracción, desmontando automáticamente a `'Bodega_2_Reutilizable'` cualquier llanta que estuviera ocupando esa posición.

Ejecuta `python -m pytest tests/ -v` y confirma que el 100% de las pruebas pasen en verde.