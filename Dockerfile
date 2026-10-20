FROM python:3.12-slim

# Evitar generación de .pyc y habilitar salida de logs sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV APP_BUILD_ID=20261020-rebuild-railway

WORKDIR /app

# Instalar dependencias del sistema mínimas necesarias para compilación y fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Asegurar que el archivo seed_inspecciones.db exista en la raíz del contenedor (fuera del punto de montaje del volumen)
RUN cp -n data/inspecciones.db /app/seed_inspecciones.db 2>/dev/null || true

# Asegurar existencia y permisos del directorio data para SQLite
RUN mkdir -p /app/data && chmod 777 /app/data


# Exponer puerto
EXPOSE 8000

# Comando de arranque directo con Python (parseo robusto de puerto)
CMD ["python", "server.py"]
