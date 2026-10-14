# Evaluación de Ingeniería y Prompt de Implementación — Automatización de Placa y Llantas por Cliente

## 1. ¿Cómo veo estos ajustes a nivel técnico y operativo?

**Calificación del ajuste: 10 / 10 (Alto impacto en velocidad de captura en patio y calidad de datos).**

### A. Asociación fija Placa ↔ Esquema de Vehículo (`tipologia`)
* **Reducción de fricción operativa:** Ahorra entre **4 y 6 clics por vehículo** y evita que el inspector tenga que recordar cuántos ejes o llantas tiene cada unidad.
* **Integridad del diagnóstico y del PDF:** En el código actual (`templates/index.html`, función `verificarInspeccionAnterior`), cuando el inspector digita la placa, el sistema consulta la posición 1 pero **ignora la `tipologia`, el `cliente`, el `subcliente` y la `tipo_operacion` históricas** del vehículo. Si en el mes 1 una placa se registró como `Tráiler 3 Ejes (12 llantas)` y en el mes 2 el inspector olvida cambiar el selector y la deja como `Cabezote 6x4 (10 llantas)`, el diagnóstico mezcla esquemas distintos para la misma placa.
* **Persistencia permanente:** Al vincular la placa a una tabla maestra `catalogo_vehiculos` (que se alimenta automáticamente al guardar cualquier inspección o al importar desde Excel), el sistema reconoce la configuración en menos de 50 ms apenas se termina de escribir la placa.

### B. Autocompletado de Llanta (`numero_interno`) dependiente del Cliente
* **Solución real al problema Multi-Flota:** En la operación real, la numeración interna o número de fuego (ej. `"1010"` o `"LL-1010"`) no es global, sino propia de cada empresa de transporte. *TransCarga* puede tener la llanta `"1010"` como una **Michelin X Multi Z 295/80R22.5 (16.5 mm)** y *Axxom* puede tener su propia llanta `"1010"` como una **Bridgestone M726 11R22.5 (24.5 mm)**.
* **Agilidad en rotaciones:** Cuando una llanta se rota de posición (por ejemplo, pasa de la posición 3 a la 7 dentro del mismo cliente), basta con digitar `"1010"` para que el sistema traiga instantáneamente `marca`, `diseno`, `dimension`, `vida`, `banda_reen`, `prof_inicial`, `precio` y `km_montaje`.
* **⚠️ Ajuste clave en el Candado 3 (Duplicidad de Número Interno):** Actualmente en `database.py` (líneas 221-243), el Candado 3 bloquea cualquier número interno que haya aparecido alguna vez en otra posición del mismo cliente en toda la historia. Para que las rotaciones entre meses funcionen sin falso bloqueo, el Candado 3 debe impedir que la misma llanta del cliente se registre en dos posiciones o placas distintas **en el mismo mes de inspección (`strftime('%Y-%m', fecha)`)**, permitiendo que en un nuevo mes sea rotada y autocompletada limpiamente.

---

## 2. Prompt listo para copiar y pegar en Antigravity

Copia el siguiente bloque y pégalo directamente en **Antigravity**:

