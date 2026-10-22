# 📊 Prompt para Antigravity IDE (AGY): Implementación de la Pestaña «Composición de Flota» (Versión 3.5 Enterprise Actualizada)

> **INSTRUCCIÓN DIRECTA PARA EL AGENTE DE CÓDIGO (ANTIGRAVITY IDE):**
> Actúa como un Arquitecto Principal Full-Stack y Especialista en Visualización de Datos BI (FastAPI + SQLite + Pandas + Chart.js v4 + Tailwind CSS). Tu objetivo es desplegar en **TireAnalyze Pro / TireCheck Pro** (`database.py`, `server.py` y `templates/index.html`) la nueva pestaña principal **«Composición de Flota» (`#vista_composicion` / `#vista-composicion`)** siguiendo al 100% la especificación técnica, matemática y visual del **Manual Técnico y Funcional Completo de Composición de Flota v3.5 Enterprise (Versión Actualizada)**, garantizando que esté disponible tanto en **Modo Light** como en **Modo Full** y opere de forma reactiva en memoria con `0 ms` de latencia.

---

## 1. Reglas Inquebrantables (Guardrails)

1. **Aislamiento de Base de Datos en Tests:** NUNCA modifiques ni ejecutes pruebas destructivas sobre `data/inspecciones.db`. Todas las pruebas en `pytest` deben usar el fixture `test_db` de `tests/conftest.py`.
2. **Compatibilidad de Licencias:** Esta pestaña debe ser 100% funcional y visible tanto en **Modo LIGHT** como en **Modo FULL / PRO**.
3. **Gráficos HD Nítidos y Sin Etiquetas Superpuestas:** Usa `devicePixelRatio >= 2`, leyendas enriquecidas con porcentajes directos (ej. `MICHELIN (38.5%)`), tooltips oscuros tipo cristal y formato numérico claro.
4. **Las 3 Reglas Especiales del Motor de Cálculo (Sección 7 del Manual Actualizado):**
   - **División por Cero Protegida:** Si `totalLlantas == 0`, todos los porcentajes deben retornar exactamente `'0.0%'` y las tarjetas de marcas/dimensiones/diseños deben mostrar `'—'` evitando `NaN`, `Infinity` o caídas de ejecución.
   - **Tratamiento de Llantas de Repuesto:** Las llantas en posición de repuesto (`tipo_eje === 'repuesto'` o `eje === 99`) **NO se suman** a los ejes operativos (`direccional`, `traccion` o `libre`) cuando se filtra por uno de ellos; solo se incluyen cuando el filtro de eje está en `'TODOS'` (*Todos los Ejes*).
   - **Normalización Estricta de Cadenas:** Marcas, diseños y dimensiones con diferencias de espacios o capitalización (ej. `'Michelin'`, `'MICHELIN '` y `'michelin'`) deben unificarse obligatoriamente mediante `.trim().toUpperCase()` tanto en el backend como en el agregador JS para evitar duplicidades espurias en filtros, tarjetas, gráficos y matriz.

---

## 2. Backend: Enriquecimiento de `tipo_eje` en `database.py` y `GET /api/kpis-llantas`

Según la Sección 2 y Sección 7 del manual actualizado, la pestaña consume `GET /api/kpis-llantas` obteniendo la última fotografía válida de cada neumático (`group.iloc[-1]` agrupado por `numero_interno` ordenado por `numero_interno, fecha ASC, id ASC`) e incluyendo el campo calculado **`tipo_eje`**.

### 2.1 Función `determinar_tipo_eje_posicion(tipologia: str, posicion: int, cache_esquemas: dict = None) -> str` en `database.py`
Implementa en `database.py` esta función siguiendo exactamente el algoritmo de la **Sección 7 (Clasificación Heurística de Tipo de Eje)**:
1. Consulta el esquema de la tipología (`obtener_esquema_tipologia(tipologia)` usando un diccionario de caché en memoria `cache_esquemas` para no repetir consultas SQLite en el bucle).
2. Si la posición coincide dentro de `esquema`, normaliza `eje_item.get('tipo', '')` y el `rol` de la posición:
   - Si `eje == 99` o contiene `'rep'` $\rightarrow$ retorna `'repuesto'`.
   - Si contiene `'dir'` $\rightarrow$ retorna `'direccional'`.
   - Si contiene `'trac'` $\rightarrow$ retorna `'traccion'`.
   - Si contiene `'lib'`, `'rem'`, `'arr'` o `'tra'` (trailer) $\rightarrow$ retorna `'libre'`.
