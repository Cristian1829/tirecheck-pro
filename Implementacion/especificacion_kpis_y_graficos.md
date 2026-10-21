# Guía Técnica de KPIs y Visualizaciones de Neumáticos (Para Implementación en Software Externo)

Este documento contiene la especificación funcional, matemática y técnica de los 20 Indicadores Clave de Desempeño (KPIs) del sistema de gestión de neumáticos de flotas comerciales. Diseñado para ser consumido e implementado directamente por un modelo de Inteligencia Artificial o un equipo de ingeniería de software.

---

## 1. Arquitectura de Datos de Entrada

Cualquier motor de cálculo de estos KPIs requiere las siguientes entidades relacionales mínimas:

```json
{
  "Inspeccion": {
    "id": "INTEGER",
    "fecha": "DATE (YYYY-MM-DD)",
    "placa": "VARCHAR(10)",
    "posicion": "INTEGER (1 a 24)",
    "numero_interno": "VARCHAR(50)",
    "marca": "VARCHAR(50)",
    "diseno": "VARCHAR(50)",
    "dimension": "VARCHAR(30)",
    "vida": "ENUM('Original', 'Reencauche')",
    "prof_ext": "FLOAT (mm)",
    "prof_cent": "FLOAT (mm)",
    "prof_int": "FLOAT (mm)",
    "psi": "FLOAT",
    "kilometraje": "FLOAT (km vehículo)",
    "novedades": "VARCHAR(255)",
    "cliente": "VARCHAR(100)",
    "subcliente": "VARCHAR(100)",
    "tipo_operacion": "VARCHAR(100)"
  },
  "LlantaMaestro": {
    "numero_interno": "VARCHAR(50) PRIMARY KEY",
    "precio_compra": "FLOAT",
    "costo_reencauches": "FLOAT",
    "costo_reparaciones": "FLOAT",
    "km_acumulados_total": "FLOAT",
    "ciclo_vida_actual": "INTEGER (1 = Original, 2 = 1er Reencauche, etc.)",
    "estado_actual": "ENUM('Montada', 'Stock_Bodega_1', 'Stock_Bodega_2', 'En_Reencauche', 'En_Reparacion', 'Garantia', 'Desecho_FVU')"
  }
}
```

---

## 2. Catálogo Detallado de KPIs

---

### KPI 01: Semáforo de Profundidades de Flota
* **Objetivo:** Monitorear el nivel de desgaste y seguridad de todas las llantas actualmente rodando en la flota.
* **Fórmula Matemática:**
  $$\text{Profundidad Mínima}(\text{Llanta}_i) = \min(\text{prof\_ext}_i, \text{prof\_cent}_i, \text{prof\_int}_i)$$
  $$\text{Categoría} = \begin{cases} 
  \text{Verde (Óptimo)}, & \text{si } \text{Prof Mínima} \ge 5.0\text{ mm} \\ 
  \text{Amarillo (Precaución)}, & \text{si } 3.0\text{ mm} < \text{Prof Mínima} < 5.0\text{ mm} \\ 
  \text{Rojo (Crítico / Retiro)}, & \text{si } \text{Prof Mínima} \le \text{Límite Retiro (ej. 3.0 mm)} 
  \end{cases}$$
* **Tipo de Gráfico Recomendado:** **Gráfico Donut / Torta (Doughnut Chart)** con contador central y desglose por ejes en **Gráfico de Barras Apiladas (Stacked Bar)**.
* **Paleta de Colores:** Verde (`#10b981`), Amarillo (`#f59e0b`), Rojo (`#ef4444`).
* **Interactividad UI:** Clic en el segmento rojo abre la lista de placas y posiciones que requieren cambio inmediato.

---

### KPI 02: Desgaste Promedio por Tipo de Eje
* **Objetivo:** Comparar la severidad del desgaste entre ejes Direccionales, Tracción y Libres (Tráiler).
* **Fórmula Matemática:**
  $$\text{Promedio Eje}_k = \frac{1}{N_k} \sum_{j=1}^{N_k} \text{prof\_min}_j$$
  Donde $k \in \{\text{Direccional}, \text{Tracción}, \text{Arrastre/Tráiler}\}$.
* **Tipo de Gráfico Recomendado:** **Gráfico de Radar (Spider/Radar Chart)** o **Barras Horizontales con Target Line (Bullet Chart)**.
* **Ejes / Dimensiones:**
  - Eje X: Milímetros remanentes (0 a 20 mm).
  - Eje Y: Tipo de Eje.
  - Línea de Referencia: Umbral de retiro legal y de reencauche (3.0 mm / 4.0 mm).

---

