from django.db import models
from django.utils import timezone
from django.db.models import Avg


class ESP32Device(models.Model):
    """
    Modelo para registrar dispositivos ESP32
    """
    DEVICE_TYPES = [
        ('soil', 'Sensor de Humedad de Suelo'),
        ('environment', 'Sensores Ambientales'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    esp32_ip = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, unique=True, null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Dispositivo ESP32"
        verbose_name_plural = "Dispositivos ESP32"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()})"
    
    @property
    def esta_conectado(self):
        """Retorna True si el dispositivo se conectó en los últimos 60 segundos"""
        if not self.last_seen:
            return False
        delta = (timezone.now() - self.last_seen).total_seconds()
        return delta < 60


class SoilMoisture(models.Model):
    """
    Modelo para datos del ESP32 #1: Humedad del Suelo
    """
    device = models.ForeignKey(
        ESP32Device, 
        on_delete=models.CASCADE,
        related_name='soil_readings',
        limit_choices_to={'device_type': 'soil'}
    )
    humedad_suelo = models.FloatField(
        help_text="Lectura cruda ADC de humedad del suelo enviada por la ESP32"
    )
    tipo_planta = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Tipo de planta asociada a la medición"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Fecha y hora de la medición"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Medición de Humedad de Suelo"
        verbose_name_plural = "Mediciones de Humedad de Suelo"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['device', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.tipo_planta} - raw {self.humedad_suelo} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class LuminosityData(models.Model):
    """
    Modelo para datos del ESP32 #2: Sensor de luminosidad
    """
    device = models.ForeignKey(
        ESP32Device, 
        on_delete=models.CASCADE,
        related_name='luminosity_readings',
        limit_choices_to={'device_type': 'environment'}
    )
    luminosidad = models.FloatField(
        help_text="Nivel de luz en lux (0-200000)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Fecha y hora de la medición"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dato de Luminosidad"
        verbose_name_plural = "Datos de Luminosidad"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['device', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.luminosidad} lux - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class WeatherData(models.Model):
    """
    Modelo para almacenar datos meteorológicos de AEMET
    """
    # Identificación
    estacion_id = models.CharField(
        max_length=20,
        help_text="ID de la estación meteorológica de AEMET"
    )
    estacion_nombre = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nombre de la estación"
    )
    
    # Datos meteorológicos
    temperatura = models.FloatField(
        null=True,
        blank=True,
        help_text="Temperatura en °C"
    )
    temperatura_maxima = models.FloatField(
        null=True,
        blank=True,
        help_text="Temperatura máxima en °C"
    )
    temperatura_minima = models.FloatField(
        null=True,
        blank=True,
        help_text="Temperatura mínima en °C"
    )
    humedad = models.FloatField(
        null=True,
        blank=True,
        help_text="Humedad relativa en %"
    )
    precipitacion = models.FloatField(
        null=True,
        blank=True,
        default=0.0,
        help_text="Precipitación acumulada en mm"
    )
    velocidad_viento = models.FloatField(
        null=True,
        blank=True,
        help_text="Velocidad del viento en km/h"
    )
    direccion_viento = models.CharField(
        max_length=50,
        blank=True,
        help_text="Dirección del viento"
    )
    presion = models.FloatField(
        null=True,
        blank=True,
        help_text="Presión atmosférica en hPa"
    )
    radiacion_solar = models.FloatField(
        null=True,
        blank=True,
        help_text="Radiación solar global en W/m²"
    )
    insolacion = models.FloatField(
        null=True,
        blank=True,
        help_text="Horas de insolación (horas)"
    )
    
    # Timestamps
    fecha_observacion = models.DateTimeField(
        help_text="Fecha y hora de la observación meteorológica"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    
    class Meta:
        ordering = ['-fecha_observacion']
        verbose_name = "Dato Meteorológico"
        verbose_name_plural = "Datos Meteorológicos"
        indexes = [
            models.Index(fields=['-fecha_observacion']),
            models.Index(fields=['estacion_id', '-fecha_observacion']),
        ]
        unique_together = ['estacion_id', 'fecha_observacion']
    
    def __str__(self):
        return f"AEMET {self.estacion_id} - {self.fecha_observacion.strftime('%d/%m/%Y %H:%M')}"


class WeatherForecastSnapshot(models.Model):
    """
    Snapshot persistente de previsión AEMET normalizada para frontend.
    """

    municipio_id = models.CharField(
        max_length=20,
        db_index=True,
        help_text="ID del municipio de AEMET"
    )
    municipio_nombre = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nombre del municipio"
    )
    dias = models.PositiveSmallIntegerField(
        default=5,
        help_text="Número de días incluidos en la previsión"
    )
    elaborado = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha/hora de elaboración reportada por AEMET"
    )
    payload = models.JSONField(
        default=dict,
        help_text="Previsión normalizada completa"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Snapshot de previsión meteorológica"
        verbose_name_plural = "Snapshots de previsión meteorológica"
        ordering = ['-updated_at']
        unique_together = ('municipio_id', 'dias')
        indexes = [
            models.Index(fields=['municipio_id', 'dias']),
            models.Index(fields=['-updated_at']),
        ]

    def __str__(self):
        return f"Forecast {self.municipio_id} ({self.dias}d) - {self.updated_at.strftime('%d/%m/%Y %H:%M')}"


class Measurement(models.Model):
    """
    Modelo LEGACY - Mantener para compatibilidad con código existente
    Se recomienda usar SoilMoisture y LuminosityData
    """
    temperatura = models.FloatField(
        help_text="Temperatura en grados Celsius"
    )
    humedad = models.FloatField(
        help_text="Humedad relativa en porcentaje"
    )
    esp32_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Dirección IP del ESP32"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha y hora de la medición"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Medición (Legacy)"
        verbose_name_plural = "Mediciones (Legacy)"
        indexes = [
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Medición {self.id}: {self.temperatura}°C, {self.humedad}%"
    
    @property
    def fecha_formateada(self):
        """Retorna la fecha en formato legible"""
        return self.created_at.strftime("%d/%m/%Y %H:%M:%S")


class IrrigationConfig(models.Model):
    """
    Configuración del sistema de riego automático
    Puede haber una configuración activa por cada tipo de planta
    """
    PLANT_TYPES = [
        ('lechuga', 'Lechuga'),
        ('fresa', 'Fresa'),
        ('general', 'General'),
    ]
    
    tipo_planta = models.CharField(
        max_length=20,
        choices=PLANT_TYPES,
        default='general',
        help_text="Tipo de planta para la que aplica esta configuración"
    )
    activo = models.BooleanField(
        default=True,
        help_text="Si esta configuración está activa"
    )
    riego_automatico_activo = models.BooleanField(
        default=True,
        help_text="Activar/desactivar riego automático"
    )
    modo_riego = models.CharField(
    	max_length=10,
    	choices=[
        	('umbral', 'Umbral automático'),
        	('ia',     'Inteligencia Artificial'),
        	('manual', 'Solo manual'),
    	        ],
    	default='umbral',
    	help_text="Modo de decisión de riego"
    )
    mediciones_para_media = models.PositiveSmallIntegerField(
        default=4,
        help_text="Número de mediciones usadas para calcular la media del riego automático"
    )
    umbral_humedad_minimo = models.FloatField(
        default=40.0,
        help_text="Porcentaje de humedad mínimo antes de activar riego"
    )
    tiempo_riego_segundos = models.IntegerField(
        default=30,
        help_text="Duración del riego en segundos"
    )
    max_riegos_dia = models.IntegerField(
        default=6,
        help_text="Número máximo de riegos por día"
    )
    tiempo_minimo_entre_riegos = models.IntegerField(
        default=3600,
        help_text="Tiempo mínimo entre riegos en segundos (default: 1 hora)"
    )
    configuracion_por_planta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuración específica por planta. Ejemplo: {'lechuga': {...}, 'fresa': {...}}"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración de Riego"
        verbose_name_plural = "Configuraciones de Riego"
        ordering = ['-created_at']
        unique_together = ('tipo_planta', 'activo')
    
    def __str__(self):
        estado = "Activo" if self.activo else "Inactivo"
        planta = self.get_tipo_planta_display()
        return f"Configuración de Riego - {planta} ({estado})"
    
    def save(self, *args, **kwargs):
        """Si se marca como activo, desactivar otras activas del MISMO tipo de planta"""
        if self.activo:
            IrrigationConfig.objects.filter(
                tipo_planta=self.tipo_planta,
                activo=True
            ).exclude(pk=self.pk).update(activo=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config_by_plant(cls, tipo_planta='general'):
        """Obtiene la configuración activa para un tipo de planta específico"""
        config = cls.objects.filter(
            tipo_planta=tipo_planta,
            activo=True
        ).first()
        if not config:
            config = cls.objects.filter(
                tipo_planta='general',
                activo=True
            ).first()
        return config


class IrrigationEvent(models.Model):
    """
    Registro de eventos de riego (historial)
    """
    device = models.ForeignKey(
        ESP32Device,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='irrigation_events',
        limit_choices_to={'device_type': 'soil'}
    )
    relay = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Relé/zona que debe ejecutar el riego"
    )
    tipo_planta = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Tipo de planta asociado al riego"
    )
    fecha_inicio = models.DateTimeField(
        help_text="Fecha y hora de inicio del riego"
    )
    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora de fin del riego"
    )
    duracion_planificada_segundos = models.IntegerField(
        help_text="Duración planificada en segundos"
    )
    duracion_real_segundos = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duración real en segundos"
    )
    litros = models.FloatField(
        null=True,
        blank=True,
        help_text="Cantidad de agua utilizada en litros"
    )
    humedad_inicial = models.FloatField(
        help_text="Humedad al inicio del riego (%)"
    )
    humedad_final = models.FloatField(
        null=True,
        blank=True,
        help_text="Humedad al final del riego (%)"
    )
    temperatura_inicial = models.FloatField(
        null=True,
        blank=True,
        help_text="Temperatura al inicio (°C)"
    )
    temperatura_final = models.FloatField(
        null=True,
        blank=True,
        help_text="Temperatura al final (°C)"
    )
    razon = models.CharField(
        max_length=200,
        default="Riego automático",
        help_text="Razón del riego"
    )
    automatico = models.BooleanField(
        default=True,
        help_text="Si fue riego automático o manual"
    )
    stop_requested = models.BooleanField(
        default=False,
        help_text="Indica si el servidor ha solicitado detener el riego"
    )
    device_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Momento en el que la ESP32 confirmó el inicio"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Evento de Riego"
        verbose_name_plural = "Eventos de Riego"
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['-fecha_inicio']),
            models.Index(fields=['fecha_fin']),
        ]
    
    def __str__(self):
        estado = "En curso" if not self.fecha_fin else "Completado"
        return f"Riego {self.id} ({estado}) - {self.fecha_inicio.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def esta_activo(self):
        """Retorna True si el riego está en curso"""
        return self.fecha_fin is None
    
    @property
    def duracion_formateada(self):
        """Retorna la duración en formato legible"""
        if self.duracion_real_segundos:
            minutos = self.duracion_real_segundos // 60
            segundos = self.duracion_real_segundos % 60
            return f"{minutos}m {segundos}s"
        return "En curso"


