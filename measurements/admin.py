from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Measurement, 
    IrrigationConfig, 
    IrrigationEvent,
    IrrigationNotification,
    ESP32Device,
    SoilMoisture,
    LuminosityData,
    WeatherData,
    WeatherForecastSnapshot,
    TrainingDataset,
    ModelVersion,
    WaterTankReading,
    SensorCalibrationSettings,
)


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración de Django para Measurement
    Accesible en http://localhost:8000/admin/measurements/measurement/
    """
    
    # Campos que se muestran en la lista con iconos y colores
    list_display = (
        'id',
        'temperatura_display',
        'humedad_display',
        'esp32_ip_display',
        'created_at_display'
    )
    
    # Filtros laterales
    list_filter = (
        'created_at',
        'esp32_ip',
    )
    
    # Campos de búsqueda
    search_fields = (
        'esp32_ip',
    )
    
    # Ordenamiento por defecto
    ordering = ('-created_at',)
    
    # Jerarquía de fecha en la parte superior
    date_hierarchy = 'created_at'
    
    # Número de elementos por página
    list_per_page = 50
    
    # Campos de solo lectura
    readonly_fields = ('created_at', 'temperatura_gauge', 'humedad_gauge')
    
    # Organización de campos en el formulario de edición
    fieldsets = (
        ('📊 Datos del Sensor', {
            'fields': ('temperatura', 'temperatura_gauge', 'humedad', 'humedad_gauge'),
            'description': 'Datos recopilados por los sensores del ESP32'
        }),
        ('🌐 Información de Conexión', {
            'fields': ('esp32_ip',),
            'description': 'Dirección IP del dispositivo ESP32'
        }),
        ('🕐 Fecha y Hora', {
            'fields': ('created_at',),
            'classes': ('collapse',),
            'description': 'Marca temporal de la medición'
        }),
    )
    
    # Métodos personalizados para mostrar con formato
    @admin.display(description='🌡️ Temperatura', ordering='temperatura')
    def temperatura_display(self, obj):
        """Muestra temperatura con color según el valor"""
        temp = obj.temperatura
        if temp < 15:
            color = '#2196f3'  # Azul - Frío
        elif temp < 25:
            color = '#4caf50'  # Verde - Óptimo
        elif temp < 30:
            color = '#ff9800'  # Naranja - Caliente
        else:
            color = '#f44336'  # Rojo - Muy caliente
        
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 16px;">{}°C</span>',
            color, round(temp, 1)
        )
    
    @admin.display(description='💧 Humedad', ordering='humedad')
    def humedad_display(self, obj):
        """Muestra humedad con color según el valor"""
        hum = obj.humedad
        if hum < 30:
            color = '#f44336'  # Rojo - Muy seco
        elif hum < 50:
            color = '#ff9800'  # Naranja - Seco
        elif hum < 70:
            color = '#4caf50'  # Verde - Óptimo
        else:
            color = '#2196f3'  # Azul - Húmedo
        
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 16px;">{}%</span>',
            color, round(hum, 1)
        )
    
    @admin.display(description='📡 ESP32 IP', ordering='esp32_ip')
    def esp32_ip_display(self, obj):
        """Muestra IP con icono"""
        if obj.esp32_ip:
            return format_html(
                '<span style="font-family: monospace; background: #e8f5e9; padding: 4px 8px; '
                'border-radius: 4px; color: #2e7d32;">🔗 {}</span>',
                obj.esp32_ip
            )
        return format_html('<span style="color: #9e9e9e;">Sin IP</span>')
    
    @admin.display(description='📅 Fecha y Hora', ordering='created_at')
    def created_at_display(self, obj):
        """Muestra fecha formateada con icono"""
        return format_html(
            '<span style="color: #1976d2;">⏰ {}</span>',
            obj.created_at.strftime("%d/%m/%Y %H:%M:%S")
        )
    
    @admin.display(description='🌡️ Indicador Temperatura')
    def temperatura_gauge(self, obj):
        """Muestra un indicador visual de temperatura"""
        temp = obj.temperatura
        percentage = min(100, max(0, (temp + 10) * 2))  # Escala de -10 a 50
        
        if temp < 15:
            color = '#2196f3'
        elif temp < 25:
            color = '#4caf50'
        elif temp < 30:
            color = '#ff9800'
        else:
            color = '#f44336'
        
        return format_html(
            '<div style="width: 200px; background: #e0e0e0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; padding: 8px; color: white; '
            'text-align: center; font-weight: bold; border-radius: 10px;">{}°C</div>'
            '</div>',
            percentage, color, round(temp, 1)
        )
    
    @admin.display(description='💧 Indicador Humedad')
    def humedad_gauge(self, obj):
        """Muestra un indicador visual de humedad"""
        hum = obj.humedad
        
        if hum < 30:
            color = '#f44336'
        elif hum < 50:
            color = '#ff9800'
        elif hum < 70:
            color = '#4caf50'
        else:
            color = '#2196f3'
        
        return format_html(
            '<div style="width: 200px; background: #e0e0e0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; padding: 8px; color: white; '
            'text-align: center; font-weight: bold; border-radius: 10px;">{}%</div>'
            '</div>',
            hum, color, round(hum, 1)
        )
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }


@admin.register(IrrigationConfig)
class IrrigationConfigAdmin(admin.ModelAdmin):
    """
    Panel de administración para configuración de riego
    """
    list_display = (
        'id',
        'activo_display',
        'automatico_display',
        'mediciones_display',
        'umbral_display',
        'tiempo_riego_display',
        'max_riegos_display',
        'updated_at_display'
    )
    
    list_filter = ('activo', 'riego_automatico_activo', 'created_at')
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('⚙️ Estado del Sistema', {
            'fields': ('activo', 'riego_automatico_activo'),
            'description': 'Control general del sistema de riego automático'
        }),
        ('🌱 Parámetros de Riego', {
            'fields': (
                'mediciones_para_media',
                'umbral_humedad_minimo',
                'tiempo_riego_segundos',
                'max_riegos_dia',
                'tiempo_minimo_entre_riegos'
            ),
            'description': 'Configuración de umbrales y tiempos de riego'
        }),
        ('🪴 Configuración por Planta', {
            'fields': ('configuracion_por_planta',),
            'description': 'Opcional: sobrescribe valores globales por tipo de planta (lechuga/fresa) usando JSON.'
        }),
        ('📅 Información', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='✅ Activo', boolean=True)
    def activo_display(self, obj):
        return obj.activo
    
    @admin.display(description='🤖 Automático', boolean=True)
    def automatico_display(self, obj):
        return obj.riego_automatico_activo

    @admin.display(description='🧮 Medias')
    def mediciones_display(self, obj):
        return format_html(
            '<span style="font-weight: bold; color: #673ab7;">{} valores</span>',
            obj.mediciones_para_media
        )
    
    @admin.display(description='💧 Umbral Humedad')
    def umbral_display(self, obj):
        return format_html(
            '<span style="font-weight: bold; color: #2196f3;">{}%</span>',
            obj.umbral_humedad_minimo
        )
    
    @admin.display(description='⏱️ Tiempo Riego')
    def tiempo_riego_display(self, obj):
        minutos = obj.tiempo_riego_segundos // 60
        segundos = obj.tiempo_riego_segundos % 60
        if minutos > 0:
            texto = f"{minutos}m {segundos}s"
        else:
            texto = f"{segundos}s"
        
        return format_html(
            '<span style="font-weight: bold; color: #4caf50;">{}</span>',
            texto
        )
    
    @admin.display(description='🔢 Máx Riegos/Día')
    def max_riegos_display(self, obj):
        return format_html(
            '<span style="font-weight: bold; color: #ff9800;">{} riegos</span>',
            obj.max_riegos_dia
        )
    
    @admin.display(description='🕐 Última Actualización')
    def updated_at_display(self, obj):
        return obj.updated_at.strftime("%d/%m/%Y %H:%M:%S")


@admin.register(IrrigationEvent)
class IrrigationEventAdmin(admin.ModelAdmin):
    """
    Panel de administración para eventos de riego
    """
    list_display = (
        'id',
        'estado_display',
        'fecha_inicio_display',
        'duracion_display',
        'humedad_cambio_display',
        'tipo_display'
    )
    
    list_filter = (
        'automatico',
        'fecha_inicio',
        'fecha_fin'
    )
    
    readonly_fields = (
        'fecha_inicio',
        'fecha_fin',
        'created_at',
        'humedad_comparacion'
    )
    
    fieldsets = (
        ('📊 Información del Riego', {
            'fields': (
                'fecha_inicio',
                'fecha_fin',
                'duracion_planificada_segundos',
                'duracion_real_segundos'
            )
        }),
        ('🌡️ Condiciones Ambientales', {
            'fields': (
                ('humedad_inicial', 'humedad_final'),
                ('temperatura_inicial', 'temperatura_final'),
                'humedad_comparacion'
            )
        }),
        ('ℹ️ Detalles', {
            'fields': ('razon', 'automatico', 'created_at')
        }),
    )
    
    @admin.display(description='📊 Estado')
    def estado_display(self, obj):
        if obj.esta_activo:
            return format_html(
                '<span style="background: #4caf50; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-weight: bold;">🟢 EN CURSO</span>'
            )
        else:
            return format_html(
                '<span style="background: #9e9e9e; color: white; padding: 4px 12px; '
                'border-radius: 12px;">⚫ COMPLETADO</span>'
            )
    
    @admin.display(description='📅 Inicio')
    def fecha_inicio_display(self, obj):
        return obj.fecha_inicio.strftime("%d/%m/%Y %H:%M:%S")
    
    @admin.display(description='⏱️ Duración')
    def duracion_display(self, obj):
        if obj.duracion_real_segundos:
            segundos = obj.duracion_real_segundos
        else:
            segundos = obj.duracion_planificada_segundos
        
        minutos = segundos // 60
        segs = segundos % 60
        
        if minutos > 0:
            texto = f"{minutos}m {segs}s"
        else:
            texto = f"{segs}s"
        
        color = '#4caf50' if obj.fecha_fin else '#ff9800'
        
        return format_html(
            '<span style="font-weight: bold; color: {};">⏰ {}</span>',
            color, texto
        )
    
    @admin.display(description='💧 Cambio Humedad')
    def humedad_cambio_display(self, obj):
        if obj.humedad_final:
            cambio = obj.humedad_final - obj.humedad_inicial
            if cambio > 0:
                color = '#4caf50'
                icono = '📈'
                signo = '+'
            else:
                color = '#f44336'
                icono = '📉'
                signo = ''
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {}{}%</span><br>'
                '<small style="color: #9e9e9e;">{}% → {}%</small>',
                color, icono, signo, round(cambio, 1),
                round(obj.humedad_inicial, 1), round(obj.humedad_final, 1)
            )
        else:
            return format_html(
                '<span style="color: #9e9e9e;">En curso...</span><br>'
                '<small>Inicial: {}%</small>',
                round(obj.humedad_inicial, 1)
            )
    
    @admin.display(description='🔧 Tipo')
    def tipo_display(self, obj):
        if obj.automatico:
            return format_html(
                '<span style="color: #2196f3;">🤖 Automático</span>'
            )
        else:
            return format_html(
                '<span style="color: #ff9800;">👤 Manual</span>'
            )
    
    @admin.display(description='📊 Comparación Humedad')
    def humedad_comparacion(self, obj):
        """Gráfico visual de comparación de humedad"""
        if not obj.humedad_final:
            return format_html('<p style="color: #9e9e9e;">Riego en curso, sin datos finales aún</p>')
        
        inicial = obj.humedad_inicial
        final = obj.humedad_final
        cambio = final - inicial
        
        color_inicial = '#f44336' if inicial < 40 else '#4caf50'
        color_final = '#f44336' if final < 40 else '#4caf50'
        
        return format_html(
            '<div style="display: flex; gap: 20px; align-items: center;">'
            '<div style="text-align: center;">'
            '<div style="font-size: 12px; color: #9e9e9e;">Inicial</div>'
            '<div style="width: 80px; background: #e0e0e0; border-radius: 10px; overflow: hidden; margin: 8px 0;">'
            '<div style="width: {}%; background: {}; padding: 8px; color: white; '
            'text-align: center; font-weight: bold;">{}%</div>'
            '</div>'
            '</div>'
            '<div style="font-size: 24px; color: {};">{}</div>'
            '<div style="text-align: center;">'
            '<div style="font-size: 12px; color: #9e9e9e;">Final</div>'
            '<div style="width: 80px; background: #e0e0e0; border-radius: 10px; overflow: hidden; margin: 8px 0;">'
            '<div style="width: {}%; background: {}; padding: 8px; color: white; '
            'text-align: center; font-weight: bold;">{}%</div>'
            '</div>'
            '</div>'
            '<div style="text-align: center;">'
            '<div style="font-size: 12px; color: #9e9e9e;">Cambio</div>'
            '<div style="font-size: 18px; font-weight: bold; color: {};">{}{:.1f}%</div>'
            '</div>'
            '</div>',
            min(100, inicial), color_inicial, round(inicial, 1),
            '#4caf50' if cambio > 0 else '#f44336',
            '→' if abs(cambio) < 1 else ('↗️' if cambio > 0 else '↘️'),
            min(100, final), color_final, round(final, 1),
            '#4caf50' if cambio > 0 else '#f44336',
            '+' if cambio > 0 else '', cambio
        )
    
    def has_add_permission(self, request):
        """No permitir crear eventos manualmente desde admin"""
        return False


# ============================================================================
# NUEVOS MODELOS - MULTI ESP32
# ============================================================================

@admin.register(ESP32Device)
class ESP32DeviceAdmin(admin.ModelAdmin):
    """
    Panel de administración para dispositivos ESP32
    """
    list_display = (
        'id',
        'name',
        'device_type_display',
        'connection_status',
        'esp32_ip_display',
        'mac_address_display',
        'last_seen_display',
        'active_display'
    )
    
    list_filter = ('device_type', 'active', 'last_seen')
    search_fields = ('name', 'mac_address', 'esp32_ip')
    ordering = ('name',)
    
    readonly_fields = ('last_seen', 'created_at', 'esta_conectado')
    
    fieldsets = (
        ('📱 Información del Dispositivo', {
            'fields': ('name', 'device_type', 'active')
        }),
        ('🌐 Conexión', {
            'fields': ('esp32_ip', 'mac_address', 'last_seen', 'esta_conectado')
        }),
        ('📅 Fechas', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='📱 Tipo de Dispositivo')
    def device_type_display(self, obj):
        colors = {
            'soil': '#8bc34a',
            'environment': '#2196f3'
        }
        icons = {
            'soil': '🌱',
            'environment': '🌡️'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-weight: bold;">{} {}</span>',
            colors.get(obj.device_type, '#9e9e9e'),
            icons.get(obj.device_type, '📱'),
            obj.get_device_type_display()
        )
    
    @admin.display(description='🔌 Estado Conexión')
    def connection_status(self, obj):
        if obj.esta_conectado:
            return format_html(
                '<span style="background: #4caf50; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-weight: bold;">🟢 CONECTADO</span>'
            )
        else:
            return format_html(
                '<span style="background: #9e9e9e; color: white; padding: 4px 12px; '
                'border-radius: 12px;">⚫ DESCONECTADO</span>'
            )
    
    @admin.display(description='🌐 IP')
    def esp32_ip_display(self, obj):
        if obj.esp32_ip:
            return format_html(
                '<span style="font-family: monospace; background: #e3f2fd; '
                'padding: 4px 8px; border-radius: 4px; color: #1976d2;">{}</span>',
                obj.esp32_ip
            )
        return format_html('<span style="color: #9e9e9e;">-</span>')
    
    @admin.display(description='🔑 MAC Address')
    def mac_address_display(self, obj):
        if obj.mac_address:
            return format_html(
                '<span style="font-family: monospace; font-size: 11px;">{}</span>',
                obj.mac_address
            )
        return format_html('<span style="color: #9e9e9e;">-</span>')
    
    @admin.display(description='🕐 Última Conexión')
    def last_seen_display(self, obj):
        if obj.last_seen:
            from django.utils.timesince import timesince
            tiempo = timesince(obj.last_seen)
            color = '#4caf50' if obj.esta_conectado else '#9e9e9e'
            return format_html(
                '<span style="color: {};">hace {}</span>',
                color, tiempo
            )
        return format_html('<span style="color: #9e9e9e;">Nunca</span>')
    
    @admin.display(description='✅ Activo', boolean=True)
    def active_display(self, obj):
        return obj.active


@admin.register(SoilMoisture)
class SoilMoistureAdmin(admin.ModelAdmin):
    """
    Panel de administración para mediciones de humedad del suelo
    """
    list_display = (
        'id',
        'device_name_display',
        'humedad_suelo_display',
        'humedad_gauge_mini',
        'created_at_display'
    )
    
    list_filter = ('device', 'created_at')
    search_fields = ('device__name',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    readonly_fields = ('created_at', 'humedad_gauge_full')
    
    fieldsets = (
        ('📊 Medición', {
            'fields': ('device', 'humedad_suelo', 'humedad_gauge_full')
        }),
        ('📅 Fecha', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='📱 Dispositivo')
    def device_name_display(self, obj):
        return format_html(
            '<span style="background: #8bc34a; color: white; padding: 2px 8px; '
            'border-radius: 8px;">🌱 {}</span>',
            obj.device.name
        )
    
    @admin.display(description='💧 Humedad Suelo', ordering='humedad_suelo')
    def humedad_suelo_display(self, obj):
        hum = obj.humedad_suelo
        if hum < 30:
            color = '#f44336'
            icon = '🔴'
        elif hum < 50:
            color = '#ff9800'
            icon = '🟠'
        elif hum < 70:
            color = '#4caf50'
            icon = '🟢'
        else:
            color = '#2196f3'
            icon = '🔵'
        
        return format_html(
            '{} <span style="color: {}; font-weight: bold; font-size: 16px;">{}%</span>',
            icon, color, round(hum, 1)
        )
    
    @admin.display(description='📊')
    def humedad_gauge_mini(self, obj):
        hum = obj.humedad_suelo
        color = '#f44336' if hum < 30 else '#ff9800' if hum < 50 else '#4caf50' if hum < 70 else '#2196f3'
        return format_html(
            '<div style="width: 60px; background: #e0e0e0; border-radius: 4px; overflow: hidden; height: 8px;">'
            '<div style="width: {}%; background: {}; height: 8px;"></div>'
            '</div>',
            min(100, hum), color
        )
    
    @admin.display(description='💧 Indicador Humedad Suelo')
    def humedad_gauge_full(self, obj):
        hum = obj.humedad_suelo
        color = '#f44336' if hum < 30 else '#ff9800' if hum < 50 else '#4caf50' if hum < 70 else '#2196f3'
        return format_html(
            '<div style="width: 300px; background: #e0e0e0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; padding: 12px; color: white; '
            'text-align: center; font-weight: bold; border-radius: 10px; font-size: 18px;">{}%</div>'
            '</div>',
            min(100, hum), color, round(hum, 1)
        )
    
    @admin.display(description='📅 Fecha', ordering='created_at')
    def created_at_display(self, obj):
        return obj.created_at.strftime("%d/%m/%Y %H:%M:%S")


@admin.register(LuminosityData)
class LuminosityDataAdmin(admin.ModelAdmin):
    """Panel de administración para datos de luminosidad"""
    list_display = (
        'id',
        'device_name_display',
        'luminosidad_display',
        'created_at_display'
    )
    
    list_filter = ('device', 'created_at')
    search_fields = ('device__name',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('☀️ Datos de Luminosidad', {
            'fields': (
                'luminosidad',
            )
        }),
        ('📱 Dispositivo', {
            'fields': ('device',)
        }),
        ('📅 Fecha', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='📱 Dispositivo')
    def device_name_display(self, obj):
        return format_html(
            '<span style="background: #2196f3; color: white; padding: 2px 8px; '
            'border-radius: 8px;">☀️ {}</span>',
            obj.device.name
        )
    
    @admin.display(description='☀️ Luminosidad', ordering='luminosidad')
    def luminosidad_display(self, obj):
        lux = obj.luminosidad
        if lux < 100:
            icon = '🌙'
            color = '#37474f'
        elif lux < 1000:
            icon = '☁️'
            color = '#78909c'
        elif lux < 10000:
            icon = '⛅'
            color = '#ffa726'
        else:
            icon = '☀️'
            color = '#ffb300'
        
        return format_html(
            '{} <span style="color: {}; font-weight: bold;">{:,.0f} lux</span>',
            icon, color, lux
        )
    
    @admin.display(description='📅 Fecha', ordering='created_at')
    def created_at_display(self, obj):
        return obj.created_at.strftime("%d/%m/%Y %H:%M:%S")


@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    """
    Panel de administración para datos meteorológicos AEMET
    """
    list_display = (
        'id',
        'estacion_display',
        'temperatura_display',
        'humedad_display',
        'precipitacion_display',
        'viento_display',
        'fecha_observacion_display'
    )
    
    list_filter = ('estacion_id', 'fecha_observacion')
    search_fields = ('estacion_id', 'estacion_nombre')
    ordering = ('-fecha_observacion',)
    date_hierarchy = 'fecha_observacion'
    list_per_page = 50
    
    readonly_fields = ('created_at', 'temp_gauge', 'precip_gauge')
    
    fieldsets = (
        ('📍 Estación', {
            'fields': ('estacion_id', 'estacion_nombre')
        }),
        ('🌡️ Temperaturas', {
            'fields': (
                ('temperatura', 'temp_gauge'),
                ('temperatura_maxima', 'temperatura_minima')
            )
        }),
        ('🌧️ Condiciones', {
            'fields': (
                ('humedad', 'precipitacion', 'precip_gauge'),
                ('velocidad_viento', 'direccion_viento'),
                'presion'
            )
        }),
        ('📅 Fechas', {
            'fields': ('fecha_observacion', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='📍 Estación')
    def estacion_display(self, obj):
        return format_html(
            '<div><strong>{}</strong></div><small style="color: #9e9e9e;">{}</small>',
            obj.estacion_id,
            obj.estacion_nombre or 'Sin nombre'
        )
    
    @admin.display(description='🌡️ Temperatura', ordering='temperatura')
    def temperatura_display(self, obj):
        if obj.temperatura is None:
            return '-'
        temp = obj.temperatura
        color = '#2196f3' if temp < 15 else '#4caf50' if temp < 25 else '#ff9800' if temp < 30 else '#f44336'
        
        extras = []
        if obj.temperatura_maxima:
            extras.append(f'↑{obj.temperatura_maxima:.1f}°')
        if obj.temperatura_minima:
            extras.append(f'↓{obj.temperatura_minima:.1f}°')
        
        extra_text = ' ' + ' '.join(extras) if extras else ''
        
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 16px;">{}°C</span>'
            '<small style="color: #9e9e9e;">{}</small>',
            color, round(temp, 1), extra_text
        )

    @admin.display(description='💧 Humedad', ordering='humedad')
    def humedad_display(self, obj):
        if obj.humedad is None:
            return '-'
        hum = obj.humedad
        color = '#f44336' if hum < 30 else '#ff9800' if hum < 50 else '#4caf50' if hum < 70 else '#2196f3'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, round(hum, 1)
        )
    
    @admin.display(description='🌧️ Precipitación', ordering='precipitacion')
    def precipitacion_display(self, obj):
        if obj.precipitacion is None or obj.precipitacion == 0:
            return format_html('<span style="color: #9e9e9e;">0 mm</span>')
        
        precip = obj.precipitacion
        if precip < 1:
            icon = '🌦️'
            color = '#81c784'
        elif precip < 10:
            icon = '🌧️'
            color = '#42a5f5'
        else:
            icon = '⛈️'
            color = '#1976d2'
        
        return format_html(
            '{} <span style="color: {}; font-weight: bold;">{:.1f} mm</span>',
            icon, color, precip
        )
    
    @admin.display(description='💨 Viento', ordering='velocidad_viento')
    def viento_display(self, obj):
        if obj.velocidad_viento is None:
            return '-'
        
        vel = obj.velocidad_viento
        dir_text = f' {obj.direccion_viento}' if obj.direccion_viento else ''
        
        if vel < 10:
            icon = '🍃'
            color = '#81c784'
        elif vel < 30:
            icon = '💨'
            color = '#42a5f5'
        else:
            icon = '🌪️'
            color = '#f44336'
        
        return format_html(
            '{} <span style="color: {}; font-weight: bold;">{:.1f} km/h{}</span>',
            icon, color, vel, dir_text
        )
    
    @admin.display(description='📅 Fecha Observación', ordering='fecha_observacion')
    def fecha_observacion_display(self, obj):
        return obj.fecha_observacion.strftime("%d/%m/%Y %H:%M:%S")
    
    @admin.display(description='🌡️ Indicador')
    def temp_gauge(self, obj):
        if obj.temperatura is None:
            return '-'
        temp = obj.temperatura
        percentage = min(100, max(0, (temp + 10) * 2))
        color = '#2196f3' if temp < 15 else '#4caf50' if temp < 25 else '#ff9800' if temp < 30 else '#f44336'
        return format_html(
            '<div style="width: 200px; background: #e0e0e0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; padding: 8px; color: white; '
            'text-align: center; font-weight: bold;">{}°C</div>'
            '</div>',
            percentage, color, round(temp, 1)
        )
    
    @admin.display(description='🌧️ Indicador')
    def precip_gauge(self, obj):
        if obj.precipitacion is None:
            return '-'
        precip = obj.precipitacion
        percentage = min(100, precip * 5)  # Escala: 20mm = 100%
        color = '#81c784' if precip < 1 else '#42a5f5' if precip < 10 else '#1976d2'
        return format_html(
            '<div style="width: 200px; background: #e0e0e0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; padding: 8px; color: white; '
            'text-align: center; font-weight: bold;">{:.1f} mm</div>'
            '</div>',
            percentage, color, precip
        )


@admin.register(WeatherForecastSnapshot)
class WeatherForecastSnapshotAdmin(admin.ModelAdmin):
    list_display = ('municipio_id', 'municipio_nombre', 'dias', 'elaborado', 'updated_at')
    list_filter = ('dias', 'municipio_id')
    search_fields = ('municipio_id', 'municipio_nombre')
    ordering = ('-updated_at',)
    readonly_fields = ('created_at', 'updated_at', 'payload')

    fieldsets = (
        ('📍 Municipio', {
            'fields': ('municipio_id', 'municipio_nombre', 'dias')
        }),
        ('🕒 Metadatos', {
            'fields': ('elaborado', 'created_at', 'updated_at')
        }),
        ('🗂️ Payload', {
            'fields': ('payload',),
            'classes': ('collapse',),
        }),
    )


@admin.register(TrainingDataset)
class TrainingDatasetAdmin(admin.ModelAdmin):
    """
    Panel de administración para datasets de entrenamiento
    """
    list_display = (
        'id',
        'necesita_riego_display',
        'humedad_suelo_display',
        'temperatura_display',
        'fuente_display',
        'split_display',
        'created_at_display'
    )
    
    list_filter = ('necesita_riego', 'fuente', 'split', 'usado_entrenamiento', 'created_at')
    search_fields = ('id',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 100
    
    readonly_fields = ('created_at', 'evapotranspiracion_estimada')
    
    fieldsets = (
        ('🎯 Target (Label)', {
            'fields': ('necesita_riego', 'cantidad_agua_segundos')
        }),
        ('📊 Features - Sensores', {
            'fields': (
                'humedad_suelo',
                'temperatura',
                'humedad_ambiente',
                'luminosidad',
                'nivel_agua'
            )
        }),
        ('🌦️ Features - AEMET', {
            'fields': (
                'temperatura_exterior',
                'precipitacion_24h',
                'velocidad_viento',
                'presion_atmosferica'
            )
        }),
        ('🕐 Features - Temporales', {
            'fields': ('hora_dia', 'dia_semana', 'mes', 'estacion'),
            'classes': ('collapse',)
        }),
        ('🔬 Features - Derivadas', {
            'fields': (
                'deficit_hidrico',
                'humedad_promedio_24h',
                'temperatura_promedio_24h',
                'num_riegos_24h',
                'evapotranspiracion_estimada'
            ),
            'classes': ('collapse',)
        }),
        ('✅ Resultado Real', {
            'fields': (
                'se_rego',
                'humedad_post_riego',
                'efectividad_riego'
            ),
            'classes': ('collapse',)
        }),
        ('ℹ️ Metadata', {
            'fields': ('fuente', 'usado_entrenamiento', 'split', 'created_at')
        }),
    )
    
    @admin.display(description='🎯 Target', ordering='necesita_riego')
    def necesita_riego_display(self, obj):
        if obj.necesita_riego:
            return format_html(
                '<span style="background: #4caf50; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-weight: bold;">💧 REGAR</span>'
            )
        else:
            return format_html(
                '<span style="background: #9e9e9e; color: white; padding: 4px 12px; '
                'border-radius: 12px;">⏸️ NO REGAR</span>'
            )
    
    @admin.display(description='💧 Humedad Suelo', ordering='humedad_suelo')
    def humedad_suelo_display(self, obj):
        return f'{obj.humedad_suelo:.1f}%'
    
    @admin.display(description='🌡️ Temp', ordering='temperatura')
    def temperatura_display(self, obj):
        return f'{obj.temperatura:.1f}°C'
    
    @admin.display(description='📦 Fuente', ordering='fuente')
    def fuente_display(self, obj):
        colors = {'real': '#2196f3', 'sintetico': '#ff9800'}
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            colors.get(obj.fuente, '#9e9e9e'),
            obj.get_fuente_display()
        )
    
    @admin.display(description='🔀 Split', ordering='split')
    def split_display(self, obj):
        if not obj.split:
            return '-'
        colors = {'train': '#4caf50', 'val': '#ff9800', 'test': '#2196f3'}
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 8px; font-size: 11px;">{}</span>',
            colors.get(obj.split, '#9e9e9e'),
            obj.get_split_display()
        )
    
    @admin.display(description='📅 Fecha')
    def created_at_display(self, obj):
        return obj.created_at.strftime("%d/%m/%Y")


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    """
    Panel de administración para versiones de modelos de IA
    """
    list_display = (
        'version',
        'activo_display',
        'accuracy_display',
        'mae_display',
        'r2_display',
        'num_muestras_display',
        'fecha_entrenamiento_display'
    )
    
    list_filter = ('activo', 'fecha_entrenamiento')
    search_fields = ('version', 'notas')
    ordering = ('-fecha_entrenamiento',)
    
    readonly_fields = ('fecha_entrenamiento',)
    
    fieldsets = (
        ('📦 Versión', {
            'fields': ('version', 'activo', 'entrenado_por')
        }),
        ('📊 Métricas', {
            'fields': (
                'accuracy_clasificacion',
                'mae_regresion',
                'r2_regresion'
            )
        }),
        ('⚙️ Hiperparámetros', {
            'fields': ('n_estimators', 'max_depth', 'hyperparameters'),
            'classes': ('collapse',)
        }),
        ('📁 Archivos', {
            'fields': (
                'modelo_clasificacion_path',
                'modelo_regresion_path',
                'scaler_path'
            ),
            'classes': ('collapse',)
        }),
        ('📈 Dataset', {
            'fields': (
                'num_muestras_train',
                'num_muestras_test',
                'fecha_inicio_datos',
                'fecha_fin_datos'
            )
        }),
        ('📝 Notas', {
            'fields': ('notas',)
        }),
        ('📅 Fecha', {
            'fields': ('fecha_entrenamiento',)
        }),
    )
    
    @admin.display(description='✅ Activo', boolean=True)
    def activo_display(self, obj):
        return obj.activo
    
    @admin.display(description='🎯 Accuracy', ordering='accuracy_clasificacion')
    def accuracy_display(self, obj):
        acc = obj.accuracy_clasificacion * 100
        color = '#4caf50' if acc >= 80 else '#ff9800' if acc >= 60 else '#f44336'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, acc
        )
    
    @admin.display(description='📏 MAE', ordering='mae_regresion')
    def mae_display(self, obj):
        mae = obj.mae_regresion
        color = '#4caf50' if mae < 5 else '#ff9800' if mae < 10 else '#f44336'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f} ml</span>',
            color, mae
        )
    
    @admin.display(description='📊 R²', ordering='r2_regresion')
    def r2_display(self, obj):
        r2 = obj.r2_regresion * 100
        color = '#4caf50' if r2 >= 80 else '#ff9800' if r2 >= 60 else '#f44336'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, r2
        )
    
    @admin.display(description='📈 Muestras')
    def num_muestras_display(self, obj):
        total = obj.num_muestras_train + obj.num_muestras_test
        return format_html(
            '<strong>{:,}</strong><br>'
            '<small style="color: #9e9e9e;">Train: {:,} | Test: {:,}</small>',
            total, obj.num_muestras_train, obj.num_muestras_test
        )
    
    @admin.display(description='📅 Fecha Entrenamiento', ordering='fecha_entrenamiento')
    def fecha_entrenamiento_display(self, obj):
        return obj.fecha_entrenamiento.strftime("%d/%m/%Y %H:%M")


@admin.register(WaterTankReading)
class WaterTankReadingAdmin(admin.ModelAdmin):
    """
    Histórico de lecturas del tanque de agua
    """
    list_display = (
        'created_at_display',
        'distancia_display',
        'porcentaje_display',
        'litros_display',
    )
    
    list_filter = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ('distancia', 'porcentaje', 'litros', 'created_at')
    
    list_per_page = 50
    
    def has_add_permission(self, request):
        return False  # Las lecturas se crean automáticamente
    
    @admin.display(description='📅 Fecha/Hora')
    def created_at_display(self, obj):
        return obj.created_at.strftime("%d/%m/%Y %H:%M:%S")
    @admin.display(description='📏 Distancia')
    def distancia_display(self, obj):
        return format_html(
            '<span style="color: #607d8b;">{:.1f} cm</span>',
            obj.distancia
        )
    
    @admin.display(description='💧 Porcentaje')
    def porcentaje_display(self, obj):
        pct = obj.porcentaje
        if pct >= 70:
            color = '#4caf50'  # Verde
        elif pct >= 30:
            color = '#ff9800'  # Naranja
        else:
            color = '#f44336'  # Rojo
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, pct
        )
    
    @admin.display(description='🪣 Litros')
    def litros_display(self, obj):
        return format_html(
            '<span style="color: #2196f3; font-weight: bold;">{:.2f} L</span>',
            obj.litros
        )


@admin.register(IrrigationNotification)
class IrrigationNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'notification_type', 'relay', 'tipo_planta', 'event', 'device', 'created_at')
    list_filter = ('notification_type', 'relay', 'tipo_planta', 'created_at')
    search_fields = ('reason', 'tipo_planta', 'device__name', 'device__mac_address')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(SensorCalibrationSettings)
class SensorCalibrationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'distancia_minima_tanque',
        'distancia_maxima_tanque',
        'capacidad_litros_tanque',
        'ev1_litros_1s',
        'ev2_litros_1s',
        'updated_at',
    )
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('Tanque', {
            'fields': ('distancia_minima_tanque', 'distancia_maxima_tanque', 'capacidad_litros_tanque')
        }),
        ('Electroválvula 1', {
            'fields': ('ev1_litros_1s', 'ev1_litros_5s', 'ev1_litros_10s')
        }),
        ('Electroválvula 2', {
            'fields': ('ev2_litros_1s', 'ev2_litros_5s', 'ev2_litros_10s')
        }),
        ('Humedad Suelo Sensor 1', {
            'fields': ('suelo1_valor_seco', 'suelo1_valor_mojado')
        }),
        ('Humedad Suelo Sensor 2', {
            'fields': ('suelo2_valor_seco', 'suelo2_valor_mojado')
        }),
        ('Auditoría', {
            'fields': ('updated_at',)
        }),
    )

    def has_add_permission(self, request):
        return not SensorCalibrationSettings.objects.exists()