### KPI 03: Proyección de Desmonte de Llantas a 30, 60 y 90 Días
* **Objetivo:** Planificar compras de llantas nuevas y cupos de reencauche antes de que las llantas queden fuera de norma.
* **Fórmula Matemática:**
  $$\text{Tasa Desgaste (mm/km)}_i = \frac{\text{Prof Anterior}_i - \text{Prof Actual}_i}{\text{Km Actual} - \text{Km Anterior}}$$
  $$\text{Km Restantes}_i = \frac{\text{Prof Actual}_i - \text{Límite Retiro}}{\text{Tasa Desgaste}_i}$$
  $$\text{Días para Retiro}_i = \frac{\text{Km Restantes}_i}{\text{Km Diario Promedio de la Flota}}$$
* **Tipo de Gráfico Recomendado:** **Histograma / Barras por Rango de Tiempo (Bar Chart)**.
  - Columnas: `< 30 días`, `31 - 60 días`, `61 - 90 días`, `> 90 días`.
* **Uso Funcional:** Alimentar el módulo de compras MRP.

---

### KPI 04: Semáforo y Desviación de Presión de Inflado (PSI)
* **Objetivo:** Identificar pérdidas de combustible y desgaste prematuro por rodar con presión incorrecta.
* **Fórmula Matemática:**
  $$\Delta \text{PSI}_i = \frac{\text{PSI Leído}_i - \text{PSI Objetivo}_i}{\text{PSI Objetivo}_i} \times 100\%$$
  $$\text{Estado Presión} = \begin{cases}
  \text{Baja Severa (Peligro)}, & \text{si } \Delta \text{PSI} < -15\% \\
  \text{Baja Moderada}, & \text{si } -15\% \le \Delta \text{PSI} < -5\% \\
  \text{Correcta}, & \text{si } -5\% \le \Delta \text{PSI} \le +5\% \\
  \text{Sobrepresión}, & \text{si } \Delta \text{PSI} > +10\%
  \end{cases}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Dispersión / Campana de Gauss (Scatter Plot)** y **Gauge / Tacómetro**.
* **Impacto Económico Directo:** Una subpresión del 10% reduce en 9% la vida útil del neumático y aumenta el consumo de combustible en un 1.5%.

---

### KPI 05: Pérdida Económica por Desalineación (Desgaste Irregular de Hombros)
* **Objetivo:** Detectar fallas de convergencia, divergencia y camber en el eje direccional o en ejes de tráiler.
* **Fórmula Matemática:**
  $$\Delta \text{Hombros}_i = |\text{prof\_ext}_i - \text{prof\_int}_i|$$
  $$\text{Alerta Alineación} = \text{Verdadero si } \Delta \text{Hombros}_i \ge 2.0\text{ mm}$$
  $$\text{Pérdida Económica (\$) } = \Delta \text{Hombros} \times \text{Costo por mm de Caucho}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Barras Bidireccionales (Tornado Chart / Diverging Bar Chart)** mostrando lado Izquierdo vs Lado Derecho.

---

### KPI 06: Mal Apareo en Pachas (Duales) y Sobrecarga
* **Objetivo:** Evitar que en una rueda dual (pacha) una llanta soporte más del 70% del peso del eje debido a diferencias de diámetro.
* **Fórmula Matemática:**
  $$\Delta \text{Pacha}_{a,b} = |\text{prof\_min}_a - \text{prof\_min}_b|$$
  $$\text{Condición Mal Apareo} = \Delta \text{Pacha}_{a,b} > 2.5\text{ mm (o marcas/dimensiones diferentes)}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Cajas y Bigotes (Box Plot)** por Eje o **Heatmap Matricial** de diferencias.

---

### KPI 07: Plan de Rotación Tándem 6x4 (Equis Larga)
* **Objetivo:** Balancear el desgaste desigual entre el Eje Motriz 1 y el Eje Motriz 2 de cabezotes 6x4.
* **Fórmula Matemática:**
  $$\Delta \text{Tándem} = |\overline{\text{Prof}}_{\text{Eje Motriz 1}} - \overline{\text{Prof}}_{\text{Eje Motriz 2}}|$$
  Si $\Delta \text{Tándem} \ge 1.5\text{ mm}$, generar orden de rotación cruzada en equis:
  $$P3 \leftrightarrow P9, \quad P4 \leftrightarrow P10, \quad P5 \leftrightarrow P7, \quad P6 \leftrightarrow P8$$
* **Tipo de Gráfico Recomendado:** **Diagrama de Flujo / Esquema de Chasis Interactivo (SVG / Canvas)** con flechas animadas de intercambio.

---

