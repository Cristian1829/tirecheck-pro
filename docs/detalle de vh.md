# 🔧 Prompt para Antigravity IDE (AGY): Implementación de la Tabla «Detalle de Vehículos y Planes de Acción», Auto-Ajuste Interno y Matriz Semáforo (Versión 3.5 Enterprise)

> **INSTRUCCIÓN DIRECTA PARA EL AGENTE DE CÓDIGO (ANTIGRAVITY IDE):**
> Actúa como un Arquitecto Principal Full-Stack (FastAPI + SQLite + Pandas + Tailwind CSS). Tu objetivo es actualizar en **TireAnalyze Pro / TireCheck Pro** (`database.py`, `server.py` y `templates/index.html`) el módulo **«Diagnóstico & Planes de Mantenimiento» (`#vista-diagnostico` / `#vista_diagnostico`)** siguiendo al 100% la especificación técnica, algorítmica y visual del **Manual Técnico y de Fórmulas de Mantenimiento: Tabla «Detalle de Vehículos y Planes de Acción» v3.5 Enterprise**.

---

## 1. Reglas Inquebrantables (Guardrails)

1. **Aislamiento de Base de Datos en Tests:** NUNCA modifiques ni ejecutes pruebas destructivas sobre `data/inspecciones.db`. Todas las pruebas en `pytest` deben usar el fixture `test_db` de `tests/conftest.py`.
2. **Retrocompatibilidad de Llaves JSON:** En `analizar_inspecciones_df()`, conserva todas las llaves actuales (`Vehículo/Placa`, `Plan_Cambio_Llanta`, `Plan_Alineacion`, `Plan_Dual_Mal_Apareado`, `Detalle_Cambio`, `Detalle_Alineacion`, `Detalle_Dual`, etc.) para no romper `pdf_generator.py` ni tests previos, y añade las nuevas llaves requeridas por el manual (`Cant_Cambios`, `Cant_Proximas`, `Cant_Presiones`, `Plan_Rotacion`, `Badge_Rotacion`, `Detalle_Auto_Ajuste`, `Bloques_Recomendaciones`, `Llantas_Posiciones`).
3. **Exclusión Estricta de Lecturas Cero:** Si un surco reporta `0.0 mm`, calcula $P_{\min} = \min(\{p \in \{P_{\text{ext}}, P_{\text{cent}}, P_{\text{int}}\} \mid p > 0\})$ para no generar falsos retiros.
4. **Serialización JSON Segura:** Pasa siempre la salida de `/api/diagnostico` por `sanitizar_nativos()`.

---

## 2. Backend: Actualización de `database.py` y `GET /api/diagnostico` en `server.py`

### 2.1 Filtro por Rango de Fechas y Deduplicación en `obtener_todas_inspecciones()` y `analizar_inspecciones_df()`
1. En `server.py`, actualiza `GET /api/diagnostico` para aceptar los parámetros opcionales `fecha_desde: str = ""`, `fecha_hasta: str = ""` y `usuario: str = ""`:
   ```python
   @app.get("/api/diagnostico")
   def api_diagnostico(
       usuario: str = "",
       fecha_desde: str = "",
       fecha_hasta: str = "",
       usuario_actual: dict = Depends(obtener_usuario_actual)
   ):
   ```
   - Si se envían `fecha_desde` y/o `fecha_hasta`, filtra `df` por `substr(fecha, 1, 10) >= fecha_desde` y `substr(fecha, 1, 10) <= fecha_hasta` antes de invocar `database.analizar_inspecciones_df(df)`.
2. **Deduplicación Obligatoria (Fase 02 del Manual):**
   - Al inicio de `analizar_inspecciones_df(df_inspecciones)` en `database.py`, ordena el DataFrame por `['fecha', 'id']` de forma descendente (`ascending=[False, False]`) y ejecuta `.drop_duplicates(subset=['placa', 'posicion'], keep='first')`.
   - De este modo, el motor conserva **únicamente la última medición real vigente de cada posición** en cada chasis.

---

### 2.2 Los 7 Sub-Motores de Decisión y Fórmulas Matemáticas en `analizar_inspecciones_df()` (`database.py`)

