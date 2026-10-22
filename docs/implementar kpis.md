# 📊 Prompt Maestro para Antigravity IDE (AGY): Implementación de la Suite Analítica de 20 KPIs (5 Pestañas Homologadas) en Gráficos Modernos HD

> **INSTRUCCIÓN DIRECTA PARA EL AGENTE DE CÓDIGO (ANTIGRAVITY IDE):**
> Actúa como un Arquitecto Principal de Software Full-Stack y Especialista en Visualización de Datos BI (FastAPI + SQLite + Pandas + Chart.js v4 + `chartjs-plugin-datalabels` + Tailwind CSS). Tu objetivo es desplegar en **TireAnalyze Pro / TireCheck Pro** (`database.py`, `server.py` y `templates/index.html`) la especificación completa y exacta del **Manual Maestro de los 20 KPIs organizados en las 5 Pestañas Estándar Homologadas**, respetando los niveles de licencia **`LIGHT` (Operativo)** vs. **`FULL` / `PRO` (Financiero Integral)** y garantizando que todos los gráficos se vean **modernos, en Alta Definición (HD) y 100% entendibles sin textos superpuestos**.

---

## 1. Reglas Inquebrantables de Calidad Visual HD y Claridad de Gráficos

Para que cada uno de los 20 KPIs luzca como un dashboard ejecutivo de última generación y sea 100% legible tanto en monitor como en móvil, aplica obligatoriamente estas 7 reglas en Chart.js y Tailwind CSS:

1. **Renderizado Nítido en Alta Definición (Retina / 2x HD):**
   - Configura globalmente en Chart.js:
     ```javascript
     Chart.defaults.devicePixelRatio = Math.max(window.devicePixelRatio || 1, 2);
     Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
     Chart.defaults.color = '#475569';
     ```
2. **Cero Etiquetas Encimadas o Cortadas (*Data Pills Inteligentes*):**
   - Usa `chartjs-plugin-datalabels` con fondo tipo pastilla redondeada (`borderRadius: 5`, `padding: {top: 2, bottom: 2, left: 6, right: 6}`, `font: { weight: '800', size: 10 }`).
   - Agrega un margen superior extra (`layout: { padding: { top: 26, right: 16, bottom: 8, left: 8 } }`) y `grace: '15%'` en el eje `y` / `y1` para que ninguna etiqueta superior quede cortada por el borde del canvas.
   - Si una serie tiene más de 10 puntos en el eje X, muestra las etiquetas de datos de forma alternada (`(ctx.dataIndex % 2 === 0 || ctx.dataIndex === ctx.dataset.data.length - 1)`) o al pasar el cursor (`display: 'auto'`), evitando saturación visual.
3. **Gradientes Modernos y Bordes Suavizados:**
   - Todas las barras (`type: 'bar'`) deben usar `borderRadius: 6`, `borderSkipped: false` y rellenos con degradado vertical (`ctx.createLinearGradient(0, 0, 0, 280)`).
   - Todas las curvas (`type: 'line'`) deben usar `tension: 0.35`, `borderWidth: 2.8`, puntos con halo blanco (`pointBackgroundColor`, `pointBorderColor: '#fff'`, `pointBorderWidth: 2`, `pointRadius: 4`, `pointHoverRadius: 6`).
4. **Formato Numérico Colombiano Exacto (`es-CO`) y Unidades Claras:**
   - Miles con punto y decimales con coma: `1.143 llantas`, `78.403 km`, `5.226,9 km/mm`, `$ 320.066.913`, `93,3%`, `3,0 mm`.
   - Todo gráfico con doble eje (`y` izquierdo y `y1` derecho) debe mostrar título explícito en ambos ejes (`title: { display: true, text: '...' }`) y ocultar la grilla secundaria (`grid: { drawOnChartArea: false }`) para no cruzar líneas de fondo.