class IrrigationNotification(models.Model):
    """Registro de notificaciones intercambiadas con la ESP32 de riego."""

    NOTIFICATION_TYPES = [
        ('poll', 'Consulta de comando'),
        ('start', 'Inicio de riego'),
        ('stop', 'Parada de riego'),
        ('completed', 'Riego completado'),
        ('manual-stop', 'Parada manual solicitada'),
        ('error', 'Error'),
    ]

    device = models.ForeignKey(
        ESP32Device,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='irrigation_notifications',
        limit_choices_to={'device_type': 'soil'}
    )
    event = models.ForeignKey(
        IrrigationEvent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    relay = models.PositiveSmallIntegerField(null=True, blank=True)
    tipo_planta = models.CharField(max_length=50, null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Notificación de Riego"
        verbose_name_plural = "Notificaciones de Riego"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} - relay {self.relay or '-'} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class TrainingDataset(models.Model):
    """
    Dataset preparado para entrenar modelos de IA
    Combina datos de sensores con resultados de riego
    """
    # Features de sensores
    humedad_suelo = models.FloatField()
    temperatura = models.FloatField()
    humedad_ambiente = models.FloatField()
    luminosidad = models.FloatField()
    nivel_agua = models.FloatField()
    
    # Features meteorológicas (AEMET)
    temperatura_exterior = models.FloatField(null=True, blank=True)
    precipitacion_24h = models.FloatField(default=0.0)
    velocidad_viento = models.FloatField(null=True, blank=True)
    presion_atmosferica = models.FloatField(null=True, blank=True)
    
    # Features temporales (ya calculadas)
    hora_dia = models.IntegerField()  # 0-23
    dia_semana = models.IntegerField()  # 0-6 (0=Lunes)
    mes = models.IntegerField()  # 1-12
    estacion = models.IntegerField()  # 1=Primavera, 2=Verano, 3=Otoño, 4=Invierno
    
    # Features derivadas (ingeniería de características)
    deficit_hidrico = models.FloatField()  # 70 - humedad_suelo
    humedad_promedio_24h = models.FloatField()
    temperatura_promedio_24h = models.FloatField()
    num_riegos_24h = models.IntegerField(default=0)
    evapotranspiracion_estimada = models.FloatField(default=0.0)
    
    # Labels (variables objetivo)
    necesita_riego = models.BooleanField()  # Target clasificación
    cantidad_agua_segundos = models.IntegerField(null=True, blank=True)  # Target regresión
    
    # Resultado real (para evaluar efectividad)
    se_rego = models.BooleanField(default=False)
    humedad_post_riego = models.FloatField(null=True, blank=True)
    efectividad_riego = models.FloatField(null=True, blank=True)  # Delta humedad
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    fuente = models.CharField(
        max_length=20,
        choices=[
            ('real', 'Datos Reales'),
            ('sintetico', 'Datos Sintéticos')
        ],
        default='real'
    )
    usado_entrenamiento = models.BooleanField(default=False)
    split = models.CharField(
        max_length=10,
        choices=[
            ('train', 'Entrenamiento'),
            ('val', 'Validación'),
            ('test', 'Test')
        ],
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dataset de Entrenamiento"
        verbose_name_plural = "Datasets de Entrenamiento"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['usado_entrenamiento', 'split']),
            models.Index(fields=['necesita_riego']),
            models.Index(fields=['fuente']),
        ]
    
    def __str__(self):
        return f"Training {self.id} - {'Regar' if self.necesita_riego else 'No regar'} - {self.created_at.strftime('%d/%m/%Y')}"