Para cada vehículo (`placa, group`), calcula y evalúa los siguientes **7 algoritmos formales** (Sección 6 del Manual):

1. **Plan 1 — Retiro Inmediato (`Cambio YA`):**
   - $P_{\min} = \min(\{P_{\text{ext}}, P_{\text{cent}}, P_{\text{int}}\} > 0)$.
   - Condición: $0 < P_{\min} \le \text{Limite\_Retiro\_Cliente}$ (por defecto `3.0 mm` o el configurado en `configuracion_limites_retiro`).
   - Cuenta cuántas llantas cumplen la condición (`cant_cambios`) y registra posición y milímetros.

2. **Plan 2 — Regla Especial de Par Direccional:**
   - En las parejas direccionales (`(1, 2)` y, si es Cuatro Manos `8x4`, también `(3, 4)`):
   - Si **exactamente 1 llanta** del par tiene `Cambio YA` ($P_{\min} \le \text{Limite\_Retiro}$) y la llanta opuesta del mismo eje cumple:
     $$(P_{\text{ini\_opuesta}} - P_{\min\_\text{opuesta}}) \ge 3.0\text{ mm}$$
     (usando `prof_inicial` si es $> 0$, o `16.0 mm` por defecto):
   - Se ordena el cambio de **ambas llantas a nuevas** (`Ajuste Par Direccional: retirar también Pos X (Y mm) a Bodega 2 Recambio para mantener alturas gemelas en dirección`).

3. **Plan 3 — Próxima a Cambio (`Próximas`):**
   - Condición:
     $$\text{Limite\_Retiro} < P_{\min} \le (\text{Limite\_Retiro} + 2.0\text{ mm})$$
   - Cuenta cuántas llantas están en esta ventana preventiva (`cant_proximas`) y lista sus posiciones (`Detalle_Proximas`).

4. **Plan 4 — Alineación Direccional (`Alineación`):**
   - En posiciones direccionales (`Pos 1, 2` o `1..4` en `8x4`, y en tráileres):
     $$\Delta_{\text{Hombros}} = \vert{}P_{\text{int}} - P_{\text{ext}}\vert{} \ge 2.0\text{ mm}$$
   - Activa `Plan_Alineacion = "SÍ"` e incluye la prescripción: `"Pos X (dif Y mm): Rotar en el mismo rin + alineación"`.

5. **Plan 5 — Mal Apareo en Pachas (`Dual Parejas`):**
   - Para cada pareja dual `(Pos A, Pos B)` (`(3,4), (5,6), (7,8), (9,10)` en `6x4`; `(5,6), (7,8), (9,10), (11,12)` en `8x4`; `(1,2)..(11,12)` en tráiler):
     $$\Delta_{\text{Pacha}} = \vert{}P_{\min}(A) - P_{\min}(B)\vert{} > 2.5\text{ mm} \quad \text{o} \quad \text{Dimensión}(A) \ne \text{Dimensión}(B)$$
   - Activa `Plan_Dual_Mal_Apareado = "SÍ"`.

6. **Plan 6 — Rotación en Equis Larga (`Tracción 6x4 / 8x4`):**
   - En vehículos con doble eje motriz (`6x4`: `Eje 1 = Prom(P3..P6)`, `Eje 2 = Prom(P7..P10)`; `8x4`: `Eje 1 = Prom(P5..P8)`, `Eje 2 = Prom(P9..P12)`):
     $$\vert{}\text{Prom\_Eje1} - \text{Prom\_Eje2}\vert{} \ge 2.0\text{ mm}$$
   - Prescribe **Cruce en Equis Larga**: `Cruzar Pos 3↔9, 4↔10, 5↔7 y 6↔8` (o el equivalente en `8x4`).

7. **Plan 7 — Calibración de Presión (`PSI`):**
   - Para cada llanta con `psi > 0`, tomando $\text{PSI}_{\text{obj}} = 100.0$ (o el objetivo del eje si está parametrizado):
     $$\text{PSI}_{\min} = \text{PSI}_{\text{obj}} \times 0.90\;\;(-10\%), \qquad \text{PSI}_{\max} = \text{PSI}_{\text{obj}} \times 1.10\;\;(+10\%)$$
   - Si $\text{PSI} < \text{PSI}_{\min}$ o $\text{PSI} > \text{PSI}_{\max}$, incrementa `cant_presiones` y activa `Plan_Calibracion_PSI = "SÍ"`.