5. **Tooltips Ejecutivos Enriquecidos:**
   - Configura tooltips oscuros con efecto cristal (`backgroundColor: 'rgba(15, 23, 42, 0.94)'`, `titleFont: { size: 12, weight: 'bold' }`, `bodyFont: { size: 11 }`, `padding: 12`, `cornerRadius: 10`, `boxPadding: 5`) que expliquen el valor, la unidad y el porcentaje o brecha.
6. **Animación Fluida a 60 FPS:**
   - Usa animación escalonada en cascada: `animation: { duration: 850, easing: 'easeOutQuart', delay: (ctx) => (ctx.type === 'data' && ctx.mode === 'default') ? ctx.dataIndex * 35 : 0 }`.
7. **Controles de Visibilidad (Checkboxes) + Acciones por Tarjeta:**
   - Cada KPI debe contar con un checkbox/switch para mostrarlo u ocultarlo dinámicamente, un botón `[📷 PNG HD]` para descargar el gráfico en alta resolución y un subtítulo pedagógico de 1 línea que explique qué mide el indicador y cómo interpretarlo.

---

## 2. Estructura de Navegación Superior y las 5 Pestañas Homologadas (`#vista-kpis`)

Dentro de la sección `#vista-kpis` de `templates/index.html`, implementa:

### 2.1 Barra Permanente de Filtros Globales en Cascada (Arriba de las 5 Pestañas)
Sincroniza reactivamente todos los gráficos y tablas al cambiar cualquiera de estos 8 controles:
- **`Cliente`** (`filtroKpiCliente`)
- **`Sede / Subcliente`** (`filtroKpiSubcliente` — cargado en cascada según el cliente)
- **`Operación`** (`filtroKpiOperacion`)
- **`Tipología`** (`filtroKpiTipologia`)
- **`Marca`** (`filtroKpiMarca`)
- **`Dimensión`** (`filtroKpiDimension`)
- **`Eje Temporal`** (`filtroKpiEjeTemporal`: `"Por Mes (YYYY-MM)"` vs. `"Por Corte Consecutivo (INSP 1..N)"`)
- **`Conmutador de Licencia`** (`[ LIGHT (Operativo) | FULL / PRO (Financiero) ]`) + Botón **`[🔄 Actualizar]`** y **`[📥 Exportar Excel]`**.

### 2.2 Barra de las 5 Sub-Pestañas Estándar Homologadas

| Botón de Sub-Pestaña | Rango de KPIs | Nivel de Licencia | Comportamiento de Licencia |
| :--- | :---: | :---: | :--- |
| **1. 🚛 Inspección & Parque** | `KPI 01` al `KPI 04` | `LIGHT` / `FULL` | En `LIGHT` oculta el `KPI 01` (Padrón) y muestra `KPI 02`, `03` y `04`. En `FULL` muestra los 4. |
| **2. 🔧 Mantenimiento & Pérdida** | `KPI 05` al `KPI 11` | `LIGHT` / `FULL` | En `LIGHT` muestra `KPI 05` a `10` (sin cruce de Bodega 2 ni `$` en `KPI 11`). En `FULL` muestra del `05` al `11` completos con impacto en `$`. |
| **3. 📈 Producto & Proyecciones** | `KPI 12` al `KPI 16` | **SOLO `FULL`** | En `LIGHT` muestra badge `🔒 Exclusivo Licencia FULL` con vista previa bloqueada; en `FULL` despliega del `KPI 12` al `16`. |
| **4. ♻️ Tablero Bajas / FVU** | `KPI 17` al `KPI 19` | **SOLO `FULL`** | En `LIGHT` muestra badge `🔒 Exclusivo Licencia FULL`; en `FULL` despliega del `KPI 17` al `19`. |
| **5. 🏭 Balance 7 Bodegas MRP** | `KPI 20` | **SOLO `FULL`** | En `LIGHT` muestra badge `🔒 Exclusivo Licencia FULL`; en `FULL` despliega la Gran Matriz y Gráfico MRP (`KPI 20`). |