### KPI 08: Índice de Reencauchabilidad de Carcasas
* **Objetivo:** Medir la calidad del mantenimiento de carcasas y el retorno de inversión en renovado.
* **Fórmula Matemática:**
  $$\text{Índice Reencauchabilidad} = \frac{\text{Llantas en Ciclo } \ge 2}{\text{Total de Llantas Activas}} \times 100\%$$
  $$\text{Factor de Reencauche} = \frac{\text{Total de Reencauches Ejecutados en la Historia}}{\text{Total de Carcasas Nuevas Compradas}}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Embudo (Funnel Chart)**:
  - Nivel 1: Llantas Nuevas Originales (100%).
  - Nivel 2: 1er Reencauche (ej. 75%).
  - Nivel 3: 2do Reencauche (ej. 45%).
  - Nivel 4: 3er Reencauche (ej. 15%).

---

### KPI 09: Costo por Kilómetro (CPK) por Marca y Modelo
* **Objetivo:** Definir con datos objetivos qué marca y modelo es la más rentable para la operación.
* **Fórmula Matemática:**
  $$\text{CPK Individual}_i = \frac{\text{Precio Compra}_i + \sum \text{Costos Reencauche}_i + \sum \text{Costos Reparaciones}_i}{\text{Kilómetros Totales Recorridos}_i}$$
  $$\text{CPK Flota (\$/km)} = \frac{\sum \text{Costos Totales Neumáticos}}{\sum \text{Km Recorridos por la Flota}}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Burbujas (Bubble Chart)**:
  - Eje X: Kilometraje total alcanzado.
  - Eje Y: CPK (\$/km) [menor es mejor].
  - Tamaño de la burbuja: Costo total de adquisición.
  - Color: Marca de la llanta.

---

### KPI 10: Rendimiento Kilométrico por Milímetro ($km/mm$)
* **Objetivo:** Conocer la tasa de rendimiento real del caucho de cada fabricante sin sesgo por profundidad de molde.
* **Fórmula Matemática:**
  $$\text{Rendimiento } (km/mm) = \frac{\text{Km Recorridos en el Ciclo}}{\text{Profundidad Inicial} - \text{Profundidad Actual}}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Barras Horizontales con Línea de Benchmark (Bullet Graph)**.

---

### KPI 11: Eficiencia de Retiro y Desperdicio de Milímetros
* **Objetivo:** Auditar si las llantas se retiran exactamente en el milímetro objetivo o si se envían carcasas con caucho útil a la basura.
* **Fórmula Matemática:**
  $$\text{mm Desperdiciados}_i = \max(0, \text{Profundidad Retiro}_i - \text{Límite Objetivo})$$
  $$\text{Costo Desperdiciado (\$)}_i = \text{mm Desperdiciados}_i \times \left( \frac{\text{Precio Llanta}}{\text{Profundidad Inicial} - \text{Límite Objetivo}} \right)$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Dispersión / Área Apilada** mostrando la pérdida monetaria acumulada en el mes.

---

### KPI 12: Composición y Matriz de Marcas/Diseños de la Flota
* **Objetivo:** Conocer la uniformidad del parque de neumáticos de la empresa.
* **Fórmula Matemática:**
  $$\% \text{ Participación Marca}_m = \frac{\text{Cantidad Llantas Marca}_m}{\text{Total Llantas Activas}} \times 100\%$$
* **Tipo de Gráfico Recomendado:** **Gráfico Treemap (Mapa de Árbol)** o **Sunburst** agrupado jerárquicamente: `Marca -> Dimensión -> Diseño`.

---

### KPI 13: Top Causas de Salida a Fin de Vida Útil (FVU / Chatarra)
* **Objetivo:** Diagnosticar si las bajas son por desgaste natural o por problemas operacionales en vía (cortes, impactos, rodado sin aire).
* **Fórmula Matemática:**
  $$\% \text{ Causa}_c = \frac{\text{Cantidad de Desechos por Causa}_c}{\text{Total Llantas en Bodega 7}} \times 100\%$$
* **Tipo de Gráfico Recomendado:** **Diagrama de Pareto (Pareto Chart: Barras ordenadas + Línea de % acumulado 80/20)**.

---

### KPI 14: Rotación y Permanencia de Stock en Bodegas
* **Objetivo:** Evitar capital inmovilizado y envejecimiento de neumáticos en almacén.
* **Fórmula Matemática:**
  $$\text{Días en Bodega}_i = \text{Fecha Actual} - \text{Fecha de Ingreso a la Bodega}_i$$
  $$\text{Promedio Días} = \frac{1}{N} \sum_{i=1}^N \text{Días en Bodega}_i$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Columnas con Semaforización por Antigüedad**:
  - `0 - 30 días` (Verde)
  - `31 - 90 días` (Amarillo)
  - `> 90 días` (Rojo - Stock Estancado)

