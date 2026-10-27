# pyright: reportMissingImports=false
"""
Vistas de administración para CRUD de tablas
Solo accesibles para usuarios con rol admin (is_staff o is_superuser)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.apps import apps
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import time
import os
import json
import uuid
import ssl
from .models import (
    ESP32Device,
    SoilMoisture,
    LuminosityData,
    WeatherData,
    Measurement,
    IrrigationConfig,
    IrrigationEvent,
    IrrigationNotification,
    TrainingDataset,
    ModelVersion,
    WaterTankReading,
    SensorCalibrationSettings,
    FCMToken,
    NotificationHistory,
    GeminiAuditLog,
)
from .irrigation_control import IrrigationController
from .serializers import (
    ESP32DeviceSerializer,
    SoilMoistureSerializer,
    LuminosityDataSerializer,
    WeatherDataSerializer,
    MeasurementSerializer,
    IrrigationNotificationSerializer,
    GeminiAuditLogSerializer,
    FCMTokenSerializer,
)
from rest_framework import serializers
import logging
import paho.mqtt.client as mqtt_paho

logger = logging.getLogger(__name__)
SMOKE_TEST_MAC_PREFIX = "AA:BB:CC:DD:EE"


def _publish_mqtt_command(topic: str, payload: dict) -> bool:
    """Publica un mensaje MQTT puntual desde una vista Django."""
    host = os.getenv("MQTT_HOST", "mqtt")
    port = int(os.getenv("MQTT_PORT", "8883"))
    username = os.getenv("MQTT_USERNAME", "")
    password = os.getenv("MQTT_PASSWORD", "")
    ca_cert = os.getenv("MQTT_TLS_CA_CERT", "/app/certs/mqtt-ca.pem")

    client = mqtt_paho.Client(client_id=f"django-admin-{int(time.time())}")
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
        logger.warning("MQTT direct publish failed: %s", exc)
        return False


def _get_preferred_soil_device():
    """Selecciona ESP32 de suelo priorizando dispositivos reales sobre MACs de smoke test."""
    devices = ESP32Device.objects.filter(device_type='soil', active=True)
    preferred = devices.exclude(mac_address__istartswith=SMOKE_TEST_MAC_PREFIX).order_by('-last_seen').first()
    if preferred:
        return preferred
    return devices.order_by('-last_seen').first()


# Serializers adicionales para admin
class IrrigationConfigSerializer(serializers.ModelSerializer):
    def validate_configuracion_por_planta(self, value):
        if value in (None, ''):
            return {}

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError(
                    f'configuracion_por_planta debe ser JSON válido: {exc}'
                )

        if not isinstance(value, dict):
            raise serializers.ValidationError('configuracion_por_planta debe ser un objeto JSON.')

        return value

    class Meta:
        model = IrrigationConfig
        fields = '__all__'


class IrrigationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IrrigationEvent
        fields = '__all__'


class TrainingDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingDataset
        fields = '__all__'


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = '__all__'


class WaterTankReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterTankReading
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined', 'last_login']
        read_only_fields = ['date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'password']
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# Mapeo de modelos disponibles para administración
ADMIN_MODELS = {
    'devices': {
        'model': ESP32Device,
        'serializer': ESP32DeviceSerializer,
        'name': 'Dispositivos ESP32',
        'description': 'Gestión de dispositivos ESP32 conectados'
    },
    'soil_moisture': {
        'model': SoilMoisture,
        'serializer': SoilMoistureSerializer,
        'name': 'Datos de Humedad del Suelo',
        'description': 'Mediciones de humedad del suelo'
    },
    'environmental': {
        'model': LuminosityData,
        'serializer': LuminosityDataSerializer,
        'name': 'Datos de Luminosidad',
        'description': 'Mediciones del sensor de luz (lux)',
    },
    'weather': {
        'model': WeatherData,
        'serializer': WeatherDataSerializer,
        'name': 'Datos Meteorológicos',
        'description': 'Datos meteorológicos de AEMET'
    },
    'measurements': {
        'model': Measurement,
        'serializer': MeasurementSerializer,
        'name': 'Datos de Temperatura y Humedad',
        'description': 'Datos de temperatura y humedad'
    },
    'irrigation_config': {
        'model': IrrigationConfig,
        'serializer': IrrigationConfigSerializer,
        'name': 'Configuración de Riego',
        'description': 'Parámetros de configuración del riego automático'
    },
    'irrigation_events': {
        'model': IrrigationEvent,
        'serializer': IrrigationEventSerializer,
        'name': 'Eventos de Riego',
        'description': 'Historial de eventos de riego'
    },
    'irrigation_notifications': {
        'model': IrrigationNotification,
        'serializer': IrrigationNotificationSerializer,
        'name': 'Notificaciones de Riego',
        'description': 'Registro de consultas e inicios/paradas reportados por la ESP32'
    },
    'training_datasets': {
        'model': TrainingDataset,
        'serializer': TrainingDatasetSerializer,
        'name': 'Datasets de Entrenamiento',
        'description': 'Datos para entrenamiento de modelos IA'
    },
    'model_versions': {
        'model': ModelVersion,
        'serializer': ModelVersionSerializer,
        'name': 'Versiones de Modelos',
        'description': 'Control de versiones de modelos IA'
    },
    'water_tank_readings': {
        'model': WaterTankReading,
        'serializer': WaterTankReadingSerializer,
        'name': 'Datos del Tanque',
        'description': 'Histórico de lecturas del nivel de agua del tanque'
    },
    'users': {
        'model': User,
        'serializer': UserSerializer,
        'create_serializer': UserCreateSerializer,
        'name': 'Usuarios',
        'description': 'Gestión de usuarios del sistema'
    },
    'fcm_tokens': {
        'model': FCMToken,
        'serializer': FCMTokenSerializer,
        'name': 'Tokens Firebase FCM',
        'description': 'Tokens de dispositivos para notificaciones push'
    },
    'gemini_audit_logs': {
        'model': GeminiAuditLog,
        'serializer': GeminiAuditLogSerializer,
        'name': 'Logs de Auditoría Gemini',
        'description': 'Historial de comunicaciones con Google Gemini AI'
    },
}


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_tables(request):
    """
    Listar todas las tablas disponibles para administración
    GET /api/admin/tables/
    """
    tables = []
    for key, config in ADMIN_MODELS.items():
        model = config['model']
        tables.append({
            'key': key,
            'name': config['name'],
            'description': config['description'],
            'count': model.objects.count(),
        })
    
    return Response({
        'success': True,
        'tables': tables
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_table_schema(request, table_name):
    """
    Obtener el esquema de una tabla (campos disponibles)
    GET /api/admin/tables/{table_name}/schema/
    """
    if table_name not in ADMIN_MODELS:
        return Response({
            'error': f'Tabla "{table_name}" no encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    
    config = ADMIN_MODELS[table_name]
    model = config['model']
    exclude_fields = config.get('exclude_fields', [])
    
    fields = []
    for field in model._meta.get_fields():
        if hasattr(field, 'name') and field.name not in exclude_fields:
            field_info = {
                'name': field.name,
                'type': field.__class__.__name__,
                'verbose_name': getattr(field, 'verbose_name', field.name),
                'null': getattr(field, 'null', False),
                'blank': getattr(field, 'blank', False),
                'editable': getattr(field, 'editable', True),
                'help_text': str(getattr(field, 'help_text', '')),
            }
            
            # Para campos con choices
            if hasattr(field, 'choices') and field.choices:
                field_info['choices'] = list(field.choices)
            
            # Para campos ForeignKey
            if field.__class__.__name__ == 'ForeignKey':
                field_info['related_model'] = field.related_model.__name__
            
            fields.append(field_info)
    
    return Response({
        'success': True,
        'table': table_name,
        'name': config['name'],
        'description': config['description'],
        'fields': fields
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def table_list_create(request, table_name):
    """
    Listar registros o crear nuevo registro
    GET  /api/admin/tables/{table_name}/
    POST /api/admin/tables/{table_name}/
    """
    if table_name not in ADMIN_MODELS:
        return Response({
            'error': f'Tabla "{table_name}" no encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    
    config = ADMIN_MODELS[table_name]
    model = config['model']
    serializer_class = config['serializer']
    
    if request.method == 'GET':
        # Listar registros con paginación
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 25))
        
        offset = (page - 1) * page_size
        total = model.objects.count()
        
        queryset = model.objects.all()[offset:offset + page_size]
        serializer = serializer_class(queryset, many=True)
        
        return Response({
            'success': True,
            'table': table_name,
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size,
            'data': serializer.data
        })
    
    elif request.method == 'POST':
        # Crear nuevo registro
        create_serializer = config.get('create_serializer', serializer_class)
        serializer = create_serializer(data=request.data)
        
        if serializer.is_valid():
            instance = serializer.save()
            output_serializer = serializer_class(instance)
            return Response({
                'success': True,
                'message': 'Registro creado exitosamente',
                'data': output_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'error': 'Datos inválidos',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def table_detail(request, table_name, pk):
    """
    Obtener, actualizar o eliminar un registro específico
    GET    /api/admin/tables/{table_name}/{pk}/
    PUT    /api/admin/tables/{table_name}/{pk}/
    DELETE /api/admin/tables/{table_name}/{pk}/
    """
    if table_name not in ADMIN_MODELS:
        return Response({
            'error': f'Tabla "{table_name}" no encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    
    config = ADMIN_MODELS[table_name]
    model = config['model']
    serializer_class = config['serializer']
    
    try:
        instance = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return Response({
            'error': f'Registro con ID {pk} no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = serializer_class(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        serializer = serializer_class(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Registro actualizado exitosamente',
                'data': serializer.data
            })
        return Response({
            'error': 'Datos inválidos',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        instance.delete()
        return Response({
            'success': True,
            'message': 'Registro eliminado exitosamente'
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_delete(request, table_name):
    """
    Eliminar múltiples registros
    POST /api/admin/tables/{table_name}/bulk-delete/
    Body: { "ids": [1, 2, 3] }
    """
    if table_name not in ADMIN_MODELS:
        return Response({
            'error': f'Tabla "{table_name}" no encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    
    config = ADMIN_MODELS[table_name]
    model = config['model']
    
    ids = request.data.get('ids', [])
    if not ids:
        return Response({
            'error': 'Se requiere lista de IDs'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    deleted_count, _ = model.objects.filter(pk__in=ids).delete()
    
    return Response({
        'success': True,
        'message': f'{deleted_count} registros eliminados',
        'deleted_count': deleted_count
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def sensor_calibration(request):
    """
    Obtener o actualizar la calibración de sensores.
    GET  /api/admin/sensor-calibration
    POST /api/admin/sensor-calibration
    """
    config = SensorCalibrationSettings.get_config()

    if request.method == 'GET':
        return Response({
            'success': True,
            'data': {
                'distancia_minima_tanque': config.distancia_minima_tanque,
                'distancia_maxima_tanque': config.distancia_maxima_tanque,
                'capacidad_litros_tanque': config.capacidad_litros_tanque,
                'ev1_litros_1s': config.ev1_litros_1s,
                'ev1_litros_5s': config.ev1_litros_5s,
                'ev1_litros_10s': config.ev1_litros_10s,
                'ev2_litros_1s': config.ev2_litros_1s,
                'ev2_litros_5s': config.ev2_litros_5s,
                'ev2_litros_10s': config.ev2_litros_10s,
                'suelo1_valor_seco': config.suelo1_valor_seco,
                'suelo1_valor_mojado': config.suelo1_valor_mojado,
                'suelo2_valor_seco': config.suelo2_valor_seco,
                'suelo2_valor_mojado': config.suelo2_valor_mojado,
                'updated_at': config.updated_at.isoformat() if config.updated_at else None,
            }
        })

    updatable_fields = [
        'distancia_minima_tanque', 'distancia_maxima_tanque', 'capacidad_litros_tanque',
        'ev1_litros_1s', 'ev1_litros_5s', 'ev1_litros_10s',
        'ev2_litros_1s', 'ev2_litros_5s', 'ev2_litros_10s',
        'suelo1_valor_seco', 'suelo1_valor_mojado',
        'suelo2_valor_seco', 'suelo2_valor_mojado',
    ]

    changed_fields = []
    for field_name in updatable_fields:
        if field_name in request.data:
            try:
                value = float(request.data[field_name])
            except (TypeError, ValueError):
                return Response({
                    'error': f'El campo {field_name} debe ser numérico'
                }, status=status.HTTP_400_BAD_REQUEST)

            setattr(config, field_name, value)
            changed_fields.append(field_name)

    if config.distancia_maxima_tanque <= config.distancia_minima_tanque:
        return Response({
            'error': 'La distancia máxima del tanque debe ser mayor que la mínima'
        }, status=status.HTTP_400_BAD_REQUEST)

    if config.suelo1_valor_seco == config.suelo1_valor_mojado:
        return Response({
            'error': 'Sensor 1: seco y mojado no pueden ser iguales'
        }, status=status.HTTP_400_BAD_REQUEST)

    if config.suelo2_valor_seco == config.suelo2_valor_mojado:
        return Response({
            'error': 'Sensor 2: seco y mojado no pueden ser iguales'
        }, status=status.HTTP_400_BAD_REQUEST)

    if changed_fields:
        config.save(update_fields=changed_fields)

    return Response({
        'success': True,
        'message': 'Calibración guardada correctamente',
        'data': {
            'distancia_minima_tanque': config.distancia_minima_tanque,
            'distancia_maxima_tanque': config.distancia_maxima_tanque,
            'capacidad_litros_tanque': config.capacidad_litros_tanque,
            'ev1_litros_1s': config.ev1_litros_1s,
            'ev1_litros_5s': config.ev1_litros_5s,
            'ev1_litros_10s': config.ev1_litros_10s,
            'ev2_litros_1s': config.ev2_litros_1s,
            'ev2_litros_5s': config.ev2_litros_5s,
            'ev2_litros_10s': config.ev2_litros_10s,
            'suelo1_valor_seco': config.suelo1_valor_seco,
            'suelo1_valor_mojado': config.suelo1_valor_mojado,
            'suelo2_valor_seco': config.suelo2_valor_seco,
            'suelo2_valor_mojado': config.suelo2_valor_mojado,
            'updated_at': config.updated_at.isoformat() if config.updated_at else None,
        }
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sensor_calibration_valve_test(request):
    """
    Lanza una prueba rápida de electroválvula para calibración.
    POST /api/admin/sensor-calibration/valve-test
    Body: { "relay": 1|2, "duration_seconds": 1|5|10 }
    """
    relay = request.data.get('relay')
    duration_seconds = request.data.get('duration_seconds')

    try:
        relay = int(relay)
        duration_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        return Response({'error': 'relay y duration_seconds deben ser enteros'}, status=status.HTTP_400_BAD_REQUEST)

    if relay not in [1, 2]:
        return Response({'error': 'relay debe ser 1 o 2'}, status=status.HTTP_400_BAD_REQUEST)

    if duration_seconds <= 0:
        return Response({'error': 'duration_seconds debe ser mayor que 0'}, status=status.HTTP_400_BAD_REQUEST)

    plant_type = 'lechuga' if relay == 1 else 'fresa'
    device = _get_preferred_soil_device()

    try:
        controller = IrrigationController()
        event = controller.iniciar_riego(
            razon=f'Prueba de calibración EV{relay} ({duration_seconds}s)',
            device=device,
            relay=relay,
            tipo_planta=plant_type,
            duracion_segundos=duration_seconds,
            automatico=False,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)

    # Publicar comando MQTT inmediatamente para no esperar el poll de 5 min.
    mqtt_sent = False
    if device and device.mac_address:
        topic = f"esp32/{device.mac_address}/commands/response"
        mqtt_payload = {
            "status": "ok",
            "server_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "next_poll_ms": 5000,
            "active_poll_ms": 5000,
            "commands": [{
                "relay": relay,
                "plant_type": plant_type,
                "command": "ON",
                "duration": duration_seconds,
                "reason": f"Prueba calibración EV{relay}",
                "event_id": event.id,
            }],
        }
        mqtt_sent = _publish_mqtt_command(topic, mqtt_payload)

    return Response({
        'success': True,
        'message': 'Comando enviado a la ESP32.' if mqtt_sent else 'Evento creado; la ESP32 lo ejecutará en su próximo poll.',
        'mqtt_sent': mqtt_sent,
        'data': {
            'event_id': event.id,
            'relay': relay,
            'duration_seconds': event.duracion_planificada_segundos,
            'estimated_liters': event.litros,
            'device_name': device.name if device else None,
            'created_at': event.fecha_inicio.isoformat(),
        }
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sensor_calibration_soil_sample(request):
    """
    Devuelve las 5 últimas lecturas disponibles del sensor de humedad para calibración.
    POST /api/admin/sensor-calibration/soil-sample
    Body: { "relay": 1|2 }
    """
    relay = request.data.get('relay', 1)

    try:
        relay = int(relay)
    except (TypeError, ValueError):
        return Response({'error': 'relay debe ser un entero'}, status=status.HTTP_400_BAD_REQUEST)

    if relay not in [1, 2]:
        return Response({'error': 'relay debe ser 1 o 2'}, status=status.HTTP_400_BAD_REQUEST)

    plant_type = 'lechuga' if relay == 1 else 'fresa'
    calibration = SensorCalibrationSettings.get_config()

    latest_readings = list(SoilMoisture.objects.filter(tipo_planta=plant_type).order_by('-created_at')[:5])

    readings = []
    calibrated_values = []
    raw_values = []

    for index, reading_obj in enumerate(latest_readings, start=1):
        raw_value = float(reading_obj.humedad_suelo)
        calibrated = calibration.calibrate_soil_humidity(raw_value, relay=relay)
        ts = reading_obj.created_at.isoformat()

        raw_values.append(raw_value)
        if calibrated is not None:
            calibrated_values.append(calibrated)

        readings.append({
            'second': index,
            'value': calibrated,
            'value_raw': raw_value,
            'timestamp': ts,
        })

    captured = len(raw_values)
    average = round(sum(calibrated_values) / len(calibrated_values), 2) if calibrated_values else None
    average_raw = round(sum(raw_values) / len(raw_values), 0) if raw_values else None

    return Response({
        'success': True,
        'data': {
            'relay': relay,
            'plant_type': plant_type,
            'seconds': captured,
            'readings': readings,
            'average': average,
            'average_raw': average_raw,
            'captured': captured,
            'sampled_at': timezone.now().isoformat(),
        }
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sensor_calibration_soil_live_read(request):
    """
    Solicita una lectura en vivo de humedad al ESP32 vía MQTT y espera respuesta breve.
    POST /api/admin/sensor-calibration/soil-live-read
    Body: { "relay": 1|2 }
    """
    relay = request.data.get('relay', 1)

    try:
        relay = int(relay)
    except (TypeError, ValueError):
        return Response({'error': 'relay debe ser un entero'}, status=status.HTTP_400_BAD_REQUEST)

    if relay not in [1, 2]:
        return Response({'error': 'relay debe ser 1 o 2'}, status=status.HTTP_400_BAD_REQUEST)

    plant_type = 'lechuga' if relay == 1 else 'fresa'
    device = _get_preferred_soil_device()

    if not device or not device.mac_address:
        return Response({'error': 'No hay dispositivo ESP32 de suelo disponible'}, status=status.HTTP_409_CONFLICT)

    request_id = str(uuid.uuid4())
    topic = f"esp32/{device.mac_address}/commands/response"
    mqtt_payload = {
        'status': 'ok',
        'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'next_poll_ms': 5000,
        'active_poll_ms': 5000,
        'commands': [{
            'relay': relay,
            'plant_type': plant_type,
            'command': 'READ_SOIL',
            'duration': 0,
            'reason': 'Lectura solicitada desde calibracion',
            'request_id': request_id,
            'event_id': None,
        }],
    }

    mqtt_sent = _publish_mqtt_command(topic, mqtt_payload)
    if not mqtt_sent:
        return Response({'error': 'No se pudo enviar comando MQTT a la ESP32'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    deadline = time.time() + 12.0
    calibration = SensorCalibrationSettings.get_config()
    latest_known = SoilMoisture.objects.filter(tipo_planta=plant_type).order_by('-created_at').first()

    while time.time() < deadline:
        notification = IrrigationNotification.objects.filter(
            device=device,
            relay=relay,
            notification_type='poll',
            payload__kind='sensor_read',
            payload__request_id=request_id,
        ).order_by('-created_at').first()

        if notification:
            raw_value = notification.payload.get('value_raw') if isinstance(notification.payload, dict) else None
            if raw_value is None:
                raw_value = notification.payload.get('humedad_suelo') if isinstance(notification.payload, dict) else None

            if raw_value is None:
                return Response({'error': 'La ESP32 respondió sin valor de humedad'}, status=status.HTTP_502_BAD_GATEWAY)

            raw_value = float(raw_value)
            calibrated = calibration.calibrate_soil_humidity(raw_value, relay=relay)

            return Response({
                'success': True,
                'data': {
                    'relay': relay,
                    'plant_type': plant_type,
                    'request_id': request_id,
                    'value_raw': round(raw_value, 0),
                    'value': calibrated,
                    'timestamp': notification.created_at.isoformat(),
                    'device_name': device.name,
                }
            })

        time.sleep(0.4)

    if latest_known:
        raw_value = float(latest_known.humedad_suelo)
        calibrated = calibration.calibrate_soil_humidity(raw_value, relay=relay)

        return Response({
            'success': True,
            'pending': True,
            'warning': 'La ESP32 no respondió a tiempo; se muestra la última lectura disponible',
            'data': {
                'relay': relay,
                'plant_type': plant_type,
                'request_id': request_id,
                'value_raw': round(raw_value, 0),
                'value': calibrated,
                'timestamp': latest_known.created_at.isoformat(),
                'device_name': device.name,
                'source': 'cached',
            }
        })

    return Response({
        'error': 'La ESP32 no respondió a tiempo (timeout lectura en vivo)'
    }, status=status.HTTP_504_GATEWAY_TIMEOUT)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sensor_calibration_tank_sample(request):
    """
    Devuelve las 5 últimas lecturas disponibles del sensor de distancia del tanque.
    POST /api/admin/sensor-calibration/tank-sample
    Body: {}
    """
    latest_readings = list(WaterTankReading.objects.order_by('-created_at')[:5])

    readings = []
    raw_values = []
    percentages = []
    liters_values = []

    for index, reading_obj in enumerate(latest_readings, start=1):
        value_raw = float(reading_obj.distancia)
        percentage = float(reading_obj.porcentaje)
        liters = float(reading_obj.litros)

        raw_values.append(value_raw)
        percentages.append(percentage)
        liters_values.append(liters)

        readings.append({
            'second': index,
            'value_raw': value_raw,
            'percentage': percentage,
            'liters': liters,
            'timestamp': reading_obj.created_at.isoformat(),
        })

    captured = len(raw_values)
    average_raw = round(sum(raw_values) / len(raw_values), 2) if raw_values else None
    average_percentage = round(sum(percentages) / len(percentages), 2) if percentages else None
    average_liters = round(sum(liters_values) / len(liters_values), 2) if liters_values else None

    return Response({
        'success': True,
        'data': {
            'seconds': captured,
            'readings': readings,
            'average_raw': average_raw,
            'average_percentage': average_percentage,
            'average_liters': average_liters,
            'captured': captured,
            'sampled_at': timezone.now().isoformat(),
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_stats(request):
    """
    Obtener estadísticas generales del sistema
    GET /api/admin/stats/
    """
    stats = {}
    
    for key, config in ADMIN_MODELS.items():
        model = config['model']
        stats[key] = {
            'name': config['name'],
            'count': model.objects.count()
        }
    
    return Response({
        'success': True,
        'stats': stats
    })


# ============================================================================
# ENDPOINTS DE FIREBASE CLOUD MESSAGING (FCM)
# ============================================================================

from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny


@api_view(['POST'])
@authentication_classes([SessionAuthentication])   # ← esto elimina SessionAuthentication → sin CSRF
@permission_classes([AllowAny])
def register_fcm_token(request):
    """
    Registrar token FCM de un dispositivo/navegador.
    Cada vez que el cliente obtiene un nuevo token, lo envía aquí.
    NO requiere autenticación - si el usuario está autenticado, guarda su ID.
    
    POST /api/fcm/register/
    
    Body:
    {
        "token": "string (token FCM)",
        "device_name": "string (iPhone 12, Chrome, Firefox, etc.)",
        "user_agent": "string (User-Agent opcional)"
    }
    """
    from .models import FCMToken
    
    try:
        token = request.data.get('token', '').strip()
        device_name = request.data.get('device_name', '').strip()
        user_agent = request.data.get('user_agent', '').strip()
        
        if not token:
            return Response(
                {'error': 'Token FCM requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Registrar o actualizar token
        # Si el usuario está autenticado, guardar su ID; si no, dejar NULL
        user = request.user if request.user.is_authenticated else None

        # Fallback: leer sesión Django manualmente (DRF no autentica sin X-CSRFToken)
        if user is None:
            session_key = request.COOKIES.get('sessionid')
            if session_key:
                try:
                    from django.contrib.sessions.backends.db import SessionStore
                    _session = SessionStore(session_key)
                    _user_id = _session.get('_auth_user_id')
                    if _user_id:
                        user = User.objects.filter(pk=_user_id).first()
                except Exception:
                    pass

        existing = FCMToken.objects.filter(token=token).first()

        # Solo actualizar user si tenemos uno real, o si no había ninguno
        update_user = user if user is not None else (existing.user if existing else None)

        fcm_token, created = FCMToken.objects.update_or_create(
            token=token,
            defaults={
                'user': update_user,
                'device_name': device_name,
                'user_agent': user_agent,
                'is_active': True,
            }
        )
        
        user_info = request.user.username if request.user.is_authenticated else "anonymous"
        logger.info(f"FCM token {'registered' if created else 'updated'} for user {user_info}")
        
        return Response({
            'success': True,
            'message': f'Token {"registrado" if created else "actualizado"} correctamente',
            'token_id': fcm_token.id,
        })
    
    except Exception as e:
        logger.error(f"Error registering FCM token: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_fcm_notification(request):
    """
    Enviar notificación FCM a un usuario o a todos.
    Solo disponible para administradores.
    
    POST /api/fcm/send/
    
    Body:
    {
        "user_id": int (opcional, si no se especifica va a TODOS),
        "title": "string (título)",
        "body": "string (cuerpo)",
        "data": {"key": "value"} (opcional),
        "icon": "string (URL icono, opcional)"
    }
    """
    from .firebase_service import firebase_service
    
    try:
        title = request.data.get('title', '').strip()
        body = request.data.get('body', '').strip()
        user_id = request.data.get('user_id')
        data = request.data.get('data', {})
        icon = request.data.get('icon')
        
        if not title or not body:
            return Response(
                {'error': 'Título y cuerpo son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Enviar
        if user_id:
            # A usuario específico
            result = firebase_service.send_to_user(
                user_id,
                title=title,
                body=body,
                data=data,
                icon=icon
            )
            message = f"Notificación enviada a usuario {user_id}"
        else:
            # A TODOS
            result = firebase_service.send_to_all_users(
                title=title,
                body=body,
                data=data,
                icon=icon
            )
            message = f"Notificación broadcast enviada a {result.get('users_targeted', 0)} usuarios"
        
        logger.info(f"FCM notification sent: {message}")
        
        return Response({
            'success': result.get('success', False),
            'message': message,
            'result': result
        })
    
    except Exception as e:
        logger.error(f"Error sending FCM notification: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_fcm_tokens(request):
    """
    Obtener mis tokens FCM registrados.
    GET /api/fcm/my-tokens/
    """
    from .models import FCMToken
    
    try:
        tokens = FCMToken.objects.filter(user=request.user).values(
            'id', 'token', 'device_name', 'created_at', 'is_active'
        )
        
        return Response({
            'success': True,
            'tokens': list(tokens),
            'count': len(tokens)
        })
    
    except Exception as e:
        logger.error(f"Error fetching FCM tokens: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_fcm_token(request, token_id):
    """
    Eliminar un token FCM específico.
    DELETE /api/fcm/tokens/{token_id}/
    """
    from .models import FCMToken
    
    try:
        token = FCMToken.objects.get(id=token_id, user=request.user)
        token.delete()
        
        logger.info(f"FCM token {token_id} deleted for user {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Token eliminado correctamente'
        })
    
    except FCMToken.DoesNotExist:
        return Response(
            {'error': 'Token no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting FCM token: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_notification_history(request):
    """
    Obtener historial de notificaciones enviadas (paginado).
    Solo administradores.
    
    GET /api/notifications/history/?page=1&page_size=20&user_id=1&status=sent
    """
    try:
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        user_id = request.query_params.get('user_id')
        status_filter = request.query_params.get('status')
        
        # Validar paginación
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        
        # Query base
        queryset = NotificationHistory.objects.all().order_by('-created_at')
        
        # Filtros
        if user_id:
            try:
                queryset = queryset.filter(user_id=int(user_id))
            except ValueError:
                pass
        
        if status_filter:
            valid_statuses = ['pending', 'sent', 'failed', 'read']
            if status_filter in valid_statuses:
                queryset = queryset.filter(status=status_filter)
        
        # Contar total
        total = queryset.count()
        total_pages = (total + page_size - 1) // page_size
        
        # Paginar
        start = (page - 1) * page_size
        end = start + page_size
        notifications = queryset[start:end]
        
        # Serializar
        data = []
        for notif in notifications:
            data.append({
                'id': notif.id,
                'user': {
                    'id': notif.user.id,
                    'username': notif.user.username,
                    'email': notif.user.email,
                },
                'title': notif.title,
                'body': notif.body,
                'status': notif.status,
                'created_at': notif.created_at.isoformat(),
                'sent_at': notif.sent_at.isoformat() if notif.sent_at else None,
                'num_tokens_sent': notif.num_tokens_sent,
                'num_tokens_failed': notif.num_tokens_failed,
                'sent_by': notif.sent_by.username if notif.sent_by else 'Sistema',
                'error_message': notif.error_message,
            })
        
        return Response({
            'success': True,
            'data': data,
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
        })
    
    except Exception as e:
        logger.error(f"Error fetching notification history: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_notification_to_user(request):
    """
    Enviar notificación a un usuario específico.
    Solo administradores.
    
    POST /api/notifications/send/
    
    Body:
    {
        "user_id": int (requerido),
        "title": "string (título)",
        "body": "string (cuerpo)",
        "data": {"key": "value"} (opcional),
        "icon": "string (URL icono, opcional)"
    }
    """
    from .firebase_service import firebase_service
    
    try:
        user_id = request.data.get('user_id')
        title = request.data.get('title', '').strip()
        body = request.data.get('body', '').strip()
        data = request.data.get('data', {})
        icon = request.data.get('icon')
        
        # Validar
        if not user_id:
            return Response(
                {'error': 'user_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not title or not body:
            return Response(
                {'error': 'Título y cuerpo son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario existe
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Enviar
        result = firebase_service.send_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
            icon=icon,
            sent_by_user_id=request.user.id
        )
        
        logger.info(f"Notification sent by {request.user.username} to {target_user.username}: {result}")
        
        return Response({
            'success': result.get('success', False),
            'message': f"Notificación enviada a {target_user.username}",
            'notification_id': result.get('notification_id'),
            'sent': result.get('sent', 0),
            'failed': result.get('failed', 0),
        })
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_notification_broadcast(request):
    """
    Enviar notificación a TODOS los usuarios.
    Solo administradores.
    
    POST /api/notifications/broadcast/
    
    Body:
    {
        "title": "string (título)",
        "body": "string (cuerpo)",
        "data": {"key": "value"} (opcional),
        "icon": "string (URL icono, opcional)"
    }
    """
    from .firebase_service import firebase_service
    
    try:
        title = request.data.get('title', '').strip()
        body = request.data.get('body', '').strip()
        data = request.data.get('data', {})
        icon = request.data.get('icon')
        
        if not title or not body:
            return Response(
                {'error': 'Título y cuerpo son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Enviar a todos
        result = firebase_service.send_to_all_users(
            title=title,
            body=body,
            data=data,
            icon=icon
        )
        
        logger.info(f"Broadcast notification sent by {request.user.username}: {result}")
        
        return Response({
            'success': result.get('success', False),
            'message': f"Notificación broadcast enviada a {result.get('total_sent', 0)} dispositivos",
            'users_targeted': result.get('users_targeted', 0),
            'total_sent': result.get('total_sent', 0),
            'total_failed': result.get('total_failed', 0),
        })
    
    except Exception as e:
        logger.error(f"Error sending broadcast notification: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# ENDPOINT MODO DE RIEGO
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def irrigation_mode(request, tipo_planta):
    """
    Consultar o cambiar el modo de riego de una planta.
    GET  /api/admin/irrigation-mode/<tipo_planta>/
    POST /api/admin/irrigation-mode/<tipo_planta>/
    Body POST: { "modo": "umbral" | "ia" | "manual" }
    """
    PLANTAS_VALIDAS = ('lechuga', 'fresa', 'general')
    MODOS_VALIDOS   = ('umbral', 'ia', 'manual')

    if tipo_planta not in PLANTAS_VALIDAS:
        return Response(
            {'error': f'Planta inválida. Usa: {", ".join(PLANTAS_VALIDAS)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    config = IrrigationConfig.get_config_by_plant(tipo_planta)
    if not config:
        return Response(
            {'error': f'No hay configuración activa para "{tipo_planta}"'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        return Response({
            'success': True,
            'planta': tipo_planta,
            'modo_riego': config.modo_riego,
            'riego_automatico_activo': config.riego_automatico_activo,
        })

    modo = request.data.get('modo', '').strip()
    if modo not in MODOS_VALIDOS:
        return Response(
            {'error': f'Modo inválido. Usa: {", ".join(MODOS_VALIDOS)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    config.modo_riego = modo
    config.save(update_fields=['modo_riego'])
    logger.info(f"Modo de riego '{tipo_planta}' cambiado a '{modo}' por {request.user.username}")

    return Response({
        'success': True,
        'planta':  tipo_planta,
        'modo_riego': config.modo_riego,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def gemini_audit_logs(request):
    """
    Obtener el historial de comunicaciones con Gemini AI
    GET /api/admin/gemini-logs/?tipo_planta=lechuga&limit=50
    
    Parámetros query:
    - tipo_planta: lechuga, fresa o general (opcional)
    - limit: máximo número de registros (default: 50, max: 200)
    - offset: para paginación (default: 0)
    """
    tipo_planta = request.query_params.get('tipo_planta', None)
    limit = min(int(request.query_params.get('limit', 50)), 200)
    offset = int(request.query_params.get('offset', 0))
    
    queryset = GeminiAuditLog.objects.all().order_by('-created_at')
    
    if tipo_planta and tipo_planta in ('lechuga', 'fresa'):
        queryset = queryset.filter(tipo_planta=tipo_planta)
    
    total = queryset.count()
    logs = queryset[offset:offset + limit]
    
    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'tipo': log.tipo,
            'tipo_planta': log.tipo_planta,
            'prompt': log.prompt[:200] + '...' if len(log.prompt) > 200 else log.prompt,  # Resumen
            'prompt_completo': log.prompt,
            'modelo': log.modelo,
            'respuesta_raw': log.respuesta_raw[:200] + '...' if log.respuesta_raw and len(log.respuesta_raw) > 200 else log.respuesta_raw,
            'respuesta_completa': log.respuesta_raw,
            'respuesta_json': log.respuesta_json,
            'decision_regar': log.decision_regar,
            'decision_duracion_s': log.decision_duracion_s,
            'decision_razon': log.decision_razon,
            'tokens_entrada': log.tokens_entrada,
            'tokens_salida': log.tokens_salida,
            'latencia_ms': log.latencia_ms,
            'exito': log.exito,
            'error_mensaje': log.error_mensaje,
            'created_at': log.created_at.isoformat(),
        })
    
    return Response({
        'success': True,
        'total': total,
        'limit': limit,
        'offset': offset,
        'count': len(data),
        'logs': data,
    })