---

## 3. Especificación Matemática, Visual y de Layout de los 20 KPIs

Implementa en `database.py` la función `obtener_suite_completa_20_kpis(filtros: dict = None) -> dict` y exponla en `server.py` en `GET /api/kpis/suite-20` (protegida con `Depends(obtener_usuario_actual)` y `sanitizar_nativos()`), cumpliendo al 100% la disposición espacial y fórmulas del documento:

---

### 📂 PESTAÑA 1: Inspección General y Parque Vehicular (`KPI 01` al `KPI 04`)

#### **`KPI 01` — % Cumplimiento de Inspección vs. Parque Vehicular (`SOLO FULL`)**
- **Disposición en Pantalla:** Banner superior de ancho completo (`100% width`, `col-span-12`).
- **Tipo de Gráfico / UI:** Contador numérico de gran formato + **Barra de Progreso Lineal Reactiva** con gradiente púrpura/esmeralda (`from-indigo-600 via-blue-500 to-emerald-500`) + contador `Vehículos Auditados / Total Padrón Activo` + botón interactivo **`[📋 Placas Pendientes (N)]`**.
- **Fórmula:**
  $$\%\text{ Cumplimiento} = \left(\frac{\text{Vehículos Inspeccionados en el Mes}}{\max(1,\; \text{Total Vehículos Activos en Padrón})}\right) \times 100$$
- **Interactividad UI:** Al hacer clic en **`Placas Pendientes (N)`**, abre un modal emergente listando Placa, Sede, Tipología y Estado Operativo de los vehículos del padrón (`padron_vehiculos_cliente` / `catalogo_vehiculos`) que no tienen inspección en el mes de corte.

#### **`KPI 02` — Volumen Auditado Mes a Mes (Llantas vs. Vehículos) (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Fila 1, columna izquierda (`50% width`, `lg:col-span-6`), contenedor de `280px` de alto con badge resumen superior (`Promedio: X,X llantas/vehículo`).
- **Tipo de Gráfico:** **Gráfico Mixto Doble Eje** (`Barras Azules con gradiente` = Total Llantas `COUNT(id)`, `Línea Esmeralda con puntos` = Vehículos `COUNT(DISTINCT placa)`).
- **Interactividad UI:** Tooltip muestra Llantas, Vehículos y la razón exacta `Llantas / Vehículo` del mes.

#### **`KPI 03` — % de Reencauche (Meta 70%) y Unidades por Ciclo (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Fila 1, columna derecha (`50% width`, `lg:col-span-6`), subdividido internamente en **2 subpaneles gemelos**:
  - **Subpanel A:** Gráfica de Línea temporal de `% Reencauche` con línea horizontal punteada roja de **Umbral de Meta (`70%`)**.
  - **Subpanel B:** Gráfico de Barras Apiladas por Ciclo de Vida (`Original`, `R1`, `R2`, `R3+`).
- **Fórmula:**
  $$\%\text{ Reencauche} = \left(\frac{\text{Llantas Reencauchadas}}{\max(1,\; \text{Total Llantas Rodando})}\right) \times 100$$
- **Interactividad UI:** Badge dinámico de estado de meta: 🟢 **Verde** si $\ge 70\%$, 🟡 **Ámbar** entre $55\%$ y $69,9\%$, 🔴 **Rojo** si $< 55\%$.

#### **`KPI 04` — Composición de Flota: Tipología, Marca y Dimensión (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Bloque Fila 2 de ancho completo (`100% width`, `col-span-12`) con **cuadrícula interna de 3 columnas (`33%` c/u)**:
  1. **Columna A:** Barras Horizontales por **Tipología Vehicular**.
  2. **Columna B:** Barras Verticales por **Marca de Llanta**.
  3. **Columna C:** Gráfico **Donut (Doughnut)** interactivo por **Dimensión y Diseño** con porcentajes.
