"""
Servicio de decision de riego usando Google Gemini
"""
import json
import time
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_irrigation_decision(tipo_planta: str) -> dict:
    try:
        from google import genai
        from google.genai import types
        from .models import SoilMoisture, Measurement, IrrigationEvent, GeminiAuditLog, WaterTankReading

        MODELO = getattr(settings, 'GEMINI_MODEL', 'models/gemini-3.1-flash-lite')
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        SYSTEM_PROMPT = """Eres el controlador de riego de un sistema de agricultura de interior.
Responde SIEMPRE con este JSON exacto, sin texto adicional:
{"regar": true, "duracion_segundos": 15, "confianza": "alta", "razon": "explicacion breve en espanol"}
Reglas:
- Para fresas: humedad optima 65-75%. Regar si < 60%
- Para lechuga: humedad optima 60-80%. Regar si < 55%
- No regar si hubo riego hace menos de 60 minutos
- No regar entre las 00:00 y las 07:00 (madrugada, plantas en reposo)
- No regar entre las 13:00 y las 16:00 (calor extremo, estres radicular)
- Preferir riego temprano (07:00-10:00) o tarde (18:00-21:00)
- duracion_segundos entre 5 y 60 segun el deficit
- duracion_segundos = 0 si regar es false"""

        ultima_medicion = Measurement.objects.order_by("-created_at").first()
        ultimas_suelo = list(SoilMoisture.objects.filter(tipo_planta=tipo_planta).order_by("-created_at")[:10])

        if not ultimas_suelo:
            GeminiAuditLog.objects.create(
                tipo="irrigation", tipo_planta=tipo_planta, modelo=MODELO,
                prompt="Sin datos de sensor", exito=False,
                error_mensaje="Sin datos de sensor de suelo"
            )
            return {"regar": False, "duracion_segundos": 0, "confianza": "baja", "razon": "Sin datos de sensor de suelo"}

        # Obtener calibración para normalizar raw ADC a porcentaje
        from measurements.models import SensorCalibrationSettings
        cal = SensorCalibrationSettings.objects.order_by('-updated_at').first()
        def _humedad(raw, tipo):
            if cal is None or raw <= 100:
                return raw  # ya es porcentaje
            if tipo == 'fresa':
                seco, mojado = cal.suelo2_valor_seco, cal.suelo2_valor_mojado
            else:
                seco, mojado = cal.suelo1_valor_seco, cal.suelo1_valor_mojado
            if seco == mojado:
                return 0.0
            pct = (seco - raw) / (seco - mojado) * 100
            return round(max(0.0, min(100.0, pct)), 1)

        humedad_media = round(sum(_humedad(m.humedad_suelo, tipo_planta) for m in ultimas_suelo) / len(ultimas_suelo), 1)
        
        # Calcular tendencia de humedad
        lecturas = [_humedad(m.humedad_suelo, tipo_planta) for m in ultimas_suelo]
        tendencia = lecturas[0] - lecturas[-1]  # positivo = subiendo, negativo = bajando
        tendencia_str = f"+{tendencia:.1f}%" if tendencia > 0 else f"{tendencia:.1f}%"
        
        ultimo_riego = IrrigationEvent.objects.filter(
            tipo_planta=tipo_planta, fecha_fin__isnull=False
        ).order_by("-fecha_fin").first()
        
        # Calcular tiempo desde el último riego
        if ultimo_riego:
            minutos = int((timezone.now() - ultimo_riego.fecha_fin).total_seconds() / 60)
            ultimo_str = f"{ultimo_riego.fecha_fin.strftime('%H:%M')} (hace {minutos} min)"
        else:
            ultimo_str = "Sin riegos previos"
        
        ahora = timezone.now()
        
        # Calcular estación del año
        mes = ahora.month
        estacion = "primavera" if 3 <= mes <= 5 else "verano" if 6 <= mes <= 8 else "otoño" if 9 <= mes <= 11 else "invierno"
        
        # Obtener nivel del tanque
        tanque = WaterTankReading.objects.order_by('-created_at').first()
        nivel_tanque = f"{tanque.porcentaje:.0f}%" if tanque else "desconocido"
        
        prompt = (
            f"Planta: {tipo_planta}\n"
            f'CONTEXTO: {estacion.upper()}, {ahora.strftime("%A").upper()} {ahora.strftime("%d/%m/%Y")}\n'
            f'HORA ACTUAL: {ahora.strftime("%H:%M")}\n'
            f"SENSORES:\n"
            f"- Humedad suelo: {humedad_media}% (tendencia: {tendencia_str} en últimas 10 lecturas)\n"
            f"- Temperatura ambiente: {ultima_medicion.temperatura if ultima_medicion else 'N/A'}C\n"
            f"- Humedad ambiente: {ultima_medicion.humedad if ultima_medicion else 'N/A'}%\n"
            f"- Nivel tanque agua: {nivel_tanque}\n"
            f"HISTORIAL:\n"
            f"- Ultimo riego: {ultimo_str}\n"
            f"- Duracion ultimo riego: {ultimo_riego.duracion_real_segundos if ultimo_riego else 0}s\n"
            f"Se debe regar ahora?"
        )

        log = GeminiAuditLog(tipo="irrigation", tipo_planta=tipo_planta, modelo=MODELO, prompt=prompt)
        t0 = time.time()
        try:
            response = client.models.generate_content(
                model=MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            latencia_ms = int((time.time() - t0) * 1000)
            raw = response.text
            result = json.loads(raw)
            log.respuesta_raw = raw
            log.respuesta_json = result
            log.decision_regar = result.get("regar", False)
            log.decision_duracion_s = result.get("duracion_segundos", 0)
            log.decision_razon = result.get("razon", "")
            log.latencia_ms = latencia_ms
            log.exito = True
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                log.tokens_entrada = getattr(response.usage_metadata, "prompt_token_count", None)
                log.tokens_salida = getattr(response.usage_metadata, "candidates_token_count", None) or                                     getattr(response.usage_metadata, "total_token_count", None)
            log.save()
            logger.info("[Gemini] %s: regar=%s | %dms", tipo_planta, result.get("regar"), latencia_ms)
            return result
        except Exception as e:
            log.exito = False
            log.error_mensaje = str(e)
            log.latencia_ms = int((time.time() - t0) * 1000)
            log.save()
            raise

    except Exception as e:
        logger.error("[Gemini] Error en decision de riego: %s", e)
        return {"regar": False, "duracion_segundos": 0, "confianza": "baja", "razon": f"Error IA: {str(e)}"}
