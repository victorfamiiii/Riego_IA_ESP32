# pyright: reportMissingImports=false
"""
Vistas para nuevos endpoints: ESP32 multi-dispositivo y AEMET
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Max, Min, Sum, Q
from django.utils import timezone
from datetime import timedelta
import os
import json
import time
import ssl
import paho.mqtt.client as mqtt_paho
from .models import (
    ESP32Device,
    SoilMoisture,
    LuminosityData,
    WeatherData,
    IrrigationEvent,
    IrrigationConfig,
    IrrigationNotification,
    SensorCalibrationSettings,
)
from .serializers import (
    ESP32DeviceSerializer,
    SoilMoistureSerializer,
    SoilMoistureCreateSerializer,
    LuminosityDataSerializer,
    LuminosityDataCreateSerializer,
    WeatherDataSerializer,
    IrrigationEventSerializer,
    IrrigationConfigSerializer,
    IrrigationNotificationSerializer,
)
from .aemet_service import AEMETService
from .irrigation_control import IrrigationController
from .data_monitoring_service import monitoring_service
import logging

logger = logging.getLogger(__name__)

# Evita cerrar eventos justo después del ON manual/automático cuando la ESP32
# todavía no ha actualizado su estado de zona.
IRRIGATION_STARTUP_GRACE_SECONDS = 12


def _publish_mqtt_command(topic: str, payload: dict) -> bool:
    """Publica un comando MQTT puntual (arranque inmediato de relé)."""
    host = os.getenv('MQTT_HOST', 'mqtt')
    port = int(os.getenv('MQTT_PORT', '8883'))
    username = os.getenv('MQTT_USERNAME', '')
    password = os.getenv('MQTT_PASSWORD', '')
    ca_cert = os.getenv('MQTT_TLS_CA_CERT', '/app/certs/mqtt-ca.pem')

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
        return True
    except Exception as exc:
        logger.warning('MQTT direct publish failed: %s', exc)
        return False


def _normalize_plant_type(tipo_planta=None):
    raw = (tipo_planta or 'lechuga').strip().lower()
    if raw in ('fresa', 'fresas'):
        return 'fresa'
    if raw in ('lechuga', 'lechugas'):
        return 'lechuga'
    return 'lechuga'


def _resolve_soil_relay(tipo_planta=None):
    return 2 if _normalize_plant_type(tipo_planta) == 'fresa' else 1


def _get_or_create_irrigation_device(mac_address, esp32_ip=None):
    device = None
    if mac_address:
        device, _ = ESP32Device.objects.get_or_create(
            mac_address=mac_address,
            defaults={
                'name': f'ESP32-Riego-{mac_address[-5:]}',
                'device_type': 'soil',
            }
        )
        device.last_seen = timezone.now()
        if esp32_ip:
            device.esp32_ip = esp32_ip
        device.save(update_fields=['last_seen', 'esp32_ip'] if esp32_ip else ['last_seen'])
    return device


class ESP32DeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar dispositivos ESP32
    
    Endpoints:
    - GET    /api/devices/              Lista todos los dispositivos
    - POST   /api/devices/              Registrar nuevo dispositivo
    - GET    /api/devices/{id}/         Detalle de un dispositivo
    - PUT    /api/devices/{id}/         Actualizar dispositivo
    - DELETE /api/devices/{id}/         Eliminar dispositivo
    - GET    /api/devices/connected/    Dispositivos conectados
    """
    queryset = ESP32Device.objects.all()
    serializer_class = ESP32DeviceSerializer
    
    @action(detail=False, methods=['get'])
    def connected(self, request):
        """
        Listar solo dispositivos conectados (última conexión < 60s)
        GET /api/devices/connected/
        """
        devices = ESP32Device.objects.filter(active=True)
        connected = [d for d in devices if d.esta_conectado]
        serializer = self.get_serializer(connected, many=True)
        return Response(serializer.data)


