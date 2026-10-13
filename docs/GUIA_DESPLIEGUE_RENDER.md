# 🌐 Guía de Despliegue en Render.com (Plan Gratuito 24/7)

Esta guía te explica cómo publicar **TireCheck Pro** en internet de forma **100% gratuita** utilizando **Render.com** para que cualquier persona pueda ver y probar la aplicación desde su computadora o celular a través de una URL pública con HTTPS.

---

## 📋 Requisitos Previos

1. Una cuenta gratuita en **[GitHub](https://github.com)**.
2. Una cuenta gratuita en **[Render.com](https://render.com)** (puedes registrarte con tu cuenta de GitHub con 1 clic).

---

## 🚀 Método Recomendado: Despliegue en 3 Pasos

### Paso 1: Subir el Proyecto a tu GitHub

1. En tu cuenta de GitHub, crea un nuevo repositorio (por ejemplo, `tirecheck-pro`). Puedes elegir si es **Público** o **Privado**.
2. En tu terminal o consola en la carpeta de TireCheck Pro, sube tu código:
   ```bash
   git init
   git add .
   git commit -m "TireCheck Pro: Versión Demo para Despliegue en Render"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/tirecheck-pro.git
   git push -u origin main
   ```

---

### Paso 2: Crear el Servicio Web en Render.com

1. Inicia sesión en **[dashboard.render.com](https://dashboard.render.com/)**.
2. Haz clic en el botón azul **`New +`** (arriba a la derecha) y selecciona **`Web Service`**.
3. Selecciona la opción **`Build and deploy from a Git repository`**.
4. Conecta tu cuenta de GitHub y selecciona tu repositorio `tirecheck-pro`.
5. Render leerá automáticamente el archivo `render.yaml` o te pedirá confirmar estos datos:
   - **Name:** `tirecheck-pro` (o el nombre que prefieras).
   - **Region:** `Oregon (US West)` o la más cercana.
   - **Branch:** `main`.
   - **Runtime:** `Python 3` (o `Docker`).
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Selecciona **`Free`** ($0.00 / month).
6. Haz clic en **`Create Web Service`**.

---

### Paso 3: ¡Listo! Accede a tu Aplicativo

1. Render comenzará a instalar las dependencias y en 2 a 3 minutos mostrará el mensaje en verde:
   ```text
   ==> Your service is live 🎉
   ```
2. En la parte superior izquierda de tu dashboard verás tu URL pública oficial con certificado SSL seguro gratuito:
   ```text
   https://tirecheck-pro.onrender.com
   ```
3. ¡Comparte ese enlace con tus clientes o evaluadores! Funciona directamente desde computadoras de escritorio, tablets y teléfonos celulares.

---

## ℹ️ Características del Plan Gratuito de Render

- **Costo:** $0.00 USD / mes.
- **Certificado SSL / HTTPS:** Automático y gratuito.
- **Comportamiento en inactividad (*Spin down*):**
  - Si la aplicación no recibe visitas durante 15 minutos, Render pone el contenedor en reposo para ahorrar energía.
  - Cuando alguien vuelve a entrar a la URL, la aplicación se reactiva automáticamente en unos 30-45 segundos. Las siguientes solicitudes responden de forma instantánea.
- **Usuarios de prueba listos:**
  - `admin` (clave: `admin123`)
  - `inspector1` (clave: `1234`)
