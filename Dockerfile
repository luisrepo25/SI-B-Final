FROM python:3.12-slim

# Evitar prompts y usar apt seguro
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Instalar cliente postgres (pg_dump/psql) y dependencias mínimas
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el resto del código
COPY . /app

# Exponer puerto (informativo)
EXPOSE 8080

# Ejecutar Gunicorn respetando la variable PORT si está presente
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080}"]
