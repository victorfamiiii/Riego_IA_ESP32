from rest_framework import serializers
from .models import (
    Measurement, 
    ESP32Device, 
    SoilMoisture, 
    LuminosityData,
    WeatherData,
    TrainingDataset,
    ModelVersion,
    IrrigationEvent,
    IrrigationConfig,
    IrrigationNotification,
    SensorCalibrationSettings,
    FCMToken,
    GeminiAuditLog,
)


class MeasurementSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Measurement
    """
    fecha = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()
    
    class Meta:
        model = Measurement
        fields = ['id', 'temperatura', 'humedad', 'esp32_ip', 'created_at', 'fecha', 'timestamp']
        read_only_fields = ['id', 'created_at', 'fecha', 'timestamp']
    
    def get_fecha(self, obj):
        """Retorna fecha formateada"""
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")
    
    def get_timestamp(self, obj):
        """Retorna timestamp en milisegundos"""
        return int(obj.created_at.timestamp() * 1000)


class MeasurementCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear mediciones (compatible con ESP32)
    """
    esp32_ip = serializers.IPAddressField(required=False, allow_null=True)
    
    class Meta:
        model = Measurement
        fields = ['temperatura', 'humedad', 'esp32_ip']
    
    def validate_temperatura(self, value):
        """Validar temperatura razonable"""
        if value < -50 or value > 100:
            raise serializers.ValidationError("Temperatura fuera de rango válido (-50 a 100°C)")
        return value
    
    def validate_humedad(self, value):
        """Validar humedad razonable"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Humedad fuera de rango válido (0 a 100%)")
        return value


class StatsSerializer(serializers.Serializer):
    """
    Serializador para estadísticas
    """
    total_mediciones = serializers.IntegerField()
    temperatura_promedio = serializers.FloatField()
    humedad_promedio = serializers.FloatField()
    luminosidad_promedio = serializers.FloatField(allow_null=True, required=False)
    ultima_medicion = serializers.DictField(allow_null=True)
    esp32_conectado = serializers.BooleanField()
    esp32_ip = serializers.CharField(allow_null=True)
    mediciones_24h = serializers.IntegerField()


# ============================================================================
# SERIALIZERS PARA NUEVOS MODELOS
# ============================================================================

class ESP32DeviceSerializer(serializers.ModelSerializer):
    """
    Serializador para dispositivos ESP32
    """
    esta_conectado = serializers.BooleanField(read_only=True)
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    
    class Meta:
        model = ESP32Device
        fields = [
            'id', 'name', 'device_type', 'device_type_display',
            'esp32_ip', 'mac_address', 'last_seen', 'active',
            'esta_conectado', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'esta_conectado']


class SoilMoistureSerializer(serializers.ModelSerializer):
    """
    Serializador para lecturas de humedad del suelo
    """
    device_name = serializers.CharField(source='device.name', read_only=True)
    fecha = serializers.SerializerMethodField()
    humedad_suelo = serializers.SerializerMethodField()
    humedad_suelo_raw = serializers.FloatField(source='humedad_suelo', read_only=True)
    
    class Meta:
        model = SoilMoisture
        fields = ['id', 'device', 'device_name', 'tipo_planta', 'humedad_suelo', 'humedad_suelo_raw', 'created_at', 'fecha']
        read_only_fields = ['id', 'created_at']
    
    def get_fecha(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")

    def get_humedad_suelo(self, obj):
        calibration = SensorCalibrationSettings.get_config()
        relay = 2 if obj.tipo_planta == 'fresa' else 1
        return calibration.calibrate_soil_humidity(obj.humedad_suelo, relay=relay)


class SoilMoistureCreateSerializer(serializers.Serializer):
    """
    Serializador para crear lecturas de humedad (compatible con ESP32)
    Acepta MAC address o device_id
    """
    mac_address = serializers.CharField(max_length=17, required=False, allow_blank=True)
    device_id = serializers.IntegerField(required=False)
    esp32_ip = serializers.IPAddressField(required=False, allow_null=True)
    relay = serializers.IntegerField(required=False)
    tipo_planta = serializers.CharField(max_length=50)
    humedad_suelo = serializers.FloatField()

    def validate_tipo_planta(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("El tipo de planta es obligatorio")
        return value
    
    def validate_humedad_suelo(self, value):
        if value < 0 or value > 5000:
            raise serializers.ValidationError("Humedad fuera de rango (0-5000)")
        return value
    
    def validate(self, data):
        """Validar que al menos uno de mac_address o device_id esté presente"""
        if not data.get('mac_address') and not data.get('device_id'):
            raise serializers.ValidationError(
                "Se requiere 'mac_address' o 'device_id'"
            )
        return data
    
    def create(self, validated_data):
        from django.utils import timezone
        
        # Buscar o crear dispositivo
        if validated_data.get('device_id'):
            try:
                device = ESP32Device.objects.get(id=validated_data['device_id'])
            except ESP32Device.DoesNotExist:
                raise serializers.ValidationError("Dispositivo no encontrado")
        else:
            mac = validated_data['mac_address']
            device, created = ESP32Device.objects.get_or_create(
                mac_address=mac,
                defaults={
                    'name': f'ESP32-Soil-{mac[-5:]}',
                    'device_type': 'soil'
                }
            )
        
        # Actualizar last_seen
        device.last_seen = timezone.now()
        if validated_data.get('esp32_ip'):
            device.esp32_ip = validated_data['esp32_ip']
        device.save()
        
        return SoilMoisture.objects.create(
            device=device,
            tipo_planta=validated_data['tipo_planta'],
            humedad_suelo=validated_data['humedad_suelo']
        )


class LuminosityDataSerializer(serializers.ModelSerializer):
    """Serializador para datos de luminosidad"""
    device_name = serializers.CharField(source='device.name', read_only=True)
    fecha = serializers.SerializerMethodField()
    
    class Meta:
        model = LuminosityData
        fields = ['id', 'device', 'device_name', 'luminosidad', 'created_at', 'fecha']
        read_only_fields = ['id', 'created_at']
    
    def get_fecha(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")


class LuminosityDataCreateSerializer(serializers.Serializer):
    """Serializador para crear datos de luminosidad (compatible con ESP32)"""
    mac_address = serializers.CharField(max_length=17, required=False, allow_blank=True)
    device_id = serializers.IntegerField(required=False)
    esp32_ip = serializers.IPAddressField(required=False, allow_null=True)
    luminosidad = serializers.FloatField()
    # Campos legacy opcionales para no romper firmware antiguo.
    temperatura = serializers.FloatField(required=False, write_only=True)
    humedad_ambiente = serializers.FloatField(required=False, write_only=True)
    nivel_agua = serializers.FloatField(required=False, write_only=True)
    
    def validate_luminosidad(self, value):
        if value < 0:
            raise serializers.ValidationError("Luminosidad no puede ser negativa")
        return value
    
    def validate(self, data):
        if not data.get('mac_address') and not data.get('device_id'):
            raise serializers.ValidationError(
                "Se requiere 'mac_address' o 'device_id'"
            )
        return data
    
    def create(self, validated_data):
        from django.utils import timezone
        
        # Buscar o crear dispositivo
        if validated_data.get('device_id'):
            try:
                device = ESP32Device.objects.get(id=validated_data['device_id'])
            except ESP32Device.DoesNotExist:
                raise serializers.ValidationError("Dispositivo no encontrado")
        else:
            mac = validated_data['mac_address']
            device, created = ESP32Device.objects.get_or_create(
                mac_address=mac,
                defaults={
                    'name': f'ESP32-Lux-{mac[-5:]}',
                    'device_type': 'environment'
                }
            )
        
        # Actualizar last_seen
        device.last_seen = timezone.now()
        if validated_data.get('esp32_ip'):
            device.esp32_ip = validated_data['esp32_ip']
        device.save()
        
        # Crear medición
        return LuminosityData.objects.create(
            device=device,
            luminosidad=validated_data['luminosidad']
        )


class WeatherDataSerializer(serializers.ModelSerializer):
    """
    Serializador para datos meteorológicos de AEMET
    """
    fecha_formateada = serializers.SerializerMethodField()
    
    class Meta:
        model = WeatherData
        fields = [
            'id', 'estacion_id', 'estacion_nombre',
            'temperatura', 'temperatura_maxima', 'temperatura_minima',
            'humedad', 'precipitacion', 'velocidad_viento',
            'direccion_viento', 'presion', 'radiacion_solar',
            'insolacion', 'fecha_observacion',
            'fecha_formateada', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_fecha_formateada(self, obj):
        return obj.fecha_observacion.strftime("%Y-%m-%d %H:%M:%S")


class TrainingDatasetSerializer(serializers.ModelSerializer):
    """
    Serializador para dataset de entrenamiento
    """
    class Meta:
        model = TrainingDataset
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ModelVersionSerializer(serializers.ModelSerializer):
    """
    Serializador para versiones de modelos
    """
    class Meta:
        model = ModelVersion
        fields = '__all__'
        read_only_fields = ['id', 'fecha_entrenamiento']


class IrrigationEventSerializer(serializers.ModelSerializer):
    """
    Serializador para eventos de riego
    """
    fecha_inicio_formateada = serializers.SerializerMethodField()
    fecha_fin_formateada = serializers.SerializerMethodField()
    
    class Meta:
        model = IrrigationEvent
        fields = [
            'id', 'fecha_inicio', 'fecha_fin', 
            'fecha_inicio_formateada', 'fecha_fin_formateada',
            'device', 'relay', 'tipo_planta',
            'duracion_planificada_segundos', 'duracion_real_segundos',
            'litros', 'humedad_inicial', 'humedad_final',
            'temperatura_inicial', 'temperatura_final',
            'razon', 'automatico', 'stop_requested', 'device_started_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_fecha_inicio_formateada(self, obj):
        return obj.fecha_inicio.strftime("%Y-%m-%d %H:%M:%S")
    
    def get_fecha_fin_formateada(self, obj):
        if obj.fecha_fin:
            return obj.fecha_fin.strftime("%Y-%m-%d %H:%M:%S")
        return None


class IrrigationConfigSerializer(serializers.ModelSerializer):
    """
    Serializador para configuración de riego
    """
    def validate_configuracion_por_planta(self, value):
        if value in (None, ''):
            return {}

        if isinstance(value, str):
            import json

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
        read_only_fields = ['id', 'created_at', 'updated_at']


class IrrigationNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = IrrigationNotification
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class FCMTokenSerializer(serializers.ModelSerializer):
    """
    Serializador para tokens de Firebase Cloud Messaging (FCM)
    """
    class Meta:
        model = FCMToken
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at', 'last_used']


class GeminiAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializador para logs de auditoría de Gemini AI
    """
    fecha_formateada = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = GeminiAuditLog
        fields = [
            'id', 'tipo', 'tipo_display', 'tipo_planta', 'prompt',
            'modelo', 'respuesta_raw', 'respuesta_json',
            'decision_regar', 'decision_duracion_s', 'decision_razon',
            'tokens_entrada', 'tokens_salida', 'latencia_ms',
            'exito', 'error_mensaje', 'evento_riego',
            'created_at', 'fecha_formateada'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_fecha_formateada(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")