3. **Fallback heurístico obligatorio** (cuando no coincida con un esquema):
   - Si `'trailer'` o `'remolque'` está en `tipologia.lower()` $\rightarrow$ retorna `'libre'`.
   - Si `'cuatro manos'` o `'8x4'` o `'biarticulado'` está en `tipologia.lower()` y `posicion in (1, 2, 3, 4)` $\rightarrow$ retorna `'direccional'`.
   - Si `posicion in (1, 2)` $\rightarrow$ retorna `'direccional'`.
   - En cualquier otro caso $\rightarrow$ retorna `'traccion'`.

### 2.2 Incluir `tipo_eje` y `tipologia` en `obtener_trazabilidad_kpis_llanta()` (`database.py`)
En `obtener_trazabilidad_kpis_llanta(numero_interno='', filtros=None)`:
- Asegúrate de incluir `tipologia` en el `SELECT` sobre `inspecciones`.
- Normaliza `marca`, `diseno` y `dimension` con `.strip().upper()`.
- Para cada llanta (`ultima = group.iloc[-1]`), calcula `tipo_eje = determinar_tipo_eje_posicion(ultima.get('tipologia', ''), ultima.get('posicion', 1), cache_esquemas)` y añade al diccionario de salida:
  - `'tipologia': str(ultima.get('tipologia', '') or '').strip().upper()`
  - `'tipo_eje': tipo_eje` (`'direccional'`, `'traccion'`, `'libre'`, `'repuesto'`)

---

## 3. Frontend: Nueva Pestaña «Composición de Flota» en `templates/index.html`

### 3.1 Botón en la Barra de Navegación Principal (`.app-hd__nav`)
Agrega en `.app-hd__nav` el botón de navegación para la nueva pestaña:
```html
<button type="button" onclick="navegarTab('composicion')" id="nav-btn-composicion" class="nav-tab-btn">
  <i style="--c:#06b6d4"></i>
  <span>Composición de Flota</span>
</button>
```
Actualiza `navegarTab(tabId)` para soportar tanto `'composicion'` como el contenedor `#vista-composicion` (con alias compatible `#vista_composicion`) y que, al activarse por primera vez, invoque automáticamente `cargarComposicionFlotaWeb()` si `cacheComposicionLlantas` está vacío (o `renderizarComposicionFlotaWeb()` si ya está cargado en memoria).

---

### 3.2 Estructura Visual de la Vista (`#vista-composicion`)

Construye la sección `<section id="vista-composicion" data-vista="vista_composicion" class="hidden max-w-7xl mx-auto px-4 py-4 space-y-5">` con los siguientes **5 bloques exactos del manual actualizado**:

#### Bloque 1: Cabecera Ejecutiva + Alertas de las 4 Reglas de Oro + Botón «Actualizar Composición»
- Título: **`Composición & Caracterización de Flota`** con subtítulo *"Radiografía estructural en tiempo real por condición de ciclo de vida, tipo de eje, marcas, estandarización dimensional y modelos de banda"*.
- Botón azul a la derecha: **`[ 🔄 Actualizar Composición ]`** (`onclick="cargarComposicionFlotaWeb(true)"`) que fuerza la recarga limpia de `GET /api/kpis-llantas` contra la base de datos, y botón **`[ 📥 Exportar Matriz Excel ]`** (`onclick="exportarComposicionExcel()"`).
- **Panel Dinámico de Auditoría ("Las 4 Reglas de Oro de Negocio" — Sección 8 del Manual):**
  1. **Regla de Oro 1 (Cero Reencauches en Eje Direccional):** Si existen llantas montadas en `tipo_eje === 'direccional'` cuya condición sea Reencauche (`% Reencauche en Dirección > 0.0%`), muestra una alerta roja crítica prominente: `🚨 REGLA DE ORO 1 INCUMPLIDA (Seguridad Vial): Se detectaron X llanta(s) reencauchada(s) en Eje Direccional (Y%). El estándar exige estrictamente 0.0%.` Si es `0.0%`, muestra un badge verde `✅ Regla de Oro 1 Cumplida: 0.0% Reencauches en Dirección`.
  2. **Regla de Oro 2 (Adopción de Renovado en Remolques y Tracción):** Muestra el indicador de madurez de reencauche en ejes libres (meta $> 70\%$) y en ejes de tracción (meta saludable entre $50\%$ y $65\%$).
  3. **Regla de Oro 3 (Índice de Dispersión Dimensional):** Si la `Dimensión Top` concentra menos del `70%` del inventario y existen más de `4` dimensiones activas, muestra una alerta preventiva ámbar advirtiendo **Dispersión Dimensional** y recomendando racionalización de medidas.
  4. **Regla de Oro 4 (Homogeneidad en Parejas Duales):** Indicador informativo que permite verificar en la tabla matriz la homogeneidad de modelos y medidas montadas.