- **Interactividad UI:** Clic en un segmento de la dona filtra visualmente la dimensión seleccionada.

---

### 📂 PESTAÑA 2: Plan de Mantenimiento, Alineación y Costo de Pérdida (`KPI 05` al `KPI 11`)

#### **`KPI 05` — Cuadro de Cambios + Matriz Placa vs. Posición + Regla Direccional (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Bloque superior de ancho completo (`100% width`, `col-span-12`) estructurado en **2 niveles**:
  - **Nivel 1 (Arriba):** A la izquierda, **Tabla Cruzada Matricial `Dimensión vs. Eje`** (`Direccional`, `Tracción`, `Arrastre`, `Total`); a la derecha, **Gráfico de Barras de Retiros Mensuales**.
  - **Nivel 2 (Abajo):** **Gran Matriz de Calor (Heatmap) `Placa vs. Posición 1..12`** con scroll vertical y celdas coloreadas en 🔴 Rojo ($\le \text{mm\_retiro}$), 🟡 Amarillo ($\le \text{mm\_retiro} + 2.0\text{ mm}$) y 🟢 Verde ($> \text{mm\_retiro} + 2.0\text{ mm}$).
- **Fórmula y Regla Direccional:**
  - $\text{Requiere\_Cambio} = (\text{prof\_min} \le \text{mm\_retiro\_eje})$.
  - **Regla de Seguridad Vial de Par Direccional:** Si en el eje direccional (`Pos 1` o `Pos 2`) solo 1 llanta requiere cambio y la compañera tiene diferencia $> 3.0\text{ mm}$ frente a una nueva, se fuerza la solicitud de **2 llantas nuevas** para el eje y la compañera sana pasa a `Bodega 2 Recambio`.

#### **`KPI 06` — Seguimiento de Alineación y Rotar Dirección (Matriz de `mm` Perdidos) (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Fila de 2 columnas (`50% / 50%`):
  - **Izquierda:** Gráfico de **Barras 100% Apiladas Mensual** (`% Alineación OK` en Azul `#0ea5e9` vs. `% Mal Alineadas` en Rojo `#dc2626`).
  - **Derecha:** **Tabla Detallada de Pérdida por Placa** ordenada por severidad descendente (`Placa | Pos 1 mm perdidos | Pos 2 mm perdidos | Total mm | Pérdida $$ | Acción`).
- **Fórmula:**
  $$\text{Alerta\_Alineacion} = \vert{}\text{prof\_ext} - \text{prof\_int}\vert{} \ge \text{tolerancia\_desalineacion\_mm}\;\;(2.0\text{ mm})$$
  $$\text{Pérdida \$\$} = \text{mm\_perdidos\_hombro} \times \left(\frac{\text{Precio\_Llanta}}{\max(1.0,\; \text{prof\_inicial} - \text{mm\_retiro})}\right)$$

#### **`KPI 07` — Plan de Rotaciones Tándem (Equis Larga) y Tráiler (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Columna izquierda (`50% width`, `lg:col-span-6`, compartiendo fila con `KPI 08`).
- **Tipo de Gráfico / UI:** Tabla scrollable de Órdenes de Mantenimiento con esquema visual de intercambio **Equis Larga** (`P3 ↔ P9`, `P4 ↔ P10`, `P5 ↔ P7`, `P6 ↔ P8` cuando $\vert{}\overline{\text{Prof}}_{\text{Eje 1}} - \overline{\text{Prof}}_{\text{Eje 2}}\vert{} \ge 1.5\text{ mm}$) y jerarquía de tráiler (`Eje 2 < Eje 1 < Eje 3`), con badges de estado **`Solucionada`** (verde) vs. **`Reincidente`** (rojo si persistió desde la inspección anterior).

