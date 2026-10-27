from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from .models import Measurement, IrrigationEvent, IrrigationConfig, LuminosityData, WaterTankReading, SensorCalibrationSettings
from .serializers import (
    MeasurementSerializer,
    MeasurementCreateSerializer,
    StatsSerializer
)
from .irrigation_control import IrrigationController
from .data_monitoring_service import monitoring_service


# Variable global para almacenar la última IP del ESP32
esp32_last_ip = None
esp32_last_seen = None


class MeasurementViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar mediciones
    
    Endpoints automáticos:
    - GET    /api/measurements/          Lista todas las mediciones
    - POST   /api/measurements/          Crear nueva medición
    - GET    /api/measurements/{id}/     Detalle de una medición
    - PUT    /api/measurements/{id}/     Actualizar medición
    - DELETE /api/measurements/{id}/     Eliminar medición
    
    Endpoints personalizados:
    - GET    /api/measurements/stats/    Estadísticas generales
    - GET    /api/measurements/history/  Historial limitado
    - POST   /api/measurements/data/     Endpoint compatible con ESP32 (Flask)
    """
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    
    def get_serializer_class(self):
        """Usar serializador diferente para crear"""
        if self.action == 'create' or self.action == 'data':
            return MeasurementCreateSerializer
        return MeasurementSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear nueva medición y actualizar ESP32 IP"""
        global esp32_last_ip, esp32_last_seen
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Guardar IP del ESP32
        esp32_ip = serializer.validated_data.get('esp32_ip') or request.META.get('REMOTE_ADDR')
        if esp32_ip:
            esp32_last_ip = esp32_ip
            esp32_last_seen = timezone.now()
        
        self.perform_create(serializer)
        
        # MONITOREO DE DATOS
        # Verificar nivel del tanque de agua
        try:
            monitoring_service.check_water_tank_level()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Water tank monitoring failed: {e}")
        
        # CONTROL DE RIEGO AUTOMÁTICO
        # Después de guardar la medición, verificar si se necesita riego (por planta)
        controller = IrrigationController()
        estado_riego = controller.verificar_y_gestionar_riego()
        
        # Para compatibilidad con ESP32 firmaware, devolver comando de LA PRIMERA PLANTA ACTIVA
        # Prioridad: lechuga > fresa
        comando_esp32 = 'OFF'
        razon_esp32 = 'Sin riego requerido'
        tiempo_restante_esp32 = 0
        evento_id_esp32 = None
        
        for planta in ['lechuga', 'fresa']:
            if estado_riego['plantas'][planta]['comando'] == 'ON':
                comando_esp32 = 'ON'
                razon_esp32 = estado_riego['plantas'][planta]['razon']
                tiempo_restante_esp32 = estado_riego['plantas'][planta]['tiempo_restante']
                evento_id_esp32 = estado_riego['plantas'][planta]['evento_id']
                break  # Prioridad: lechuga primero
        
        headers = self.get_success_headers(serializer.data)
        
        # Retornar datos de la medición + comando de riego
        response_data = {
            'measurement': serializer.data,
            'irrigation': {
                'command': comando_esp32,  # 'ON' o 'OFF'
                'active': estado_riego['riego_activo'],
                'reason': razon_esp32,
                'time_remaining': tiempo_restante_esp32,
                'event_id': evento_id_esp32,
                'all_plants': estado_riego['plantas']  # Información completa por planta
            }
        }
        
        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Obtener estadísticas generales
        GET /api/measurements/stats/
        """
        global esp32_last_ip, esp32_last_seen
        
        total = Measurement.objects.count()
        
        if total == 0:
            return Response({
                'total_mediciones': 0,
                'temperatura_promedio': 0,
                'humedad_promedio': 0,
                'ultima_medicion': None,
                'esp32_conectado': False,
                'esp32_ip': None,
                'mediciones_24h': 0
            })
        
        # Última medición
        ultima = Measurement.objects.first()

        # Conteo de mediciones de las últimas 24 horas (se mantiene para compatibilidad)
        hace_24h = timezone.now() - timedelta(hours=24)
        mediciones_24h = Measurement.objects.filter(created_at__gte=hace_24h)

        # Promedios basados en las últimas 10 lecturas reales
        mediciones_recientes = list(Measurement.objects.order_by('-created_at')[:10])
        if mediciones_recientes:
            temp_prom = sum(m.temperatura for m in mediciones_recientes) / len(mediciones_recientes)
            hum_prom = sum(m.humedad for m in mediciones_recientes) / len(mediciones_recientes)
        else:
            temp_prom = ultima.temperatura
            hum_prom = ultima.humedad

        # Luminosidad basada en las últimas 10 lecturas
        lux_prom = None
        env_data_recientes = list(LuminosityData.objects.order_by('-created_at')[:10])
        if env_data_recientes:
            lux_promedio = sum(item.luminosidad for item in env_data_recientes) / len(env_data_recientes)
            lux_prom = round(lux_promedio, 1)
        else:
            # Si no hay datos recientes, usar el último disponible
            ultimo_env = LuminosityData.objects.first()
            if ultimo_env:
                lux_prom = round(ultimo_env.luminosidad, 1)
        
        # Verificar si ESP32 está conectado (última conexión < 60 segundos)
        esp32_conectado = False
        if esp32_last_seen:
            delta = (timezone.now() - esp32_last_seen).total_seconds()
            esp32_conectado = delta < 60
        
        data = {
            'total_mediciones': total,
            'temperatura_promedio': round(temp_prom, 1),
            'humedad_promedio': round(hum_prom, 1),
            'luminosidad_promedio': lux_prom,
            'ultima_medicion': {
                'temperatura': ultima.temperatura,
                'humedad': ultima.humedad,
                'fecha': ultima.created_at.strftime("%Y-%m-%d %H:%M:%S")
            },
            'esp32_conectado': esp32_conectado,
            'esp32_ip': esp32_last_ip,
            'mediciones_24h': mediciones_24h.count()
        }
        
        serializer = StatsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Obtener historial de mediciones con límite
        GET /api/measurements/history/?limit=20
        """
        limit = int(request.query_params.get('limit', 50))
        mediciones = Measurement.objects.all()[:limit]
        serializer = self.get_serializer(mediciones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def data(self, request):
        """
        Endpoint compatible con el código Flask anterior del ESP32
        POST /api/measurements/data/
        Body: {"temperatura": 22.5, "humedad": 65.3, "esp32_ip": "192.168.1.50"}
        """
        global esp32_last_ip, esp32_last_seen
        
        serializer = MeasurementCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            # Guardar IP del ESP32
            esp32_ip = serializer.validated_data.get('esp32_ip') or request.META.get('REMOTE_ADDR')
            if esp32_ip:
                esp32_last_ip = esp32_ip
                esp32_last_seen = timezone.now()
            
            serializer.save()
            
            return Response(
                {'status': 'ok'},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def health(self, request):
        """
        Health check endpoint
        GET /api/measurements/health/
        """
        return Response({
            'status': 'ok',
            'timestamp': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    @action(detail=False, methods=['get'])
    def irrigation_command(self, request):
        """
        Endpoint para que la ESP32 obtenga comandos de riego
        GET /api/measurements/irrigation_command/
        """
        controller = IrrigationController()
        estado = controller.verificar_y_gestionar_riego()

        comando = 'OFF'
        razon = 'Sin riego requerido'
        tiempo_restante = 0
        evento_id = None
        planta_activa = None
        relay = None

        for planta in ['lechuga', 'fresa']:
            if estado['plantas'][planta]['comando'] == 'ON':
                comando = 'ON'
                planta_activa = planta
                relay = 1 if planta == 'lechuga' else 2
                razon = estado['plantas'][planta]['razon']
                tiempo_restante = estado['plantas'][planta]['tiempo_restante']
                evento_id = estado['plantas'][planta]['evento_id']
                break

        response = {
            'command': comando,
            'reason': razon,
            'all_plants': estado['plantas']
        }

        if comando == 'ON':
            response['duration'] = tiempo_restante
            response['event_id'] = evento_id
            response['tipo_planta'] = planta_activa
            response['relay'] = relay

        return Response(response)
    
    @action(detail=False, methods=['get'])
    def irrigation_status(self, request):
        """
        Estado completo del sistema de riego
        GET /api/measurements/irrigation_status/
        """
        controller = IrrigationController()
        estado = controller.get_estado_actual()
        return Response(estado)
    
    @action(detail=False, methods=['post'])
    def irrigation_config(self, request):
        """
        Actualizar configuración de riego
        POST /api/measurements/irrigation_config/
        Body: {
            "tipo_planta": "lechuga",  # opcional: lechuga o fresa
            "umbral_humedad_minimo": 40,
            "tiempo_riego_segundos": 30,
            "max_riegos_dia": 6,
            "riego_automatico_activo": true
        }
        """
        try:
            tipo_planta = request.data.get('tipo_planta', 'lechuga')
            config = IrrigationConfig.get_config_by_plant(tipo_planta)
            
            if not config:
                config = IrrigationConfig.objects.create(
                    tipo_planta=tipo_planta,
                    activo=True
                )
            
            # Actualizar campos si vienen en el request
            if 'umbral_humedad_minimo' in request.data:
                config.umbral_humedad_minimo = request.data['umbral_humedad_minimo']

            if 'mediciones_para_media' in request.data:
                config.mediciones_para_media = request.data['mediciones_para_media']
            
            if 'tiempo_riego_segundos' in request.data:
                config.tiempo_riego_segundos = request.data['tiempo_riego_segundos']
            
            if 'max_riegos_dia' in request.data:
                config.max_riegos_dia = request.data['max_riegos_dia']
            
            if 'riego_automatico_activo' in request.data:
                config.riego_automatico_activo = request.data['riego_automatico_activo']
            
            if 'tiempo_minimo_entre_riegos' in request.data:
                config.tiempo_minimo_entre_riegos = request.data['tiempo_minimo_entre_riegos']
            
            config.save()
            
            return Response({
                'status': 'ok',
                'config': {
                    'mediciones_para_media': config.mediciones_para_media,
                    'umbral_humedad_minimo': config.umbral_humedad_minimo,
                    'tiempo_riego_segundos': config.tiempo_riego_segundos,
                    'max_riegos_dia': config.max_riegos_dia,
                    'tiempo_minimo_entre_riegos': config.tiempo_minimo_entre_riegos,
                    'riego_automatico_activo': config.riego_automatico_activo
                }
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def irrigation_history(self, request):
        """
        Historial de eventos de riego
        GET /api/measurements/irrigation_history/?limit=20
        """
        limit = int(request.query_params.get('limit', 20))
        eventos = IrrigationEvent.objects.all()[:limit]
        
        data = []
        for evento in eventos:
            data.append({
                'id': evento.id,
                'fecha_inicio': evento.fecha_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                'fecha_fin': evento.fecha_fin.strftime("%Y-%m-%d %H:%M:%S") if evento.fecha_fin else None,
                'duracion_planificada': evento.duracion_planificada_segundos,
                'duracion_real': evento.duracion_real_segundos,
                'humedad_inicial': evento.humedad_inicial,
                'humedad_final': evento.humedad_final,
                'temperatura_inicial': evento.temperatura_inicial,
                'temperatura_final': evento.temperatura_final,
                'razon': evento.razon,
                'automatico': evento.automatico,
                'activo': evento.esta_activo
            })
        
        return Response({
            'total': IrrigationEvent.objects.count(),
            'eventos': data
        })


# ============================================
# Endpoints del Depósito de Agua
# ============================================

@api_view(['GET'])
def water_tank_status(request):
    """
    Obtener estado actual del depósito de agua
    GET /api/water-tank/status/
    
    Respuesta:
    {
        "percentage": 75.5,
        "liters": 7.55,
        "capacity": 10,
        "distancia": 30.5,
        "distancia_minima": 5,
        "distancia_maxima": 100,
        "last_update": "2026-02-18T10:30:00Z"
    }
    """
    calibration = SensorCalibrationSettings.get_config()
    latest = WaterTankReading.objects.order_by('-created_at').first()

    percentage = 0
    liters = 0
    distancia = None
    last_update = None
    if latest:
        distancia = latest.distancia
        percentage, liters = calibration.calculate_tank_level(distancia)
        last_update = latest.created_at.isoformat()

    return Response({
        'percentage': percentage,
        'liters': liters,
        'capacity': calibration.capacidad_litros_tanque,
        'distancia': distancia,
        'distancia_minima': calibration.distancia_minima_tanque,
        'distancia_maxima': calibration.distancia_maxima_tanque,
        'last_update': last_update
    })


@api_view(['POST'])
def water_tank_update(request):
    """
    Actualizar nivel del depósito de agua (desde ESP32)
    La ESP32 solo envía la distancia medida por el sensor ultrasónico.
    El servidor calcula el porcentaje y litros usando la configuración guardada.
    
    POST /api/water-tank/update/
    Body: {
        "distancia": 30.5  # distancia en cm medida por el sensor ultrasónico
    }
    
    Respuesta:
    {
        "status": "ok",
        "distancia": 30.5,
        "percentage": 75.5,
        "liters": 7.55,
        "capacity": 10
    }
    """
    distancia = request.data.get('distancia')
    
    if distancia is None:
        return Response(
            {'error': 'Se requiere el campo distancia (en cm)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validar distancia
    try:
        distancia = float(distancia)
        if distancia < 0:
            distancia = 0
    except (ValueError, TypeError):
        return Response(
            {'error': 'La distancia debe ser un número'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Obtener configuración activa y calcular nivel
    calibration = SensorCalibrationSettings.get_config()
    porcentaje, litros = calibration.calculate_tank_level(distancia)

    # Guardar lectura en histórico
    WaterTankReading.objects.create(
        distancia=distancia,
        porcentaje=porcentaje,
        litros=litros,
    )
    
    # MONITOREO DE DATOS
    # Verificar nivel del tanque de agua
    try:
        monitoring_service.check_water_tank_level()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Water tank monitoring failed: {e}")
    
    return Response({
        'status': 'ok',
        'distancia': distancia,
        'percentage': porcentaje,
        'liters': litros,
        'capacity': calibration.capacidad_litros_tanque
    })


@api_view(['GET', 'POST'])
def water_tank_config(request):
    """
    Obtener o configurar parámetros del depósito de agua
    
    GET /api/water-tank/config/
    Obtiene la configuración actual
    
    POST /api/water-tank/config/
    Body: {
        "capacidad_litros": 10,      # Capacidad máxima del tanque en litros
        "distancia_minima": 5,       # Distancia en cm cuando está LLENO
        "distancia_maxima": 100      # Distancia en cm cuando está VACÍO
    }
    
    Nota: Todos los campos son opcionales, solo se actualizan los enviados.
    """
    config = SensorCalibrationSettings.get_config()
    latest = WaterTankReading.objects.order_by('-created_at').first()

    ultimo_porcentaje = None
    ultimos_litros = None
    ultima_distancia = None
    ultima_actualizacion = None
    if latest:
        ultima_distancia = latest.distancia
        ultimo_porcentaje, ultimos_litros = config.calculate_tank_level(ultima_distancia)
        ultima_actualizacion = latest.created_at.isoformat()
    
    if request.method == 'GET':
        return Response({
            'capacidad_litros': config.capacidad_litros_tanque,
            'distancia_minima': config.distancia_minima_tanque,
            'distancia_maxima': config.distancia_maxima_tanque,
            'ultimo_porcentaje': ultimo_porcentaje,
            'ultimos_litros': ultimos_litros,
            'ultima_distancia': ultima_distancia,
            'ultima_actualizacion': ultima_actualizacion,
        })
    
    # POST - Actualizar configuración
    updated_fields = []
    
    # Actualizar capacidad
    if 'capacidad_litros' in request.data:
        try:
            capacidad = float(request.data['capacidad_litros'])
            if capacidad <= 0:
                return Response(
                    {'error': 'La capacidad debe ser mayor que 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            config.capacidad_litros_tanque = capacidad
            updated_fields.append('capacidad_litros_tanque')
        except (ValueError, TypeError):
            return Response(
                {'error': 'La capacidad debe ser un número'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Actualizar distancia mínima (tanque lleno)
    if 'distancia_minima' in request.data:
        try:
            dist_min = float(request.data['distancia_minima'])
            if dist_min < 0:
                return Response(
                    {'error': 'La distancia mínima no puede ser negativa'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            config.distancia_minima_tanque = dist_min
            updated_fields.append('distancia_minima_tanque')
        except (ValueError, TypeError):
            return Response(
                {'error': 'La distancia mínima debe ser un número'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Actualizar distancia máxima (tanque vacío)
    if 'distancia_maxima' in request.data:
        try:
            dist_max = float(request.data['distancia_maxima'])
            if dist_max <= 0:
                return Response(
                    {'error': 'La distancia máxima debe ser mayor que 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            config.distancia_maxima_tanque = dist_max
            updated_fields.append('distancia_maxima_tanque')
        except (ValueError, TypeError):
            return Response(
                {'error': 'La distancia máxima debe ser un número'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Validar que distancia_maxima > distancia_minima
    if config.distancia_maxima_tanque <= config.distancia_minima_tanque:
        return Response(
            {'error': 'La distancia máxima debe ser mayor que la distancia mínima'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Guardar cambios
    if updated_fields:
        config.save(update_fields=updated_fields)
    
    return Response({
        'status': 'ok',
        'updated_fields': updated_fields,
        'capacidad_litros': config.capacidad_litros_tanque,
        'distancia_minima': config.distancia_minima_tanque,
        'distancia_maxima': config.distancia_maxima_tanque
    })


@api_view(['GET'])
def water_tank_history(request):
    """
    Obtener histórico de lecturas del nivel de agua
    GET /api/water-tank/history/
    
    Parámetros opcionales:
    - limit: número máximo de registros (default: 100)
    - hours: filtrar por las últimas X horas
    - days: filtrar por los últimos X días
    
    Ejemplos:
    GET /api/water-tank/history/?limit=50
    GET /api/water-tank/history/?hours=24
    GET /api/water-tank/history/?days=7
    
    Respuesta:
    {
        "count": 50,
        "readings": [
            {
                "timestamp": "2024-02-18T10:30:00Z",
                "distancia": 30.5,
                "porcentaje": 75.5,
                "litros": 7.55
            },
            ...
        ]
    }
    """
    from .models import WaterTankReading
    from django.utils import timezone
    from datetime import timedelta
    
    # Obtener parámetros
    limit = int(request.GET.get('limit', 100))
    hours = request.GET.get('hours')
    days = request.GET.get('days')
    
    # Filtrar lecturas
    readings = WaterTankReading.objects.all()
    
    if hours:
        try:
            hours = int(hours)
            since = timezone.now() - timedelta(hours=hours)
            readings = readings.filter(created_at__gte=since)
        except ValueError:
            pass
    elif days:
        try:
            days = int(days)
            since = timezone.now() - timedelta(days=days)
            readings = readings.filter(created_at__gte=since)
        except ValueError:
            pass
    
    # Limitar resultados
    readings = readings[:limit]
    
    # Formatear respuesta
    data = [
        {
            'timestamp': r.created_at.isoformat(),
            'distancia': r.distancia,
            'porcentaje': r.porcentaje,
            'litros': r.litros
        }
        for r in readings
    ]
    
    return Response({
        'count': len(data),
        'readings': data
    })