#### Bloque 2: Los 7 Filtros Interactivos en Cascada (Sección 3 del Manual)
Cuadrícula horizontal responsive (`grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5`) con los **IDs exactos requeridos**:
1. **Cliente** (`id="filtro_comp_cliente"`): Filtra por empresa o `'TODOS'` (*Todos los Clientes*). Al cambiar, **repuebla en cascada** las Sedes, Marcas, Medidas y Diseños disponibles en ese cliente y ejecuta `renderizarComposicionFlotaWeb()`.
2. **Sede / Subcliente** (`id="filtro_comp_subcliente"`): Segmenta por base operativa, patio o sucursal específica.
3. **Tipo de Eje Global** (`id="filtro_comp_tipo_eje"`): Opciones: `TODOS` (*Todos los Ejes*), `direccional` (*Eje Direccional*), `traccion` (*Eje de Tracción*), `libre` (*Eje Libre / Remolque*). Filtra absolutamente toda la vista y **sincroniza automáticamente los 4 botones rápidos del Gráfico 1**.
4. **Condición / Vida** (`id="filtro_comp_vida"`): Opciones: `TODAS` (*Todas las Vidas*), `ORIGINAL` (*Solo Original / Nueva*), `REENCAUCHE` (*Solo Reencauchadas* — normalizando variantes como `'Reenc'`, `'1R'`, `'2R'`, `'3R'`, `'R1'`, `'R2'`).
5. **Marca** (`id="filtro_comp_marca"`): Lista única normalizada (`.trim().toUpperCase()`) y ordenada alfabéticamente de fabricantes registrados.
6. **Dimensión / Medida** (`id="filtro_comp_dimension"`): Lista normalizada de medidas (ej. `295/80R22.5`, `11R22.5`, `12R22.5`, `315/80R22.5`).
7. **Diseño de Banda** (`id="filtro_comp_diseno"`): Modelos comerciales de banda de rodamiento (ej. `KMAX S`, `G658`, `M726EL`, `X MULTI D`).
*(Incluye botón rápido `[Limpiar Filtros]` para restablecer los 7 selectores).*

#### Bloque 3: Las 6 Tarjetas Resumen de KPIs (*Scorecards* — Sección 4 del Manual)
Grid de 6 tarjetas (`grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3`):
1. **Total Llantas** (Fondo Oscuro `bg-slate-900 text-white`):
   - Valor principal (`#comp_kpi_total_llantas`): `totalLlantas` (ej. `842`).
   - Subtítulo (`#comp_kpi_total_vehiculos`): `X vehículo(s) activo(s)` calculado con `new Set(placas).size`.
2. **% Reencauche** (Gradiente Esmeralda `bg-gradient-to-br from-emerald-600 to-teal-700 text-white`):
   - Valor principal (`#comp_kpi_pct_reenc`): `pctReenc%` (ej. `54.2%`, o `0.0%` si `totalLlantas == 0`).
   - Subtítulo (`#comp_kpi_cnt_reenc`): `X llanta(s) reencauchada(s)`.
3. **% Original (Nueva)** (Gradiente Azul Cielo `bg-gradient-to-br from-sky-500 to-blue-700 text-white`):
   - Valor principal (`#comp_kpi_pct_orig`): `pctOrig%` (ej. `45.8%`, o `0.0%` si `totalLlantas == 0`).
   - Subtítulo (`#comp_kpi_cnt_orig`): `X llanta(s) originales`.
4. **Marca Principal** (Tarjeta Blanca Bordeada):
   - Valor principal (`#comp_kpi_top_marca`): `topMarca` (ej. `GOODYEAR`, o `'—'` si `totalLlantas == 0`).
   - Subtítulo (`#comp_kpi_sub_marca`): `X llantas (Y%)`.
5. **Dimensión Top** (Tarjeta Blanca Bordeada):
   - Valor principal (`#comp_kpi_top_dim`): `topDim` (ej. `295/80R22.5`, o `'—'` si `totalLlantas == 0`).
   - Subtítulo (`#comp_kpi_sub_dim`): `X llantas (Y%)`.
6. **Diseño Top** (Tarjeta Blanca Bordeada):
   - Valor principal (`#comp_kpi_top_diseno`): `topDis` (ej. `KMAX S`, o `'—'` si `totalLlantas == 0`).
   - Subtítulo (`#comp_kpi_sub_diseno`): `X llantas montadas (Y%)`.