class ModelVersion(models.Model):
    """
    Control de versiones de modelos entrenados
    """
    version = models.CharField(
        max_length=20,
        unique=True,
        help_text="Versión del modelo (ej: v1.0.0)"
    )
    modelo_clasificacion_path = models.CharField(
        max_length=500,
        help_text="Ruta al archivo del modelo de clasificación"
    )
    modelo_regresion_path = models.CharField(
        max_length=500,
        help_text="Ruta al archivo del modelo de regresión"
    )
    scaler_path = models.CharField(
        max_length=500,
        help_text="Ruta al archivo del scaler"
    )
    
    # Métricas de evaluación
    accuracy_clasificacion = models.FloatField(
        help_text="Accuracy del modelo de clasificación (0-1)"
    )
    mae_regresion = models.FloatField(
        help_text="MAE del modelo de regresión (ml)"
    )
    r2_regresion = models.FloatField(
        help_text="R² Score del modelo de regresión (0-1)"
    )
    
    # Hiperparámetros
    n_estimators = models.IntegerField(default=100)
    max_depth = models.IntegerField(default=10)
    hyperparameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Otros hiperparámetros en formato JSON"
    )
    
    # Dataset usado
    num_muestras_train = models.IntegerField()
    num_muestras_test = models.IntegerField()
    fecha_inicio_datos = models.DateTimeField()
    fecha_fin_datos = models.DateTimeField()
    
    # Metadata
    entrenado_por = models.CharField(max_length=100, default='Sistema')
    fecha_entrenamiento = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(
        default=False,
        help_text="Modelo activo en producción"
    )
    notas = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-fecha_entrenamiento']
        verbose_name = "Versión de Modelo"
        verbose_name_plural = "Versiones de Modelos"
    
    def __str__(self):
        estado = "✓ Activo" if self.activo else "Inactivo"
        return f"{self.version} ({estado})"
    
    def save(self, *args, **kwargs):
        """Si se marca como activo, desactivar los demás"""
        if self.activo:
            ModelVersion.objects.filter(activo=True).update(activo=False)
        super().save(*args, **kwargs)