```text
Actúa como un Ingeniero de Software Senior Full-Stack (FastAPI, SQLite y Vanilla JS SPA).

Vamos a implementar dos automatizaciones clave en **TireCheck Pro** para reducir clics manuales y garantizar consistencia de datos en patio:
1. **Asociación permanente Placa ↔ Esquema del Vehículo (`tipologia`, `cliente`, `subcliente`, `tipo_operacion`, `ultimo_km`).**
2. **Autocompletado de Especificaciones de Llanta por `numero_interno` dependiente del `cliente` seleccionado.**

Respeta estrictamente las invariantes de `docs/AGENTS.md`:
- NUNCA modifiques ni ejecutes pruebas destructivas sobre `data/inspecciones.db` real (usa siempre el fixture `test_db` de `tests/conftest.py`).
- Conserva los 6 candados de seguridad y la función `sanitizar_nativos()` en `server.py`.

Implementa los cambios siguiendo estos 4 pasos exactos:

---

### PASO 1: Capa de Datos y Consultas Inteligentes en `database.py`

1. **Tabla Maestra `catalogo_vehiculos` y Auto-Sincronización:**
   - En `inicializar_bd()`, crea la tabla:
     ```sql
     CREATE TABLE IF NOT EXISTS catalogo_vehiculos (
         placa TEXT PRIMARY KEY,
         tipologia TEXT NOT NULL,
         cliente TEXT DEFAULT '',
         subcliente TEXT DEFAULT '',
         tipo_operacion TEXT DEFAULT '',
         ultimo_km REAL DEFAULT 0.0,
         fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     )
     ```
   - En `inicializar_bd()`, agrega una migración automática inicial (backfill) que poble `catalogo_vehiculos` tomando el último registro histórico de cada `placa` existente en la tabla `inspecciones` (`INSERT OR IGNORE INTO catalogo_vehiculos ...`).
   - En `insertar_inspeccion()`, `actualizar_inspeccion()` y `cargar_excel_a_bd()`, haz un `INSERT INTO catalogo_vehiculos ... ON CONFLICT(placa) DO UPDATE SET tipologia=excluded.tipologia, cliente=excluded.cliente, subcliente=excluded.subcliente, tipo_operacion=excluded.tipo_operacion, ultimo_km=MAX(catalogo_vehiculos.ultimo_km, excluded.ultimo_km), fecha_actualizacion=CURRENT_TIMESTAMP` siempre que `placa` y `tipologia` no estén vacíos.

2. **Función `obtener_perfil_vehiculo(placa: str) -> dict | None`:**
   - Normaliza `placa = str(placa or '').strip().upper()`.
   - Busca primero en `catalogo_vehiculos` y, como respaldo, en el último registro de `inspecciones` para esa `placa` (`ORDER BY fecha DESC, id DESC LIMIT 1`).
   - Si existe, retorna:
     `{"encontrado": True, "placa": placa, "tipologia": ..., "cliente": ..., "subcliente": ..., "tipo_operacion": ..., "ultimo_km": ..., "cant_llantas": len(obtener_posiciones_por_tipologia(tipologia)), "esquema": obtener_esquema_tipologia(tipologia), "posiciones": obtener_posiciones_por_tipologia(tipologia)}`.
   - Si no existe, retorna `{"encontrado": False, "placa": placa}`.

3. **Función `obtener_llanta_por_cliente(cliente: str, numero_interno: str, placa: str = "", posicion: int | None = None) -> dict | None`:**
   - Normaliza `num_norm = str(numero_interno or '').strip().upper()` y `cli_norm = str(cliente or '').strip()`.
   - Si `not num_norm`, retorna `None`.
   - Consulta en `inspecciones` el último registro donde `UPPER(TRIM(numero_interno)) = ?` y `UPPER(TRIM(cliente)) = UPPER(TRIM(?))` ordenado por `fecha DESC, id DESC LIMIT 1`.
   - Si no se pasó `cliente` (está vacío) pero se pasó `placa`, infiere el cliente de la placa o busca coincidencia por `placa` y `numero_interno`.
   - Retorna un diccionario con las especificaciones técnicas de esa llanta para ese cliente:
     `{"encontrado": True, "numero_interno": num_norm, "cliente": row_cliente, "marca": ..., "diseno": ..., "dimension": ..., "vida": ..., "banda_reen": ..., "prof_inicial": ..., "precio": ..., "km_montaje": ..., "ult_placa": ..., "ult_posicion": ..., "ult_fecha": ..., "ult_prof_ext": ..., "ult_prof_cent": ..., "ult_prof_int": ...}`.

4. **Refinamiento del Candado 3 (Duplicidad de Número Interno en el mismo ciclo mensual):**
   - En `validar_inspeccion_candados()`, ajusta la consulta `sql_dup` del Candado de Número Interno para que valide que el mismo `numero_interno` dentro del mismo `cliente` no esté asignado a otra `placa` o `posicion` **en el mismo mes de inspección (`strftime('%Y-%m', fecha) = ?`)**, permitiendo que una llanta pueda rotarse de posición en meses posteriores y autocompletarse sin falso bloqueo.

---

### PASO 2: Nuevos Endpoints REST en `server.py`

1. Crea el endpoint `GET /api/vehiculo-perfil`:
   - Recibe `placa: str`.
   - Invoca `database.obtener_perfil_vehiculo(placa)` y retorna el JSON sanitizado con `sanitizar_nativos()`.
2. Crea el endpoint `GET /api/llanta-por-cliente`:
   - Recibe `numero_interno: str`, `cliente: str = ""`, `placa: str = ""`.
   - Invoca `database.obtener_llanta_por_cliente(cliente=cliente, numero_interno=numero_interno, placa=placa)` y retorna `{"encontrado": True, "datos": res}` o `{"encontrado": False}`.
3. En `GET /api/inspeccion-anterior`:
   - Si se provee `placa` y `posicion`, incluye también en la respuesta el perfil del vehículo (`tipologia`, `cliente`, `subcliente`, `tipo_operacion`) para mantener retrocompatibilidad total.

---

### PASO 3: Automatización Reactiva en Frontend Web (`templates/index.html`) y Escritorio (`app.py`)

1. **Autocompletado de Placa → Esquema y Flota en `templates/index.html`:**
   - Agrega una función `consultarPerfilPlaca(placa)` (con debounce de 300 ms en `oninput` y ejecución inmediata en `onblur` del input `#placa`).
   - Cuando `/api/vehiculo-perfil?placa=...` devuelva `encontrado: true`:
     - Si el usuario no tiene un cliente fijo bloqueado por rol, autocompleta `#cliente`, carga sus sedes y selecciona `#subcliente` y `#tipo_operacion`.
     - Selecciona automáticamente la `#tipologia` guardada para esa placa, ejecuta `cambioTipologia()` para redibujar inmediatamente el chasis interactivo con su esquema fijo y bloquea el selector `#tipologia` (agregando un pequeño botón/candado `"🔓 Cambiar esquema"` por si un administrador necesita reconfigurar el vehículo).
     - Muestra un indicador visual junto a la placa o tipología: `"✓ Esquema vinculado a placa"`.

