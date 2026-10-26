# 📋 Registro y Documentación Técnica de Ajustes Realizados
**Proyecto:** TireAnalyze Pro — Suite Integral Web de Inspección y Diagnóstico de Flotas  
**Fecha:** 26 de Octubre de 2026  
**Ambiente:** Producción (Railway) & Repositorio Git (`origin/main`)  
**URL Producción:** [https://www.tireanalizepro.com/](https://www.tireanalizepro.com/)  
**Estado de Pruebas:** 254 pruebas ejecutadas, 254 aprobadas (100% Pass)

---

## 📌 Tabla de Contenidos

1. [Ruta Raíz (`/`) y Enrutamiento de Acceso al Aplicativo (`/login`, `/app`)](#1-ruta-raíz--y-enrutamiento-de-acceso-al-aplicativo-login-app)
2. [Control de Reencauche en Eje Direccional Parametrizable por Tipología](#2-control-de-reencauche-en-eje-direccional-parametrizable-por-tipología)
3. [KPIs Gerenciales, Metas por Cliente y Pestaña de Tendencias](#3-kpis-gerenciales-metas-por-cliente-y-pestaña-de-tendencias)
4. [Gestión Multisede, 4 Variantes de CPK, Medición por Horas y MRP Proyectado](#4-gestión-multisede-4-variantes-de-cpk-medición-por-horas-y-mrp-proyectado)
5. [Ciclo de Vida Unificado, Kardex Central y Dos Fases de Baja Técnica (B6/B7)](#5-ciclo-de-vida-unificado-kardex-central-y-dos-fases-de-baja-técnica-b6b7)
6. [Integridad de Datos Financieros: Eliminación de Precios y Llantas Asumidas](#6-integridad-de-datos-financieros-eliminación-de-precios-y-llantas-asumidas)
7. [Seguridad Multinquilino, Licenciamiento (LIGHT vs FULL) y Perfiles](#7-seguridad-multinquilino-licenciamiento-light-vs-full-y-perfiles)
8. [Catálogo Nacional de Colombia y Autocompletado Reactivo Modelo-Dimensión](#8-catálogo-nacional-de-colombia-y-autocompletado-reactivo-modelo-dimensión)
9. [Matriz de Pruebas Automatizadas y Calidad de Código](#9-matriz-de-pruebas-automatizadas-y-calidad-de-código)
10. [Historial de Commits y Despliegue en Producción](#10-historial-de-commits-y-despliegue-en-producción)

---

## 1. Ruta Raíz (`/`) y Enrutamiento de Acceso al Aplicativo (`/login`, `/app`)

### 🎯 Objetivo
Hacer que cualquier visitante que ingrese a la dirección principal [https://www.tireanalizepro.com/](https://www.tireanalizepro.com/) vea en primera instancia el portafolio comercial completo de servicios técnicos de TireAnalyze Pro (`servicios.html` / `servicios_v3.html`), y que desde los botones de acción ("Ingresar", "Ingresar a la plataforma", "Empezar a ahorrar") sea guiado directamente a la pantalla de inicio de sesión (`/login`) para ingresar a la plataforma.

### 🛠️ Ajustes Realizados
1. **Enrutador en `server.py`:**
   - La ruta raíz `@app.get("/")`, junto con sus alias `@app.get("/servicios")` y `@app.get("/landing")`, entregan la plantilla comercial `servicios_v3.html` (o `servicios.html` como fallback).
   - Se crearon rutas dedicadas para la aplicación web principal: `@app.get("/login")`, `@app.get("/app")`, `@app.get("/sistema")` y `@app.get("/index.html")`, que entregan `templates/index.html` con cabeceras `no-cache` y abren de inmediato el modal de login si no existe una sesión local activa.
2. **Plantillas HTML (`templates/servicios_v3.html` y `templates/servicios.html`):**
   - El botón **"Ingresar"** en la barra de navegación superior (desktop y menú móvil desplegable) ahora apunta a `href="/login"`.
   - El botón de la calculadora de ahorro industrial ("Empezar a ahorrar") apunta a `href="/login"`.
   - El botón del bloque final de llamado a la acción ("Ingresar a la plataforma") apunta a `href="/login"`.
   - El enlace "Plataforma" del pie de página apunta a `href="/login"`.
   - El logotipo de la cabecera apunta a `href="/"`, permitiendo regresar a la portada de servicios en cualquier momento.
   - Se incorporaron las etiquetas de indexación canónica: `<link rel="canonical" href="https://www.tireanalizepro.com/">` y OpenGraph `og:url`.
3. **PWA y Service Worker Offline (`sw.js` y `manifest.json`):**
   - Se actualizó el listado de activos cacheados (`PRECACHE_ASSETS`) para pre-almacenar `/`, `/app` y `/login`.
   - La estrategia de intercepción de navegación en `sw.js` ahora responde sin conexión en `/`, `/app` y `/login`.
4. **Validación:**
   - Pruebas unitarias actualizadas en `tests/test_api_web.py`, `tests/test_composicion_flota.py` y `tests/test_offline_sync.py`.

---

## 2. Control de Reencauche en Eje Direccional Parametrizable por Tipología

### 🎯 Objetivo
Por estándar de seguridad y normativa de transporte, las llantas reencauchadas (vidas R1, R2, etc.) no deben montarse ni admitirse en ejes direccionales. Sin embargo, ciertas configuraciones o tipos de vehículos específicos requieren admitir reencauche en dirección. El sistema debía permitir habilitar esta excepción únicamente cuando en el catálogo de tipologías se marque explícitamente una casilla para esa tipología.

### 🛠️ Ajustes Realizados
1. **Base de Datos y Migración Automática (`database.py`):**
   - Se añadió la columna `permite_reencauche_direccion INTEGER NOT NULL DEFAULT 0` a la tabla `catalogo_tipologias`.
   - Se implementó la migración automática idempotent para bases de datos SQLite en producción.
   - Se creó la función de consulta rápida `tipologia_permite_reencauche_direccion(codigo_o_nombre, conexion) -> bool`.
2. **Backend API (`server.py`):**
   - Se actualizó el esquema Pydantic `TipologiaCatalogoItem` con el campo booleano opcional `permite_reencauche_direccion: bool = False`.
   - Endpoints de consulta (`GET /api/catalogos`), creación (`POST /api/catalogos/tipologias`) y edición (`PUT /api/catalogos/tipologias/{codigo}`) reciben y almacenan este parámetro.
   - En la validación de inspección en patio (`validar_registro_inspeccion`), si la vida es reencauche y la posición corresponde a eje direccional, se consulta la tipología del vehículo: si `permite_reencauche_direccion == 1`, se aprueba; de lo contrario, se bloquea con advertencia técnica.
3. **Módulo de Bodegas y Taller (`modulo_bodegas_taller.py`):**
   - En el endpoint de montaje de llanta a vehículo (`/api/bodegas/montar-llanta`), se verifica la posición de destino y la tipología del vehículo receptor, bloqueando el montaje de reencauches en dirección si la tipología no lo autoriza.
4. **Interfaz de Usuario (`templates/index.html` y JavaScript):**
   - Se añadió el interruptor/checkbox en el formulario modal de Crear/Editar Tipología:
     `"Permitir llantas reencauchadas en eje direccional para esta tipología"`
   - `modulo_catalogos.js`: lectura, renderizado y guardado del estado del checkbox.
   - `modulo_patio.js`: validación interactiva inmediata en el esquema del chasis al ingresar o registrar llanta reencauchada en posición direccional.
   - `app_core.js`: soporte de sincronización y validación en modo patio offline.

---

## 3. KPIs Gerenciales, Metas por Cliente y Pestaña de Tendencias

### 🎯 Objetivo
Garantizar que los tableros de control analítico reflejen las condiciones contractuales y tolerancias de cada cliente, calcular métricas consolidadas ponderadas reales (sin promediar porcentajes) y ofrecer una vista evolutiva mes a mes para comités gerenciales.

### 🛠️ Ajustes Realizados
1. **Tolerancias de Presión y Pareto por Cliente:**
   - Rangos de sobrepresión y subpresión configurados individualmente por cliente en el catálogo de operaciones.
   - El gráfico de Pareto y los semáforos se adaptan dinámicamente a las metas de cada flota.
2. **KPI 01 (Índice de Cobertura de Inspección):**
   - Flotas sin padrón vehicular registrado ya no asumen falsamente un 100% de cobertura; ahora muestran claramente la etiqueta `"Sin padrón"` y detallan la fuente censada.
3. **Metas Operativas Editables por Cliente:**
   - Meta de porcentaje de reencauchabilidad, tasa de aprobación de cascos en planta y nivel de stock general parametrizables por cliente.
4. **CPK y Desgaste Ponderado:**
   - Cálculo de CPK consolidado como $\frac{\sum \text{Costo Total}}{\sum \text{Kilómetros Recorridos}}$ y tasa de desgaste como $\frac{\sum \text{Km}}{\sum \text{mm desgastados}}$ (KPI 14 y Trazabilidad), eliminando la distorsión matemática de promediar promedios.
5. **Transparencia en Calidad de Datos:**
   - Notificación al usuario con el recuento exacto de llantas excluidas de los cálculos monetarios o de rendimiento por falta de precio, presión inicial o kilometraje.
6. **Nueva Pestaña de Tendencias Mensuales:**
   - Módulo visual de evolución temporal que compara mes a mes el desempeño de la flota para comités directivos.

---

## 4. Gestión Multisede, 4 Variantes de CPK, Medición por Horas y MRP Proyectado

### 🎯 Objetivo
Proveer control de acceso segmentado por sedes geográficas, soportar vehículos industriales cuya vida útil se mide en horas de motor, estandarizar las 4 familias de Costo por Kilómetro (CPK) y planificar compras con un MRP proyectado.

### 🛠️ Ajustes Realizados
1. **Control de Alcance por Sede:**
   - Usuarios de perfil operativo o jefatura restringidos exclusivamente a las sedes asignadas de sus clientes en patio, bodegas, consultas de base de datos e informes.
2. **Medición Dual: Kilómetros u Horas de Motor:**
   - Parámetro a nivel de vehículo para registrar desgaste y rotación por `km` o por `horas`. Selector de unidad en los módulos de KPIs y Trazabilidad.
3. **4 Variantes Oficiales de CPK:**
   - **CPK Operativo:** Basado en el desgaste real observado entre inspecciones consecutivas.
   - **CPK Proyectado:** Extrapolación de vida útil esperada hasta el milímetro de retiro normativo.
   - **CPK Total de Ciclo:** Consolidado histórico desde el estado nuevo hasta el fin de vida útil.
   - **CPK Administrativo Mensual:** Gasto contable mensual imputado por flota dividido entre los kilómetros o horas recorridos en el periodo.
4. **MRP Proyectado a 3 Meses:**
   - Motor de proyección de compras de llantas y bandas que calcula el punto de pedido tomando en cuenta el stock disponible en almacén, las llantas en proceso de reencauche en planta externa y la tasa de desecho esperada por medida y eje.

---

## 5. Ciclo de Vida Unificado, Kardex Central y Dos Fases de Baja Técnica (B6/B7)

### 🎯 Objetivo
Eliminar discrepancias entre el módulo de Taller y el de Almacén, formalizar las bajas de neumáticos y asegurar que la trazabilidad de vidas sea estrictamente secuencial y auditable.

### 🛠️ Ajustes Realizados
1. **Kardex Unificado de Movimientos:**
   - Una sola estructura relacional de movimientos de inventario que alimenta simultáneamente Taller, Bodegas y Hoja de Vida de la llanta.
2. **Fin de Vida Útil (FVU) en Dos Fases:**
   - **Fase B6 (Baja Técnica):** La llanta sale de servicio por desgaste o daño insalvable y se traslada al área de desecho para inspección final.
   - **Fase B7 (Disposición Final):** Generación de acta formal de chatarrización o entrega a gestor ambiental certificado con registro fotográfico.
3. **Reingreso Auditado desde FVU:**
   - Bloqueo de reactivación accidental. El reingreso de una llanta en desecho exige justificación escrita, responsable registrado y confirmación administrativa.
4. **Candado de Secuencia de Vidas:**
   - Transiciones estrictas: `Original -> R1 -> R2 -> R3...`. Se previene el salto de ciclos de reencauche y la pérdida del contador de vida original.

---

## 6. Integridad de Datos Financieros: Eliminación de Precios y Llantas Asumidas

### 🎯 Objetivo
Erradicar valores prellenados por defecto en costos y modelos que pudieran alterar los informes de ahorro y auditoría económica de las flotas.

### 🛠️ Ajustes Realizados
1. **Cero Precios Ficticios:**
   - Se removió por completo el valor por defecto de `$1.450.000 COP` que existía en altas de llantas y hoja de vida.
   - Si una llanta no tiene factura o precio registrado en su catálogo de cliente, sus cálculos se muestran en `N/D` o se excluyen explícitamente de las sumatorias en pesos sin asumir precios de otros clientes.
2. **Montaje Estricto de Llantas:**
   - Si se monta una llanta nueva no registrada en el inventario, el formulario exige obligatoriamente marca, modelo y dimensión reales, eliminando la creación automática de llantas modelo `Michelin X-LINE` inventadas.
3. **Cálculo Real de Ahorro por Reencauche:**
   - Se corrigió la lectura de campos en la Hoja de Vida de la Llanta para comparar el costo del reencauche contra el precio histórico real de la llanta nueva del mismo cliente.

---

## 7. Seguridad Multinquilino, Licenciamiento (LIGHT vs FULL) y Perfiles

### 🎯 Objetivo
Blindar la seguridad de la información entre clientes competidores, asegurar el modelo de licenciamiento comercial y bloquear cuentas o endpoints de prueba.

### 🛠️ Ajustes Realizados
1. **Licencia Vinculada a Base de Datos:**
   - El modo de licencia (`LIGHT` o `FULL`) proviene estrictamente del registro del cliente en la base de datos. Se bloqueó la manipulación mediante parámetros en la URL. Clientes sin configuración explícita se cargan de forma segura en modo `LIGHT`.
2. **Aislamiento Multinquilino Estricto:**
   - Los usuarios sin cliente asignado son bloqueados por el servidor con código HTTP `403 Forbidden`. No se permite la creación de usuarios huérfanos.
3. **Restricción de Vistas y Permisos:**
   - El rol `Inspector` solo puede acceder a la interfaz de patio. Se retiraron contraseñas por defecto predecibles y se sanearon endpoints de mantenimiento.

---

## 8. Catálogo Nacional de Colombia y Autocompletado Reactivo Modelo-Dimensión

### 🎯 Objetivo
Agilizar la labor del inspector en patio evitando errores tipográficos en dimensiones y reduciendo el tiempo de captura por llanta.

### 🛠️ Ajustes Realizados
1. **Catálogo de ~120 Modelos Comunes en Colombia:**
   - Precarga en base de datos de modelos comerciales de transporte pesado, urbano y pasajeros (Bridgestone, Michelin, Goodyear, Pirelli, Continental, Firestone, Double Coin, Aeolus, etc.) y bandas de reencauche (Bandag, Marangoni, Renovado Michelin).
2. **Endpoint y Autocompletado Reactivo:**
   - Endpoint `GET /api/dimensiones-modelo?marca={marca}&diseno={diseno}`.
   - Al seleccionar la marca y diseño en patio o bodega, la dimensión compatible más común se autoselecciona automáticamente tanto en línea como en el motor IndexedDB offline.

---

## 9. Matriz de Pruebas Automatizadas y Calidad de Código

### 📊 Resultado de la Suite de Pruebas Pytest
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\crist\OneDrive\Documentos\Tyre\TireCheck_Pro_Proyecto
collected 254 items

tests\test_alerta_frecuencia_copiar_marca.py ........                    [  3%]
tests\test_api_web.py .......................                            [ 12%]
tests\test_auditoria_bodegas_sentido_negocio.py .......                  [ 14%]
tests\test_auditoria_ciclo_vida.py ................                      [ 21%]
tests\test_auditoria_datos.py .....                                      [ 23%]
tests\test_auditoria_funciones_nuevas.py ................                [ 29%]
tests\test_auditoria_kpis.py .........                                   [ 33%]
tests\test_auditoria_seguridad.py ............                           [ 37%]
tests\test_automatizacion_placa_llanta.py .......                        [ 40%]
tests\test_bodegas_hoja_vida.py .....                                    [ 42%]
tests\test_bodegas_mrp.py ......                                         [ 44%]
tests\test_calculos_coherentes.py .......                                [ 47%]
tests\test_candados.py ...............                                   [ 53%]
tests\test_catalogo_modelos_colombia.py ...                              [ 54%]
tests\test_composicion_flota.py ....                                     [ 56%]
tests\test_configuracion_marcas_cliente.py .....                         [ 58%]
tests\test_detalle_vehiculos_planes.py .....                             [ 60%]
tests\test_diagnostico.py .....                                          [ 62%]
tests\test_diagrama_chasis.py .........                                  [ 65%]
tests\test_dimension_modelo.py .....                                     [ 67%]
tests\test_directorio_clientes.py ..                                     [ 68%]
tests\test_estructura_ejes.py .....                                      [ 70%]
tests\test_frecuencia_parametrizable_cliente.py ...                      [ 71%]
tests\test_kpis.py ...                                                   [ 72%]
tests\test_login_seguridad_frontend.py .............                     [ 77%]
tests\test_matriz_semaforos.py ........                                  [ 81%]
tests\test_migracion_pext_ciudad_limpia.py ...                           [ 82%]
tests\test_offline_sync.py ......                                        [ 84%]
tests\test_pdf.py .......                                                [ 87%]
tests\test_precision_graficos_ground_truth.py ............               [ 92%]
tests\test_seguridad_y_rendimiento.py ....                               [ 93%]
tests\test_sincronizacion_kilometraje_vehiculo.py .....                  [ 95%]
tests\test_suite_20_kpis_manual.py .....                                 [ 97%]
tests\test_tipologia_mayusculas_limites.py ......                        [100%]

================= 254 passed, 3 warnings in 173.47s (0:02:53) =================
```

---

## 10. Historial de Commits y Despliegue en Producción

Todos los cambios fueron integrados, consolidados en el bundle de código unificado `CODIGO_COMPLETO_PROYECTO.md` y desplegados de forma continua hacia **Railway**:

| Hash | Mensaje de Commit | Módulos Impactados |
| :--- | :--- | :--- |
| `52d8423` | `feat(routing): presentar landing de servicios en ruta raiz / y boton ingresar hacia /login` | `server.py`, `templates/servicios.html`, `templates/servicios_v3.html`, pruebas |
| `73c4549` | `docs: actualizar bundle CODIGO_COMPLETO_PROYECTO.md con permiso de reencauche direccional` | `CODIGO_COMPLETO_PROYECTO.md` |
| `192dbf1` | `feat(tipologia): permitir reencauche en eje direccional segun configuracion de tipologia` | `database.py`, `server.py`, `modulo_bodegas_taller.py`, `index.html`, JS |
| `0653614` | `fix(kpis): etiquetas reales, metas por cliente, CPK ponderado, calidad de datos y tendencias` | `server.py`, KPIs, reportes, tendencias |
| `a3277a7` | `feat(gestion): sede por usuario, precios por cliente, 4 CPK, base de KPI, horas y MRP proyectado` | `server.py`, `database.py`, bodegas, MRP |
| `b8c5f65` | `fix(ciclo-vida): estados y movimientos unificados, transiciones validadas y vida exacta` | Kardex, bodegas, transiciones FVU |
| `a6e97b4` | `fix(datos): sin precios ni llantas inventados y CPK rotulado por tipo` | Hoja de vida, montajes, CPK |
| `117a94f` | `fix(seguridad): licencias, alcance por cliente, vistas y usuarios por defecto` | Autenticación, licencias LIGHT/FULL |
| `398b63d` | `feat(catalogo): autocompletar dimension por modelo y cargar modelos comunes en Colombia` | Catálogos, modelos de llanta, API |

### 🚀 Verificación en Vivo (Producción)
- **Ruta Raíz:** [https://www.tireanalizepro.com/](https://www.tireanalizepro.com/) $\rightarrow$ Renderiza Portafolio de Servicios Técnicos con botones hacia el aplicativo.
- **Acceso / Login:** [https://www.tireanalizepro.com/login](https://www.tireanalizepro.com/login) $\rightarrow$ Renderiza Suite Operativa con Modal de Login inmediato.