#### Bloque 4: Los 4 Bloques Gráficos Analíticos en Chart.js HD (Sección 5 del Manual)
Cuadrícula de 2x2 (`grid-cols-1 lg:grid-cols-2 gap-5`):

1. **Gráfico 1: Condición / Vida de Llanta por Eje (`#chartCompVidaEje`)**
   - **Tipo:** `doughnut` (Anillo) con `cutout: '62%'`.
   - **Paleta:** Azul (`#3b82f6`) para `Original`, Esmeralda (`#10b981`) para `Reencauche`.
   - **Selector Integrado de Ejes en Cabecera:** 4 botones píldora interactivos:
     - `[Todos]` (`id="btn_eje_comp_TODOS"`, `onclick="seleccionarEjeRapidoComposicion('TODOS')"`)
     - `[Dirección]` (`id="btn_eje_comp_direccional"`, `onclick="seleccionarEjeRapidoComposicion('direccional')"`)
     - `[Tracción]` (`id="btn_eje_comp_traccion"`, `onclick="seleccionarEjeRapidoComposicion('traccion')"`)
     - `[Libre]` (`id="btn_eje_comp_libre"`, `onclick="seleccionarEjeRapidoComposicion('libre')"`)
   - Al hacer clic en cualquiera de estos 4 botones, sincroniza `#filtro_comp_tipo_eje` y actualiza toda la pantalla en menos de 15 ms.

2. **Gráfico 2: Participación por Marca — Top 7 (`#chartCompMarcas`)**
   - **Tipo:** `doughnut` (Anillo) con `cutout: '58%'`.
   - **Paleta Curada de 7 Colores:** Azul (`#2563eb`), Cian (`#06b6d4`), Verde (`#10b981`), Ámbar (`#f59e0b`), Violeta (`#8b5cf6`), Rosa (`#ec4899`) y Pizarra (`#64748b`).
   - **Leyenda Inferior con Porcentaje Directo:** Cada elemento de la leyenda incluye directamente el nombre y el porcentaje exacto: `MICHELIN (38.5%)`.

3. **Gráfico 3: Distribución por Dimensión — Top 6 (`#chartCompDimensiones`)**
   - **Tipo:** `pie` (Torta completa de $360^\circ$).
   - **Paleta Viva de 6 Colores:** Violeta (`#7c3aed`), Cian (`#0891b2`), Ámbar (`#d97706`), Esmeralda (`#059669`), Azul (`#1d4ed8`) y Fucsia (`#c026d3`).
   - Muestra el Top 6 de medidas montadas en la flota con etiquetas y leyenda enriquecida.

4. **Gráfico 4: Top Diseños de Rodamiento — Top 6 (`#chartCompDisenos`)**
   - **Tipo:** `bar` (Barra Vertical) con `borderRadius: 6`.
   - **Paleta:** Ámbar Intenso (`#f59e0b`) con bordes suaves y etiquetas superiores de cantidad y porcentaje.

#### Bloque 5: Tabla Matriz de Inventario y Participación Detallada (Sección 6 del Manual Actualizado)
Contenedor con scroll vertical (`max-h-[460px] overflow-y-auto custom-scroll`), **Cabecera Congelada (`sticky top-0 z-10 bg-slate-900 text-white`)**, **Contador Dinámico** en el encabezado de la tarjeta (`# badge_comp_combinaciones`: `"X combinaciones activas"`) y `tbody id="tbody_composicion_flota"` con microinteracción `hover:bg-slate-50 transition-colors`.

Agrupa las llantas filtradas en tuplas únicas $[\text{Marca} \times \text{Diseño} \times \text{Dimensión}]$, ordenadas descendentemente por `Total Llantas`, con estas **8 columnas exactas**:
1. **`Marca`** (Texto Mayúsculas en negrita, Alineación Izquierda, ej. `GOODYEAR`, `MICHELIN`)
2. **`Diseño`** (Texto, Alineación Izquierda, ej. `KMAX S`, `X MULTI D`)
3. **`Dimensión`** (Texto Monospace `font-mono`, Alineación Izquierda, ej. `295/80R22.5`)
4. **`Original`** (Entero en Azul `text-blue-600 font-bold`, Alineación Centro)
5. **`Reencauche`** (Entero en Verde `text-emerald-600 font-bold`, Alineación Centro)
6. **`Total Llantas`** (Entero Negrita en Gris Oscuro `text-slate-900 font-black`, Alineación Centro: $\text{Original} + \text{Reencauche}$)
7. **`% Part. Flota`** (Porcentaje en Índigo `text-indigo-600 font-extrabold`, Alineación Centro: $(\text{Total Combinación} / \text{Total Llantas Flota}) \times 100$ con 1 decimal, ej. `28.4%`)
8. **`Prof. Promedio`** (Decimal en $\text{mm}$ con semáforo visual, Alineación Centro: $\text{Prof\_Prom} = \left(\sum \text{prof\_actual\_min}_i\right) / K$ para las $K$ llantas de esa combinación con lectura válida $> 0$, ej. `11.8 mm`).