---

### 2.3 Motor Avanzado de Auto-Ajuste Interno (Sección 7 del Manual)

Implementa en `database.py` la función `calcular_auto_ajuste_chasis(group_df, t_veh: str, es_cuatro_manos: bool) -> dict` e intégrala dentro de `analizar_inspecciones_df()` aplicando las **4 Reglas Físicas de Optimización de Chasis**:

1. **Regla 1 — Direccionamiento en Eje Direccional:**
   - La llanta con mayor profundidad **SIEMPRE** debe ir en la **Posición 1 (Izquierda)** (y en `Pos 3` frente a `Pos 4` en `8x4`).
   - Si $P_{\min}(\text{Pos } 2) - P_{\min}(\text{Pos } 1) \ge 0.5\text{ mm}$, genera instrucción de Auto-Ajuste: `"Auto-Ajuste Dirección: Cruzar P1 ↔ P2 (mayor altura a Izquierda Pos 1)"`.
2. **Regla 2 — Mayor Altura al Exterior en Pachas Duales:**
   - En cada pacha dual (donde en el esquema estándar `Izquierda = (Ext, Int)` y `Derecha = (Int, Ext)`), verifica el rol `EXT` vs `INT` de cada pareja.
   - Si la llanta en posición `INT` supera a su compañera `EXT` en $\ge 0.5\text{ mm}$, o si reordenando las llantas no-direccionales del vehículo se corrige un mal apareo ($\Delta_{\text{Pacha}} \le 2.5\text{ mm}$), genera la instrucción de intercambio: `"Auto-Ajuste Pacha: Invertir Pos {p_int} ↔ Pos {p_ext} (mayor altura al Exterior)"`.
3. **Regla 3 — Jerarquía de Ejes en Tráiler 2 Ejes (`2E`):**
   - En remolques de 2 ejes (`8 llantas`), verifica que $\text{Prom}(\text{Eje 1 Delantero}) \le \text{Prom}(\text{Eje 2 Trasero})$. Si $\text{Prom}(\text{Eje 1}) - \text{Prom}(\text{Eje 2}) \ge 1.5\text{ mm}$, ordena: `"Auto-Ajuste Tráiler 2E: Pasar llantas de mayor altura al Eje 2 Trasero (Eje 1 < Eje 2)"`.
4. **Regla 4 — Jerarquía en Tráiler 3 Ejes (`Tridem 3E`):**
   - En remolques de 3 ejes (`12 llantas`), la jerarquía obligatoria de menor a mayor altura es:
     $$\text{Eje 2 Central (Menor)} < \text{Eje 1 Delantero (Intermedio)} < \text{Eje 3 Trasero (Mayor)}$$
   - Si los promedios actuales incumplen este orden por $\ge 1.5\text{ mm}$, genera la instrucción de reubicación entre ejes del tridem.

**Estado del Badge de la Columna 10 (`Badge_Rotacion`):**
- Si hay instrucciones de auto-ajuste interno $\rightarrow$ `"AUTO-AJUSTE"`
- Si hay rotación en Equis Larga o por desgaste irregular/escalonado $\rightarrow$ `"SÍ"`
- En caso contrario $\rightarrow$ `"OK"`

---

### 2.4 Mapa de Semáforos por Posición (`Llantas_Posiciones`) en cada Fila de `analizar_inspecciones_df()`

Para alimentar la **Matriz de Semáforos por Posición (Sección 8 del Manual)** sin hacer peticiones adicionales, incluye en cada diccionario de vehículo retornado por `analizar_inspecciones_df()` la llave `'Llantas_Posiciones'`:
- Diccionario o lista con las posiciones `1` a `12` (o hasta `max_pos` del vehículo) donde cada posición contiene:
  ```python
  {
      "posicion": int(pos_r),
      "prof_min": round(pb_r, 1),
      "numero_interno": str(r.get("numero_interno") or "").strip(),
      "psi": round(to_float(r.get("psi", 0)), 0),
      "dimension": str(r.get("dimension") or "").strip(),
      "semaforo": "ROJO" if (0 < pb_r <= limite_cambio_cliente) else (
          "AMARILLO" if (limite_cambio_cliente < pb_r <= limite_cambio_cliente + 2.0) else (
              "VERDE" if pb_r > (limite_cambio_cliente + 2.0) else "GRIS"
          )
      )
  }
  ```

