"""
Comando para monitorear la falta de datos de sensores
Se debe ejecutar periódicamente (cada 15-30 minutos) mediante cron o Celery

Uso:
python manage.py check_sensor_data

En production, agregar a crontab:
*/15 * * * * cd /ruta/proyecto && python manage.py check_sensor_data
"""

from django.core.management.base import BaseCommand
from measurements.data_monitoring_service import monitoring_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verifica si faltan datos de sensores por más de 2 horas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        
        if verbose:
            self.stdout.write(self.style.SUCCESS("🔍 Iniciando verificación de datos de sensores..."))
        
        # Ejecutar verificación
        result = monitoring_service.check_missing_data()
        
        if result.get('missing'):
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️ Se encontraron {len(result['missing'])} sensores sin datos recientes:\n" +
                    "\n".join([f"  • {item}" for item in result['missing']])
                )
            )
            if verbose:
                self.stdout.write(self.style.WARNING("Información de última recepción:"))
                for key, timestamp in result.get('last_timestamps', {}).items():
                    if timestamp:
                        self.stdout.write(f"  {key}: {timestamp}")
                    else:
                        self.stdout.write(f"  {key}: Nunca recibido")
        else:
            self.stdout.write(self.style.SUCCESS("✅ Todos los sensores están actualizados"))
        
        if verbose:
            self.stdout.write(self.style.SUCCESS("✅ Verificación completada"))