#### **`KPI 08` — Duales Mal Apareados ($> 3\text{ mm}$) + Cruce con Bodega 2 Recambio (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Columna derecha (`50% width`, `lg:col-span-6`, compartiendo fila con `KPI 07`).
- **Tipo de Gráfico / UI:** Arriba, **Gráfico de Barras Mensual de Frecuencia de Desapareo**; abajo, **Tarjetas Interactivas de Cruce con Bodega 2** que muestran para cada pacha afectada (`P3-P4`, `P5-P6`, `P7-P8`, `P9-P10`, `P11-P12` con $\Delta > 2.5\text{–}3.0\text{ mm}$) qué llanta disponible en `Bodega 2 Recambio` tiene la misma dimensión y milimetraje compatible ($\pm 1.5\text{ mm}$) para emparejarla de inmediato.

#### **`KPI 09` — Estado de Presiones (Donut PSI de 4 Segmentos) y Ahorro de Combustible (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Fila 4, columna izquierda (`50% width`, `lg:col-span-6`, compartida con `KPI 10`).
- **Tipo de Gráfico / UI:** **Gráfico Donut de 4 Segmentos** basado 100% en lectura real de PSI ($\Delta\text{PSI}\% = \frac{\text{PSI}_{\text{Leído}} - \text{PSI}_{\text{Obj}}}{\text{PSI}_{\text{Obj}}} \times 100$):
  1. `Baja Severa (< -15%)` — Rojo `#dc2626`
  2. `Baja Moderada (-15% a -5%)` — Ámbar `#f59e0b`
  3. `Correcta (±5%)` — Verde Esmeralda `#10b981`
  4. `Sobrepresión (> +10%)` — Azul Índigo `#6366f1`
- **Interactividad UI:** Badge superior de `% Calibración Correcta` y tarjeta inferior que calcula en tiempo real los **Galones de Combustible (ACPM/Diesel) Desperdiciados al Mes** (aplicando la regla técnica: por cada $10\%$ de subpresión promedio se pierde un $1,5\%$ adicional de combustible).

#### **`KPI 10` — Diagrama de Pareto de Novedades y Efectividad del Taller (`LIGHT & FULL`)**
- **Disposición en Pantalla:** Fila 4, columna derecha (`50% width`, `lg:col-span-6`, compartida con `KPI 09`).
- **Tipo de Gráfico / UI:** **Diagrama de Pareto Doble Eje Y**: Barras verticales ordenadas de mayor a menor frecuencia de novedad (eje Y izquierdo) + Línea curva de `% Acumulado 80/20` (eje Y derecho de $0\%$ a $100\%$) + Badge superior con **`% Efectividad de Solución del Taller`** ($\frac{\text{Novedades Resueltas}}{\text{Novedades Mes Anterior}} \times 100$).

#### **`KPI 11` — Impacto Económico Interanual (`Pérdida mm` y `Pérdida $$`) (`SOLO FULL`)**
- **Disposición en Pantalla:** Bloque de ancho completo (`100% width`, `col-span-12`) al cierre de la Pestaña 2.
- **Tipo de Gráfico / UI:** Header con 2 tarjetas financieras destacadas (`Total mm Perdidos` e `Impacto Económico Total $ COP`) + **Gráfico Mixto de 12 Meses** (`Barras de Milímetros Perdidos` en eje izquierdo + `Línea Naranja de Pérdida Monetaria en Pesos $` en eje derecho).
- **Fórmula:**
  $$\text{Pérdida Total \$\$} = \text{Pérdida\_Alineación\$\$} + \text{Pérdida\_Apareo\$\$} + \text{Pérdida\_Combustible\_PSI\$\$}$$

---

### 📂 PESTAÑA 3: Desempeño de Producto y CPK (`KPI 12` al `KPI 16`) — [`SOLO FULL`]

