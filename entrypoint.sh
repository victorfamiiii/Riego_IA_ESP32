#!/bin/bash
set -e

echo "Esperando a que PostgreSQL este listo..."
MAX_ATTEMPTS=30
ATTEMPT=1

until python manage.py check --database default > /dev/null 2>&1; do
  if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "PostgreSQL no respondio despues de $MAX_ATTEMPTS intentos"
    exit 1
  fi
  echo "Esperando base de datos... ($ATTEMPT/$MAX_ATTEMPTS)"
  sleep 2
  ATTEMPT=$((ATTEMPT + 1))
done

echo "PostgreSQL esta listo"

echo "Verificando que no falten migraciones versionadas..."
python manage.py makemigrations --check --dry-run --noinput || {
  echo "Hay cambios de modelos sin migraciones versionadas."
  echo "Genera y commitea las migraciones para evitar desalineacion de esquema."
}

echo "Aplicando migraciones..."
python manage.py migrate --noinput || {
  echo "Error en migraciones, continuando..."
}

echo "Creando superusuario si no existe..."
python manage.py shell << 'PYTHON' || true
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'Sistemas2025!yupiPl3lpop')
    print('Superusuario creado')
else:
    print('Superusuario ya existe')
PYTHON

echo "Iniciando Gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:8000 \
  --workers ${GUNICORN_WORKERS:-3} \
  --threads ${GUNICORN_THREADS:-2} \
  --timeout ${GUNICORN_TIMEOUT:-300} \
  --graceful-timeout 30 \
  --worker-class sync \
  --access-logfile - \
  --error-logfile - \
  --log-level ${LOG_LEVEL:-info} \
  backend.wsgi:application