---

## 3. Frontend: Rediseño de `#vista-diagnostico` en `templates/index.html`

Actualiza la sección `#vista-diagnostico` en `templates/index.html` manteniendo compatibilidad de alias para que funcionen tanto los nuevos IDs del manual como cualquier llamada existente:

### 3.1 Las 5 Tarjetas Resumen de Diagnóstico (*KPI Scorecards* — Sección 4 del Manual)
En la parte superior de `#vista-diagnostico`, despliega la cuadrícula de **5 tarjetas interactivas** (al hacer clic en cualquiera de ellas, filtra automáticamente la tabla por esa acción):
1. **Vehículos Evaluados** (Fondo Blanco, borde Slate):
   - Valor (`#cardDiagTotal` / `#diag_kpi_vehiculos`): `totalVeh` (`new Set(filtrados.map(r => r['Vehículo/Placa'])).size`).
   - Subtítulo: *"Unidades auditadas en corte"*.
2. **Llantas Retiro YA** (Borde y texto Rose `#e11d48`):
   - Valor (`#cardDiagCambio` / `#diag_kpi_retiro_ya`): `cantCambios` (Suma total de llantas con $P_{\min} \le \text{Limite\_Retiro}$ en los vehículos filtrados).
   - Subtítulo: *"Desmonte inmediato ($\le$ Límite)"*.
3. **Próximas Cambio** (Borde y texto Ámbar `#d97706`):
   - Valor (`#cardDiagProximas` / `#diag_kpi_proximas`): `cantProximas` (Suma total de llantas con $\text{Limite} < P_{\min} \le \text{Limite} + 2.0\text{ mm}$).
   - Subtítulo: *"Ventana preventiva (+2.0 mm)"*.
4. **Alineación & Dual** (Borde y texto Índigo `#4f46e5`):
   - Valor (`#cardDiagAlineacion` / `#diag_kpi_alineacion_dual`): `cantRotaciones` (Vehículos con desalineación $\ge 2.0\text{ mm}$, mal apareo $> 2.5\text{ mm}$ o rotación/auto-ajuste).
   - Subtítulo: *"Banco de alineación y auto-ajuste"*.
5. **Calibración Presión** (Borde y texto Azul `#2563eb`):
   - Valor (`#cardDiagPresion` / `#diag_kpi_presion`): `cantPresiones` (Total de llantas con desviación $> \pm 10\%$ de PSI).
   - Subtítulo: *"Desviación $> \pm 10\%$ PSI objetivo"*.

---

### 3.2 Los 6 Controles de Filtro Reactivos en Cabecera (Sección 3 del Manual)
Construye la barra de filtros con los **identificadores exactos del manual** (manteniendo sincronizados los alias previos si algún test los consulta):
1. **Búsqueda por Placa (`id="filtro_diag_busqueda"`, alias `filtroDiagPlaca`):** Input reactivo (`oninput="filtrarTablaDiagnostico()"`), soporta coincidencias parciales (ej. `'WMK'`).
2. **Selector de Cliente (`id="filtro_diag_cliente"`, alias `filtroDiagCliente`):** Lista única de empresas. Al cambiar, repuebla automáticamente Sedes y Tipos de Operación y actualiza el botón `Consolidado Flota PDF`.
3. **Sede / Subcliente (`id="filtro_diag_subcliente"`, alias `filtroDiagSede`):** Filtra por patio o sucursal operativa.
4. **Tipo de Operación (`id="filtro_diag_operacion"`, alias `filtroDiagOperacion`):** Segmenta según el perfil de carga.
5. **Rango de Fechas (`id="filtro_diag_fecha_desde"` y `id="filtro_diag_fecha_hasta"`):** Inputs tipo `date` que al cambiar invocan `cargarDiagnostico()` pasando `?fecha_desde=...&fecha_hasta=...` al endpoint `/api/diagnostico`.
6. **Filtro por Acción (`id="filtro_diag_accion"`, alias `filtroDiagAlerta`):**
   - Opciones exactas:
     - `Todos` (*Todas las Acciones*)
     - `Retiro Inmediato` (Vehículos con `Cant_Cambios > 0` / `Plan_Cambio_Llanta === 'SÍ'`)
     - `Próximas a Cambio` (Vehículos con `Cant_Proximas > 0`)
     - `Estado OK` (Vehículos sin alertas activas)
     - `Rotaciones` (Vehículos con `Badge_Rotacion === 'AUTO-AJUSTE'` o `'SÍ'`)
     - `Alineación` (Vehículos con `Plan_Alineacion === 'SÍ'`)
     - `Dual` (Vehículos con `Plan_Dual_Mal_Apareado === 'SÍ'`)
     - `Presión` (Vehículos con `Plan_Calibracion_PSI === 'SÍ'`)

