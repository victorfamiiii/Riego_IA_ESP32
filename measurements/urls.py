from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views_esp32
from . import auth_views
from . import admin_views

# Router SIN trailing slash
router = DefaultRouter(trailing_slash=False)
router.register(r'measurements', views.MeasurementViewSet, basename='measurement')

# Nuevos endpoints para multi-ESP32
router.register(r'devices', views_esp32.ESP32DeviceViewSet, basename='device')
router.register(r'soil', views_esp32.SoilMoistureViewSet, basename='soil')
router.register(r'luminosity', views_esp32.LuminosityDataViewSet, basename='luminosity')
# Alias legacy para mantener compatibilidad con firmware existente.
router.register(r'environmental', views_esp32.LuminosityDataViewSet, basename='environmental')
router.register(r'weather', views_esp32.WeatherDataViewSet, basename='weather')

# Endpoints para riego
router.register(r'irrigation', views_esp32.IrrigationEventViewSet, basename='irrigation')
router.register(r'irrigation-config', views_esp32.IrrigationConfigViewSet, basename='irrigation-config')

urlpatterns = [
    path('', include(router.urls)),
    
    # Rutas de autenticación SIN barra final
    path('auth/csrf', auth_views.get_csrf_token, name='csrf_token'),
    path('auth/login', auth_views.login_view, name='login'),
    path('auth/logout', auth_views.logout_view, name='logout'),
    path('auth/register', auth_views.register_view, name='register'),
    path('auth/check', auth_views.check_auth, name='check_auth'),
    
    # Rutas del depósito de agua
    path('water-tank/status', views.water_tank_status, name='water_tank_status'),
    path('water-tank/update', views.water_tank_update, name='water_tank_update'),
    path('water-tank/config', views.water_tank_config, name='water_tank_config'),
    path('water-tank/history', views.water_tank_history, name='water_tank_history'),
    
    # Rutas de administración (solo para admins)
    path('admin/tables', admin_views.list_tables, name='admin_tables'),
    path('admin/stats', admin_views.admin_stats, name='admin_stats'),
    path('admin/sensor-calibration', admin_views.sensor_calibration, name='admin_sensor_calibration'),
    path('admin/sensor-calibration/valve-test', admin_views.sensor_calibration_valve_test, name='admin_sensor_calibration_valve_test'),
    path('admin/sensor-calibration/soil-sample', admin_views.sensor_calibration_soil_sample, name='admin_sensor_calibration_soil_sample'),
    path('admin/sensor-calibration/soil-live-read', admin_views.sensor_calibration_soil_live_read, name='admin_sensor_calibration_soil_live_read'),
    path('admin/sensor-calibration/tank-sample', admin_views.sensor_calibration_tank_sample, name='admin_sensor_calibration_tank_sample'),
    path('admin/irrigation-mode/<str:tipo_planta>/', admin_views.irrigation_mode, name='admin_irrigation_mode'),
    path('admin/gemini-logs', admin_views.gemini_audit_logs, name='admin_gemini_logs'),
    path('admin/tables/<str:table_name>/schema', admin_views.get_table_schema, name='admin_table_schema'),
    path('admin/tables/<str:table_name>/bulk-delete', admin_views.bulk_delete, name='admin_bulk_delete'),
    path('admin/tables/<str:table_name>/<int:pk>', admin_views.table_detail, name='admin_table_detail'),
    path('admin/tables/<str:table_name>', admin_views.table_list_create, name='admin_table_list_create'),
    
    # Rutas de Firebase Cloud Messaging (FCM)
    path('fcm/register', admin_views.register_fcm_token, name='register_fcm_token'),
    path('fcm/send', admin_views.send_fcm_notification, name='send_fcm_notification'),
    path('fcm/my-tokens', admin_views.my_fcm_tokens, name='my_fcm_tokens'),
    path('fcm/tokens/<int:token_id>', admin_views.delete_fcm_token, name='delete_fcm_token'),
    
    # Rutas de Historial de Notificaciones
    path('notifications/history', admin_views.get_notification_history, name='get_notification_history'),
    path('notifications/send', admin_views.send_notification_to_user, name='send_notification_to_user'),
    path('notifications/broadcast', admin_views.send_notification_broadcast, name='send_notification_broadcast'),
]