---

## 4. Funciones JavaScript Obligatorias en `templates/index.html`

Implementa de forma limpia y modular:
- `let cacheComposicionLlantas = [];`
- `let chartsComposicion = { vida: null, marca: null, dimension: null, diseno: null };`
- `function normalizarTextoComp(val, fallback = 'SIN ESPECIFICAR')`:
  - Retorna `String(val || '').trim().toUpperCase() || fallback`.
- `function esLlantaReencauchadaComp(vidaStr)`:
  - Retorna `true` si `String(vidaStr || '').toLowerCase()` contiene `'reenc'`, `'1r'`, `'2r'`, `'3r'`, `'4r'`, `'r1'`, `'r2'`, `'r3'` o `'renov'`.
- `async function cargarComposicionFlotaWeb(forzarRecarga = false)`:
  - Consulta `GET /api/kpis-llantas`, normaliza en memoria cada registro (`marca`, `diseno`, `dimension`, `cliente`, `subcliente`, `tipo_eje`), guarda la colección en `cacheComposicionLlantas`, puebla los selectores (`poblarFiltrosComposicionCascada()`) y ejecuta `renderizarComposicionFlotaWeb()`.
- `function alCambiarClienteComposicion()`:
  - Recalcula en cascada Sedes, Marcas, Medidas y Diseños disponibles para el cliente seleccionado y llama a `renderizarComposicionFlotaWeb()`.
- `function seleccionarEjeRapidoComposicion(tipoEje)`:
  - Sincroniza `#filtro_comp_tipo_eje`, actualiza el estado activo de los 4 botones rápidos sobre el Gráfico 1 y llama a `renderizarComposicionFlotaWeb()`.
- `function renderizarComposicionFlotaWeb()`:
  - Filtra `cacheComposicionLlantas` en un solo pase lineal $O(N)$ (excluyendo `tipo_eje === 'repuesto'` cuando se filtra por un eje operativo específico), evalúa las Reglas de Oro, actualiza las 6 tarjetas KPI (con protección contra división por cero cuando `totalLlantas === 0`), actualiza los 4 gráficos Chart.js y renderiza `#tbody_composicion_flota` junto con el contador `"X combinaciones activas"`.

---

## 5. Suite de Pruebas Automatizadas (`tests/test_composicion_flota.py`)

Crea el archivo `tests/test_composicion_flota.py` (usando `test_db` y `auth_client`) con estas 4 pruebas:
1. **`test_api_kpis_llantas_incluye_tipo_eje_heuristico_y_esquema(test_db, auth_client)`:**
   - Inserta inspecciones en un `Cabezote (6x4)` (Posición 1 direccional y Posición 3 tracción), en un `Trailer (3 Ejes - 12 Llantas)` (Posición 5 libre) y en un `Trailer (2 Ejes - 8 Llantas + Repuesto)` (Posición 9 repuesto).
   - Llama a `GET /api/kpis-llantas` y verifica que cada elemento retornado incluya `tipo_eje` con los valores exactos `'direccional'`, `'traccion'`, `'libre'` y `'repuesto'`.
2. **`test_normalizacion_marcas_y_calculos_matriz_composicion(test_db, auth_client)`:**
   - Inserta llantas con variantes `'Michelin'`, `'MICHELIN '` y `'michelin'`, unas `Original` y otras `Reencauche`, con profundidades `12.0` y `10.0 mm`.
   - Verifica que `GET /api/kpis-llantas` unifique todas bajo `'MICHELIN'` y calcule `prof_actual_min` excluyendo valores $\le 0$.
3. **`test_regla_de_oro_1_direccion_sin_reencauches(test_db, auth_client)`:**
   - Verifica que el candado y el filtro de `tipo_eje == 'direccional'` identifiquen el `0.0%` de reencauche en dirección en una flota saludable.
4. **`test_vista_composicion_presente_en_html(auth_client)`:**
   - Verifica que `GET /` retorne `HTTP 200` e incluya `#vista-composicion`, los 7 filtros (`filtro_comp_cliente` a `filtro_comp_diseno`), el contador de combinaciones activas, los 4 canvas de gráficos y `tbody_composicion_flota`.

Ejecuta `python -m pytest tests/ -v` y confirma que el 100% de las pruebas pasen en verde.