2. **Autocompletado de Llanta (`#numero_interno`) dependiente del `#cliente` en `templates/index.html`:**
   - En el campo `#numero_interno`, escucha los eventos `onblur` y `oninput` (con debounce de 350 ms).
   - Al ingresar un número de llanta (ej. `"1010"`), toma el valor actual de `#cliente` (y `#placa`) y consulta `GET /api/llanta-por-cliente?cliente=...&numero_interno=...&placa=...`.
   - Si `encontrado: true`:
     - Autocompleta automáticamente `#marca`, `#diseno`, `#dimension`, `#vida`, `#banda_reen`, `#prof_inicial`, `#precio` y `#km_montaje` usando `asignarValorSelect()` y `validarVida()`.
     - Muestra en `#badgeHistorialPrevia` el texto `"✓ Llanta reconocida para este cliente"` y un toast sutil o subtítulo indicando su última profundidad registrada.
   - Si el inspector cambia el selector `#cliente` y ya había un `#numero_interno` escrito, vuelve a disparar la búsqueda para actualizar las especificaciones según el nuevo cliente seleccionado.

3. **Sincronización en `app.py` (Escritorio Tkinter):**
   - En `al_perder_foco_placa_pc`, consulta `database.obtener_perfil_vehiculo(nueva_placa)` y autocompleta `tipologia`, `cliente`, `subcliente` y `tipo_operacion`, refrescando el chasis con `on_cambio_tipologia_pc()`.
   - En el `Entry` de `numero_interno` en PC, enlaza `<FocusOut>` para que consulte `database.obtener_llanta_por_cliente(cliente, numero_interno)` y autocomplete `marca`, `diseno`, `dimension`, `vida`, `banda_reen`, `prof_inicial`, `precio` y `km_montaje`.

---

### PASO 4: Pruebas Automatizadas en `tests/`

Agrega pruebas unitarias y de integración (usando el fixture `test_db`) que verifiquen:
1. **`test_asociacion_fija_placa_esquema`:** Guardar una inspección para la placa `TRL-999` con tipología `Trailer 3 Ejes (12 llantas)` y verificar que `GET /api/vehiculo-perfil?placa=TRL-999` devuelve exactamente esa tipología, cliente y las 12 posiciones del esquema.
2. **`test_autocompletado_llanta_dependiente_cliente`:**
   - Registrar la llanta `1010` en el cliente `Cliente A` con `marca="Michelin"`, `diseno="X Multi Z"`, `dimension="295/80R22.5"`, `prof_inicial=16.5`.
   - Registrar la misma numeración `1010` en el cliente `Cliente B` con `marca="Bridgestone"`, `diseno="M726 EL"`, `dimension="11R22.5"`, `prof_inicial=24.5`.
   - Consultar `GET /api/llanta-por-cliente?cliente=Cliente A&numero_interno=1010` y comprobar que devuelve `Michelin` / `295/80R22.5` / `16.5`.
   - Consultar `GET /api/llanta-por-cliente?cliente=Cliente B&numero_interno=1010` y comprobar que devuelve `Bridgestone` / `11R22.5` / `24.5`.
3. Ejecuta `python -m pytest tests/ -v` y verifica que todos los tests pasen al 100%.
```