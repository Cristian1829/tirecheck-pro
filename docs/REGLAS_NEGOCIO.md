# Reglas de Negocio, Algoritmos y Fórmulas Técnicas - TireCheck Pro

Este documento especifica formalmente los fundamentos técnicos, los algoritmos predictivos y las fórmulas matemáticas que rigen la operación de **TireCheck Pro**.

---

## 1. Los 6 Candados de Seguridad Inquebrantables

Implementados en `database.validar_inspeccion_candados()`, estos candados actúan como barrera transaccional estricta tanto en capturas manuales, ediciones e importaciones masivas desde Excel.

### 🔒 Candado 1: Límite Máximo de Profundidad por Dimensión
- **Justificación Técnica:** Los estándares internacionales de fabricación de neumáticos de carga establecen que una llanta radial nueva de rin 22.5" no supera los 27.0 mm de profundidad de banda de rodamiento. Valores superiores indican error tipográfico o lectura defectuosa del profundímetro.
- **Regla:**
  $$\text{Si } \text{dimensión contiene } "22.5" \implies \max(p_{ext}, p_{cent}, p_{int}) \le 27.0\text{ mm}$$
  $$\text{Otras dimensiones} \implies \max(p_{ext}, p_{cent}, p_{int}) \le 32.0\text{ mm}$$
- **Acción ante violación:** Rechazo de la transacción con error: `"La profundidad (X mm) supera el límite máximo permitido (27.0 mm) para neumáticos R22.5."`

---

### 🔒 Candado 2: Límite por Profundidad Inicial de Diseño
- **Justificación Técnica:** Una llanta en servicio no puede poseer un remanente superior a su condición original de fabricación.
- **Regla:**
  $$\text{Si } prof\_inicial > 0 \implies \max(p_{ext}, p_{cent}, p_{int}) \le prof\_inicial$$
- **Acción ante violación:** Rechazo inmediato: `"La profundidad medida (X mm) no puede ser mayor a la profundidad inicial configurada (Y mm)."`

---

### 🔒 Candado 3: Duplicidad de Número Interno en Flota
- **Justificación Técnica:** Una llanta física (identificada unívocamente por su número de fuego / código interno) no puede estar físicamente montada en dos vehículos o posiciones simultáneamente dentro del mismo cliente o flota.
- **Regla:**
  $$\text{No existe } I_{prev} \text{ tal que } I_{prev}.numero\_interno = I.numero\_interno \land I_{prev}.cliente = I.cliente \land (I_{prev}.placa \ne I.placa \lor I_{prev}.posicion \ne I.posicion)$$
  *(Excluyendo la inspección en edición si aplica).*
- **Acción ante violación:** Rechazo con mensaje: `"El número interno LL-XXXX ya se encuentra registrado y activo en el vehículo PLACA en la posición POS."`

---

### 🔒 Candado 4: Frecuencia Mensual Única por Posición
- **Justificación Técnica:** Las auditorías de patio se realizan en ciclos mensuales de control de desgaste. Registrar dos inspecciones de la misma rueda en el mismo mes calendario distorsiona los cálculos de desgaste y proyección.
- **Regla:**
  $$\text{No existe } I_{prev} \text{ tal que } I_{prev}.placa = I.placa \land I_{prev}.posicion = I.posicion \land \text{Mes}(I_{prev}.fecha) = \text{Mes}(I.fecha)$$
- **Acción ante violación:** Rechazo con mensaje: `"El vehículo PLACA ya fue inspeccionado en la posición POS en el mes YYYY-MM."`

---

### 🔒 Candado 5: Odómetro No Regresivo
- **Justificación Técnica:** El kilometraje acumulado de un vehículo es una función monótona no decreciente en el tiempo. Un odómetro menor al histórico evidencia un error de digitación o adulteración del velocímetro.
- **Regla:**
  $$I.kilometraje \ge \max_{prev}(I_{prev}.kilometraje) \quad \forall I_{prev} \text{ de la misma } placa$$
- **Acción ante violación:** Rechazo con mensaje: `"El kilometraje actual (X km) no puede ser menor al de la última inspección registrada (Y km) para el vehículo PLACA."`

---

### 🔒 Candado 6: Desgaste No Negativo (Profundidad No Ascendente)
- **Justificación Técnica:** El remanente de hule disminuye con la rodadura. Si una llanta tenía 8.0 mm en su última inspección, no puede presentar 11.0 mm en la siguiente a menos que haya sido reencauchada o reemplazada (lo que requiere una nueva vida o modelo).
- **Tolerancia:** Se admite un margen de error humano de medición de hasta **1.0 mm**.
- **Regla:**
  $$\min(p_{ext}, p_{cent}, p_{int})_{actual} \le \min(p_{ext}, p_{cent}, p_{int})_{anterior} + 1.0\text{ mm}$$
- **Acción ante violación:** Rechazo con mensaje: `"La profundidad medida (X mm) es mayor a la de la inspección anterior (Y mm). El neumático no puede aumentar su hule sin un cambio de vida."`

---

