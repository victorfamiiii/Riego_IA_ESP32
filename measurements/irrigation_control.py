# pyright: reportMissingImports=false

"""
Sistema de control automático de riego
Analiza la humedad del suelo y decide cuándo activar/desactivar el riego
"""
import json
import logging
import os
import time
import ssl

from django.utils import timezone
from django.core.exceptions import MultipleObjectsReturned
from datetime import timedelta
from .models import (
    Measurement,
    IrrigationEvent,
    IrrigationConfig,
    SoilMoisture,
    SensorCalibrationSettings,
)

logger = logging.getLogger(__name__)


def _publish_mqtt_command(topic, payload):
    host = os.getenv('MQTT_HOST', 'mqtt')
    port = int(os.getenv('MQTT_PORT', '8883'))
    username = os.getenv('MQTT_USERNAME', '')
    password = os.getenv('MQTT_PASSWORD', '')
    ca_cert = os.getenv('MQTT_TLS_CA_CERT', '/app/certs/mqtt-ca.pem')

    import paho.mqtt.client as mqtt_paho

    client = mqtt_paho.Client(client_id=f'django-irrigation-{int(time.time())}')
    if username:
        client.username_pw_set(username, password)

    try:
        client.tls_set(ca_certs=ca_cert, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        client.tls_insecure_set(False)
        client.connect(host, port, keepalive=5)
        client.loop_start()
        info = client.publish(topic, json.dumps(payload), qos=1)
        info.wait_for_publish(timeout=3)
        client.disconnect()
        client.loop_stop()
        return True
    except Exception as exc:
        logger.warning('MQTT publish failed: %s', exc)
        try:
            client.loop_stop()
        except Exception:
            pass
        return False


class IrrigationController:
    """
    Controlador de riego automático
    
    Reglas básicas:
    1. Si humedad < umbral_minimo (40%) → ACTIVAR riego
    2. Regar durante tiempo_riego_segundos (configurable)
    3. No regar más de max_riegos_dia veces al día
    4. Esperar tiempo_minimo_entre_riegos entre riegos
    """
    
    def __init__(self):
        """Inicializar controlador"""
        self.calibration = SensorCalibrationSettings.get_config()
    
    @classmethod
    def get_or_create_default_config_by_plant(cls, tipo_planta='general'):
        """Obtener o crear configuración activa por tipo de planta"""
        tipo_planta = cls._normalize_plant_type_static(tipo_planta)
        
        defaults = {
            'umbral_humedad_minimo': 40.0,  # % humedad mínima
            'mediciones_para_media': 4,
            'tiempo_riego_segundos': 10,     # 10 segundos de riego
            'max_riegos_dia': 6,             # Máximo 6 riegos al día
            'tiempo_minimo_entre_riegos': 3600,  # 1 hora entre riegos
            'riego_automatico_activo': True,
            'configuracion_por_planta': {},
        }

        try:
            config, _ = IrrigationConfig.objects.get_or_create(
                tipo_planta=tipo_planta,
                activo=True,
                defaults=defaults,
            )
            return config
        except MultipleObjectsReturned:
            # Si hay múltiples configs activas para la misma planta, desactivar todas menos la más reciente
            active_configs = IrrigationConfig.objects.filter(
                tipo_planta=tipo_planta,
                activo=True
            ).order_by('-updated_at', '-created_at')
            config = active_configs.first()
            if config:
                IrrigationConfig.objects.filter(
                    tipo_planta=tipo_planta,
                    activo=True
                ).exclude(pk=config.pk).update(activo=False)
                return config
            
            config = IrrigationConfig.objects.create(
                tipo_planta=tipo_planta,
                activo=True,
                **defaults
            )
            return config
    
    @staticmethod
    def _normalize_plant_type_static(tipo_planta=None):
        raw = (tipo_planta or 'lechuga').strip().lower()
        if raw in ('fresa', 'fresas'):
            return 'fresa'
        if raw in ('lechuga', 'lechugas'):
            return 'lechuga'
        return 'lechuga'
    
    def get_config_by_plant(self, tipo_planta='lechuga'):
        """Obtener configuración activa para un tipo de planta específico"""
        return IrrigationConfig.get_config_by_plant(tipo_planta)

    def _as_float(self, value, fallback):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    def _as_int(self, value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)

    def _normalize_plant_type(self, tipo_planta=None):
        raw = (tipo_planta or 'lechuga').strip().lower()
        if raw in ('fresa', 'fresas'):
            return 'fresa'
        if raw in ('lechuga', 'lechugas'):
            return 'lechuga'
        return 'lechuga'

    def get_plant_config(self, tipo_planta=None):
        """Obtiene la configuración específica para un tipo de planta"""
        plant_key = self._normalize_plant_type(tipo_planta)
        
        # Obtener config específica por planta o la general como fallback
        config = IrrigationConfig.get_config_by_plant(plant_key)
        
        if config:
            return {
                'plant_type': plant_key,
                'umbral_humedad_minimo': config.umbral_humedad_minimo,
                'mediciones_para_media': config.mediciones_para_media,
                'tiempo_riego_segundos': config.tiempo_riego_segundos,
                'max_riegos_dia': config.max_riegos_dia,
                'tiempo_minimo_entre_riegos': config.tiempo_minimo_entre_riegos,
                'riego_automatico_activo': config.riego_automatico_activo,
                'modo_riego': config.modo_riego,
            }
        
        # Fallback a valores por defecto si no hay configuración
        return {
            'plant_type': plant_key,
            'umbral_humedad_minimo': 40.0,
            'mediciones_para_media': 4,
            'tiempo_riego_segundos': 10,
            'max_riegos_dia': 6,
            'tiempo_minimo_entre_riegos': 3600,
            'riego_automatico_activo': True,
        }

    def get_all_plant_configs(self):
        return {
            'lechuga': self.get_plant_config('lechuga'),
            'fresa': self.get_plant_config('fresa'),
        }
    
    def necesita_riego(self, humedad_actual, tipo_planta=None):
        """
        Determinar si se necesita activar el riego
        
        Args:
            humedad_actual (float): Porcentaje de humedad del suelo
            
        Returns:
            tuple: (necesita_riego: bool, razon: str)
        """
        # Verificar si el riego automático está activo
        plant_config = self.get_plant_config(tipo_planta)
        
        if not plant_config['riego_automatico_activo']:
            return False, "Riego automático desactivado para " + plant_config['plant_type']
        
        plant_label = plant_config['plant_type']
        
        # Verificar si el modo de riego permite riego por umbral
        modo_riego = plant_config.get('modo_riego', 'umbral')
        if modo_riego != 'umbral':
            return False, f"Modo de riego es '{modo_riego}' (no umbral) para {plant_label}"
        
        # Verificar si la humedad está por debajo del umbral
        if humedad_actual >= plant_config['umbral_humedad_minimo']:
            return False, f"Humedad OK {plant_label} ({humedad_actual}% >= {plant_config['umbral_humedad_minimo']}%)"
        
        # Verificar si hay riego activo actualmente
        active_query = IrrigationEvent.objects.filter(fecha_fin__isnull=True)
        if tipo_planta:
            active_query = active_query.filter(tipo_planta=plant_config['plant_type'])
        riego_activo = active_query.first()
        
        if riego_activo:
            return False, "Ya hay un riego en curso"
        
        # Verificar tiempo mínimo entre riegos
        last_query = IrrigationEvent.objects.filter(fecha_fin__isnull=False)
        if tipo_planta:
            last_query = last_query.filter(tipo_planta=plant_config['plant_type'])
        ultimo_riego = last_query.first()
        
        if ultimo_riego:
            tiempo_desde_ultimo = (timezone.now() - ultimo_riego.fecha_fin).total_seconds()
            if tiempo_desde_ultimo < plant_config['tiempo_minimo_entre_riegos']:
                minutos_espera = int((plant_config['tiempo_minimo_entre_riegos'] - tiempo_desde_ultimo) / 60)
                return False, f"Esperar {minutos_espera} minutos más para {plant_label} desde último riego"
        
        # Verificar máximo de riegos por día
        hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_query = IrrigationEvent.objects.filter(fecha_inicio__gte=hoy_inicio)
        if tipo_planta:
            day_query = day_query.filter(tipo_planta=plant_config['plant_type'])
        riegos_hoy = day_query.count()
        
        if riegos_hoy >= plant_config['max_riegos_dia']:
            return False, f"Máximo de riegos diarios para {plant_label} alcanzado ({riegos_hoy}/{plant_config['max_riegos_dia']})"
        
        # ¡NECESITA RIEGO!
        return True, f"Humedad baja {plant_label} ({humedad_actual}% < {plant_config['umbral_humedad_minimo']}%)"

    def get_latest_soil_measurement(self, tipo_planta=None, device=None):
        queryset = SoilMoisture.objects.all()
        if tipo_planta:
            queryset = queryset.filter(tipo_planta=self._normalize_plant_type(tipo_planta))
        if device:
            queryset = queryset.filter(device=device)
        return queryset.order_by('-created_at').first()

    def get_recent_soil_measurements(self, tipo_planta=None, device=None, limit=4):
        queryset = SoilMoisture.objects.all()
        if tipo_planta:
            queryset = queryset.filter(tipo_planta=self._normalize_plant_type(tipo_planta))
        if device:
            queryset = queryset.filter(device=device)
        return list(queryset.order_by('-created_at')[:limit])

    def _resolve_relay(self, relay=None, tipo_planta=None):
        normalized_plant = self._normalize_plant_type(tipo_planta) if tipo_planta else None
        if normalized_plant == 'fresa':
            return 2
        if normalized_plant == 'lechuga':
            return 1
        if relay in (1, 2):
            return relay
        return 1

    def _get_calibrated_soil_humidity(self, value, relay=None, tipo_planta=None):
        resolved_relay = self._resolve_relay(relay=relay, tipo_planta=tipo_planta)
        return self.calibration.calibrate_soil_humidity(value, relay=resolved_relay)

    def estimate_liters(self, relay=None, duration_seconds=None, tipo_planta=None):
        resolved_relay = self._resolve_relay(relay=relay, tipo_planta=tipo_planta)
        return self.calibration.estimate_liters(resolved_relay, duration_seconds)

    def estimate_duration_seconds(self, relay=None, litros=None, tipo_planta=None):
        resolved_relay = self._resolve_relay(relay=relay, tipo_planta=tipo_planta)
        return self.calibration.estimate_duration_seconds(resolved_relay, litros)

    def _resolve_device_for_riego(self, tipo_planta=None, device=None):
        if device is not None:
            return device

        plant_key = self._normalize_plant_type(tipo_planta)
        last_reading = self.get_latest_soil_measurement(tipo_planta=plant_key)
        if last_reading and getattr(last_reading, 'device', None):
            return last_reading.device

        return None

    def necesita_riego_por_planta(self, tipo_planta=None, device=None, relay=None):
        plant_config = self.get_plant_config(tipo_planta)
        sample_size = max(1, self._as_int(plant_config.get('mediciones_para_media', 4), 4))
        mediciones = self.get_recent_soil_measurements(tipo_planta=tipo_planta, device=device, limit=sample_size)
        if not mediciones:
            return False, 'Sin medición de humedad de suelo reciente', None

        humedades_calibradas = [
            self._get_calibrated_soil_humidity(
                medicion.humedad_suelo,
                relay=relay,
                tipo_planta=tipo_planta,
            )
            for medicion in mediciones
        ]
        humedad_promedio = round(sum(humedades_calibradas) / len(humedades_calibradas), 2)

        necesita, razon = self.necesita_riego(humedad_promedio, tipo_planta=tipo_planta)
        razon = f"{razon} (media últimas {len(humedades_calibradas)}: {humedad_promedio}%)"

        # Mantener compatibilidad: devolver la medicion mas reciente junto a la decision.
        medicion_reciente = mediciones[0]
        return necesita, razon, medicion_reciente
    
    def iniciar_riego(self, razon="Riego automático", *, device=None, relay=None, tipo_planta=None, duracion_segundos=None, automatico=True):
        """
        Iniciar un nuevo evento de riego
        
        Args:
            razon (str): Razón del riego
            
        Returns:
            IrrigationEvent: Evento de riego creado
        """
        normalized_plant = self._normalize_plant_type(tipo_planta)
        resolved_relay = self._resolve_relay(relay=relay, tipo_planta=normalized_plant)
        resolved_device = self._resolve_device_for_riego(tipo_planta=normalized_plant, device=device)

        # Obtener última medición para registrar valores
        ultima_medicion = Measurement.objects.first()
        ultima_medicion_suelo = self.get_latest_soil_measurement(tipo_planta=normalized_plant, device=resolved_device)
        
        plant_config = self.get_plant_config(normalized_plant)
        planned_duration = duracion_segundos or plant_config['tiempo_riego_segundos']

        evento = IrrigationEvent.objects.create(
            device=resolved_device,
            relay=resolved_relay,
            tipo_planta=normalized_plant,
            fecha_inicio=timezone.now(),
            humedad_inicial=(
                self._get_calibrated_soil_humidity(
                    ultima_medicion_suelo.humedad_suelo,
                    relay=resolved_relay,
                    tipo_planta=normalized_plant,
                )
                if ultima_medicion_suelo
                else (ultima_medicion.humedad if ultima_medicion else 0)
            ),
            temperatura_inicial=ultima_medicion.temperatura if ultima_medicion else 0,
            duracion_planificada_segundos=planned_duration,
            litros=self.estimate_liters(
                relay=resolved_relay,
                duration_seconds=planned_duration,
                tipo_planta=normalized_plant,
            ),
            razon=razon,
            automatico=automatico
        )                          # ← paréntesis de cierre aquí

        try:                       # ← 8 espacios, mismo nivel que "evento ="
            from .firebase_service import firebase_service
            planta_label = normalized_plant.capitalize()
            firebase_service.send_to_all_users(
                title=f"💧 Regando {planta_label}",
                body=f"{'⏱️ Automático' if automatico else '🖐️ Manual'} · {planned_duration}s — {razon}",
                data={
                    "tipo": "riego_inicio",
                    "planta": normalized_plant,
                    "trigger": "automatico" if automatico else "manual",
                    "duracion": str(planned_duration),
                    "evento_id": str(evento.id),
                }
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"FCM notification failed: {e}")

        # Publicar comando MQTT inmediato si conocemos el dispositivo (igual que riego manual)
        try:
            device_mac = getattr(resolved_device, 'mac_address', None)
            if device_mac:
                # Construir payload igual que en frontend manual
                mqtt_payload = {
                    'status': 'ok',
                    'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'next_poll_ms': 5000,
                    'active_poll_ms': 5000,
                    'commands': [{
                        'relay': resolved_relay,
                        'plant_type': normalized_plant,
                        'command': 'ON',
                        'duration': evento.duracion_planificada_segundos,
                        'reason': evento.razon,
                        'event_id': evento.id,
                    }],
                }
                topic = f"esp32/{device_mac}/commands/response"
                if _publish_mqtt_command(topic, mqtt_payload):
                    logger.info("MQTT command published for event %s to %s", evento.id, device_mac)
                else:
                    logger.warning("MQTT publish failed for event %s to %s", evento.id, device_mac)
        except Exception:
            # No impedir que el flujo principal falle por este extra
            logger.debug("No se pudo enviar MQTT inmediato (device desconocido o error)", exc_info=True)

        return evento

    def registrar_inicio_dispositivo(self, evento_id):
        """
        Marcar el momento en que la ESP32 confirmó realmente el arranque.

        Esto permite medir la duración real desde el inicio efectivo del riego,
        no desde el instante en que el servidor creó el evento.
        """
        try:
            evento = IrrigationEvent.objects.get(id=evento_id)
        except IrrigationEvent.DoesNotExist:
            return None

        if evento.device_started_at is None:
            evento.device_started_at = timezone.now()
            evento.save(update_fields=['device_started_at'])

        return evento

    def solicitar_parada(self, evento_id):
        try:
            evento = IrrigationEvent.objects.get(id=evento_id)
        except IrrigationEvent.DoesNotExist:
            return None

        if not evento.fecha_fin:
            evento.stop_requested = True
            evento.save(update_fields=['stop_requested'])
        return evento
    
    def finalizar_riego(self, evento_id, humedad_final=None, temperatura_final=None):
        """
        Finalizar un evento de riego
        
        Args:
            evento_id (int): ID del evento a finalizar
            
        Returns:
            IrrigationEvent: Evento actualizado
        """
        try:
            evento = IrrigationEvent.objects.get(id=evento_id)
            
            # Si ya está finalizado, no hacer nada
            if evento.fecha_fin:
                return evento
            
            # Finalizar evento
            evento.fecha_fin = timezone.now()
            inicio_real = evento.device_started_at or evento.fecha_inicio
            evento.duracion_real_segundos = int((evento.fecha_fin - inicio_real).total_seconds())
            
            # Obtener humedad final
            ultima_medicion = Measurement.objects.first()
            ultima_medicion_suelo = self.get_latest_soil_measurement(tipo_planta=evento.tipo_planta, device=evento.device)
            if humedad_final is not None:
                evento.humedad_final = self._get_calibrated_soil_humidity(
                    humedad_final,
                    relay=evento.relay,
                    tipo_planta=evento.tipo_planta,
                )
            elif ultima_medicion_suelo:
                evento.humedad_final = self._get_calibrated_soil_humidity(
                    ultima_medicion_suelo.humedad_suelo,
                    relay=evento.relay,
                    tipo_planta=evento.tipo_planta,
                )
            elif ultima_medicion:
                evento.humedad_final = ultima_medicion.humedad

            if evento.litros is None:
                evento.litros = self.estimate_liters(
                    relay=evento.relay,
                    duration_seconds=evento.duracion_real_segundos,
                    tipo_planta=evento.tipo_planta,
                )

            if temperatura_final is not None:
                evento.temperatura_final = temperatura_final
            elif ultima_medicion:
                evento.temperatura_final = ultima_medicion.temperatura
            
            evento.save()
            return evento
            
        except IrrigationEvent.DoesNotExist:
            return None
    
    def verificar_y_gestionar_riego(self):
        """
        Verificar si hay riegos que finalizar y si se necesita iniciar uno nuevo
        
        AHORA: Riegos PARALELOS por planta
        - Lechuga (relay 1) y Fresa (relay 2) pueden estar activas simultáneamente
        - Cada planta se gestiona de forma independiente
        
        Esta función debe llamarse cada vez que llega una nueva medición
        
        Returns:
            dict: Estado del sistema de riego
        """
        resultado = {
            'riego_activo': False,
            'comando': 'OFF',  # OFF o ON
            'evento_id': None,
            'razon': '',
            'tiempo_restante': 0,
            'plantas': {}  # Nueva clave para riegos por planta
        }
        
        # Verificar y gestionar riegos por PLANTA de forma independiente
        for tipo_planta in ['lechuga', 'fresa']:
            resultado['plantas'][tipo_planta] = self._verificar_riego_planta(tipo_planta)
            
            # Si alguna planta está activa, marcar como riego_activo
            if resultado['plantas'][tipo_planta]['comando'] == 'ON':
                resultado['riego_activo'] = True
        
        return resultado
    
    def _verificar_riego_planta(self, tipo_planta):
        """
        Verificar y gestionar riego para UNA PLANTA específica
        Permite riegos paralelos independientes
        
        Returns:
            dict: Estado de riego para esta planta
        """
        resultado = {
            'comando': 'OFF',
            'evento_id': None,
            'razon': '',
            'tiempo_restante': 0
        }
        
        # 1. Buscar riego ACTIVO para ESTA PLANTA
        riego_activo = IrrigationEvent.objects.filter(
            fecha_fin__isnull=True,
            tipo_planta=tipo_planta
        ).first()
        
        if riego_activo:
            tiempo_transcurrido = (timezone.now() - riego_activo.fecha_inicio).total_seconds()
            tiempo_restante = riego_activo.duracion_planificada_segundos - tiempo_transcurrido
            
            if tiempo_transcurrido >= riego_activo.duracion_planificada_segundos:
                self.finalizar_riego(riego_activo.id)
                resultado['comando'] = 'OFF'
                resultado['razon'] = f'{tipo_planta.capitalize()}: riego completado'
            else:
                resultado['comando'] = 'ON'
                resultado['evento_id'] = riego_activo.id
                resultado['tiempo_restante'] = int(tiempo_restante)
                resultado['razon'] = f'{tipo_planta.capitalize()} en curso ({int(tiempo_restante)}s restantes)'
            
            return resultado
        
        # 2. No hay riego activo para ESTA PLANTA, verificar si lo necesita
        necesita, razon, medicion_reciente = self.necesita_riego_por_planta(tipo_planta=tipo_planta)

        if not medicion_reciente:
            resultado['razon'] = razon
            return resultado

        if necesita:
            dispositivo = getattr(medicion_reciente, 'device', None)
            evento = self.iniciar_riego(
                razon,
                tipo_planta=tipo_planta,
                device=dispositivo,
                relay=None,
                automatico=True
            )
            resultado['comando'] = 'ON'
            resultado['evento_id'] = evento.id
            plant_config = self.get_plant_config(tipo_planta)
            resultado['tiempo_restante'] = plant_config['tiempo_riego_segundos']
            resultado['razon'] = razon
        else:
            resultado['razon'] = razon
        
        return resultado
    
    def get_estado_actual(self):
        """
        Obtener estado actual del sistema sin modificar nada
        
        Ahora incluye estado INDEPENDIENTE de cada planta (lechuga y fresa)
        Puede haber riegos simultáneos
        
        Returns:
            dict: Estado actual del sistema
        """
        ultima_medicion = Measurement.objects.first()
        
        estado = {
            'configuracion': {
                'umbral_humedad': self.get_plant_config('lechuga')['umbral_humedad_minimo'],
                'tiempo_riego': self.get_plant_config('lechuga')['tiempo_riego_segundos'],
                'max_riegos_dia': self.get_plant_config('lechuga')['max_riegos_dia'],
                'automatico_activo': (
                    self.get_plant_config('lechuga')['riego_automatico_activo']
                    or self.get_plant_config('fresa')['riego_automatico_activo']
                )
            },
            'configuracion_por_planta': self.get_all_plant_configs(),
            'humedad_actual': ultima_medicion.humedad if ultima_medicion else None,
            'temperatura_actual': ultima_medicion.temperatura if ultima_medicion else None,
            'riegos_activos': {}  # Nueva estructura: por planta
        }
        
        # Estado de riegos por PLANTA (independientes)
        for tipo_planta in ['lechuga', 'fresa']:
            riego_activo = IrrigationEvent.objects.filter(
                fecha_fin__isnull=True,
                tipo_planta=tipo_planta
            ).first()
            
            if riego_activo:
                tiempo_transcurrido = (timezone.now() - riego_activo.fecha_inicio).total_seconds()
                tiempo_restante = max(0, riego_activo.duracion_planificada_segundos - tiempo_transcurrido)
                
                estado['riegos_activos'][tipo_planta] = {
                    'id': riego_activo.id,
                    'inicio': riego_activo.fecha_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                    'tiempo_transcurrido': int(tiempo_transcurrido),
                    'tiempo_restante': int(tiempo_restante),
                    'humedad_inicial': riego_activo.humedad_inicial,
                    'razon': riego_activo.razon
                }
            else:
                estado['riegos_activos'][tipo_planta] = None
        
        # Estadísticas del día POR PLANTA
        hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        estado['estadisticas_hoy'] = {}
        for tipo_planta in ['lechuga', 'fresa']:
            riegos_planta = IrrigationEvent.objects.filter(
                fecha_inicio__gte=hoy_inicio,
                tipo_planta=tipo_planta
            ).count()
            plant_config = self.get_plant_config(tipo_planta)
            
            estado['estadisticas_hoy'][tipo_planta] = {
                'riegos_realizados': riegos_planta,
                'max_riegos_dia': plant_config['max_riegos_dia'],
                'riegos_restantes': max(0, plant_config['max_riegos_dia'] - riegos_planta)
            }
        
        # Compatibilidad: agregar riego_activo general (para endpoints legacy)
        estado['riego_activo'] = any(estado['riegos_activos'].values())
        
        return estado
