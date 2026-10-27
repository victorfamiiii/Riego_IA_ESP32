# Informe de Vulnerabilidades y Estado de Mitigación

Fecha: 2026-05-23

## Resumen
- Este informe lista vulnerabilidades detectadas en el repositorio, su nivel de riesgo y si el servidor/proyecto ya cuenta con mitigaciones. Incluye acciones concretas recomendadas.

## Hallazgos
- Contraseña enviada desde frontend en JSON: el cliente envía `password` en el cuerpo JSON al endpoint de login. Archivo: [frontend-nextjs/app/login/page.tsx](frontend-nextjs/app/login/page.tsx#L53). Riesgo: bajo/medio si se usa TLS; crítico si no se usa TLS.
- Cookie de sesión accesible por JavaScript: `SESSION_COOKIE_HTTPONLY = False` en [backend/settings.py](backend/settings.py#L104). Riesgo: medio (exposición ante XSS).
- Cookie CSRF accesible por JavaScript: `CSRF_COOKIE_HTTPONLY = False` (necesario para el flujo actual), en [backend/settings.py](backend/settings.py#L88). Riesgo: mitigado por CSRF tokens, pero requiere cuidado con XSS.
- Algoritmo de hashing en servidor: Django usa la lista por defecto (primero PBKDF2) — referencia en el entorno virtual: [.venv/lib/python3.13/site-packages/django/conf/global_settings.py](.venv/lib/python3.13/site-packages/django/conf/global_settings.py#L545). Riesgo: bajo (PBKDF2 es seguro), se puede mejorar con Argon2.
- Credenciales embebidas en código de dispositivos (ESP32): hay `mqttPass` y SSID/password hardcodeados en varios archivos bajo `esp32_codigo_completo/` (ej.: [esp32_codigo_completo/rele/rele.ino](esp32_codigo_completo/rele/rele.ino#L16)). Riesgo: alto si esos archivos se comparten públicamente.
- Mosquitto y manejo de passwords: `mosquitto.conf` referencia `password_file /mosquitto/data/passwd` y `mosquitto/docker-entrypoint.sh` exige variables `MQTT_ESP32_PASSWORD` / `MQTT_BRIDGE_PASSWORD`. Ver [mosquitto/mosquitto.conf](mosquitto/mosquitto.conf#L3) y [mosquitto/docker-entrypoint.sh](mosquitto/docker-entrypoint.sh#L5). Riesgo: medio si el archivo `passwd` o variables se exponen.
- Mapeo de secrets en `docker-compose.yml`: varias variables de entorno sensibles pasan por compose (ej.: `MQTT_ESP32_PASSWORD`, `POSTGRES_PASSWORD`). Ver [docker-compose.yml](docker-compose.yml#L18-L20) y líneas relacionadas. Riesgo: medio/alto si `.env` o repositorio contienen valores.

## Mitigaciones actuales (en este proyecto)
- Tráfico protegido por TLS: el frontend usa `https://riegoesp32.victorfg.work` en las llamadas (ver [frontend-nextjs/app/login/page.tsx](frontend-nextjs/app/login/page.tsx#L7-L8)). Si el servidor está correctamente configurado con certificados y Nginx, el tránsito queda cifrado.
- Cookies marcadas `Secure`: `CSRF_COOKIE_SECURE = True` y `SESSION_COOKIE_SECURE = True` en [backend/settings.py](backend/settings.py#L90-L106). Good.
- HSTS y otros encabezados de seguridad: `SECURE_HSTS_SECONDS = 31536000`, `SECURE_CONTENT_TYPE_NOSNIFF = True`, `SECURE_BROWSER_XSS_FILTER = True` (ver [backend/settings.py](backend/settings.py#L110-L121)).
- Validación y throttling en login: existe `validate_password_strength` y `LoginRateThrottle` en [measurements/auth_views.py](measurements/auth_views.py#L1-L40) y uso de throttling en la vista `login_view`. Reduce ataques de fuerza bruta.
- Django aplica hashing de contraseñas en servidor al usar `User.objects.create_user(...)` (ver [measurements/auth_views.py](measurements/auth_views.py#L269)).

## Recomendaciones (priorizadas)
1. Activar `HttpOnly` en la cookie de sesión para proteger frente a XSS:

   - Cambiar en `backend/settings.py`:

     ```py
     SESSION_COOKIE_HTTPONLY = True
     ```

   - Nota: `CSRF_COOKIE_HTTPONLY` debe permanecer `False` si el frontend necesita leer `csrftoken` desde JavaScript.

2. Mejorar hasheo de contraseñas en servidor usando Argon2 (recomendado):

   - Instalar la dependencia y actualizar `PASSWORD_HASHERS` en `backend/settings.py`:

     ```bash
     pip install argon2-cffi
     ```

     ```py
     PASSWORD_HASHERS = [
       "django.contrib.auth.hashers.Argon2PasswordHasher",
       "django.contrib.auth.hashers.PBKDF2PasswordHasher",
       "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
       "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
       "django.contrib.auth.hashers.ScryptPasswordHasher",
     ]
     ```

   - Django convertirá automáticamente hashes antiguos a Argon2 al hacer login de cada usuario.

3. Eliminar/rotar credenciales embebidas en el repositorio (ESP32 y otros):

   - Reemplazar valores reales por placeholders y leer credenciales desde variables de entorno o un gestor secreto.
   - Rotar las contraseñas que ya estuvieron en el repo.

4. Revisar `docker-compose.yml` y `.env`: asegurar que `.env` no esté versionado y que los valores sensibles se almacenen fuera del repo. Añadir `*.env` a `.gitignore` si aplica.

5. Revisar ACLs y permisos de Mosquitto: asegurar que el `password_file` no sea accesible públicamente y usar `acl` para limitar topics permitidos por usuario.

6. Añadir CSP y revisar el frontend para minimizar vectores XSS (con `SESSION_COOKIE_HTTPONLY=True` la cookie de sesión no será accesible desde JS aunque exista XSS).

7. Considerar autenticación multi-factor (2FA) y/o passwordless (WebAuthn) para cuentas administrativas.

## Pasos rápidos (aplicar cambios)
- Aplicar `SESSION_COOKIE_HTTPONLY`:

  Editar `backend/settings.py` y cambiar la línea correspondiente a:

  ```py
  SESSION_COOKIE_HTTPONLY = True
  ```

- Habilitar Argon2 (instalar y modificar `PASSWORD_HASHERS`) como se muestra arriba.

## Observaciones finales
- No recomendamos realizar hashing de la contraseña en el cliente como sustituto de TLS + hashing en servidor; el valor enviado desde el cliente (aunque sea hash) se comporta como una credencial reutilizable.
- Si quieres, puedo:
  - aplicar el cambio `SESSION_COOKIE_HTTPONLY = True` y crear un commit;
  - añadir `PASSWORD_HASHERS` con Argon2 y actualizar `requirements.txt` (añadir `argon2-cffi`) y probar localmente;
  - generar un patch para reemplazar credenciales en `esp32_codigo_completo/` por placeholders.

Archivo generado: [docs/SECURITY_VULN_REPORT.md](docs/SECURITY_VULN_REPORT.md)