## 2. Motor de Diagnóstico Predictivo de Flota

Ubicado en `database.analizar_inspecciones_df()` y `logica_inspeccion.py`, este motor evalúa las sábanas de datos para generar planes de acción automáticos por vehículo.

### 2.1 Alerta de Cambio Inmediato de Llanta
- **Condición:** Si la profundidad mínima de cualquiera de las llantas del vehículo es menor o igual al umbral de retiro configurado para el cliente (por defecto 3.0 mm, o el valor específico de `configuracion_clientes`).
  $$prof\_actual\_min \le limite\_retiro\_cliente$$
- **Acción:** `Plan_Cambio_Llanta = "SÍ"`, Detalle: `"Retirar llanta en Posición X (Remanente Y mm <= Z mm límite)"`.

---

### 2.2 Alerta de Alineación y Geometría en Ejes Directores
- **Condición:** En los ejes de dirección (típicamente posiciones 1 y 2, o 1 a 4 en vehículos 8x4), se comparan los remanentes entre la rueda izquierda y la rueda derecha.
  $$|\min(prof)_{izq} - \min(prof)_{der}| \ge 2.0\text{ mm}$$
- **Acción:** `Plan_Alineacion = "SÍ"`, Detalle: `"Diferencia de W mm entre directores (Pos X: Y mm vs Pos Z: K mm). Requiere alineación y balanceo"`.

---

### 2.3 Alerta de Duales Mal Apareados (Macheo de Llantas Dobles)
- **Condición:** En llantas duales (montadas en tándem interior/exterior en el mismo lado de un eje de tracción o remolque, ej. Pos 3-4, 5-6, 7-8, 9-10):
  1. **Disparidad de Desgaste:** Diferencia de remanente mayor o igual a 2.0 mm (la llanta con mayor hule asume el 80% de la carga dinámica, sobrecalentándose y fallando prematuramente).
     $$|prof_{interior} - prof_{exterior}| \ge 2.0\text{ mm}$$
  2. **Disparidad Dimensional:** Ruedas emparejadas con dimensiones o marcas de diámetro estático dispar.
- **Acción:** `Plan_Dual_Mal_Apareado = "SÍ"`, Detalle: `"Diferencia en dual Pos X-Y de W mm. Requiere rotación y apareamiento"`.

---

## 3. Fórmulas de Trazabilidad y KPIs de Rendimiento (CPK)

Implementadas en `database.obtener_trazabilidad_kpis_llanta()`:

| Indicador | Fórmula Matemática | Unidad | Descripción |
|---|---|---|---|
| **Profundidad Actual Mínima** | $P_{min} = \min(p_{ext}, p_{cent}, p_{int})$ | mm | Remanente crítico del surco más desgastado. |
| **Kilómetros Rodados** | $Km_{rodados} = Km_{actual} - Km_{montaje}$ | km | Distancia total recorrida por la llanta en su vida actual. |
| **Desgaste en Milímetros** | $\Delta mm = P_{inicial} - P_{min}$ | mm | Milímetros consumidos de banda de rodamiento. |
| **Porcentaje de Desgaste** | $\% = \left(\frac{\Delta mm}{P_{inicial} - Límite}\right) \times 100$ | % | Porcentaje consumido de la vida útil aprovechable. |
| **Rendimiento Km/mm** | $Km/mm = \frac{Km_{rodados}}{\Delta mm}$ | km/mm | Eficiencia kilométrica: cuántos km rinde cada milímetro de hule. |
| **Costo por Kilómetro (CPK Actual)** | $CPK = \frac{Precio}{Km_{rodados}}$ | $/km | Costo devengado por cada kilómetro recorrido hasta la fecha. |
| **Proyección Total de Kilómetros** | $Proy_{km} = (P_{inicial} - Límite) \times (Km/mm)$ | km | Kilometraje total estimado que rendirá la llanta al llegar a su límite de retiro. |
| **CPK Proyectado** | $CPK_{proy} = \frac{Precio}{Proy_{km}}$ | $/km | Costo unitario proyectado por kilómetro al final de la vida útil. |
| **Kilómetros Restantes** | $Km_{restantes} = (P_{min} - Límite) \times (Km/mm)$ | km | Vida útil remanente antes de requerir desmonte obligatorio. |

---

## 4. Semáforo Técnico de Profundidad de Llantas

| Nivel de Riesgo | Condición de Remanente | Código Color | Acción Operativa Obligatoria |
|---|---|---|---|
| 🟢 **Óptimo** | $P_{min} > 6.0\text{ mm}$ | `#10b981` (Verde) | Llanta en condiciones seguras de operación. |
| 🟡 **Precaución** | $3.5\text{ mm} < P_{min} \le 6.0\text{ mm}$ | `#f59e0b` (Ámbar) | Programar seguimiento en la siguiente inspección mensual. |
| 🔴 **Crítico / Retiro** | $P_{min} \le Límite\text{ (3.0 mm)}$ | `#ef4444` (Rojo) | **Desmonte inmediato.** Prohibido viaje en carretera por riesgo de explosión y sanción vial. |
