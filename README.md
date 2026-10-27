# 🌱 Riego_IA_ESP32

Sistema de riego automatizado para agricultura de precisión en interior, desarrollado como Trabajo de Fin de Grado de Ingeniería Informática. El proyecto controla el riego de lechugas y fresas mediante sensores, microcontroladores ESP32, comunicación MQTT, una API Django, una interfaz web en Next.js y decisiones de riego asistidas por inteligencia artificial.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-green)](https://www.djangoproject.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-purple)](https://mosquitto.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)

---

## 📌 Descripción

El sistema recoge datos de sensores instalados en las plantas y en el depósito de agua, los envía mediante MQTT a un servidor, los almacena en PostgreSQL y permite consultarlos y gestionar el riego desde una aplicación web y una PWA.

Además del riego automático por umbrales, el backend puede utilizar la API de Google Gemini para analizar el estado de las plantas y apoyar la decisión de riego. Si la IA no está disponible, el sistema mantiene la lógica tradicional basada en umbrales configurables.

---

## ✨ Funcionalidades

- Lectura de humedad del suelo para lechugas y fresas.
- Medición de temperatura y humedad ambiental con DHT22.
- Control del nivel de agua del depósito mediante HC-SR04.
- Comunicación MQTT entre los ESP32 y el servidor.
- Almacenamiento histórico de mediciones en PostgreSQL.
- Riego manual y automático mediante relés y electroválvulas.
- Calibración independiente de sensores para cada tipo de planta.
- Decisiones de riego por umbrales configurables.
- Decisión de riego asistida por Google Gemini.
- Notificaciones push mediante Firebase Cloud Messaging.
- Interfaz web responsive desarrollada con Next.js.
- Aplicación móvil PWA instalable.
- Autenticación de usuarios.
- Despliegue completo mediante Docker Compose.
- Acceso externo seguro mediante Cloudflare Tunnel.

---

## 🧠 Arquitectura

```text
ESP32 / Sensores / Electroválvulas
              |
              | MQTT
              v
       Mosquitto Broker
              |
              v
        Backend Django
              |
     +--------+---------+
     |                  |
 PostgreSQL         Google Gemini
     |                  
     v                  
Frontend Next.js / PWA
     |
   Nginx
     |
Cloudflare Tunnel
     |
  Internet
```

El flujo general es el siguiente:

1. Los ESP32 leen los sensores y publican las mediciones por MQTT.
2. El servicio `mqtt-bridge` consume los mensajes y los guarda en PostgreSQL.
3. El backend Django gestiona usuarios, configuración, histórico y lógica de riego.
4. Según el modo configurado, el sistema decide si regar mediante umbrales o con ayuda de Gemini.
5. Si se activa el riego, se envía la orden al ESP32 y se registra el evento.
6. El usuario consulta el estado y el histórico desde la web o la PWA.
7. Las notificaciones relevantes se envían mediante Firebase Cloud Messaging.

---

## 🛠️ Tecnologías

### Hardware

- ESP32
- Sensores capacitivos de humedad del suelo
- DHT22: temperatura y humedad ambiental
- HC-SR04: nivel de agua del depósito
- Relés
- Electroválvulas

### Backend

- Python
- Django
- Django REST Framework
- PostgreSQL
- Paho MQTT
- Gunicorn
- Firebase Admin SDK
- Google Gemini API
- AEMET OpenData API

### Frontend

- Next.js
- React
- PWA
- Firebase Cloud Messaging

### Infraestructura

- Docker
- Docker Compose
- Nginx
- Eclipse Mosquitto
- Cloudflare Tunnel
- Ubuntu Server

---

## 🐳 Servicios Docker

El sistema se despliega como varios contenedores conectados en una red interna de Docker.

| Servicio | Tecnología | Función |
|---|---|---|
| `mqtt` | Eclipse Mosquitto | Broker MQTT para la comunicación con los ESP32 |
| `mqtt-bridge` | Python / Django | Consume mensajes MQTT y persiste los datos en PostgreSQL |
| `db` | PostgreSQL | Base de datos principal del sistema |
| `web` | Django + Gunicorn | API REST, autenticación, lógica de riego e integración con IA |
| `frontend` | Next.js | Interfaz web y PWA |
| `nginx` | Nginx | Reverse proxy para HTTP/HTTPS |
| `cloudflared` | Cloudflare Tunnel | Exposición segura del servicio sin abrir puertos en el router |

---

## 📡 Sensores y control

El sistema controla dos zonas de cultivo:

- **Lechugas:** sensor de humedad del suelo con calibración propia.
- **Fresas:** sensor de humedad del suelo con calibración independiente.

También se monitorizan:

- Temperatura y humedad ambiental mediante DHT22.
- Nivel del depósito mediante HC-SR04.
- Estado de las electroválvulas mediante relés.

La calibración permite adaptar los umbrales de riego a las características de cada cultivo.

---

## 🤖 Riego con IA

El sistema dispone de dos modos de decisión:

- **Modo por umbral:** se riega cuando la humedad del suelo baja de un valor configurado para cada planta.
- **Modo IA:** el backend envía el contexto de los sensores a Google Gemini, que ayuda a valorar si conviene regar.

Si Gemini no está disponible o devuelve un error, el sistema puede volver automáticamente a la lógica basada en umbrales, garantizando que el riego siga funcionando.

---

## 🚀 Puesta en marcha

### Requisitos

- Docker
- Docker Compose
- Git
- API key de Google AI Studio para Gemini
- Proyecto de Firebase con Cloud Messaging configurado

---

## 📁 Estructura del proyecto

```text
.
├── measurements/             # Backend Django, API, modelos y lógica de riego
├── frontend-nextjs/          # Aplicación web y PWA en Next.js
├── esp32_codigo_completo/    # Código de los microcontroladores ESP32
├── mosquitto/                # Configuración del broker MQTT
├── nginx/                    # Configuración del reverse proxy
├── docker-compose.yml        # Definición de los servicios del sistema
└── README.md
```

---

## 🔒 Seguridad

- Comunicación web cifrada mediante HTTPS a través de Nginx y Cloudflare.
- Acceso externo mediante Cloudflare Tunnel, sin abrir puertos directamente en el router.
- Autenticación en la API y la aplicación web.
- Variables sensibles gestionadas mediante `.env`.
- Recomendable usar TLS también en la comunicación MQTT en un despliegue expuesto a Internet.

---


## 🎓 Contexto académico

Este proyecto fue desarrollado como Trabajo de Fin de Grado de Ingeniería Informática, con especialización en Sistemas de Información.

El objetivo fue diseñar e implementar un sistema completo de riego automatizado, integrando hardware, comunicaciones IoT, desarrollo web, bases de datos, contenedores e inteligencia artificial.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia [MIT](LICENSE).

---

## 👤 Autor

**Víctor Feo Galán**  
Ingeniería Informática — Sistemas de Información  
[GitHub](https://github.com/victorfamiiii)
