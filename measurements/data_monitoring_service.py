"""
Servicio de monitoreo de datos de sensores y notificaciones
- Nivel de tanque de agua < 10%
- Falta de datos durante más de 2 horas (por tipo de sensor)
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from .firebase_service import firebase_service
from .models import (
    WaterTankReading,
    LuminosityData,
    Measurement,
    SoilMoisture,
    NotificationHistory,
)

logger = logging.getLogger(__name__)

# Configuración de monitoreo
TWO_HOURS_AGO = 2 * 60  # 120 minutos en segundos


class DataMonitoringService:
    """Servicio centralizado para monitoreo de datos de sensores"""
    
    @staticmethod
    def check_water_tank_level():
        """
        Verifica si el nivel del tanque es < 10%
        Se debe llamar cada vez que se recibe un dato de WaterTankReading
        """
        try:
            # Obtener última lectura del tanque
            latest_reading = WaterTankReading.objects.order_by('-created_at').first()
            
            if not latest_reading:
                logger.debug("No water tank readings available")
                return
            
            # Verificar si el nivel es menor al 10%
            if latest_reading.porcentaje < 10:
                logger.warning(f"Water tank level low: {latest_reading.porcentaje}%")
                
                # Enviar notificación a todos los usuarios
                firebase_service.send_to_all_users(
                    title="⚠️ Tanque de Agua Bajo",
                    body=f"El nivel del tanque es {latest_reading.porcentaje}% (< 10%)",
                    data={
                        "tipo": "alerta_tanque",
                        "nivel_porcentaje": str(latest_reading.porcentaje),
                        "timestamp": latest_reading.created_at.isoformat(),
                    },
                    icon="🚨"
                )
                
                logger.info("Water tank low level notification sent")
        
        except Exception as e:
            logger.error(f"Error checking water tank level: {e}")
    
    @staticmethod
    def check_missing_data():
        """
        Verifica si falta datos de cualquier sensor durante más de 2 horas
        Se debe ejecutar periódicamente (cada 15-30 minutos)
        
        Verifica:
        - Datos de luminosidad
        - Datos del nivel del tanque
        - Datos de temperatura y humedad ambiente (Measurement)
        - Datos de humedad de suelo (ambas plantas: lechuga y fresa)
        """
        
        two_hours_ago = timezone.now() - timedelta(minutes=TWO_HOURS_AGO)
        missing_data_types = []
        last_timestamps = {}
        
        try:
            # 1. Verificar datos de luminosidad
            latest_luminosity = LuminosityData.objects.order_by('-created_at').first()
            if latest_luminosity:
                if latest_luminosity.created_at < two_hours_ago:
                    missing_data_types.append("📷 Luminosidad")
                    last_timestamps["luminosity"] = latest_luminosity.created_at
            else:
                missing_data_types.append("📷 Luminosidad (sin datos)")
                last_timestamps["luminosity"] = None
            
            # 2. Verificar datos del tanque de agua
            latest_tank = WaterTankReading.objects.order_by('-created_at').first()
            if latest_tank:
                if latest_tank.created_at < two_hours_ago:
                    missing_data_types.append("💧 Nivel del Tanque")
                    last_timestamps["tank"] = latest_tank.created_at
            else:
                missing_data_types.append("💧 Nivel del Tanque (sin datos)")
                last_timestamps["tank"] = None
            
            # 3. Verificar datos de temperatura y humedad ambiente (Measurement)
            latest_measurement = Measurement.objects.order_by('-created_at').first()
            if latest_measurement:
                if latest_measurement.created_at < two_hours_ago:
                    missing_data_types.append("🌡️ Temperatura/Humedad Ambiente")
                    last_timestamps["environment"] = latest_measurement.created_at
            else:
                missing_data_types.append("🌡️ Temperatura/Humedad Ambiente (sin datos)")
                last_timestamps["environment"] = None
            
            # 4. Verificar datos de humedad de suelo - LECHUGA
            latest_soil_lechuga = SoilMoisture.objects.filter(
                tipo_planta='lechuga'
            ).order_by('-created_at').first()
            if latest_soil_lechuga:
                if latest_soil_lechuga.created_at < two_hours_ago:
                    missing_data_types.append("🥬 Humedad Suelo - Lechuga")
                    last_timestamps["soil_lechuga"] = latest_soil_lechuga.created_at
            else:
                missing_data_types.append("🥬 Humedad Suelo - Lechuga (sin datos)")
                last_timestamps["soil_lechuga"] = None
            
            # 5. Verificar datos de humedad de suelo - FRESA
            latest_soil_fresa = SoilMoisture.objects.filter(
                tipo_planta='fresa'
            ).order_by('-created_at').first()
            if latest_soil_fresa:
                if latest_soil_fresa.created_at < two_hours_ago:
                    missing_data_types.append("🍓 Humedad Suelo - Fresa")
                    last_timestamps["soil_fresa"] = latest_soil_fresa.created_at
            else:
                missing_data_types.append("🍓 Humedad Suelo - Fresa (sin datos)")
                last_timestamps["soil_fresa"] = None
            
            # Si hay datos faltando, enviar notificación
            if missing_data_types:
                logger.warning(f"Missing data detected: {missing_data_types}")
                
                # Construir mensaje detallado
                body_parts = []
                timestamps_str = []
                
                for data_type in missing_data_types:
                    body_parts.append(f"• {data_type}")
                
                # Agregar información de últimas recepción
                for key, timestamp in last_timestamps.items():
                    if timestamp:
                        minutes_ago = int((timezone.now() - timestamp).total_seconds() / 60)
                        timestamps_str.append(f"{key}: hace {minutes_ago} minutos")
                    else:
                        timestamps_str.append(f"{key}: nunca recibido")
                
                body = "Sensores sin datos hace más de 2 horas:\n" + "\n".join(body_parts)
                
                data_dict = {
                    "tipo": "alerta_datos_faltantes",
                    "sensores_faltantes": ",".join(missing_data_types),
                    "timestamp": timezone.now().isoformat(),
                }
                
                # Agregar información de last timestamps
                for key, timestamp in last_timestamps.items():
                    if timestamp:
                        data_dict[f"last_{key}"] = timestamp.isoformat()
                
                # Enviar notificación a todos los usuarios
                firebase_service.send_to_all_users(
                    title="⚠️ Datos de Sensores Faltando",
                    body=body,
                    data=data_dict,
                    icon="📡"
                )
                
                logger.info("Missing sensor data notification sent")
                
                return {
                    'missing': missing_data_types,
                    'last_timestamps': last_timestamps
                }
            
            else:
                logger.debug("All sensor data is current")
                return {'missing': [], 'last_timestamps': last_timestamps}
        
        except Exception as e:
            logger.error(f"Error checking missing data: {e}")
            return {'missing': [], 'error': str(e)}


# Singleton instance
monitoring_service = DataMonitoringService()