class SoilMoistureViewSet(viewsets.ModelViewSet):
    """
    ViewSet para datos de humedad del suelo (ESP32 #1)
    
    Endpoints:
    - GET    /api/soil/                 Lista todas las mediciones
    - POST   /api/soil/                 Crear nueva medición (ESP32)
    - GET    /api/soil/{id}/            Detalle de una medición
    - GET    /api/soil/latest/          Última medición
    - GET    /api/soil/stats/           Estadísticas
    """
    queryset = SoilMoisture.objects.all()
    serializer_class = SoilMoistureSerializer
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SoilMoistureCreateSerializer
        return SoilMoistureSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Crear nueva medición de humedad de suelo
        POST /api/soil/
        
        Body:
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "tipo_planta": "lechuga",
            "relay": 1,
            "humedad_suelo": 45.5
        }

        humedad_suelo debe recibirse como valor crudo ADC.
        El backend lo guarda en crudo y lo calibra para mostrar/decidir riego.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # MONITOREO DE DATOS
        # Verificar nivel del tanque de agua
        try:
            monitoring_service.check_water_tank_level()
        except Exception as e:
            logger.warning(f"Water tank monitoring failed: {e}")
        
        # Retornar con serializador de lectura
        output_serializer = SoilMoistureSerializer(serializer.instance)
        
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """
        Obtener última medición de cada dispositivo
        GET /api/soil/latest/
        """
        devices = ESP32Device.objects.filter(device_type='soil', active=True)
        data = []
        
        for device in devices:
            latest = device.soil_readings.first()
            if latest:
                calibration = SensorCalibrationSettings.get_config()
                data.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'humedad_suelo': calibration.calibrate_soil_humidity(latest.humedad_suelo, relay=_resolve_soil_relay(latest.tipo_planta)),
                    'humedad_suelo_raw': latest.humedad_suelo,
                    'fecha': latest.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'conectado': device.esta_conectado
                })
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadísticas de humedad del suelo
        GET /api/soil/stats/?device_id=1&hours=24
        """
        device_id = request.query_params.get('device_id')
        hours = int(request.query_params.get('hours', 24))
        
        queryset = self.queryset
        if device_id:
            queryset = queryset.filter(device_id=device_id)
        
        # Filtrar por tiempo
        desde = timezone.now() - timedelta(hours=hours)
        queryset = queryset.filter(created_at__gte=desde)
        
        if not queryset.exists():
            return Response({'error': 'No hay datos'}, status=404)
        
        calibration = SensorCalibrationSettings.get_config()
        calibrated_values = [
            calibration.calibrate_soil_humidity(item.humedad_suelo, relay=_resolve_soil_relay(item.tipo_planta))
            for item in queryset
        ]
        raw_values = [item.humedad_suelo for item in queryset]
        
        return Response({
            'promedio': round(sum(calibrated_values) / len(calibrated_values), 2),
            'maximo': round(max(calibrated_values), 2),
            'minimo': round(min(calibrated_values), 2),
            'promedio_raw': round(sum(raw_values) / len(raw_values), 2),
            'maximo_raw': round(max(raw_values), 2),
            'minimo_raw': round(min(raw_values), 2),
            'total_mediciones': queryset.count(),
            'periodo_horas': hours
        })


class LuminosityDataViewSet(viewsets.ModelViewSet):
    """
    ViewSet para datos de luminosidad (ESP32 #2)
    
    Endpoints:
    - GET    /api/luminosity/        Lista todas las mediciones
    - POST   /api/luminosity/        Crear nueva medición (ESP32)
    - GET    /api/luminosity/{id}/   Detalle de una medición
    - GET    /api/luminosity/latest/ Última medición
    - GET    /api/luminosity/stats/  Estadísticas
    """
    queryset = LuminosityData.objects.all()
    serializer_class = LuminosityDataSerializer
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LuminosityDataCreateSerializer
        return LuminosityDataSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Crear nueva medición de luminosidad
        POST /api/luminosity/
        
        Body:
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "luminosidad": 45000
        }

        Compatibilidad: también acepta payload legacy con
        temperatura, humedad_ambiente y nivel_agua, pero no se guardan.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # MONITOREO DE DATOS
        # Verificar nivel del tanque de agua
        try:
            monitoring_service.check_water_tank_level()
        except Exception as e:
            logger.warning(f"Water tank monitoring failed: {e}")
        
        output_serializer = LuminosityDataSerializer(serializer.instance)
        
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """
        Obtener última medición de cada dispositivo
        GET /api/luminosity/latest/
        """
        devices = ESP32Device.objects.filter(device_type='environment', active=True)
        data = []
        
        for device in devices:
            latest = device.luminosity_readings.first()
            if latest:
                data.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'luminosidad': latest.luminosidad,
                    'fecha': latest.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'conectado': device.esta_conectado
                })
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadísticas de luminosidad
        GET /api/luminosity/stats/?device_id=1&hours=24
        """
        device_id = request.query_params.get('device_id')
        hours = int(request.query_params.get('hours', 24))
        
        queryset = self.queryset
        if device_id:
            queryset = queryset.filter(device_id=device_id)
        
        desde = timezone.now() - timedelta(hours=hours)
        queryset = queryset.filter(created_at__gte=desde)
        
        if not queryset.exists():
            return Response({'error': 'No hay datos'}, status=404)
        
        stats = queryset.aggregate(
            lux_promedio=Avg('luminosidad'),
            lux_max=Max('luminosidad'),
            lux_min=Min('luminosidad')
        )
        
        return Response({
            'luminosidad_promedio': round(stats['lux_promedio'], 2),
            'luminosidad_maxima': round(stats['lux_max'], 2),
            'luminosidad_minima': round(stats['lux_min'], 2),
            'total_mediciones': queryset.count(),
            'periodo_horas': hours
        })


class WeatherDataViewSet(viewsets.ModelViewSet):
    """
    ViewSet para datos meteorológicos de AEMET
    
    Endpoints:
    - GET    /api/weather/              Lista todos los datos
    - GET    /api/weather/latest/       Últimos datos AEMET
    - POST   /api/weather/sync/         Sincronizar datos desde AEMET
    - GET    /api/weather/stats/        Estadísticas meteorológicas
    """
    queryset = WeatherData.objects.all()
    serializer_class = WeatherDataSerializer
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """
        Obtener últimos datos meteorológicos
        GET /api/weather/latest/?estacion_id=3195
        """
        estacion_id = request.query_params.get('estacion_id', '3195')  # Madrid-Retiro por defecto
        
        latest = WeatherData.objects.filter(
            estacion_id=estacion_id
        ).order_by('-fecha_observacion').first()
        
        if not latest:
            return Response(
                {'error': f'No hay datos para estación {estacion_id}'},
                status=404
            )
        
        serializer = self.get_serializer(latest)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def sync(self, request):
        """
        Sincronizar datos desde AEMET
        POST /api/weather/sync/
        
        Body:
        {
            "estacion_id": "3195",
            "estacion_nombre": "Madrid-Retiro"  # opcional
        }
        """
        estacion_id = request.data.get('estacion_id', '3195')
        estacion_nombre = request.data.get('estacion_nombre')
        
        aemet = AEMETService()
        
        try:
            weather_data = aemet.guardar_datos_observacion(estacion_id, estacion_nombre)
            
            if weather_data:
                serializer = self.get_serializer(weather_data)
                return Response({
                    'status': 'success',
                    'message': 'Datos sincronizados correctamente',
                    'data': serializer.data
                })
            else:
                return Response(
                    {'error': 'No se pudieron obtener datos de AEMET'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Error sincronizando AEMET: {str(e)}")
            return Response(
                {'error': f'Error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadísticas meteorológicas
        GET /api/weather/stats/?estacion_id=3195&hours=24
        """
        estacion_id = request.query_params.get('estacion_id', '3195')
        hours = int(request.query_params.get('hours', 24))
        
        desde = timezone.now() - timedelta(hours=hours)
        queryset = WeatherData.objects.filter(
            estacion_id=estacion_id,
            fecha_observacion__gte=desde
        )
        
        if not queryset.exists():
            return Response({'error': 'No hay datos'}, status=404)
        
        stats = queryset.aggregate(
            temp_promedio=Avg('temperatura'),
            temp_max=Max('temperatura_maxima'),
            temp_min=Min('temperatura_minima'),
            hum_promedio=Avg('humedad'),
            precip_total=Sum('precipitacion'),
            viento_promedio=Avg('velocidad_viento')
        )
        
        # Obtener datos de AEMET service para precipitación 24h
        aemet = AEMETService()
        precipitacion_24h = aemet.obtener_precipitacion_24h(estacion_id)
        
        return Response({
            'estacion_id': estacion_id,
            'temperatura_promedio': round(stats['temp_promedio'] or 0, 2),
            'temperatura_maxima': round(stats['temp_max'] or 0, 2),
            'temperatura_minima': round(stats['temp_min'] or 0, 2),
            'humedad_promedio': round(stats['hum_promedio'] or 0, 2),
            'precipitacion_total': round(stats['precip_total'] or 0, 2),
            'precipitacion_24h': precipitacion_24h,
            'viento_promedio': round(stats['viento_promedio'] or 0, 2),
            'total_registros': queryset.count(),
            'periodo_horas': hours
        })
    
    @action(detail=False, methods=['get'])
    def forecast(self, request):
        """
        Obtener previsión meteorológica normalizada desde AEMET.

        GET /api/weather/forecast/?municipio_id=49275&municipio_nombre=Zamora
        """
        municipio_id = request.query_params.get('municipio_id', '49275')
        municipio_nombre = request.query_params.get('municipio_nombre', 'Zamora')
        dias = int(request.query_params.get('days', 5))

        aemet = AEMETService()
        try:
            forecast = aemet.obtener_prevision_normalizada(
                municipio_id=municipio_id,
                municipio_nombre=municipio_nombre,
                dias=dias,
            )

            if not forecast:
                return Response(
                    {'error': 'No se pudo obtener la previsión meteorológica'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response(forecast)

        except Exception as e:
            logger.error(f"Error obteniendo forecast AEMET: {str(e)}")
            return Response(
                {'error': f'Error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['get'])
    def estaciones(self, request):
        """
        Listar estaciones principales disponibles
        GET /api/weather/estaciones/
        """
        from .aemet_service import ESTACIONES_PRINCIPALES
        
        estaciones = [
            {'id': k, 'nombre': v}
            for k, v in ESTACIONES_PRINCIPALES.items()
        ]
        
        return Response(estaciones)


# ============================================================================
# VIEWSET PARA IRRIGATION EVENTS
# ============================================================================


class IrrigationEventViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar eventos de riego
    
    Endpoints:
    - GET    /api/irrigation/              Lista todos los eventos
    - POST   /api/irrigation/              Crear nuevo evento
    - GET    /api/irrigation/{id}/         Detalle de un evento
    - PUT    /api/irrigation/{id}/         Actualizar evento
    - DELETE /api/irrigation/{id}/         Eliminar evento
    - GET    /api/irrigation/stats/        Estadísticas de riego
    - GET    /api/irrigation/recent/       Últimos eventos
    """
    queryset = IrrigationEvent.objects.all().order_by('-fecha_inicio')
    serializer_class = IrrigationEventSerializer

    @action(detail=False, methods=['get'])
    def status(self, request):
        controller = IrrigationController()
        estado = controller.get_estado_actual()
        activo = IrrigationEvent.objects.filter(fecha_fin__isnull=True).order_by('-fecha_inicio').first()
        ultimo = IrrigationEvent.objects.order_by('-fecha_inicio').first()
        config = estado.get('configuracion', {})
        riegos_activos = estado.get('riegos_activos', {})

        plants_active = {}
        for plant in ['lechuga', 'fresa']:
            plant_state = riegos_activos.get(plant)
            plants_active[plant] = {
                'active': plant_state is not None,
                'event_id': plant_state.get('id') if plant_state else None,
                'time_remaining': plant_state.get('tiempo_restante') if plant_state else 0,
                'reason': plant_state.get('razon') if plant_state else 'Sin riego activo',
            }

        active_time_remaining = 0
        active_reason = 'Sin riego activo'
        if activo and activo.tipo_planta in plants_active:
            active_time_remaining = plants_active[activo.tipo_planta]['time_remaining']
            active_reason = plants_active[activo.tipo_planta]['reason']
        elif activo:
            active_reason = activo.razon

        return Response({
            'active': activo is not None,
            'event_id': activo.id if activo else None,
            'relay': activo.relay if activo else None,
            'plant_type': activo.tipo_planta if activo else None,
            'active_plant': activo.tipo_planta if activo else None,
            'time_remaining': active_time_remaining,
            'reason': active_reason,
            'automatic_enabled': config.get('automatico_activo', False),
            'plants_active': plants_active,
            'automatic_config': {
                'umbral_humedad': config.get('umbral_humedad'),
                'tiempo_riego': config.get('tiempo_riego'),
                'max_riegos_dia': config.get('max_riegos_dia'),
                'plants': estado.get('configuracion_por_planta', {}),
            },
            'total_activations': IrrigationEvent.objects.count(),
            'last_activation': ultimo.fecha_inicio.isoformat() if ultimo else None,
        })

    @action(detail=False, methods=['post'])
    def start(self, request):
        controller = IrrigationController()

        plant_type = _normalize_plant_type(request.data.get('plant_type'))
        relay = request.data.get('relay')
        duration = request.data.get('duration')
        liters = request.data.get('liters')

        # Regla de negocio obligatoria:
        # lechuga -> electroválvula 1, fresa/fresas -> electroválvula 2
        relay = _resolve_soil_relay(plant_type)

        if relay is None:
            return Response({'error': 'Se requiere relay o plant_type válido'}, status=status.HTTP_400_BAD_REQUEST)

        # Si se envían litros, el servidor calcula duración con la calibración EV (1s/5s/10s).
        liters_value = None
        if liters is not None and liters != '':
            try:
                liters_value = float(liters)
            except (TypeError, ValueError):
                return Response({'error': 'liters debe ser numérico'}, status=status.HTTP_400_BAD_REQUEST)

            if liters_value <= 0:
                return Response({'error': 'liters debe ser mayor que 0'}, status=status.HTTP_400_BAD_REQUEST)

            duration = controller.estimate_duration_seconds(
                relay=relay,
                litros=liters_value,
                tipo_planta=plant_type,
            )
        elif duration is not None and duration != '':
            try:
                duration = int(float(duration))
            except (TypeError, ValueError):
                return Response({'error': 'duration debe ser numérico'}, status=status.HTTP_400_BAD_REQUEST)

            if duration <= 0:
                return Response({'error': 'duration debe ser mayor que 0'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            duration = None

        # Asignar el dispositivo de suelo más reciente para que el evento manual
        # pueda ser recogido/finalizado correctamente por el flujo MQTT.
        device = ESP32Device.objects.filter(
            device_type='soil',
            active=True,
        ).order_by('-last_seen', '-created_at').first()

        activo = IrrigationEvent.objects.filter(fecha_fin__isnull=True, relay=relay).first()
        if activo:
            return Response({'error': 'Ya hay un riego en curso para ese relé'}, status=status.HTTP_400_BAD_REQUEST)

        evento = controller.iniciar_riego(
            razon='Riego manual desde dashboard',
            device=device,
            relay=relay,
            tipo_planta=plant_type,
            duracion_segundos=duration,
            automatico=False,
        )
        if liters_value is not None:
            evento.litros = liters_value
            evento.save(update_fields=['litros'])

        # Igual que la prueba de calibración: enviar ON inmediato al dispositivo
        # para no depender del siguiente poll.
        mqtt_sent = False
        if device and device.mac_address:
            topic = f"esp32/{device.mac_address}/commands/response"
            mqtt_payload = {
                'status': 'ok',
                'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'next_poll_ms': 5000,
                'active_poll_ms': 5000,
                'commands': [{
                    'relay': relay,
                    'plant_type': plant_type,
                    'command': 'ON',
                    'duration': evento.duracion_planificada_segundos,
                    'reason': 'Riego manual desde dashboard',
                    'event_id': evento.id,
                }],
            }
            mqtt_sent = _publish_mqtt_command(topic, mqtt_payload)

        return Response({
            'status': 'ok',
            'event_id': evento.id,
            'relay': relay,
            'device_id': device.id if device else None,
            'mqtt_sent': mqtt_sent,
            'duration': evento.duracion_planificada_segundos,
            'liters': evento.litros,
            'liters_requested': liters_value,
            'reason': evento.razon,
        })

    @action(detail=False, methods=['post'])
    def stop(self, request):
        controller = IrrigationController()
        relay = request.data.get('relay')

        queryset = IrrigationEvent.objects.filter(fecha_fin__isnull=True)
        if relay is not None:
            queryset = queryset.filter(relay=relay)
        activo = queryset.order_by('-fecha_inicio').first()

        if not activo:
            return Response({'error': 'No hay riego activo'}, status=status.HTTP_400_BAD_REQUEST)

        controller.solicitar_parada(activo.id)
        IrrigationNotification.objects.create(
            device=activo.device,
            event=activo,
            notification_type='manual-stop',
            relay=activo.relay,
            tipo_planta=activo.tipo_planta,
            reason='Parada solicitada desde dashboard',
            payload={'source': 'frontend'}
        )

        return Response({'status': 'ok', 'message': 'Parada solicitada', 'event_id': activo.id})

    @action(detail=False, methods=['post'])
    def device_command(self, request):
        try:
            controller = IrrigationController()
            mac_address = request.data.get('mac_address')
            esp32_ip = request.data.get('esp32_ip')
            zones = request.data.get('zones', [])

            if not mac_address:
                return Response({'error': 'Se requiere mac_address'}, status=status.HTTP_400_BAD_REQUEST)

            device = _get_or_create_irrigation_device(mac_address, esp32_ip=esp32_ip)
            commands = []

            for zone in zones:
                relay = zone.get('relay') if isinstance(zone, dict) else None
                plant_type = _normalize_plant_type(zone.get('plant_type')) if isinstance(zone, dict) else 'lechuga'
                zone_active = bool(zone.get('active')) if isinstance(zone, dict) else False
                zone_event_id = zone.get('event_id') if isinstance(zone, dict) else None

                try:
                    activo = IrrigationEvent.objects.filter(
                        Q(device=device) | Q(device__isnull=True),
                        relay=relay,
                        fecha_fin__isnull=True,
                    ).order_by('-fecha_inicio').first()

                    if activo and activo.device_id is None:
                        activo.device = device
                        activo.save(update_fields=['device'])

                    # Reconciliación: si servidor cree que hay riego activo pero la ESP32
                    # reporta la zona inactiva sin event_id, cerrar evento colgado.
                    within_startup_grace = (
                        activo
                        and activo.device_started_at is None
                        and (timezone.now() - activo.fecha_inicio).total_seconds() < IRRIGATION_STARTUP_GRACE_SECONDS
                    )
                    if (
                        activo
                        and not zone_active
                        and (zone_event_id in (None, 0, '0'))
                        and not within_startup_grace
                    ):
                        controller.finalizar_riego(activo.id)
                        commands.append({
                            'relay': relay,
                            'plant_type': activo.tipo_planta or plant_type,
                            'command': 'OFF',
                            'duration': 0,
                            'reason': 'Evento reconciliado: dispositivo inactivo',
                            'event_id': activo.id,
                        })
                        continue

                    if activo:
                        elapsed = (timezone.now() - activo.fecha_inicio).total_seconds()
                        time_remaining = max(0, int(activo.duracion_planificada_segundos - elapsed))

                        if activo.stop_requested or time_remaining <= 0:
                            if time_remaining <= 0:
                                controller.finalizar_riego(activo.id)
                            if not activo.stop_requested:
                                activo.stop_requested = True
                                activo.save(update_fields=['stop_requested'])
                            commands.append({
                                'relay': relay,
                                'plant_type': activo.tipo_planta or plant_type,
                                'command': 'OFF',
                                'duration': 0,
                                'reason': 'Parada solicitada' if activo.stop_requested else 'Duración completada',
                                'event_id': activo.id,
                            })
                        else:
                            commands.append({
                                'relay': relay,
                                'plant_type': activo.tipo_planta or plant_type,
                                'command': 'ON',
                                'duration': time_remaining,
                                'reason': activo.razon,
                                'event_id': activo.id,
                            })
                        continue

                    necesita, razon, medicion = controller.necesita_riego_por_planta(
                        tipo_planta=plant_type,
                        device=device,
                        relay=relay,
                    )
                    if necesita:
                        evento = controller.iniciar_riego(
                            razon=razon,
                            device=device,
                            relay=relay,
                            tipo_planta=plant_type,
                            automatico=True,
                        )
                        commands.append({
                            'relay': relay,
                            'plant_type': plant_type,
                            'command': 'ON',
                            'duration': evento.duracion_planificada_segundos,
                            'reason': razon,
                            'event_id': evento.id,
                        })
                    else:
                        commands.append({
                            'relay': relay,
                            'plant_type': plant_type,
                            'command': 'OFF',
                            'duration': 0,
                            'reason': razon,
                            'event_id': None,
                        })
                except Exception as zone_error:
                    logger.exception(
                        'Error generando comando de riego para relay=%s plant_type=%s mac=%s',
                        relay,
                        plant_type,
                        mac_address,
                    )
                    commands.append({
                        'relay': relay,
                        'plant_type': plant_type,
                        'command': 'OFF',
                        'duration': 0,
                        'reason': f'Error servidor: {zone_error}',
                        'event_id': None,
                    })

            return Response({
                'status': 'ok',
                'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'next_poll_ms': 300000,
                'active_poll_ms': 5000,
                'commands': commands,
            })
        except Exception as exc:
            logger.exception('Error general en device_command para mac=%s', request.data.get('mac_address'))
            return Response({
                'status': 'error',
                'error': str(exc),
                'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'next_poll_ms': 300000,
                'active_poll_ms': 5000,
                'commands': [],
            }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def device_notification(self, request):
        controller = IrrigationController()
        mac_address = request.data.get('mac_address')
        esp32_ip = request.data.get('esp32_ip')
        event_id = request.data.get('event_id')
        relay = request.data.get('relay')
        notification_type = request.data.get('notification_type')
        plant_type = _normalize_plant_type(request.data.get('plant_type'))
        reason = request.data.get('reason', '')
        humedad = request.data.get('humedad_suelo')
        temperatura = request.data.get('temperatura')
        payload = request.data.get('payload') or {}

        if not mac_address or not notification_type:
            return Response({'error': 'Se requieren mac_address y notification_type'}, status=status.HTTP_400_BAD_REQUEST)

        device = _get_or_create_irrigation_device(mac_address, esp32_ip=esp32_ip)
        event = None
        if event_id:
            event = IrrigationEvent.objects.filter(id=event_id).first()
        if not event and relay is not None:
            # Buscar evento activo por relay, filtrando también por planta si viene especificada
            query = IrrigationEvent.objects.filter(
                Q(device=device) | Q(device__isnull=True),
                relay=relay,
                fecha_fin__isnull=True,
            )
            if plant_type:
                query = query.filter(tipo_planta=plant_type)
            event = query.order_by('-fecha_inicio').first()

        if event and event.device_id is None:
            event.device = device
            event.save(update_fields=['device'])

        notification = IrrigationNotification.objects.create(
            device=device,
            event=event,
            notification_type=notification_type,
            relay=relay,
            tipo_planta=plant_type,
            reason=reason,
            payload=payload,
        )

        if event:
            if notification_type == 'start':
                controller.registrar_inicio_dispositivo(event.id)
            elif notification_type in ['stop', 'completed']:
                controller.finalizar_riego(event.id, humedad_final=humedad, temperatura_final=temperatura)

        return Response({'status': 'ok', 'notification_id': notification.id})
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadísticas de riego
        GET /api/irrigation/stats/
        """
        from django.db.models import Avg, Sum, Count
        
        # Eventos de las últimas 24 horas
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        eventos_24h = IrrigationEvent.objects.filter(fecha_inicio__gte=last_24h)
        eventos_7d = IrrigationEvent.objects.filter(fecha_inicio__gte=last_7d)
        
        return Response({
            'total_eventos': IrrigationEvent.objects.count(),
            'eventos_24h': eventos_24h.count(),
            'eventos_7d': eventos_7d.count(),
            'litros_24h': eventos_24h.aggregate(total=Sum('litros'))['total'] or 0,
            'litros_7d': eventos_7d.aggregate(total=Sum('litros'))['total'] or 0,
            'promedio_duracion': eventos_7d.aggregate(avg=Avg('duracion_real_segundos'))['avg'] or 0,
            'promedio_litros': eventos_7d.aggregate(avg=Avg('litros'))['avg'] or 0,
        })
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Últimos eventos de riego
        GET /api/irrigation/recent/?limit=10
        """
        limit = int(request.query_params.get('limit', 10))
        eventos = self.queryset[:limit]
        serializer = self.get_serializer(eventos, many=True)
        return Response(serializer.data)


class IrrigationConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar configuración de riego
    """
    queryset = IrrigationConfig.objects.all()
    serializer_class = IrrigationConfigSerializer
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Obtener configuración activa por tipo de planta
        GET /api/irrigation-config/active/ - retorna la primera activa
        GET /api/irrigation-config/active/?tipo_planta=lechuga - retorna la de lechuga
        """
        tipo_planta = request.query_params.get('tipo_planta', None)
        
        if tipo_planta:
            config = IrrigationConfig.get_config_by_plant(tipo_planta)
        else:
            config = IrrigationConfig.objects.filter(activo=True).first()
        if config:
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        return Response({'error': 'No hay configuración activa' + (f' para {tipo_planta}' if tipo_planta else '')}, status=404)