---

### KPI 15: Cumplimiento del Plan de Mantenimiento Preventivo
* **Objetivo:** Medir la efectividad del taller en la ejecución de las tareas recomendadas.
* **Fórmula Matemática:**
  $$\% \text{ Cumplimiento} = \frac{\text{Órdenes de Mantenimiento Ejecutadas}}{\text{Órdenes Recomendadas Generadas}} \times 100\%$$
* **Tipo de Gráfico Recomendado:** **Gráfico Radial / Tacómetro semicircular (Gauge Chart)** con metas (ej. Meta 95%).

---

### KPI 16: Balance MRP de Bodegas vs Demanda Proyectada
* **Objetivo:** Prevenir quiebres de inventario para rotaciones y reemplazos.
* **Fórmula Matemática:**
  $$\text{Balance Neto} = (\text{Stock Bodega 1} + \text{Stock Bodega 2}) - \text{Llantas a Retirar en 30 Días}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Barras Comparativas (Stock Actual vs Necesidad Prevista)** por cada dimensión.

---

### KPI 17: Cobertura de Inspección Mensual de la Flota
* **Objetivo:** Garantizar que el 100% de los camiones y tráileres sean medidos en el ciclo mensual.
* **Fórmula Matemática:**
  $$\% \text{ Cobertura} = \frac{\text{Vehículos Inspeccionados con al menos 1 medición en el mes}}{\text{Total Vehículos en Padrón Activo}} \times 100\%$$
* **Tipo de Gráfico Recomendado:** **Barra de Progreso Linear (Progress Bar)** con desglose por Sede / Operación.

---

### KPI 18: Score Global de Salud de la Flota (0 a 100 Puntos)
* **Objetivo:** Número único sintético para la gerencia de operaciones.
* **Fórmula Matemática:**
  $$\text{Score} = (0.35 \times \text{Score Profundidad}) + (0.25 \times \text{Score Presión}) + (0.20 \times \text{Score Apareo}) + (0.20 \times \text{Score Alineación})$$
* **Tipo de Gráfico Recomendado:** **Tarjeta KPI de Gran Formato con Gráfico Sparkline de Tendencia Histórica de 12 Meses**.

---

### KPI 19: Ahorro Económico por Reencauche vs Compra Nueva
* **Objetivo:** Demostrar el retorno financiero de la política de renovado.
* **Fórmula Matemática:**
  $$\text{Ahorro Mensual (\$)} = \sum_{j \in \text{Reencauches}} (\text{Precio Promedio Llanta Nueva} - \text{Costo Reencauche}_j)$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Cascada (Waterfall Chart)** mostrando costo base, costos de renovación y ahorro neto consolidado.

---

### KPI 20: Tasa de Novedades Físicas en Carcasa por Cada 1,000 km
* **Objetivo:** Medir la severidad de las rutas y el cuidado de los conductores.
* **Fórmula Matemática:**
  $$\text{Tasa Novedades} = \frac{\text{Total Novedades Registradas (cortes, golpes, protuberancias)}}{\text{Km Recorridos por la Flota en el Periodo} / 1000}$$
* **Tipo de Gráfico Recomendado:** **Gráfico de Líneas Temporal (Time Series)** con banda de control estadístico (Media $\pm 2\sigma$).

---

## 3. Schema JSON de Respuesta para Backend / API de KPIs

```json
{
  "periodo": "2026-10",
  "cliente": "TRANSPORTES DE LA SIERRA",
  "total_inspecciones": 850,
  "vehiculos_evaluados": 72,
  "kpis": {
    "kpi_01_profundidades": {
      "verde_optimo": 620,
      "amarillo_precaucion": 180,
      "rojo_critico": 50,
      "porcentajes": {"verde": 72.94, "amarillo": 21.18, "rojo": 5.88}
    },
    "kpi_04_presiones": {
      "correcta": 690,
      "subpresion": 110,
      "sobrepresion": 50,
      "psi_promedio_flota": 102.4
    },
    "kpi_09_cpk_marcas": [
      {"marca": "MICHELIN", "cpk_promedio": 12.4, "km_promedio": 185000, "muestra": 320},
      {"marca": "BRIDGESTONE", "cpk_promedio": 13.8, "km_promedio": 168000, "muestra": 240},
      {"marca": "GOODYEAR", "cpk_promedio": 14.1, "km_promedio": 159000, "muestra": 180}
    ],
    "kpi_18_score_salud": {
      "score_actual": 88.5,
      "calificacion": "BUENO",
      "tendencia_mes_anterior": "+2.3"
    }
  }
}
```
