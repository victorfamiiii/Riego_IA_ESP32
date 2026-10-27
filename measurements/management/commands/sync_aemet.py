"""
Management command para sincronizar datos de AEMET manualmente.

Uso:
    python manage.py sync_aemet                     # Usa estación por defecto
    python manage.py sync_aemet --estacion 8416     # Valencia
    python manage.py sync_aemet --todas              # Todas las principales
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from measurements.aemet_service import AEMETService, ESTACIONES_PRINCIPALES


class Command(BaseCommand):
    help = 'Sincroniza datos meteorológicos desde la API de AEMET'

    def add_arguments(self, parser):
        parser.add_argument(
            '--estacion',
            type=str,
            default=None,
            help='ID de la estación AEMET (ej: 3195 para Madrid-Retiro)'
        )
        parser.add_argument(
            '--todas',
            action='store_true',
            help='Sincronizar todas las estaciones principales'
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, 'AEMET_API_KEY', '')
        if not api_key:
            self.stderr.write(self.style.ERROR(
                '❌ AEMET_API_KEY no configurada. '
                'Añádela como variable de entorno o en settings.py'
            ))
            return

        aemet = AEMETService()

        if options['todas']:
            self.stdout.write(self.style.NOTICE(
                f'🔄 Sincronizando {len(ESTACIONES_PRINCIPALES)} estaciones...'
            ))
            exitos = 0
            for est_id, est_nombre in ESTACIONES_PRINCIPALES.items():
                resultado = aemet.sincronizar_datos_periodicos(est_id, est_nombre)
                if resultado:
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ {est_nombre} ({est_id})'
                    ))
                    exitos += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️ {est_nombre} ({est_id}) - sin datos'
                    ))

            self.stdout.write(self.style.SUCCESS(
                f'\n📊 Resultado: {exitos}/{len(ESTACIONES_PRINCIPALES)} estaciones sincronizadas'
            ))
        else:
            estacion_id = options['estacion'] or getattr(
                settings, 'AEMET_DEFAULT_STATION', '3195'
            )
            nombre = ESTACIONES_PRINCIPALES.get(estacion_id, '')

            self.stdout.write(self.style.NOTICE(
                f'🔄 Sincronizando estación {estacion_id} ({nombre})...'
            ))

            resultado = aemet.sincronizar_datos_periodicos(estacion_id, nombre)

            if resultado:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Datos sincronizados correctamente para {estacion_id} ({nombre})'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'❌ No se pudieron obtener datos para {estacion_id}'
                ))