---

### 3.3 Tabla Principal «Detalle de Vehículos y Planes de Acción» (`#tbody_diagnostico_web` / `#tbodyDiagnostico`)
Renderiza la tabla con cabecera congelada (`sticky top-0 z-10 bg-slate-900 text-white`) y exactamente las **12 columnas oficiales de la Sección 5 del Manual**:

| N° | Columna | Formato Visual en Celda |
| :-: | :--- | :--- |
| **1** | **Placa** | Texto Negrita `text-slate-900 font-black font-mono` (ej. `WMK941`) |
| **2** | **Cliente / Sede** | Razón social en negrita + sede entre paréntesis `text-slate-500` (ej. `LA SIERRA (MEDELLIN)`) |
| **3** | **Tipología** | Texto descriptivo del chasis + operación en sublínea sutil |
| **4** | **Inspeccionadas** | Entero centrado en badge gris/azul |
| **5** | **Límite Retiro** | Monospace centrado (ej. `3.0 mm`) |
| **6** | **Alineación** | Badge: `SÍ` (Ámbar `bg-amber-100 text-amber-800`) u `OK` (Verde `bg-emerald-50 text-emerald-700`) |
| **7** | **Dual Parejas** | Badge: `SÍ` (Púrpura `bg-purple-100 text-purple-800`) u `OK` (Verde `bg-emerald-50 text-emerald-700`) |
| **8** | **Cambio YA** | Si `Cant_Cambios > 0`: Badge rojo pulsante `URGENTE (N)` (`bg-rose-600 text-white animate-pulse font-black`); si `0`: `OK` |
| **9** | **Próximas** | Si `Cant_Proximas > 0`: Badge ámbar `PRÓXIMO (N)` (`bg-amber-100 text-amber-900 font-bold`); si `0`: `0` |
| **10** | **Rotación** | Badge: `AUTO-AJUSTE` (Cian/Índigo `bg-indigo-100 text-indigo-800 font-black`), `SÍ` (Azul) u `OK` (Verde) |
| **11** | **Detalles & Recomendaciones** | Bloques de prescripción técnica coloreados por tipo (*Retiro YA* en rojo, *Par Direccional* en rose, *Alineación* en ámbar, *Dual* en púrpura, *Auto-Ajuste / Equis Larga* en índigo, *Presión PSI* en azul) |
| **12** | **Plan PDF** | Botón interactivo Índigo (`bg-indigo-600 hover:bg-indigo-700 text-white`) que invoca `abrirModalInformePdf(placa, fecha)` |

---