class WaterTankReading(models.Model):
    """
    Histórico de lecturas del nivel de agua del tanque.
    Cada vez que la ESP32 envía una distancia, se guarda un registro.
    """
    distancia = models.FloatField(
        help_text="Distancia medida por el sensor en cm"
    )
    porcentaje = models.FloatField(
        help_text="Porcentaje de llenado calculado"
    )
    litros = models.FloatField(
        help_text="Litros calculados"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Fecha y hora de la lectura"
    )
    
    class Meta:
        verbose_name = "Lectura del Tanque de Agua"
        verbose_name_plural = "Lecturas del Tanque de Agua"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Recalcula porcentaje y litros en cada guardado usando la calibracion activa."""
        try:
            distancia = max(0.0, float(self.distancia))
        except (TypeError, ValueError):
            distancia = 0.0

        self.distancia = distancia
        calibration = SensorCalibrationSettings.get_config()
        porcentaje, litros = calibration.calculate_tank_level(distancia)
        self.porcentaje = porcentaje
        self.litros = litros

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} - {self.porcentaje}% ({self.litros}L)"


class SensorCalibrationSettings(models.Model):
    """
    Configuración de calibración para sensores y electroválvulas.
    Se maneja como singleton (registro con PK=1).
    """
    # Tanque de agua (sensor ultrasónico)
    distancia_minima_tanque = models.FloatField(default=5.0)
    distancia_maxima_tanque = models.FloatField(default=100.0)
    capacidad_litros_tanque = models.FloatField(default=10.0)

    # Electroválvulas (litros estimados por tiempo de apertura)
    ev1_litros_1s = models.FloatField(default=0.05)
    ev1_litros_5s = models.FloatField(default=0.25)
    ev1_litros_10s = models.FloatField(default=0.50)
    ev2_litros_1s = models.FloatField(default=0.05)
    ev2_litros_5s = models.FloatField(default=0.25)
    ev2_litros_10s = models.FloatField(default=0.50)

    # Humedad de suelo (calibración de extremos por sensor)
    suelo1_valor_seco = models.FloatField(default=4095.0)
    suelo1_valor_mojado = models.FloatField(default=1200.0)
    suelo2_valor_seco = models.FloatField(default=4095.0)
    suelo2_valor_mojado = models.FloatField(default=1200.0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibración de Sensores"
        verbose_name_plural = "Calibración de Sensores"

    def __str__(self):
        return "Calibración global de sensores"

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def get_soil_points(self, relay=None):
        if relay == 2:
            return self.suelo2_valor_seco, self.suelo2_valor_mojado
        return self.suelo1_valor_seco, self.suelo1_valor_mojado

    def calculate_tank_level(self, distancia):
        """Calcula porcentaje y litros del tanque usando la calibración activa."""
        if distancia <= self.distancia_minima_tanque:
            porcentaje = 100.0
        elif distancia >= self.distancia_maxima_tanque:
            porcentaje = 0.0
        else:
            rango = self.distancia_maxima_tanque - self.distancia_minima_tanque
            if rango <= 0:
                porcentaje = 0.0
            else:
                distancia_relativa = distancia - self.distancia_minima_tanque
                porcentaje = 100.0 - (distancia_relativa / rango * 100.0)

        litros = (porcentaje / 100.0) * self.capacidad_litros_tanque
        return round(porcentaje, 1), round(litros, 2)

    def calibrate_soil_humidity(self, raw_value, relay=None):
        """
        Convierte lectura cruda de humedad a porcentaje calibrado (0-100).
        Si el valor ya parece porcentaje y la calibración está en escala ADC,
        se devuelve el valor original para mantener compatibilidad.
        """
        dry, wet = self.get_soil_points(relay=relay)

        if raw_value is None:
            return None

        # Compatibilidad con firmware antiguo que ya envía porcentaje.
        if raw_value <= 100 and max(dry, wet) > 100:
            return max(0.0, min(100.0, float(raw_value)))

        if wet == dry:
            return max(0.0, min(100.0, float(raw_value)))

        calibrated = ((float(raw_value) - dry) / (wet - dry)) * 100.0
        return max(0.0, min(100.0, round(calibrated, 2)))

    def estimate_liters(self, relay, duration_seconds):
        """
        Estima litros para un relé y duración usando interpolación por puntos
        calibrados en 1s, 5s y 10s.
        """
        duration = max(0.0, float(duration_seconds or 0))

        if relay == 2:
            l1, l5, l10 = self.ev2_litros_1s, self.ev2_litros_5s, self.ev2_litros_10s
        else:
            l1, l5, l10 = self.ev1_litros_1s, self.ev1_litros_5s, self.ev1_litros_10s

        if duration <= 0:
            return 0.0

        if duration <= 1:
            return round(l1 * duration, 4)

        if duration <= 5:
            slope = (l5 - l1) / 4.0
            return round(l1 + (duration - 1) * slope, 4)

        if duration <= 10:
            slope = (l10 - l5) / 5.0
            return round(l5 + (duration - 5) * slope, 4)

        lps = l10 / 10.0 if l10 > 0 else 0.0
        return round(lps * duration, 4)

    def estimate_duration_seconds(self, relay, target_liters):
        """
        Estima segundos necesarios para alcanzar litros objetivo usando
        la misma curva por tramos de calibración (1s, 5s, 10s).
        """
        liters = max(0.0, float(target_liters or 0))

        if relay == 2:
            l1, l5, l10 = self.ev2_litros_1s, self.ev2_litros_5s, self.ev2_litros_10s
        else:
            l1, l5, l10 = self.ev1_litros_1s, self.ev1_litros_5s, self.ev1_litros_10s

        if liters <= 0:
            return 0

        # Tramo 0-1s: lineal hasta l1
        if l1 > 0 and liters <= l1:
            return max(1, int(round(liters / l1)))

        # Tramo 1-5s
        if l5 > l1 and liters <= l5:
            slope = (l5 - l1) / 4.0
            if slope <= 0:
                return 5
            seconds = 1.0 + ((liters - l1) / slope)
            return max(1, int(round(seconds)))

        # Tramo 5-10s
        if l10 > l5 and liters <= l10:
            slope = (l10 - l5) / 5.0
            if slope <= 0:
                return 10
            seconds = 5.0 + ((liters - l5) / slope)
            return max(1, int(round(seconds)))

        # Más allá de 10s: extrapolar con lps en 10s
        lps = (l10 / 10.0) if l10 > 0 else 0.0
        if lps <= 0:
            return 10

        return max(1, int(round(liters / lps)))


class FCMToken(models.Model):
    """
    Almacena tokens de Firebase Cloud Messaging para notificaciones push.
    Cada dispositivo/navegador registrado tendrá un token único.
    """
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='fcm_tokens',
        null=True,
        blank=True,
        help_text='Usuario propietario del token'
    )
    token = models.CharField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text="Token FCM único del dispositivo"
    )
    device_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nombre/descripción del dispositivo (ej: iPhone 12, Chrome)"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User-Agent del navegador/dispositivo"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Fecha de registro del token"
    )
    last_used = models.DateTimeField(
        auto_now=True,
        help_text="Última vez que se usó este token"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Token activo o desactivado"
    )

    class Meta:
        verbose_name = "Token FCM"
        verbose_name_plural = "Tokens FCM"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.device_name or 'Unknown'} ({self.token[:20]}...)"


class NotificationHistory(models.Model):
    """
    Historial de notificaciones enviadas a usuarios vía FCM.
    Permite auditar y reenviar notificaciones.
    """
    NOTIFICATION_STATUS = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviada'),
        ('failed', 'Fallida'),
        ('read', 'Leída'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='notification_history',
        help_text="Usuario destino de la notificación"
    )
    title = models.CharField(
        max_length=255,
        help_text="Título de la notificación"
    )
    body = models.TextField(
        help_text="Cuerpo/contenido de la notificación"
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos adicionales en formato JSON"
    )
    icon = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL del ícono"
    )
    status = models.CharField(
        max_length=20,
        choices=NOTIFICATION_STATUS,
        default='pending',
        help_text="Estado de envío de la notificación"
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora de envío"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Fecha de creación del registro"
    )
    sent_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notifications_sent',
        help_text="Usuario administrador que envió la notificación"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Mensaje de error si falló el envío"
    )
    num_tokens_sent = models.IntegerField(
        default=0,
        help_text="Número de tokens a los que se intentó enviar"
    )
    num_tokens_failed = models.IntegerField(
        default=0,
        help_text="Número de tokens en los que falló el envío"
    )
    
    class Meta:
        verbose_name = "Historial de Notificaciones"
        verbose_name_plural = "Historial de Notificaciones"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.title[:50]} - {self.user.username} ({self.status})"


class GeminiAuditLog(models.Model):
    DECISION_TYPES = [
        ('irrigation', 'Decision de riego'),
        ('chat', 'Chat con usuario'),
    ]
    tipo                = models.CharField(max_length=20, choices=DECISION_TYPES, default='irrigation')
    tipo_planta         = models.CharField(max_length=50, null=True, blank=True)
    prompt              = models.TextField()
    modelo              = models.CharField(max_length=50, default='gemini-2.5-flash')
    respuesta_raw       = models.TextField(blank=True)
    respuesta_json      = models.JSONField(null=True, blank=True)
    decision_regar      = models.BooleanField(null=True, blank=True)
    decision_duracion_s = models.IntegerField(null=True, blank=True)
    decision_razon      = models.TextField(blank=True)
    tokens_entrada      = models.IntegerField(null=True, blank=True)
    tokens_salida       = models.IntegerField(null=True, blank=True)
    latencia_ms         = models.IntegerField(null=True, blank=True)
    exito               = models.BooleanField(default=True)
    error_mensaje       = models.TextField(blank=True)
    evento_riego        = models.ForeignKey(
        'IrrigationEvent', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='gemini_logs'
    )
    created_at          = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log de Gemini'
        verbose_name_plural = 'Logs de Gemini'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['tipo_planta', '-created_at']),
            models.Index(fields=['exito']),
        ]

    def __str__(self):
        decision = 'Regar' if self.decision_regar else 'No regar'
        return f'[{self.tipo_planta}] {decision} - {self.created_at.strftime("%d/%m %H:%M")}'
