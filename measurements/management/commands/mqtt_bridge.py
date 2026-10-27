# pyright: reportMissingImports=false

import json
import logging
import os
import time
import ssl
from datetime import timedelta

import paho.mqtt.client as mqtt
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from measurements.irrigation_control import IrrigationController
from measurements.models import (
    ESP32Device,
    IrrigationEvent,
    IrrigationNotification,
    LuminosityData,
    Measurement,
    SensorCalibrationSettings,
    SoilMoisture,
    WaterTankReading,
)

logger = logging.getLogger(__name__)

# Evita cortar riegos recién iniciados mientras la ESP32 aún sincroniza su estado.
IRRIGATION_STARTUP_GRACE_SECONDS = 12

def get_or_create_device(mac_address, device_type="soil", esp32_ip=None):
    """
    Obtiene o crea un dispositivo ESP32.
    El device_type se establece una sola vez al crear. No se modifica después.
    """
    suffix = mac_address[-5:] if mac_address else "unknown"
    name = f"ESP32-{device_type.upper()}-{suffix}"
    device, created = ESP32Device.objects.get_or_create(
        mac_address=mac_address,
        defaults={
            "name": name,
            "device_type": device_type,
        },
    )

    changed = []
    device.last_seen = timezone.now()
    changed.append("last_seen")
    if esp32_ip and device.esp32_ip != esp32_ip:
        device.esp32_ip = esp32_ip
        changed.append("esp32_ip")

    if changed:
        device.save(update_fields=changed)

    return device