### 3.4 Matriz de Semáforos por Posición — Power BI Style (`#tbody_semaforo_matriz_flota` — Sección 8 del Manual)
Debajo de la tabla principal de Detalle de Vehículos, agrega la tarjeta **«Matriz de Semáforos por Posición (Power BI Style)»**:
- Cabecera con título, leyenda de los 4 colores de semáforo y contador de vehículos mostrados.
- Tabla con scroll horizontal y vertical (`max-h-[460px] overflow-auto custom-scroll`), columnas fijas a la izquierda (`Placa`, `Cliente / Sede`, `Tipología`, `Límite`) y columnas de posición **`P1` a `P12`** (extensible si hay vehículos de 14 posiciones), con `<tbody id="tbody_semaforo_matriz_flota">`.
- Renderizado de cada celda de posición `P1..P12`:
  - **Verde (`Óptimo`, $P_{\min} > \text{Limite} + 2.0\text{ mm}$):** Fondo `#10b981` (`bg-emerald-500 text-white`), muestra en negrita `${prof_min.toFixed(1)} mm` y debajo en micro-texto el serial `#${numero_interno}`.
  - **Amarillo (`Próxima`, $\text{Limite} < P_{\min} \le \text{Limite} + 2.0\text{ mm}$):** Fondo `#facc15` (`bg-yellow-400 text-slate-950`), muestra `${prof_min.toFixed(1)} mm` y el serial interno.
  - **Rojo (`Retiro YA`, $P_{\min} \le \text{Limite\_Retiro}$):** Fondo `#ef4444` con animación pulsante (`bg-red-500 text-white animate-pulse font-black`), muestra `${prof_min.toFixed(1)} mm` y el serial interno.
  - **Gris (`Sin Datos / Vía`):** Fondo `#f1f5f9` (`bg-slate-100 text-slate-400`), muestra `—`.
- Cada celda con datos incluye un `title` (tooltip) con: `Placa | Pos X | Remanente: Y mm | Serial: Z | PSI: W`.

---

## 4. Suite de Pruebas Automatizadas (`tests/test_detalle_vehiculos_planes.py`)

Crea el archivo `tests/test_detalle_vehiculos_planes.py` (usando `test_db` y `auth_client`) con estas **5 pruebas de verificación**:
1. **`test_deduplicacion_ultima_medicion_por_placa_posicion(test_db, auth_client)`:**
   - Inserta para la placa `WMK941` una lectura antigua en Pos 1 con `2.0 mm` (`2026-08-01`) y una lectura más reciente en Pos 1 con `14.0 mm` (`2026-10-15`).
   - Llama a `GET /api/diagnostico` y verifica que `Llantas Inspeccionadas == 1`, `Cant_Cambios == 0` y `Plan_Cambio_Llanta == "NO"`.
2. **`test_regla_especial_par_direccional_y_proximas_cambio(test_db, auth_client)`:**
   - Inserta en `TAL620` Pos 1 con `2.5 mm` ($\le 3.0\text{ mm}$ límite) y Pos 2 con `11.0 mm` y `prof_inicial = 16.0 mm` ($16.0 - 11.0 = 5.0\text{ mm} \ge 3.0\text{ mm}$), más Pos 3 con `4.5 mm` (en ventana `Próxima a Cambio` $\le 5.0\text{ mm}$).
   - Verifica que el diagnóstico active la regla de Par Direccional en `Detalle_Cambio` y contabilice `Cant_Proximas >= 1`.
3. **`test_motor_auto_ajuste_interno_direccion_pachas_y_trailer(test_db, auth_client)`:**
   - Inserta un vehículo donde Pos 2 (`14.0 mm`) > Pos 1 (`12.0 mm`) por `2.0 mm` ($\ge 0.5\text{ mm}$) y una pacha donde la llanta interior es más alta que la exterior.
   - Verifica que `Badge_Rotacion == "AUTO-AJUSTE"` y que `Detalle_Auto_Ajuste` prescriba cruzar `P1 ↔ P2` e invertir la pacha.
4. **`test_matriz_semaforo_posiciones_colores_exactos(test_db, auth_client)`:**
   - Verifica que `GET /api/diagnostico` incluya `Llantas_Posiciones` con estados `"ROJO"` ($\le 3.0$), `"AMARILLO"` ($3.1\text{–}5.0$) y `"VERDE"` ($> 5.0$), y que ignore surcos en `0.0 mm` cuando los otros surcos tienen lectura positiva.
5. **`test_filtro_rango_fechas_en_api_diagnostico(test_db, auth_client)`:**
   - Verifica que `GET /api/diagnostico?fecha_desde=2026-10-01&fecha_hasta=2026-10-31` filtre correctamente las inspecciones dentro del periodo.

Ejecuta `python -m pytest tests/ -v` y confirma que el 100% de las pruebas pasen en verde.