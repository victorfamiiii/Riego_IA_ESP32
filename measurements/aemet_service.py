"""
Servicio de integración con la API de AEMET (Agencia Estatal de Meteorología)

Documentación oficial: https://opendata.aemet.es/centrodedescargas/inicio
Para obtener API key: https://opendata.aemet.es/centrodedescargas/obtencionAPIKey

Autor: Sistema de Riego Inteligente
"""

import requests
import logging
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from .models import WeatherData, WeatherForecastSnapshot

logger = logging.getLogger(__name__)


class AEMETService:
    """
    Servicio para obtener datos meteorológicos de AEMET
    """
    
    BASE_URL = "https://opendata.aemet.es/opendata/api"
    
    def __init__(self, api_key=None):
        """
        Inicializar servicio con API key
        
        Args:
            api_key: API key de AEMET. Si es None, usa settings.AEMET_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'AEMET_API_KEY', None)
        
        if not self.api_key:
            logger.warning("⚠️ AEMET_API_KEY no configurada en settings.py")
        
        self.session = requests.Session()
        self.session.headers.update({
            'api_key': self.api_key,
            'Accept': 'application/json'
        })
    
    def _hacer_peticion(self, endpoint, params=None):
        """
        Hacer petición a la API de AEMET
        
        La API de AEMET funciona en 2 pasos:
        1. Solicitar datos -> devuelve URL temporal
        2. Acceder a URL temporal -> devuelve datos
        
        Args:
            endpoint: Endpoint de la API
            params: Parámetros de la petición
            
        Returns:
            dict con los datos o None si hay error
        """
        try:
            # Paso 1: Obtener URL temporal
            url = f"{self.BASE_URL}{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                if response.status_code == 429:
                    # Evitar golpear AEMET durante el minuto bloqueado
                    cache.set('aemet:rate_limited', True, timeout=65)
                logger.error(f"❌ Error AEMET paso 1: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            if 'datos' not in data:
                logger.error(f"❌ Respuesta AEMET sin URL de datos: {data}")
                return None
            
            # Paso 2: Obtener datos desde URL temporal
            datos_url = data['datos']
            response_datos = requests.get(datos_url, timeout=10)
            
            if response_datos.status_code != 200:
                logger.error(f"❌ Error AEMET paso 2: {response_datos.status_code}")
                return None
            
            resultado = response_datos.json()
            logger.debug(f"📊 AEMET response type: {type(resultado).__name__}, is_list: {isinstance(resultado, list)}")
            
            return resultado
            
        except requests.exceptions.Timeout:
            logger.error("⏱️ Timeout en petición a AEMET")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de conexión con AEMET: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado en petición AEMET: {str(e)}")
            return None
    
    def obtener_estaciones_cercanas(self, lat=None, lon=None):
        """
        Obtener lista de estaciones meteorológicas
        
        Si no se proporcionan coordenadas, devuelve todas las estaciones
        
        Args:
            lat: Latitud (opcional)
            lon: Longitud (opcional)
            
        Returns:
            list: Lista de estaciones
        """
        endpoint = "/valores/climatologicos/inventarioestaciones/todasestaciones"
        datos = self._hacer_peticion(endpoint)
        
        if not datos:
            return []
        
        # Si hay coordenadas, filtrar las más cercanas
        if lat and lon:
            # TODO: Implementar filtrado por distancia
            pass
        
        return datos
    
    def obtener_datos_observacion(self, estacion_id):
        """
        Obtener datos de observación de una estación específica
        (Datos más recientes - última hora)
        
        Args:
            estacion_id: ID de la estación (ej: "3195" para Madrid-Retiro)
            
        Returns:
            dict: Datos meteorológicos actuales
        """
        endpoint = f"/observacion/convencional/datos/estacion/{estacion_id}"
        datos = self._hacer_peticion(endpoint)
        
        if not datos or not isinstance(datos, list) or len(datos) == 0:
            logger.warning(f"⚠️ No hay datos de observación para estación {estacion_id}")
            return None
        
        # Tomar el dato más reciente
        return datos[-1]
    
    def obtener_prediccion_diaria(self, municipio_id):
        """
        Obtener predicción meteorológica para un municipio
        
        Args:
            municipio_id: ID del municipio (ej: "28079" para Madrid)
            
        Returns:
            dict: Predicción meteorológica
        """
        endpoint = f"/prediccion/especifica/municipio/diaria/{municipio_id}"
        datos = self._hacer_peticion(endpoint)
        
        if not datos:
            logger.warning(f"⚠️ No hay predicción diaria para municipio {municipio_id}")
            return None
        
        # Extraer primer elemento si es lista
        if isinstance(datos, list):
            if not datos:
                logger.warning(f"⚠️ Predicción diaria lista vacía para municipio {municipio_id}")
                return None
            resultado = datos[0]
        else:
            resultado = datos
        
        # Validar que sea un dict
        if not isinstance(resultado, dict):
            logger.error(f"❌ Predicción diaria no es dict para {municipio_id}, tipo: {type(resultado)}")
            return None
            
        return resultado

    def obtener_prediccion_horaria(self, municipio_id):
        """
        Intentar obtener previsión horaria para un municipio.

        Si AEMET no devolviera datos o el endpoint no estuviera disponible,
        el método retorna None y el consumidor puede usar la previsión diaria.
        """
        endpoint = f"/prediccion/especifica/municipio/horaria/{municipio_id}"
        datos = self._hacer_peticion(endpoint)

        if not datos:
            logger.info(f"ℹ️ No hay predicción horaria para municipio {municipio_id}")
            return None

        # Extraer primer elemento si es lista
        if isinstance(datos, list):
            if not datos:
                logger.info(f"ℹ️ Predicción horaria lista vacía para municipio {municipio_id}")
                return None
            resultado = datos[0]
        else:
            resultado = datos
        
        # Validar que sea un dict
        if not isinstance(resultado, dict):
            logger.warning(f"⚠️ Predicción horaria no es dict para {municipio_id}, tipo: {type(resultado)}")
            return None
            
        return resultado

    @staticmethod
    def _as_dict(item):
        if isinstance(item, dict):
            return item
        if isinstance(item, list) and item and isinstance(item[0], dict):
            return item[0]
        return {}

    @staticmethod
    def _as_list(item):
        if isinstance(item, list):
            return item
        if isinstance(item, dict):
            return [item]
        return []

    @classmethod
    def _pick(cls, item, *keys):
        data = cls._as_dict(item)
        for key in keys:
            value = data.get(key)
            if value not in (None, ''):
                return value
        return None

    @staticmethod
    def _texto_descripcion(item, fallback=''):
        data = AEMETService._as_dict(item)
        return data.get('descripcion') or data.get('value') or data.get('texto') or fallback

    @staticmethod
    def _formatear_periodo(periodo, indice):
        if periodo is None:
            return f"{indice * 3:02d}:00"

        periodo_str = str(periodo).strip()

        # AEMET a veces codifica rangos como 814 o 1420 (8-14, 14-20)
        if periodo_str.isdigit() and len(periodo_str) in (3, 4):
            if len(periodo_str) == 3:
                inicio = int(periodo_str[0])
                fin = int(periodo_str[1:])
            else:
                inicio = int(periodo_str[:2])
                fin = int(periodo_str[2:])
            # Incluye tramos nocturnos que cruzan medianoche (ej: 2002 -> 20:00)
            if 0 <= inicio <= 24 and 0 <= fin <= 24:
                return f"{inicio:02d}:00"

        if '-' in periodo_str:
            inicio = periodo_str.split('-')[0].strip()
            if inicio.isdigit():
                return f"{int(inicio):02d}:00"

        if periodo_str.isdigit():
            return f"{int(periodo_str):02d}:00"

        return periodo_str

    @staticmethod
    def _parse_hour_label(hora):
        if hora is None:
            return None
        text = str(hora).strip()
        if not text:
            return None
        if ':' in text:
            head = text.split(':', 1)[0].strip()
            if head.isdigit():
                value = int(head)
                return value if 0 <= value <= 23 else None
        if text.isdigit():
            value = int(text)
            return value if 0 <= value <= 23 else None
        return None

    @staticmethod
    def _score_block(bloque):
        if not isinstance(bloque, dict):
            return -1
        score = 0
        if bloque.get('cielo') not in (None, '', 'Sin datos'):
            score += 1
        if bloque.get('temperatura') is not None:
            score += 1
        if bloque.get('humedad') is not None:
            score += 1
        if bloque.get('viento') is not None:
            score += 1
        if bloque.get('prob_lluvia') is not None:
            score += 1
        return score

    def _normalizar_serie_24h(self, bloques, temp_fallback=None):
        """
        Devuelve una serie horaria completa de 24 elementos (00:00..23:00),
        ordenada y sin duplicados por hora.
        """
        by_hour = {}
        for bloque in self._as_list(bloques):
            if not isinstance(bloque, dict):
                continue
            hour = self._parse_hour_label(bloque.get('hora'))
            if hour is None:
                continue

            current = by_hour.get(hour)
            if current is None or self._score_block(bloque) > self._score_block(current):
                candidate = dict(bloque)
                candidate['hora'] = f"{hour:02d}:00"
                by_hour[hour] = candidate

        normalized = []
        for hour in range(24):
            existing = by_hour.get(hour)
            if existing is None:
                existing = {
                    'hora': f"{hour:02d}:00",
                    'periodo': f"{hour:02d}",
                    'prob_lluvia': None,
                    'cielo': 'Sin datos',
                    'temperatura': temp_fallback,
                    'humedad': None,
                    'viento': None,
                }
            else:
                if existing.get('temperatura') is None and temp_fallback is not None:
                    existing['temperatura'] = temp_fallback
            normalized.append(existing)

        return normalized

    def _normalizar_bloques_dia(self, dia):
        """
        Convertir la información de un día AEMET en una lista de bloques
        visuales para el frontend.
        """
        if not isinstance(dia, dict):
            return []

        probabilidades = self._as_list(dia.get('probPrecipitacion'))
        cielos = self._as_list(dia.get('estadoCielo'))
        temperatura_data = self._as_dict(dia.get('temperatura'))
        humedad_data = self._as_dict(dia.get('humedadRelativa'))
        viento_data = self._as_dict(dia.get('viento'))

        temp_max = self._parse_float(temperatura_data.get('maxima'))
        temp_min = self._parse_float(temperatura_data.get('minima'))
        temp_fallback = None
        if temp_max is not None and temp_min is not None:
            temp_fallback = round((temp_max + temp_min) / 2.0, 1)
        elif temp_max is not None:
            temp_fallback = temp_max
        elif temp_min is not None:
            temp_fallback = temp_min

        temperatura = self._as_list(temperatura_data.get('dato'))
        humedad = self._as_list(humedad_data.get('dato'))
        viento = self._as_list(viento_data.get('dato'))

        total_bloques = max(
            len(probabilidades),
            len(cielos),
            len(temperatura),
            len(humedad),
            len(viento),
            4,
        )

        bloques = []
        for indice in range(total_bloques):
            prob_item = self._as_dict(probabilidades[indice] if indice < len(probabilidades) else {})
            cielo_item = self._as_dict(cielos[indice] if indice < len(cielos) else {})
            temp_item = self._as_dict(temperatura[indice] if indice < len(temperatura) else {})
            hum_item = self._as_dict(humedad[indice] if indice < len(humedad) else {})
            viento_item = self._as_dict(viento[indice] if indice < len(viento) else {})

            periodo = (
                self._pick(prob_item, 'periodo')
                or self._pick(cielo_item, 'periodo')
                or self._pick(temp_item, 'hora', 'periodo')
            )

            temp_val = self._parse_float(self._pick(temp_item, 'value'))
            if temp_val is None:
                temp_val = temp_fallback

            bloques.append({
                'hora': self._formatear_periodo(periodo, indice),
                'periodo': str(periodo) if periodo is not None else None,
                'prob_lluvia': self._parse_float(self._pick(prob_item, 'value', 'probabilidad')),
                'cielo': self._texto_descripcion(cielo_item, 'Sin datos'),
                'temperatura': temp_val,
                'humedad': self._parse_float(self._pick(hum_item, 'value')),
                'viento': self._parse_float(self._pick(viento_item, 'velocidad', 'value')),
            })

        return bloques

    def obtener_prevision_normalizada(self, municipio_id, municipio_nombre=None, dias=5):
        """
        Obtener previsión meteorológica normalizada para frontend.

        Devuelve una estructura uniforme con:
        - bloque horario del día actual
        - previsión diaria de varios días
        """
        cache_key = f'aemet:forecast:{municipio_id}:{dias}'
        cached_forecast = cache.get(cache_key)
        if cached_forecast:
            return cached_forecast

        # Si AEMET está temporalmente limitado, devolvemos fallback sin reintentar
        if cache.get('aemet:rate_limited'):
            fallback = cache.get(f'{cache_key}:fallback')
            if fallback:
                return fallback
            return None

        # Priorizar diaria para garantizar 5 días
        raw_diaria = self.obtener_prediccion_diaria(municipio_id)
        raw_horaria = None
        # Mantener bloques horarios cuando AEMET no esté rate-limited
        if not cache.get('aemet:rate_limited'):
            raw_horaria = self.obtener_prediccion_horaria(municipio_id)

        base_raw = raw_diaria or raw_horaria
        if not base_raw:
            return cache.get(f'{cache_key}:fallback')

        # Asegurar que base_raw es un dict
        if isinstance(base_raw, list):
            if not base_raw:
                logger.error(f"❌ raw es lista vacía para municipio {municipio_id}")
                return None
            base_raw = base_raw[0]
        
        if not isinstance(base_raw, dict):
            logger.error(f"❌ raw no es dict ni lista para municipio {municipio_id}, tipo: {type(base_raw)}")
            return None

        prediccion = base_raw.get('prediccion') if isinstance(base_raw, dict) else None
        dias_raw = []
        if isinstance(prediccion, dict):
            dias_raw = prediccion.get('dia') or []

        if not isinstance(dias_raw, list) or not dias_raw:
            logger.warning(f"⚠️ La previsión AEMET para {municipio_id} no tiene días disponibles")
            return None

        dias_normalizados = []
        for dia in dias_raw[:dias]:
            if not isinstance(dia, dict):
                continue

            fecha = dia.get('fecha')
            bloques = self._normalizar_bloques_dia(dia)

            temp_data = self._as_dict(dia.get('temperatura'))
            hum_data = self._as_dict(dia.get('humedadRelativa'))

            temperaturas = []
            for item in self._as_list(temp_data.get('dato')):
                value = self._parse_float(self._pick(item, 'value'))
                if value is not None:
                    temperaturas.append(value)

            humedades = []
            for item in self._as_list(hum_data.get('dato')):
                value = self._parse_float(self._pick(item, 'value'))
                if value is not None:
                    humedades.append(value)

            probs = []
            for item in self._as_list(dia.get('probPrecipitacion')):
                value = self._parse_float(self._pick(item, 'value', 'probabilidad'))
                if value is not None:
                    probs.append(value)

            temp_max = self._parse_float(temp_data.get('maxima'))
            temp_min = self._parse_float(temp_data.get('minima'))
            if temp_max is None and temperaturas:
                temp_max = max(temperaturas)
            if temp_min is None and temperaturas:
                temp_min = min(temperaturas)

            humedad_max = max(humedades) if humedades else None
            humedad_min = min(humedades) if humedades else None

            estado_cielo = self._as_list(dia.get('estadoCielo'))
            cielo_resumen = 'Sin datos'
            if isinstance(estado_cielo, list) and estado_cielo:
                cielo_resumen = self._texto_descripcion(estado_cielo[0], 'Sin datos')
            elif isinstance(estado_cielo, dict):
                cielo_resumen = self._texto_descripcion(estado_cielo, 'Sin datos')

            try:
                fecha_dt = datetime.fromisoformat(str(fecha)) if fecha else None
            except ValueError:
                fecha_dt = None

            dias_normalizados.append({
                'fecha': fecha,
                'dia_semana': fecha_dt.strftime('%A') if fecha_dt else '',
                'temperatura_maxima': temp_max,
                'temperatura_minima': temp_min,
                'humedad_maxima': humedad_max,
                'humedad_minima': humedad_min,
                'probabilidad_lluvia_maxima': max(probs) if probs else None,
                'cielo_resumen': cielo_resumen,
                'bloques': bloques,
            })

        if not dias_normalizados:
            return cache.get(f'{cache_key}:fallback')

        bloques_hoy = dias_normalizados[0].get('bloques', [])

        # Si hay horaria, intentamos usar sus bloques para hoy (más granular)
        if isinstance(raw_horaria, list):
            raw_horaria = raw_horaria[0] if raw_horaria else None
        if isinstance(raw_horaria, dict):
            pred_h = raw_horaria.get('prediccion')
            dias_h = pred_h.get('dia') if isinstance(pred_h, dict) else None
            if isinstance(dias_h, list) and dias_h and isinstance(dias_h[0], dict):
                bloques_h = self._normalizar_bloques_dia(dias_h[0])
                if bloques_h:
                    bloques_hoy = bloques_h

        # Completar temperatura faltante en bloques de hoy con fallback diario
        if bloques_hoy:
            dia_hoy = dias_normalizados[0] if dias_normalizados else {}
            t_max = self._parse_float(dia_hoy.get('temperatura_maxima')) if isinstance(dia_hoy, dict) else None
            t_min = self._parse_float(dia_hoy.get('temperatura_minima')) if isinstance(dia_hoy, dict) else None

            temp_fallback_hoy = None
            if t_max is not None and t_min is not None:
                temp_fallback_hoy = round((t_max + t_min) / 2.0, 1)
            elif t_max is not None:
                temp_fallback_hoy = t_max
            elif t_min is not None:
                temp_fallback_hoy = t_min

            if temp_fallback_hoy is not None:
                for bloque in bloques_hoy:
                    if isinstance(bloque, dict) and self._parse_float(bloque.get('temperatura')) is None:
                        bloque['temperatura'] = temp_fallback_hoy

            # Entregar siempre una serie 24h completa y ordenada para el frontend.
            bloques_hoy = self._normalizar_serie_24h(bloques_hoy, temp_fallback=temp_fallback_hoy)

        # Asegurar llamadas defensivas a .get() en base_raw
        forecast = {
            'municipio_id': municipio_id,
            'municipio_nombre': municipio_nombre or (base_raw.get('nombre') if isinstance(base_raw, dict) else None) or (base_raw.get('origen') if isinstance(base_raw, dict) else None) or '',
            'elaborado': base_raw.get('elaborado') if isinstance(base_raw, dict) else None,
            'version': base_raw.get('version') if isinstance(base_raw, dict) else None,
            'dias': dias_normalizados,
            'bloques_hoy': bloques_hoy,
        }

        self.guardar_prevision_normalizada(
            municipio_id=municipio_id,
            municipio_nombre=forecast.get('municipio_nombre') or '',
            dias=dias,
            forecast=forecast,
        )

        cache.set(cache_key, forecast, timeout=1800)
        cache.set(f'{cache_key}:fallback', forecast, timeout=21600)
        return forecast

    def guardar_prevision_normalizada(self, municipio_id, municipio_nombre, dias, forecast):
        """Guardar o actualizar el snapshot de previsión normalizada en base de datos."""
        try:
            elaborado_raw = (forecast or {}).get('elaborado')
            elaborado_dt = None
            if elaborado_raw:
                try:
                    elaborado_dt = datetime.fromisoformat(str(elaborado_raw).replace('Z', '+00:00'))
                    if timezone.is_naive(elaborado_dt):
                        elaborado_dt = timezone.make_aware(elaborado_dt)
                except ValueError:
                    elaborado_dt = None

            WeatherForecastSnapshot.objects.update_or_create(
                municipio_id=str(municipio_id),
                dias=int(dias),
                defaults={
                    'municipio_nombre': municipio_nombre or '',
                    'elaborado': elaborado_dt,
                    'payload': forecast or {},
                },
            )
        except Exception as exc:
            logger.error(f"❌ Error guardando forecast normalizado en BD: {exc}")
    
    def obtener_radiacion_solar(self):
        """
        Obtener datos de radiación solar de la red especial de AEMET.
        Devuelve radiación global, directa y difusa de todas las estaciones.
        
        Returns:
            list: Lista de datos de radiación o None
        """
        endpoint = "/red/especial/radiacion"
        datos = self._hacer_peticion(endpoint)
        
        if not datos:
            logger.warning("⚠️ No hay datos de radiación solar disponibles")
            return None
        
        return datos
    
    def obtener_radiacion_estacion(self, estacion_id):
        """
        Obtener radiación solar para una estación específica.
        Busca entre los datos de la red de radiación.
        
        Args:
            estacion_id: ID de la estación
            
        Returns:
            float: Radiación solar global en W/m² o None
        """
        datos = self.obtener_radiacion_solar()
        
        if not datos:
            return None
        
        for registro in datos:
            if registro.get('indicativo') == estacion_id:
                return self._parse_float(registro.get('global'))
        
        logger.info(f"ℹ️ Estación {estacion_id} no tiene datos de radiación en red especial")
        return None
    
    def guardar_datos_observacion(self, estacion_id, estacion_nombre=None):
        """
        Obtener datos de AEMET y guardar en la base de datos
        
        Args:
            estacion_id: ID de la estación
            estacion_nombre: Nombre de la estación (opcional)
            
        Returns:
            WeatherData object o None
        """
        datos = self.obtener_datos_observacion(estacion_id)
        
        if not datos:
            return None
        
        try:
            # Parsear fecha de observación
            fecha_str = datos.get('fint')  # Formato: "2025-11-25T12:00:00"
            if fecha_str:
                # Convertir string a datetime
                fecha_obs = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                # Asegurar timezone aware
                if timezone.is_naive(fecha_obs):
                    fecha_obs = timezone.make_aware(fecha_obs)
            else:
                fecha_obs = timezone.now()
            
            # Crear o actualizar registro
            # NOTA: AEMET usa 'tamax'/'tamin' (NO 'tmax'/'tmin') para temp horaria max/min
            weather_data, created = WeatherData.objects.update_or_create(
                estacion_id=estacion_id,
                fecha_observacion=fecha_obs,
                defaults={
                    'estacion_nombre': estacion_nombre or datos.get('ubi', ''),
                    'temperatura': self._parse_float(datos.get('ta')),
                    'temperatura_maxima': self._parse_float(datos.get('tamax')),
                    'temperatura_minima': self._parse_float(datos.get('tamin')),
                    'humedad': self._parse_float(datos.get('hr')),
                    'precipitacion': self._parse_float(datos.get('prec', 0.0)),
                    'velocidad_viento': self._parse_float(datos.get('vv')),
                    'direccion_viento': datos.get('dv', ''),
                    'presion': self._parse_float(datos.get('pres')),
                    'insolacion': self._parse_float(datos.get('inso')),
                }
            )
            
            if created:
                logger.info(f"✅ Datos AEMET guardados: {estacion_id} - {fecha_obs}")
            else:
                logger.info(f"🔄 Datos AEMET actualizados: {estacion_id} - {fecha_obs}")
            
            return weather_data
            
        except Exception as e:
            logger.error(f"❌ Error al guardar datos AEMET: {str(e)}")
            return None
    
    def obtener_precipitacion_24h(self, estacion_id):
        """
        Calcular precipitación acumulada en las últimas 24 horas
        desde la base de datos local
        
        Args:
            estacion_id: ID de la estación
            
        Returns:
            float: Precipitación en mm (últimas 24h)
        """
        hace_24h = timezone.now() - timedelta(hours=24)
        
        precipitaciones = WeatherData.objects.filter(
            estacion_id=estacion_id,
            fecha_observacion__gte=hace_24h
        ).values_list('precipitacion', flat=True)
        
        total = sum([p for p in precipitaciones if p is not None])
        return round(total, 2)
    
    def obtener_datos_recientes(self, estacion_id, horas=24):
        """
        Obtener datos meteorológicos recientes desde la BD local
        
        Args:
            estacion_id: ID de la estación
            horas: Número de horas hacia atrás
            
        Returns:
            QuerySet de WeatherData
        """
        hace_n_horas = timezone.now() - timedelta(hours=horas)
        
        return WeatherData.objects.filter(
            estacion_id=estacion_id,
            fecha_observacion__gte=hace_n_horas
        ).order_by('-fecha_observacion')
    
    @staticmethod
    def _parse_float(value):
        """
        Convertir valor a float, manejando None y strings
        
        Args:
            value: Valor a convertir
            
        Returns:
            float o None
        """
        if value is None or value == '':
            return None
        
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def sincronizar_datos_periodicos(self, estacion_id, estacion_nombre=None):
        """
        Método para ejecutar periódicamente (cada hora)
        Actualiza los datos meteorológicos
        
        Args:
            estacion_id: ID de la estación
            estacion_nombre: Nombre de la estación
            
        Returns:
            bool: True si tuvo éxito
        """
        logger.info(f"🔄 Sincronizando datos AEMET para estación {estacion_id}...")
        
        weather_data = self.guardar_datos_observacion(estacion_id, estacion_nombre)
        
        if weather_data:
            logger.info(f"✅ Sincronización exitosa: {estacion_id}")
            return True
        else:
            logger.error(f"❌ Falló sincronización: {estacion_id}")
            return False


# ============================================================================
# ESTACIONES ÚTILES PARA ESPAÑA
# ============================================================================

ESTACIONES_PRINCIPALES = {
    # Castilla y León
    '2614': 'Zamora',
    
    # Comunidad de Madrid
    '3195': 'Madrid-Retiro',
    '3196': 'Madrid-Barajas',
    '3194': 'Madrid-Cuatro Vientos',
    
    # Andalucía
    '5783': 'Sevilla-Aeropuerto',
    '6155A': 'Granada-Aeropuerto',
    '6172X': 'Málaga-Aeropuerto',
    
    # Cataluña
    '0076': 'Barcelona-Aeropuerto',
    '0149X': 'Tarragona',
    
    # Comunidad Valenciana
    '8416': 'Valencia-Aeropuerto',
    '8025': 'Alicante-Aeropuerto',
    
    # Galicia
    '1387': 'A Coruña-Aeropuerto',
    '1484': 'Santiago de Compostela',
    
    # País Vasco
    '1082': 'Bilbao-Aeropuerto',
    '1024E': 'San Sebastián-Igueldo',
}


def obtener_estacion_por_nombre(nombre_ciudad):
    """
    Buscar estación por nombre de ciudad
    
    Args:
        nombre_ciudad: Nombre de la ciudad
        
    Returns:
        tuple: (estacion_id, nombre_estacion) o (None, None)
    """
    nombre_lower = nombre_ciudad.lower()
    
    for estacion_id, nombre_estacion in ESTACIONES_PRINCIPALES.items():
        if nombre_lower in nombre_estacion.lower():
            return estacion_id, nombre_estacion
    
    return None, None