#### **`KPI 12` — Las 4 Tarjetas Maestras de Desempeño de Flota**
- **Disposición en Pantalla:** Grid superior de 4 tarjetas (`25% width` c/u, `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`):
  1. **`mm Gastados`** (Índigo): $\text{Prof\_Inicial} - \text{Prof\_Actual}$.
  2. **`Profundidad Actual`** (Verde Esmeralda): Promedio de $\text{prof\_min}$ en mm.
  3. **`% Desgaste con Micro-Barra de Tacómetro Dinámica`** (Ámbar/Semafórico): $\frac{\text{Prof\_Inicial} - \text{Prof\_Actual}}{\text{Prof\_Inicial} - \text{mm\_retiro}} \times 100$, con barra de progreso que cambia de verde a ámbar y rojo.
  4. **`Km Recorridos`** (Azul Cielo): Promedio de kilómetros recorridos en el ciclo actual.

#### **`KPI 13` — Km Rodados Reales vs. Proyección Final al Límite de Retiro**
- **Disposición en Pantalla:** Bloque de ancho completo (`100% width`, `col-span-12`, altura `280px`).
- **Tipo de Gráfico:** **Gráfico de Barras Apareadas / Comparativas**:
  - Barra sólida azul: `Km Reales Rodados`.
  - Barra translúcida celeste con borde punteado/sólido: `Proyección Final al Retiro`.
- **Fórmula:**
  $$\text{Proyección Km Final} = \text{Km\_Actual} + \left((\text{Prof\_Actual} - \text{mm\_retiro}) \times \frac{\text{Km\_Actual}}{\max(\text{mm\_gastados},\; 0.1)}\right)$$

#### **`KPI 14` — Tríada Multidimensional Sincronizada (`Proy Km`, `KM/mm`, `CPK $`)**
- **Disposición en Pantalla:** Bloque de ancho completo (`100% width`, `col-span-12`) con **Selector de Agrupación Dinámica en Cascada** en la cabecera + **Grid de 3 Gráficas Sincronizadas lado a lado (`33%` c/u)**:
  1. **Gráfica 1 (Índigo `#4f46e5`):** `Proyección Km Final`.
  2. **Gráfica 2 (Esmeralda `#10b981`):** `Rendimiento Km/mm` ($\frac{\text{Km\_Recorridos}}{\text{mm\_consumidos}}$).
  3. **Gráfica 3 (Púrpura `#9333ea`):** `Costo por Kilómetro (CPK $/km)` ($\frac{\text{Costo\_Total\_Llanta}}{\text{Proyección\_Km\_Final}}$).
- **Interactividad UI Obligatoria:** El selector superior permite reagrupar en vivo las 3 gráficas simultáneamente por:
  1. `Marca / Diseño`
  2. `Fecha / Mes`
  3. `Consecutivo de Inspección (INSP 1..N)`
  4. `Tipo de Eje (Direccional, Tracción, Arrastre)`
  5. `Tipología Vehicular`

#### **`KPI 15` — Potencial de Llanta: Proyección Promedio vs. Envolventes Máx y Mín**
- **Disposición en Pantalla:** Fila 4, columna izquierda (`50% width`, `lg:col-span-6`). Header con badge de **`% de Brecha frente al Máximo`**.
- **Tipo de Gráfico:** **Gráfico Mixto de Barras con Envolventes**:
  - Barras: `Promedio de Proyección (km)`.
  - Línea superior azul noche: `Máximo Alcanzado (km)`.
  - Línea inferior naranja: `Mínimo / Peor Desempeño (km)`.
- **Fórmula y Blindaje:** Solo computa llantas maduras con desgaste acumulado $\ge 1.5\text{ mm}$ para evitar sesgo de recién montadas.
  $$\text{Brecha \%} = \left(\frac{\text{Max\_Proyeccion} - \text{Promedio\_Proyeccion}}{\max(1.0,\; \text{Max\_Proyeccion})}\right) \times 100$$

