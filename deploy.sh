#!/bin/bash
set -e

echo "🔄 Actualizando código desde GitHub..."
git pull origin main

echo "📦 Instalando dependencias del backend..."
pip install -r requirements.txt

echo "🗄️ Aplicando migraciones..."
python manage.py migrate

echo "🏗️ Rebuildeando contenedores..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "✅ Deploy completado!"
echo "Verificando servicios..."
sleep 5
docker compose ps
