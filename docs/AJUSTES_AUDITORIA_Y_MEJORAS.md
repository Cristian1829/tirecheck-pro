# TireAnalyze Pro — Ajustes realizados (auditoría y mejoras)

Documento de referencia de todos los cambios hechos en esta etapa: qué fallaba, qué se cambió, cómo se ve en la aplicación y qué conviene saber al usarlo.
Cada ajuste tiene una prueba automática (ver "Pruebas" al final).

## Contenido

1. [Resumen](#1-resumen)
2. [Trabajo previo a la auditoría](#2-trabajo-previo-a-la-auditoría)
3. [Bloque 1 — Seguridad y permisos](#3-bloque-1--seguridad-y-permisos)
4. [Bloque 2 — Datos inventados y CPK](#4-bloque-2--datos-inventados-y-cpk)
5. [Bloque 3 — Ciclo de vida de la llanta](#5-bloque-3--ciclo-de-vida-de-la-llanta)
6. [Bloque 4 — Funciones nuevas](#6-bloque-4--funciones-nuevas)
7. [Bloque 5 — Ajustes de KPI](#7-bloque-5--ajustes-de-kpi)
8. [Reglas de negocio acordadas](#8-reglas-de-negocio-acordadas)
9. [Pendientes y recomendaciones](#9-pendientes-y-recomendaciones)
10. [Pruebas](#10-pruebas)

---

## 1. Resumen

| Bloque | Commit | Tema |
|---|---|---|
| 1 | `117a94f` | Licencias, permisos por cliente, vistas validadas en el servidor, usuarios por defecto |
| 2 | `a6e97b4` | Fin de precios y llantas inventados; CPK rotulado por tipo |
| 3 | `b8c5f65` | Estados y movimientos unificados, transiciones, reencauche, vida exacta |
| 4 | `a3277a7` | Sede por usuario, precios por cliente, 4 CPK, base de KPI, horas, MRP proyectado |
| 5 | `0653614` | Etiquetas reales, metas por cliente, CPK ponderado, calidad de datos, candados, tendencias |

La auditoría revisó 34 hallazgos. El #5 resultó ser un falso positivo (el filtro ya era por cliente asignado, no por quien registró) y quedó cubierto con pruebas que lo protegen.

Convención de numeración: **#N** es el número del hallazgo del informe de auditoría.

---

## 2. Trabajo previo a la auditoría

Cambios hechos antes de la auditoría formal, sobre los que se apoyan los bloques siguientes.

### 2.1 Estructura de ejes como única fuente
Antes, las reglas de dirección, tracción, duales y rotación en equis se deducían del número de posición. Ahora salen del esquema de la tipología (`estructura_ejes.py`): cada eje es direccional, tracción, libre/remolque o repuesto, y de ahí se derivan los pares direccionales, los duales y el cruce en equis. Una tipología sin estructura definida se infiere y se marca en Diagnóstico para que se corrija en Catálogos.

### 2.2 Límites de retiro por eje
El límite de retiro se resuelve siempre con los parámetros asignados al cliente, por eje, con respaldo en cascada (cliente + sede + eje, cliente + eje, cliente). Aplica igual en Diagnóstico, KPI, trazabilidad, MRP y PDF.

### 2.3 Mínima, no promedio
Los indicadores de desgaste usan la **mínima** de las tres profundidades (exterior, centro, interior), no el promedio.

### 2.4 Profundidad máxima por rin
El tope de 27 mm era solo para rin 22.5. Ahora depende del modelo del catálogo (profundidad inicial + 1 mm de tolerancia) o, si el modelo no está, del rin de la medida (17.5 → 18 mm, 19.5 → 22, 22.5 → 27, 24.5 → 30, OTR → 120).

### 2.5 Cifras corregidas
PSI vacío ya no cuenta como "baja severa"; los límites de retiro se aplican por eje; las fechas futuras o imposibles se excluyen de los análisis; el KPI 11 y el acumulado FVU del MRP se corrigieron; se quitaron valores inventados (precio, 16/18 mm).

### 2.6 PDF de inspección
El informe al finalizar una inspección muestra el conteo correcto de llantas y un plan completo y ordenado (rotaciones, cambios de posición, presión, alineación, retiros) con los mismos datos del PDF.

### 2.7 Dimensión automática por modelo
Al elegir el diseño (modelo) de una marca en patio, la dimensión se completa con la del catálogo. Si el modelo está en varias medidas se respeta la ya elegida si coincide; si no está en el catálogo, usa la más frecuente del historial; funciona sin conexión.

### 2.8 Catálogo de modelos de Colombia
Se agregaron ~120 modelos de uso comercial (camión, tractomula, volqueta, bus, buseta) de Michelin, Bridgestone, Goodyear, Continental, Pirelli, Hankook, Double Coin, Linglong, Triangle, Sailun, Westlake y Aeolus, y las bandas de reencauche (Bandag, Marangoni, Vipal) en medidas 295/80R22.5, 315/80R22.5, 11R22.5, 385/65R22.5 y las de buseta (17.5 y 19.5). Se cargan una sola vez y no pisan lo que el cliente ya tenga.
**Importante:** las profundidades iniciales nuevas son valores típicos por tipo de banda, no datos de ficha técnica; deben validarse en Catálogos → Catálogo de Modelos.

---

## 3. Bloque 1 — Seguridad y permisos

| # | Problema | Cambio |
|---|---|---|
| 1 | Cualquier usuario podía pedir los KPI FULL con `licencia=FULL` en la dirección. | La licencia sale siempre de la configuración del cliente. El parámetro solo permite ver la vista LIGHT de un cliente FULL (vista previa). |
| 2 | Un cliente sin licencia configurada quedaba PRO (FULL). | Queda **LIGHT** por defecto, en la lectura, al guardar límites, al aparecer en una inspección y en los formularios. |
| 4 | Un usuario no administrador sin cliente asignado podía ver y borrar datos de cualquier cliente. | Sin cliente asignado (y sin ser administrador) no entra a datos: la sesión responde 403 con un mensaje claro, y no se puede crear ni dejar un usuario así. |
| 5 | Se creía que los KPI se filtraban por quien registró. | Falso positivo: el filtro es por clientes asignados y editar no cambia el autor. Se agregaron pruebas que lo protegen. |
| 6 | Las vistas permitidas solo se ocultaban en el navegador. | El servidor valida la vista en Diagnóstico, KPI, Composición, Bodegas, Taller y Base de datos. El inspector nuevo tiene solo "patio". |
| 7 | `jefe1` y `gerencia1` reaparecían con la clave `1234` si se borraban. | Los usuarios de ejemplo solo se crean en una base vacía. |
| 8 | Las migraciones de PEPSICO y Ciudad Limpia se podían relanzar abriendo una URL, con `forzar`. | Endpoints eliminados. Las migraciones siguen corriendo solas al arrancar, una sola vez. |

**Al desplegar:** todo usuario no administrador debe tener cliente asignado; revisar licencias de clientes que quedaron PRO por el valor anterior; cambiar la contraseña de `admin` si sigue siendo la de ejemplo.

---

## 4. Bloque 2 — Datos inventados y CPK

| # | Problema | Cambio |
|---|---|---|
| 15 | Sin precio se tomaba la mediana de otras llantas o incluso de otros clientes. | Solo cuenta el precio real de esa misma llanta (el más reciente de sus inspecciones). Sin precio queda "sin precio" y se excluye de los cálculos en pesos. |
| 16 | Se guardaban **$1.450.000** cuando faltaba el precio; montar una llanta inexistente creaba una "Michelin X-LINE 295/80R22.5 de 16 mm". | Sin precio se guarda 0 = sin precio. La pérdida FVU y el CPK de la hoja de vida muestran "Sin precio". Montar una llanta inexistente exige marca, diseño y dimensión (la profundidad se toma del catálogo del modelo). Los formularios dejaron de venir prellenados. |
| 19 | El KPI 14 decía "CPK" pero era el CPK proyectado. | Los rótulos dicen "CPK proyectado", "CPK operativo"; el servidor indica el tipo de CPK en su respuesta. |
| extra | La tarjeta de ahorro de la hoja de vida siempre mostraba $0 (leía un campo con otro nombre). | Muestra el ahorro real o "Sin precio". |

**No se tocó** el $1.450.000 ya guardado en el maestro de llantas: no se puede distinguir cuáles son reales.

---

## 5. Bloque 3 — Ciclo de vida de la llanta

### 5.1 Ubicaciones y estados (#28)
Una sola lista de ocho ubicaciones oficiales:

| Código | Nombre visible |
|---|---|
| `BODEGA_1_NUEVAS` | En Stock - Nueva |
| `BODEGA_2_RECAMBIO` | En Stock - Reutilizable |
| `BODEGA_3_REENCAUCHE` | Enviada a Reencauche |
| `BODEGA_4_REENCAUCHADAS` | En Stock - Reencauchada |
| `BODEGA_5_REPARACION` | En Reparación Mayor |
| `BODEGA_6_FVU` | FVU / Desecho |
| `BODEGA_7_CHATARRIZADA` | Disposición Final / Chatarrizada |
| `MONTADA_OPERACION` | Montada en Vehículo |

Una migración (una sola vez) llevó los estados antiguos a esta lista: "Llantas listas" → Bodega 4; "Chatarra" → Bodega 7 si tiene acta y Bodega 6 si no. Montar desde Taller ya no deja dos llantas en la misma posición.

### 5.2 Movimientos (#27)
El **kardex** es la fuente oficial. Bodegas y Taller registran ahí con la misma función; la hoja de vida lo lee completo (antes mostraba "undefined" y sin fecha).

### 5.3 FVU en dos fases
- **Bodega 6:** la llanta se desmonta y se da de baja (fin de vida útil o garantía).
- **Bodega 7:** la empresa ambiental la retira; exige el **número de acta real** (antes se inventaba uno).

### 5.4 Transiciones válidas (#24, #25)
- Solo se desmonta una llanta montada.
- Una llanta nueva no pasa directo a recambio; no se salta a disposición final sin pasar por FVU.
- **Reingreso** desde Bodega 6 o 7 a un vehículo: exige motivo, responsable y foto, y queda como movimiento `REINGRESO_MONTAJE`.
- **Reencauche:** solo se recibe una llanta que fue despachada a la planta; la banda y su profundidad son obligatorias; el precio es opcional.
- Una inspección ya no monta sola una llanta que está en planta o en FVU: registra una novedad de **"Inconsistencia de inventario"** para revisarla.

### 5.5 Máximo de reencauches (#26)
Se configura por cliente y marca (con "TODAS" como regla general) en Catálogos → Marcas por Cliente. Bloquea el despacho a planta cuando la llanta ya llegó al máximo. Sin regla no hay tope.

### 5.6 Vida exacta (#12, #13)
La vida se guarda como **Original, R1, R2…** (antes solo "ORIGINAL/REENCAUCHE"). Candados de secuencia: una reencauchada no vuelve a Original y de Original solo se pasa a R1. En patio hay que elegir la vida (no se asume Original). Una migración que corría en cada arranque borraba el número de vida (R1–R4 → "REENCAUCHE"); se corrigió.

### 5.7 Otros errores corregidos
Dictamen de garantía siempre en $0; botones de reencauche al revés en el inventario; tope fijo de 27 mm en la validación sin conexión; valores prellenados inventados (100 PSI, 18 mm, 16 mm, 20 mm, 295/80R22.5, 70 %, $1.050.000).

---

## 6. Bloque 4 — Funciones nuevas

### 6.1 Sede por usuario (#3)
Al usuario se le pueden marcar sedes de sus clientes en Catálogos → Usuarios (las sedes aparecen al marcar el cliente). Sin sedes marcadas ve todas las de sus clientes. Aplica a: inspecciones, KPI, Diagnóstico, informes por placa, Bodegas y la lista de sedes en patio. Se agregó la casilla de la vista **Bodegas**, que faltaba, y el usuario nuevo queda con solo patio y cliente obligatorio.
Se corrigió además que `/api/inspeccion-anterior` no validaba el cliente (cualquier usuario podía leer datos de cualquier placa).

### 6.2 Precios por cliente (#23)
Catálogos → **Precios por Cliente**: lista por cliente, marca, diseño (opcional), dimensión y tipo (llanta nueva o reencauche), con fecha de vigencia. Prioridad: precio de la inspección → lista del cliente vigente a la fecha → sin precio (se excluye). Nunca se toma el precio de otro cliente.

### 6.3 Los 4 CPK (#20)
Tarjeta nueva en KPI → pestaña 3:
- **Operativo:** costo de la vida ÷ km recorridos hasta la última inspección.
- **Proyectado:** costo de la vida ÷ km proyectados hasta el límite de retiro.
- **Total (ciclo completo):** Σ costos de todas las vidas ÷ Σ km de todas las vidas.
- **Administrativo (mensual):** inversión del mes en llantas instaladas **sin km acumulados** (montadas desde Bodega 1 o 4) ÷ km de la flota en el mes (suma de odómetros al corte menos el corte anterior).

Se calculan por vida (Original, R1, R2…) y por ciclo; los agregados de flota son Σcosto ÷ Σkm, no un promedio.
**Nota:** el CPK administrativo solo tiene dato donde se registran montajes en Bodegas; en el resto muestra "Sin dato".

### 6.4 Base de los KPI (#11)
Selector **"Última inspección" / "Historial completo"** en todos los KPI. El MRP siempre usa el estado actual (es un plan de compra).

### 6.5 Medición por horas de motor (#10)
Al crear una placa en patio se elige si se mide en **kilómetros u horas**; después no cambia. Patio muestra "Horómetro (horas)", y KPI tiene el selector de **unidad** con rótulos h/mm y $/h. Cada unidad ve solo sus vehículos. Pendiente: los PDF y Diagnóstico siguen diciendo "km" en placas medidas en horas (los números son correctos).

### 6.6 MRP proyectado (#29, #30)
- **Horizonte editable** (3 meses por defecto) en Bodegas: la demanda cuenta las llantas que llegan a su límite de retiro dentro del horizonte, según su ritmo de desgaste (km/mm) y el uso del vehículo (km/mes). Sin historial suficiente (dos inspecciones separadas ≥15 días) solo cuenta si ya está en el límite; la pantalla indica cuántas no tienen historial.
- **Retorno y desecho:** de las llantas que se retiran, el % de aprobación de reencauche del cliente vuelve reencauchado y el resto es desecho.
- **Stock de seguridad por medida y eje** (direccional, tracción, libre). La reserva de dirección solo se cubre con llantas nuevas. Sin reglas para una medida se usa el stock general del cliente.

### 6.7 Corrección de datos en patio
Se dejó de guardar **100 PSI** cuando la presión venía vacía y de asumir "Original" cuando no se elegía la vida. También se corrigió un error con inspecciones antiguas sin cliente que hacía fallar el CPK.

---

## 7. Bloque 5 — Ajustes de KPI

| # | Problema | Cambio |
|---|---|---|
| 32 | Las etiquetas decían "Correcta (±5 %)" aunque se medía con la tolerancia del cliente (10 %). El KPI 10 usaba 5 %, 10 % y 2 mm fijos. | Las etiquetas muestran los umbrales reales ("Correcta (-10% a +10%)"). El KPI 10 usa las tolerancias del cliente. |
| 31 | KPI 01 sin padrón mostraba **100 %** (también el gráfico de Diagnóstico). | Muestra "Sin padrón" y avisa que, sin padrón cargado, el parque son los vehículos ya inspeccionados. |
| 33 | Meta de reencauche fija en 70 %. | Meta, % de aprobación en planta y stock general se configuran por cliente (directorio de clientes). |
| 22 | El KPI 14 y Trazabilidad promediaban los CPK de cada llanta. | Σcosto ÷ Σkm proyectados y Σkm ÷ Σmm. |
| 18 | Las llantas sin dato quedaban fuera de cada KPI sin aviso. | Un aviso en KPI cuenta cuántas quedan fuera y de qué (sin presión, profundidad inicial, precio, número interno, sede, fecha inválida). |
| 14 | La importación saltaba el candado de kilometraje; además se comparaba contra la inspección más reciente aunque se editara una antigua. | La lectura (km u horas) debe quedar entre la de la inspección anterior y la posterior, al capturar, editar o importar. |
| 17 | La misma llanta en dos placas el mismo mes. | El candado ya existía en captura, edición e importación; los casos de la base local venían de datos de prueba (TMP). |
| 34 | Sin tendencias para gerencia. | Pestaña **"6. Tendencias"** con 12 meses: presión correcta, en límite de retiro, profundidad mínima, alerta de alineación y CPK operativo. |
| extra | No se podía editar ninguna inspección anterior a la última de su placa (candado de frecuencia). | Si la edición no cambia la fecha, ese candado no aplica. |

---

## 8. Reglas de negocio acordadas

- La licencia sale siempre de la configuración del cliente; sin configuración, LIGHT.
- Un usuario puede limitarse a sedes; el que no es administrador necesita cliente asignado.
- La decisión de retiro usa siempre la **mínima** de las tres profundidades.
- Los precios van por cliente; sin precio, la llanta se excluye de los cálculos en pesos.
- Reencauche en eje direccional: **bloqueado por defecto** (la excepción por tipología queda pendiente).
- Una llanta original no pasa a R2 o más sin R1; una reencauchada no vuelve a Original.
- FVU en dos fases; una llanta dada de baja puede volver a montarse solo con motivo, responsable y foto.
- El MRP proyecta la compra con el desgaste de cada llanta y el desecho esperado; horizonte editable (3 meses por defecto).
- Los indicadores se pueden ver por **última inspección o historial completo**, y en **km u horas**.
- Roles: el inspector ve el avance de las inspecciones; el jefe de flota agrega plan de mantenimiento, duración, proyecciones, CPK y composición; gerencia ve las tendencias.

---

## 9. Pendientes y recomendaciones

**Pendiente de implementar**
- Excepción configurable por tipología para permitir reencauche en eje direccional.
- Rótulos en horas en Diagnóstico y PDF.

**Datos ya guardados (no se modificaron)**
- Llantas del maestro con $1.450.000 inventados.
- Inspecciones antiguas con vida "REENCAUCHE" sin número.
- Inconsistencias de kilometraje del historial.

**Para revisar en producción**
1. Asignar cliente a todo usuario no administrador (y sedes, si aplica).
2. Revisar licencias de los clientes que quedaron PRO por el valor anterior.
3. Cargar la lista de precios por cliente para que el CPK cubra más llantas.
4. Validar en el catálogo las profundidades iniciales de los modelos nuevos.
5. Configurar, si se desea, el máximo de reencauches y el stock de seguridad por medida y eje.
6. Revisar las novedades de "Inconsistencia de inventario" en las hojas de vida.
7. Cambiar la contraseña de `admin` si sigue siendo la de ejemplo.

---

## 10. Pruebas

Suite completa: **253 pruebas**, todas pasan.

| Archivo | Cubre |
|---|---|
| `tests/test_auditoria_seguridad.py` | Bloque 1 |
| `tests/test_auditoria_datos.py` | Bloque 2 |
| `tests/test_auditoria_ciclo_vida.py` | Bloque 3 |
| `tests/test_auditoria_funciones_nuevas.py` | Bloque 4 |
| `tests/test_auditoria_kpis.py` | Bloque 5 |
| `tests/test_dimension_modelo.py` | Dimensión automática por modelo |
| `tests/test_catalogo_modelos_colombia.py` | Catálogo de modelos |

Se ajustaron pruebas antiguas cuyos supuestos cambiaron por las reglas nuevas (vocabulario de estados, transiciones, profundidad inicial obligatoria, fórmula del MRP).
