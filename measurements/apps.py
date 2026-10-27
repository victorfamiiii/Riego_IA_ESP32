import os
import threading
import logging

import firebase_admin
from firebase_admin import credentials
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MeasurementsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'measurements'
    verbose_name = 'Mediciones'

    def ready(self):
        """
        Se ejecuta cuando Django arranca.
        Inicializa Firebase y lanza el scheduler de AEMET solo en el proceso
        principal de Gunicorn, evitando duplicados en cada worker.
        """
        # ── Firebase ──────────────────────────────────────────────────────
        if not firebase_admin._apps:
            cred_path = os.environ.get(
                'FIREBASE_CREDENTIALS_PATH', '/app/firebase-adminsdk.json'
            )
            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info("🔥 Firebase inicializado correctamente")
            except Exception as e:
                logger.error(f"❌ Error inicializando Firebase: {e}")

        # ── AEMET Scheduler ───────────────────────────────────────────────
        # Solo arrancar en el proceso principal (no en migraciones, shell, etc.)
        # Gunicorn define SERVER_SOFTWARE, RUN_MAIN es para runserver
        run_main = os.environ.get('RUN_MAIN')
        server_software = os.environ.get('SERVER_SOFTWARE', '')

        if run_main == 'true' or 'gunicorn' in server_software.lower():
            self._iniciar_scheduler_aemet()
            self._iniciar_scheduler_gemini()

    def _iniciar_scheduler_gemini(self):
        """Lanza decisiones de riego con Gemini cada 30 minutos"""
        lock_file = '/tmp/gemini_scheduler.lock'
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            return

        import atexit
        atexit.register(lambda: os.remove(lock_file) if os.path.exists(lock_file) else None)

        logger.info("🌱 Scheduler Gemini iniciado: decisiones de riego cada 30 min")

        thread = threading.Thread(
            target=self._loop_gemini,
            daemon=True,
            name='gemini-scheduler'
        )
        thread.start()

    @staticmethod
    def _loop_gemini():
        import time
        from .gemini_service import get_irrigation_decision
        from .irrigation_control import IrrigationController
        
        time.sleep(60)  # Esperar 60s al arrancar

        while True:
            try:
                for planta in ['fresa', 'lechuga']:
                    # 0️⃣ VERIFICAR CONFIGURACIÓN ANTES DE LLAMAR A GEMINI
                    try:
                        controller = IrrigationController()
                        config = controller.get_plant_config(planta)
                        
                        # Comprobar si riego automático está desactivado
                        if not config.get('riego_automatico_activo', True):
                            logger.debug(f"⏭️  [Gemini] {planta}: Riego automático desactivado por configuración")
                            continue
                        
                        # Comprobar si modo de riego es IA
                        if config.get('modo_riego') != 'ia':
                            logger.debug(f"⏭️  [Gemini] {planta}: Modo de riego no es 'ia' (es '{config.get('modo_riego')}')")
                            continue
                    except Exception as cfg_error:
                        logger.warning(f"⚠️  [Gemini] {planta}: No se pudo verificar configuración: {cfg_error}")
                        continue
                    
                    # 1️⃣ OBTENER DECISIÓN DE GEMINI (solo si está en modo IA)
                    result = get_irrigation_decision(planta)
                    
                    # 2️⃣ VALIDAR ESTRUCTURA Y SEGURIDAD
                    if not isinstance(result, dict):
                        logger.error(f"[SEGURIDAD] {planta}: Respuesta no es dict: {type(result)}")
                        continue
                    
                    # Validar campos obligatorios
                    if 'regar' not in result or 'duracion_segundos' not in result:
                        logger.error(f"[SEGURIDAD] {planta}: Campos faltantes en respuesta Gemini")
                        continue
                    
                    regar = result.get('regar')
                    duracion = result.get('duracion_segundos', 0)
                    razon = result.get('razon', 'Sin razón')
                    
                    # Validar tipos de datos
                    if not isinstance(regar, bool):
                        logger.error(f"[SEGURIDAD] {planta}: 'regar' no es booleano: {type(regar)}")
                        continue
                    
                    if not isinstance(duracion, (int, float)):
                        logger.error(f"[SEGURIDAD] {planta}: 'duracion_segundos' no es número: {type(duracion)}")
                        continue
                    
                    # 3️⃣ APLICAR LÍMITES DE SEGURIDAD
                    duracion = int(duracion)
                    if duracion < 0:
                        logger.error(f"[SEGURIDAD] {planta}: Duración negativa: {duracion}")
                        duracion = 0
                    if duracion > 60:
                        logger.warning(f"[SEGURIDAD] {planta}: Duración limitada de {duracion}s a 60s máximo")
                        duracion = 60
                    
                    # 5️⃣ EJECUTAR RIEGO CON SEGURIDAD
                    if regar and duracion > 0:
                        try:
                            logger.info(f"✅ [Gemini] {planta}: Iniciando riego {duracion}s - {razon}")
                            controller = IrrigationController()
                            # Intentar determinar el dispositivo más reciente asociado a esta planta
                            try:
                                from .models import SoilMoisture
                                last_reading = SoilMoisture.objects.filter(tipo_planta=planta).order_by('-created_at').first()
                                device = last_reading.device if last_reading else None
                            except Exception:
                                device = None

                            controller.iniciar_riego(
                                razon=f"Gemini ({duracion}s): {razon}",
                                tipo_planta=planta,
                                duracion_segundos=duracion,
                                automatico=True,
                                device=device,
                            )
                        except Exception as riego_error:
                            logger.error(f"❌ [Gemini] {planta}: Error ejecutando riego: {riego_error}")
                    else:
                        logger.info(f"⏭️  [Gemini] {planta}: No riego - {razon}")
            
            except Exception as e:
                logger.error(f"❌ Error en scheduler Gemini: {e}", exc_info=True)
            
            time.sleep(600)  # 10 minutos

    def _iniciar_scheduler_aemet(self):
        """Inicia el hilo de sincronización periódica de AEMET"""
        from django.conf import settings

        api_key = getattr(settings, 'AEMET_API_KEY', '')
        if not api_key:
            logger.info("ℹ️ AEMET_API_KEY no configurada. Scheduler de AEMET desactivado.")
            return

        # Usar un lock file para que solo un worker arranque el scheduler
        lock_file = '/tmp/aemet_scheduler.lock'
        try:
            # Intentar crear el lock (O_CREAT | O_EXCL falla si ya existe)
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            logger.debug("Scheduler de AEMET ya iniciado por otro worker.")
            return

        # Registrar para limpiar el lock al salir
        import atexit
        atexit.register(lambda: os.remove(lock_file) if os.path.exists(lock_file) else None)

        estacion_id = getattr(settings, 'AEMET_DEFAULT_STATION', '3195')
        intervalo = getattr(settings, 'AEMET_SYNC_INTERVAL', 3600)  # 1 hora por defecto

        logger.info(f"🌤️ Scheduler AEMET iniciado: estación {estacion_id}, cada {intervalo}s")

        thread = threading.Thread(
            target=self._loop_sincronizacion,
            args=(estacion_id, intervalo),
            daemon=True,
            name='aemet-scheduler'
        )
        thread.start()

    @staticmethod
    def _loop_sincronizacion(estacion_id, intervalo):
        """Bucle que sincroniza datos de AEMET periódicamente"""
        import time

        # Esperar 30 segundos al arrancar para que Django esté totalmente listo
        time.sleep(30)

        logger.info(f"🔄 Primera sincronización AEMET para estación {estacion_id}...")

        while True:
            try:
                from .aemet_service import AEMETService, ESTACIONES_PRINCIPALES
                aemet = AEMETService()

                # Obtener nombre de la estación
                nombre = ESTACIONES_PRINCIPALES.get(estacion_id, '')

                resultado = aemet.sincronizar_datos_periodicos(estacion_id, nombre)
                if resultado:
                    logger.info(f"✅ AEMET sincronizado: {estacion_id} ({nombre})")
                else:
                    logger.warning(f"⚠️ AEMET sin datos para: {estacion_id}")

            except Exception as e:
                logger.error(f"❌ Error en scheduler AEMET: {str(e)}")

            # Esperar para la próxima sincronización
            time.sleep(intervalo)