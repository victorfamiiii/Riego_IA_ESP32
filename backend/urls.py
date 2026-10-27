"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from measurements.views import MeasurementViewSet

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('measurements.urls')),
    
    # Endpoint compatible con Flask anterior (ESP32 enviaba POST a /data)
    # Redirige a la acción 'data' del ViewSet
    path('data', MeasurementViewSet.as_view({'post': 'data'}), name='data-compat'),

]