#### **`KPI 16` — Curva de Proyección por Rango de Desgaste (Madurez del Caucho)**
- **Disposición en Pantalla:** Fila 4, columna derecha (`50% width`, `lg:col-span-6`).
- **Tipo de Gráfico:** **Gráfico de Columnas con Área Curva Escalonada de Fondo** en las **5 Bandas de Madurez Exactas**:
  1. `1. 0–40%`
  2. `2. 40.1–60%`
  3. `3. 60.1–80%`
  4. `4. 80.1–99.9%`
  5. `5. 100% Retiro`

---

### 📂 PESTAÑA 4: Tablero de Bajas / Fin de Vida Útil — FVU (`KPI 17` al `KPI 19`) — [`SOLO FULL`]

#### **`KPI 17` — Indicadores Globales FVU (Cantidad, I.R. y % Reencauche FVU)**
- **Disposición en Pantalla:** Bloque superior de ancho completo (`100% width`, `col-span-12`) con **3 tarjetas métricas en el header** (`Cantidad FVU`, `Índice de Reencauchabilidad I.R. FVU` y `% Reencauche FVU`) + **Gráfico de Líneas con Área Sombreada de 12 Meses**.
- **Fórmula:**
  $$\text{I.R. FVU} = \frac{\text{Total Ciclos Cumplidos de Llantas Muertas}}{\max(1,\; \text{Cantidad de Llantas Muertas})}$$
  $$\%\text{ Reencauche FVU} = \left(\frac{\text{Llantas Muertas en Ciclo } \ge 2}{\max(1,\; \text{Total Llantas Muertas})}\right) \times 100$$

#### **`KPI 18` — Participación FVU por Marca, Ciclo y Causal de Daño (+ Alerta de Garantías)**
- **Disposición en Pantalla:** Bloque Fila 2 de ancho completo con **cuadrícula de 3 columnas (`33%` c/u)**:
  1. **Columna A:** Gráfico de Barras Apiladas de **Bajas FVU por Marca**.
  2. **Columna B:** Gráfico de Barras Agrupadas por **Ciclo de Vida en que Falló** (`Original`, `R1`, `R2`, `R3+`).
  3. **Columna C:** Gráfico **Donut de Causales de Daño** (*Corte en costado, Separación de lonas, Impacto en banda, Fatiga de carcasa, Fin de vida útil normal*, etc.) + **Badge de Alerta Automática de Garantía** para carcasas dadas de baja con $< 30\%$ de desgaste.
- **Interactividad UI:** Al hacer clic en una causal de la dona, filtra cruzadamente las gráficas de marca y ciclo.

#### **`KPI 19` — Profundidad de Baja (`Máx / Prom / Mín`) y Dispersión por Milímetro**
- **Disposición en Pantalla:** Fila 3 de 2 columnas (`50% / 50%`):
  - **Izquierda:** **Gráfico de 3 Líneas Mensuales** de profundidad de desmonte (`Máximo`, `Promedio`, `Mínimo`).
  - **Derecha:** **Gráfico de Burbujas (`Bubble Chart`) de Dispersión por Milímetro (`0 a 20 mm`)**: Eje X = Milímetros al salir a FVU (`0..20 mm`), Eje Y = Costo perdido (`$`), Radio de burbuja = Cantidad de llantas retiradas en ese milímetro.
- **Fórmula:**
  $$\text{mm Desperdiciados} = \max(0,\; \text{Prof\_Baja} - \text{mm\_retiro\_cliente})$$
  $$\text{Dinero Perdido Scrap (\$)} = \text{mm Desperdiciados} \times \left(\frac{\text{Costo\_Llanta}}{\max(1.0,\; \text{mm\_utiles})}\right)$$

---

### 📂 PESTAÑA 5: Balance de Las 7 Bodegas y MRP (`KPI 20`) — [`SOLO FULL`]

