# =============================================================================
# Dockerfile para Sistema de Riego Inteligente - Backend Django
# =============================================================================

FROM python:3.11-slim AS backend

# Variables de argumento para build
ARG DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema necesarias para Django y PostgreSQL
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario non-root para seguridad
RUN useradd -m -u 1000 django && \
    mkdir -p /app /app/staticfiles /app/media && \
    chown -R django:django /app

WORKDIR /app

# Copiar requirements e instalar dependencias como root
COPY --chown=django:django requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY --chown=django:django manage.py .
COPY --chown=django:django backend/ backend/
COPY --chown=django:django measurements/ measurements/
COPY --chown=django:django static/ static/

# Copiar credenciales de Firebase (requerido para FCM)
COPY --chown=django:django firebase-adminsdk.json .

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=backend.settings \
    PATH="/home/django/.local/bin:${PATH}"

# Recopilar archivos estáticos
RUN python manage.py collectstatic --noinput --clear

# Cambiar a usuario non-root
USER django

# Exponer puerto
EXPOSE 8000

# Script de inicio que hace migraciones antes de arrancar
COPY --chown=django:django entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
