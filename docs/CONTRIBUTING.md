# Guía de Contribución y Estándares de Desarrollo - TireCheck Pro

Bienvenido a la guía de desarrollo de **TireCheck Pro**. Este documento define las pautas técnicas, convenciones de arquitectura y estándares de ingeniería para mantener la estabilidad, calidad y mantenibilidad del proyecto.

---

## 1. Configuración del Entorno de Desarrollo

### 1.1 Requisitos Previos
- **Python:** 3.10 o superior (recomendado Python 3.12 64-bit).
- **Git:** Para control de versiones.
- **Navegador Moderno:** Chrome, Edge, Firefox o Safari con soporte para ES6+.

### 1.2 Instalación Rápida
```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd TireCheck_Pro_Proyecto

# 2. Crear y activar entorno virtual (opcional pero recomendado)
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## 2. Convenciones de Código y Estilo

### 2.1 Backend (Python)
- **Estándar:** Adherencia a **PEP 8**.
- **Tipado Estático:** Uso de type hints en firmas de funciones públicas y rutas de FastAPI.
- **Validación de Datos:** Los modelos de entrada y salida deben definirse mediante **Pydantic V2** (`pydantic.BaseModel`). Usar `.model_dump()` en lugar de `.dict()` (deprecado).
- **Serialización Segura de Datos:** Debido a la integración con Pandas y SQLite, las respuestas de endpoints que contengan DataFrames procesados deben pasar por la función `sanitizar_nativos()` en `server.py` para convertir tipos `numpy.int64` y `numpy.float64` a tipos nativos de Python.

### 2.2 Frontend (HTML / JavaScript / CSS)
- **Estructura:** Single Page Application (SPA) modular dentro de `templates/index.html`.
- **Estilos:** Utilizar utilidades de **Tailwind CSS**. Evitar CSS incrustado `style="..."` excepto para posiciones dinámicas o fondos con gradientes de chasis específicos.
- **JavaScript:**
  - Código en Vanilla JavaScript ES6+ (uso de `const`, `let`, `async/await`, `fetch`).
  - Nombres de funciones en `camelCase` descriptivo (ej. `cargarDiagnostico()`, `seleccionarPosicion()`).
  - IDs de elementos en el DOM con nombres semánticos (ej. `filtroKpiCliente`, `btnGuardar`).
  - Manejo de asincronía con bloques `try/catch` y notificaciones al usuario mediante la función global `mostrarToast(mensaje, esError)`.

### 2.3 Base de Datos (SQLite)
- **Gestión de Conexiones:** Toda interacción con la base de datos debe ejecutarse mediante el context manager `with get_connection() as conn:`.
- **Inyección SQL:** Prohibida la interpolación de cadenas `f"SELECT ... WHERE id = {id}"`. Utilizar siempre parámetros parametrizados con `?` (`cursor.execute("SELECT ... WHERE id = ?", (id,))`).
- **Candados de Seguridad:** Cualquier nueva inserción o actualización de inspecciones debe invocar obligatoriamente `validar_inspeccion_candados()`.

---

## 3. Pruebas Automatizadas (QA Testing)

El proyecto cuenta con una suite completa en `tests/` que utiliza **pytest**.

### 3.1 Regla de Oro del Testing: Aislamiento de Base de Datos
- **NUNCA** apuntes las pruebas a `inspecciones.db`.
- Todas las pruebas deben heredar del fixture `test_db` definido en `tests/conftest.py`, el cual crea un archivo temporal aislado con el esquema completo de tablas y catálogos, restaurando la ruta original al finalizar.

### 3.2 Ejecución de Pruebas
```bash
# Ejecutar toda la suite con salida detallada
python -m pytest tests/ -v

# Ejecutar una categoría específica de pruebas
python -m pytest tests/test_candados.py -v
python -m pytest tests/test_api_web.py -v
python -m pytest tests/test_kpis.py -v
python -m pytest tests/test_diagnostico.py -v
python -m pytest tests/test_pdf.py -v
```

### 3.3 Requisito de Aprobación
- Antes de enviar un cambio, el 100% de las pruebas (actualmente 20 pruebas) debe terminar en **PASSED**.
- Si se agrega una nueva funcionalidad o cálculo, se debe añadir su correspondiente prueba en `tests/`.

---

## 4. Flujo de Trabajo para Añadir Funcionalidades

### 4.1 Añadir un Nuevo Endpoint en la API
1. Definir el esquema Pydantic en `server.py` si requiere payload de entrada.
2. Definir la ruta antes de rutas con parámetros dinámicos si la URL es fija.
3. Invocar la lógica de negocio en `database.py`.
4. Sanitizar la salida con `sanitizar_nativos()` si involucra DataFrames o cálculos estadísticos.
5. Crear la prueba unitaria en `tests/test_api_web.py`.
6. Documentar el endpoint en `API_REFERENCE.md`.

### 4.2 Añadir una Nueva Tipología de Chasis
1. Registrar la tipología en la tabla `catalogo_tipologias` con su nombre, cantidad de llantas y su `esquema_json`.
2. El esquema JSON debe respetar el formato canónico:
   ```json
   [
     {
       "eje": 1,
       "nombre": "Eje 1 (Direccional)",
       "tipo": "direccional",
       "posiciones": [
         {"pos": 1, "lado": "izq", "rol": "DIR"},
         {"pos": 2, "lado": "der", "rol": "DIR"}
       ]
     }
   ]
   ```
3. El frontend renderizará automáticamente el nuevo chasis sin requerir cambios en el código de dibujo.

---

## 5. Checklist de Verificación Pre-Entrega

- [ ] Las 20 pruebas de pytest pasan exitosamente (`20 passed`).
- [ ] No hay errores en la consola de JavaScript al navegar por las 6 vistas.
- [ ] Los 60 registros de `inspecciones.db` se conservan intactos.
- [ ] Los archivos de contingencia (`app.py`, `iniciar_app.bat`) permanecen operativos.
- [ ] La documentación en `DOCUMENTACION_MIGRACION.md` y `API_REFERENCE.md` refleja los cambios realizados.