#### **`KPI 20` — Matriz de Evaluación de Necesidades vs. Las 7 Bodegas (MRP)**
- **Disposición en Pantalla:** Bloque de ancho completo (`100% width`, `col-span-12`) con **Gráfico Superior de Barras Comparativas por Dimensión** (`Necesidad Bruta` vs. `Stock Disponible` vs. `Compra Neta Sugerida`) + **Gran Tabla Maestra MRP de 12 Columnas Codificadas por Color**:
  - Columnas de **Demanda** (encabezado rojo oscuro `#991b1b`): `Dimensión / Aplicación`, `Demanda Retiro Flota (con Par Dir.)`, `Reposición Bajas FVU`, `Margen Seguridad (15%)`, `NECESIDAD BRUTA TOTAL`.
  - Columnas de **Stock en Bodegas** (encabezado verde esmeralda `#065f46`): `Stock B1 (Nuevas)`, `Stock B2 (Recambio)`, `Stock B3 (En Planta x 0.90)`, `Stock B4 (Reenc. Listas)`, `STOCK DISPONIBLE TOTAL`.
  - Columnas de **Orden de Compra** (encabezado índigo vibrante `#3730a3`): `COMPRA NETA SUGERIDA` (desglosada en `Compra Nuevas Direccional` + `Compra Tracción / Reencauche`) y `Presupuesto Estimado ($ COP)`.
- **Fórmula Exacta del Manual:**
  $$\text{Necesidad Bruta} = \text{Demanda Flota} + \text{Bajas FVU} + \text{Margen Seguridad (15\%)}$$
  $$\text{Stock Disponible} = \text{Stock B1} + \text{Stock B2} + \lfloor \text{Stock B3} \times 0.90 \rfloor + \text{Stock B4}$$
  $$\text{COMPRA NETA SUGERIDA} = \max(0,\; \text{Necesidad Bruta} - \text{Stock Disponible})$$
- **Interactividad UI:** Botón **`[📥 Exportar Orden de Compra MRP a Excel]`** para descargar la planilla lista para el área de compras.

---

## 4. Suite de Pruebas Automatizadas (`tests/test_suite_20_kpis_manual.py`)

Crea el archivo `tests/test_suite_20_kpis_manual.py` usando `test_db` y `auth_client` con estas 4 pruebas de verificación:
1. **`test_estructura_5_pestanas_y_20_kpis_completos(test_db, auth_client)`:**
   - Siembra vehículos en padrón, inspecciones de varios meses y registros en bodegas/FVU.
   - Llama a `GET /api/kpis/suite-20` y verifica que retorne `HTTP 200` con los 20 objetos (`kpi_01` a `kpi_20`), comprobando que ninguno contenga `NaN` ni `Infinity`.
2. **`test_kpi14_triada_agrupacion_dinamica(test_db, auth_client)`:**
   - Verifica que `GET /api/kpis/suite-20?agrupar_kpi14=marca`, `fechas`, `inspeccion`, `eje` y `tipologia` devuelvan las 3 series sincronizadas (`proyeccion_km`, `km_mm`, `cpk`) correctamente calculadas.
3. **`test_kpi15_filtro_madurez_y_kpi20_formula_mrp(test_db, auth_client)`:**
   - Comprueba que una llanta recién montada con `0.2 mm` de desgaste no distorsione el máximo de `KPI 15` (filtro `>= 1.5 mm`), y que la ecuación del `KPI 20` aplique el factor `0.90` a `Bodega 3` y el margen de seguridad del `15%`.
4. **`test_licenciamiento_light_vs_full(test_db, auth_client)`:**
   - Verifica que el endpoint y el frontend respeten la visibilidad de indicadores según la matriz `LIGHT` (`KPI 02` a `10`) vs. `FULL` (`KPI 01` a `20`).

Ejecuta `python -m pytest tests/ -v` y confirma que el 100% de las pruebas pasen en verde.