class Command(BaseCommand):
    help = "MQTT bridge for ESP32 telemetry and irrigation commands"

    def _parse_payload_timestamp(self, payload):
        """Devuelve timestamp timezone-aware del payload o None si no es válido."""
        payload_timestamp = payload.get("timestamp")
        if not isinstance(payload_timestamp, str):
            return None

        parsed_ts = parse_datetime(payload_timestamp)
        if parsed_ts is None:
            return None
        if timezone.is_naive(parsed_ts):
            parsed_ts = timezone.make_aware(parsed_ts, timezone.get_current_timezone())
        return parsed_ts

    def _save_soil_reading_once(self, *, device, tipo_planta, humedad_raw, reading_time=None, source="unknown"):
        """
        Guarda una lectura de suelo de forma idempotente.
        Evita insertar duplicados del mismo valor/planta/dispositivo en una ventana corta.
        """
        safe_tipo_planta = (tipo_planta or "lechuga").strip().lower()
        raw_value = float(humedad_raw)
        target_time = reading_time or timezone.now()
        dedup_window = timedelta(seconds=12)

        duplicate = SoilMoisture.objects.filter(
            device=device,
            tipo_planta=safe_tipo_planta,
            humedad_suelo=raw_value,
            created_at__gte=target_time - dedup_window,
            created_at__lte=target_time + dedup_window,
        ).first()

        if duplicate:
            logger.info(
                "Soil reading deduplicated source=%s device=%s plant=%s raw=%s ts=%s existing_id=%s",
                source,
                device.id,
                safe_tipo_planta,
                raw_value,
                target_time.isoformat(),
                duplicate.id,
            )
            return duplicate, False

        reading = SoilMoisture.objects.create(
            device=device,
            tipo_planta=safe_tipo_planta,
            humedad_suelo=raw_value,
        )
        if reading_time is not None:
            SoilMoisture.objects.filter(id=reading.id).update(created_at=target_time)
        return reading, True

    def save_water_tank_reading_from_payload(self, payload):
        """
        Guarda lectura de tanque desde payload MQTT.
        Acepta:
        - distancia (cm) preferido
        - nivel_agua (%) legacy
        """
        calibration = SensorCalibrationSettings.get_config()

        # Campos compatibles para distancia en cm.
        raw_distancia = (
            payload.get("distancia")
            if payload.get("distancia") is not None
            else payload.get("nivel_deposito_cm")
        )
        if raw_distancia is not None:
            try:
                distancia = max(0.0, float(raw_distancia))
            except (TypeError, ValueError):
                logger.warning("Invalid tank distance value: %s", raw_distancia)
                return

            porcentaje, litros = calibration.calculate_tank_level(distancia)
            WaterTankReading.objects.create(
                distancia=distancia,
                porcentaje=porcentaje,
                litros=litros,
            )
            return

        # Compatibilidad con payload antiguo que manda nivel_agua como porcentaje.
        raw_nivel = payload.get("nivel_agua")
        if raw_nivel is None:
            return

        try:
            porcentaje = max(0.0, min(100.0, float(raw_nivel)))
        except (TypeError, ValueError):
            logger.warning("Invalid tank level value: %s", raw_nivel)
            return

        rango = calibration.distancia_maxima_tanque - calibration.distancia_minima_tanque
        if rango <= 0:
            distancia = calibration.distancia_maxima_tanque
        else:
            distancia = calibration.distancia_maxima_tanque - (porcentaje / 100.0) * rango

        litros = round((porcentaje / 100.0) * calibration.capacidad_litros_tanque, 2)
        WaterTankReading.objects.create(
            distancia=round(distancia, 2),
            porcentaje=round(porcentaje, 1),
            litros=litros,
        )

    def handle(self, *args, **options):
        host = os.getenv("MQTT_HOST", "mqtt")
        port = int(os.getenv("MQTT_PORT", "8883"))
        username = os.getenv("MQTT_USERNAME", "")
        password = os.getenv("MQTT_PASSWORD", "")
        ca_cert = os.getenv("MQTT_TLS_CA_CERT", "/app/certs/mqtt-ca.pem")

        client_id = f"django-mqtt-bridge-{int(time.time())}"
        client = mqtt.Client(client_id=client_id)
        if username:
            client.username_pw_set(username, password)

        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.tls_set(ca_certs=ca_cert, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        client.tls_insecure_set(False)

        while True:
            try:
                self.stdout.write(self.style.NOTICE(f"Connecting MQTT bridge to {host}:{port}"))
                client.connect(host, port, 60)
                client.loop_forever()
            except Exception as exc:
                logger.exception("MQTT bridge crashed: %s", exc)
                time.sleep(5)

    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            logger.error("MQTT connect failed with rc=%s", rc)
            return

        topics = [
            "esp32/+/telemetry/soil",
            "esp32/+/telemetry/luminosity",
            "esp32/+/telemetry/environment",
            "esp32/+/commands/request",
            "esp32/+/notifications",
        ]

        for topic in topics:
            client.subscribe(topic)

        logger.info("MQTT bridge connected and subscribed")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            logger.exception("Invalid JSON payload on topic %s", msg.topic)
            return

        parts = msg.topic.split("/")
        if len(parts) < 3 or parts[0] != "esp32":
            logger.warning("Unexpected topic format: %s", msg.topic)
            return

        mac_address = parts[1]
        category = parts[2]
        kind = parts[3] if len(parts) > 3 else None

        try:
            if category == "telemetry" and kind == "soil":
                self.handle_soil_telemetry(mac_address, payload)
            elif category == "telemetry" and kind == "luminosity":
                self.handle_luminosity_telemetry(mac_address, payload)
            elif category == "telemetry" and kind == "environment":
                self.handle_environment_telemetry(mac_address, payload)
            elif category == "commands" and kind == "request":
                self.handle_command_request(client, mac_address, payload)
            elif category == "notifications":
                self.handle_notification(mac_address, payload)
        except Exception:
            logger.exception("Error processing topic %s", msg.topic)

    def handle_soil_telemetry(self, mac_address, payload):
        esp32_ip = payload.get("esp32_ip")
        device = get_or_create_device(mac_address, device_type="soil", esp32_ip=esp32_ip)

        # Usa un timestamp común para todas las zonas del mismo paquete MQTT.
        reading_time = self._parse_payload_timestamp(payload) or timezone.now()

        # Nuevo formato: UN SOLO mensaje con array "zones" (ambas plantas)
        zones = payload.get("zones", [])
        if zones:
            for zone in zones:
                tipo_planta = (zone.get("tipo_planta") or "lechuga").strip().lower()
                humedad_raw = float(zone.get("humedad_suelo", 0.0))
                self._save_soil_reading_once(
                    device=device,
                    tipo_planta=tipo_planta,
                    humedad_raw=humedad_raw,
                    reading_time=reading_time,
                    source="telemetry.zones",
                )
        else:
            # Compatibilidad con formato antiguo (dos mensajes separados)
            tipo_planta = (payload.get("tipo_planta") or "lechuga").strip().lower()
            humedad_raw = float(payload.get("humedad_suelo", 0.0))
            self._save_soil_reading_once(
                device=device,
                tipo_planta=tipo_planta,
                humedad_raw=humedad_raw,
                reading_time=reading_time,
                source="telemetry.single",
            )

        # Luminosidad de suelo: solo guardar si el payload la envía explícitamente.
        # Así evitamos crear filas 0.0 cuando el mensaje de soil no incluye ese dato.
        luminosidad_soil = payload.get("luminosidad")
        if luminosidad_soil is not None:
            try:
                luminosidad_soil = float(luminosidad_soil)
            except (TypeError, ValueError):
                logger.warning("Invalid soil luminosity value: %s", luminosidad_soil)
                luminosidad_soil = None

        if luminosidad_soil is not None and luminosidad_soil >= 0:
            LuminosityData.objects.create(
                device=device,
                luminosidad=luminosidad_soil,
            )

        self.save_water_tank_reading_from_payload(payload)

    def handle_environment_telemetry(self, mac_address, payload):
        esp32_ip = payload.get("esp32_ip")
        get_or_create_device(mac_address, device_type="environment", esp32_ip=esp32_ip)

        # Regla: payloads telemetry/environment NO guardan luminosidad,
        # aunque traigan el campo, porque ese dispositivo siempre reporta 0 lux.
        # Guarda datos de ambiente solo si vienen completos.
        has_temperature = payload.get("temperatura") is not None
        has_humidity = payload.get("humedad_ambiente") is not None
        if has_temperature and has_humidity:
            Measurement.objects.create(
                temperatura=float(payload.get("temperatura", 0.0)),
                humedad=float(payload.get("humedad_ambiente", 0.0)),
                esp32_ip=esp32_ip,
            )

        self.save_water_tank_reading_from_payload(payload)

    def handle_luminosity_telemetry(self, mac_address, payload):
        esp32_ip = payload.get("esp32_ip")
        device = get_or_create_device(mac_address, device_type="environment", esp32_ip=esp32_ip)

        luminosidad = payload.get("luminosidad")
        if luminosidad is not None:
            try:
                luminosidad_value = float(luminosidad)
            except (TypeError, ValueError):
                logger.warning("Invalid luminosity value: %s", luminosidad)
                luminosidad_value = None

            if luminosidad_value is not None and luminosidad_value >= 0:
                LuminosityData.objects.create(
                    device=device,
                    luminosidad=luminosidad_value,
                )

        self.save_water_tank_reading_from_payload(payload)

    def handle_command_request(self, client, mac_address, payload):
        esp32_ip = payload.get("esp32_ip")
        device = get_or_create_device(mac_address, device_type="soil", esp32_ip=esp32_ip)
        zones = payload.get("zones", [])

        controller = IrrigationController()
        commands = []

        for zone in zones:
            relay = zone.get("relay")
            plant_type = zone.get("plant_type")
            zone_active = bool(zone.get("active"))
            zone_event_id = zone.get("event_id")

            activo = IrrigationEvent.objects.filter(
                Q(device=device) | Q(device__isnull=True),
                relay=relay,
                fecha_fin__isnull=True,
            ).order_by("-fecha_inicio").first()

            if activo and activo.device_id is None:
                activo.device = device
                activo.save(update_fields=["device"])

            # Reconciliación: la ESP32 reporta zona inactiva y sin event_id,
            # pero servidor mantiene un evento abierto para ese relay.
            within_startup_grace = (
                activo
                and activo.device_started_at is None
                and (timezone.now() - activo.fecha_inicio).total_seconds() < IRRIGATION_STARTUP_GRACE_SECONDS
            )
            if (
                activo
                and not zone_active
                and zone_event_id in (None, 0, "0")
                and not within_startup_grace
            ):
                controller.finalizar_riego(activo.id)
                commands.append({
                    "relay": relay,
                    "plant_type": activo.tipo_planta or plant_type,
                    "command": "OFF",
                    "duration": 0,
                    "reason": "Evento reconciliado: dispositivo inactivo",
                    "event_id": activo.id,
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
                        activo.save(update_fields=["stop_requested"])
                    commands.append({
                        "relay": relay,
                        "plant_type": activo.tipo_planta or plant_type,
                        "command": "OFF",
                        "duration": 0,
                        "reason": "Parada solicitada" if activo.stop_requested else "Duracion completada",
                        "event_id": activo.id,
                    })
                else:
                    commands.append({
                        "relay": relay,
                        "plant_type": activo.tipo_planta or plant_type,
                        "command": "ON",
                        "duration": time_remaining,
                        "reason": activo.razon,
                        "event_id": activo.id,
                    })
                continue

            needs_irrigation, reason, _ = controller.necesita_riego_por_planta(
                tipo_planta=plant_type,
                device=device,
                relay=relay,
            )

            if needs_irrigation:
                event = controller.iniciar_riego(
                    razon=reason,
                    device=device,
                    relay=relay,
                    tipo_planta=plant_type,
                    automatico=True,
                )
                commands.append({
                    "relay": relay,
                    "plant_type": plant_type,
                    "command": "ON",
                    "duration": event.duracion_planificada_segundos,
                    "reason": reason,
                    "event_id": event.id,
                })
            else:
                commands.append({
                    "relay": relay,
                    "plant_type": plant_type,
                    "command": "OFF",
                    "duration": 0,
                    "reason": reason,
                    "event_id": None,
                })

        response_topic = f"esp32/{mac_address}/commands/response"
        response_payload = {
            "status": "ok",
            "server_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "next_poll_ms": 300000,
            "active_poll_ms": 5000,
            "commands": commands,
        }
        client.publish(response_topic, json.dumps(response_payload), qos=1, retain=False)

    def handle_notification(self, mac_address, payload):
        esp32_ip = payload.get("esp32_ip")
        device = get_or_create_device(mac_address, device_type="soil", esp32_ip=esp32_ip)

        event = None
        event_id = payload.get("event_id")
        if event_id:
            event = IrrigationEvent.objects.filter(id=event_id).first()

        relay = payload.get("relay")
        if not event and relay is not None:
            event = IrrigationEvent.objects.filter(
                Q(device=device) | Q(device__isnull=True),
                relay=relay,
                fecha_fin__isnull=True,
            ).order_by("-fecha_inicio").first()

        if event and event.device_id is None:
            event.device = device
            event.save(update_fields=["device"])

        notification_type = payload.get("notification_type")
        if not notification_type:
            return

        notification_payload = payload.get("payload") or {}
        if notification_type == "poll" and isinstance(notification_payload, dict):
            if notification_payload.get("kind") == "sensor_read":
                raw_value = notification_payload.get("value_raw")
                if raw_value is None:
                    raw_value = payload.get("humedad_suelo")
                if raw_value is not None:
                    reading_time = self._parse_payload_timestamp(payload) or timezone.now()
                    self._save_soil_reading_once(
                        device=device,
                        tipo_planta=(payload.get("plant_type") or "lechuga").strip().lower(),
                        humedad_raw=raw_value,
                        reading_time=reading_time,
                        source="notifications.poll.sensor_read",
                    )

        IrrigationNotification.objects.create(
            device=device,
            event=event,
            notification_type=notification_type,
            relay=relay,
            tipo_planta=payload.get("plant_type"),
            reason=payload.get("reason", ""),
            payload=notification_payload,
        )

        if event:
            controller = IrrigationController()
            if notification_type == "start":
                controller.registrar_inicio_dispositivo(event.id)
            elif notification_type in ["stop", "completed"]:
                controller.finalizar_riego(
                    event.id,
                    humedad_final=payload.get("humedad_suelo"),
                    temperatura_final=payload.get("temperatura"),
                )
