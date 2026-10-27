"""
Vistas de autenticación para el sistema de riego
"""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle
import json
import re


# Clase de autenticación que no verifica CSRF (para login/logout)
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # No verificar CSRF


class LoginRateThrottle(AnonRateThrottle):
    """
    Rate limiting para intentos de login: 5 intentos por minuto
    """
    rate = '5/minute'


def validate_password_strength(password):
    """
    Valida que la contraseña sea segura
    """
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    if not re.search(r'[A-Z]', password):
        return False, "La contraseña debe contener al menos una mayúscula"
    if not re.search(r'[a-z]', password):
        return False, "La contraseña debe contener al menos una minúscula"
    if not re.search(r'[0-9]', password):
        return False, "La contraseña debe contener al menos un número"
    return True, ""


def check_rate_limit(username, ip_address):
    """
    Verifica intentos de login fallidos para prevenir fuerza bruta
    """
    cache_key_user = f'login_attempts_{username}'
    cache_key_ip = f'login_attempts_ip_{ip_address}'
    
    attempts_user = cache.get(cache_key_user, 0)
    attempts_ip = cache.get(cache_key_ip, 0)
    
    if attempts_user >= 5 or attempts_ip >= 10:
        return False, "Demasiados intentos fallidos. Intente nuevamente en 15 minutos."
    
    return True, ""


def record_failed_attempt(username, ip_address):
    """
    Registra un intento de login fallido
    """
    cache_key_user = f'login_attempts_{username}'
    cache_key_ip = f'login_attempts_ip_{ip_address}'
    
    attempts_user = cache.get(cache_key_user, 0)
    attempts_ip = cache.get(cache_key_ip, 0)
    
    cache.set(cache_key_user, attempts_user + 1, 900)  # 15 minutos
    cache.set(cache_key_ip, attempts_ip + 1, 900)


def clear_failed_attempts(username, ip_address):
    """
    Limpia los intentos fallidos después de un login exitoso
    """
    cache_key_user = f'login_attempts_{username}'
    cache_key_ip = f'login_attempts_ip_{ip_address}'
    
    cache.delete(cache_key_user)
    cache.delete(cache_key_ip)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """
    Vista de inicio de sesión con protección contra fuerza bruta
    """
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Validación básica
        if not username or not password:
            return Response({
                'error': 'Usuario y contraseña son requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Sanitizar username (solo alfanuméricos, guión bajo y guión medio)
        if not re.match(r'^[\w\-]+$', username):
            return Response({
                'error': 'Nombre de usuario inválido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener IP del cliente
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or \
                     request.META.get('REMOTE_ADDR', '')
        
        # Verificar rate limiting
        allowed, message = check_rate_limit(username, ip_address)
        if not allowed:
            return Response({
                'error': message
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Autenticar usuario
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if not user.is_active:
                return Response({
                    'error': 'Esta cuenta ha sido desactivada'
                }, status=status.HTTP_403_FORBIDDEN)
            
            login(request, user)
            clear_failed_attempts(username, ip_address)
            
            # Determinar rol
            role = 'admin' if (user.is_staff or user.is_superuser) else 'visitor'
            
            return Response({
                'success': True,
                'message': 'Inicio de sesión exitoso',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff,
                    'role': role
                }
            }, status=status.HTTP_200_OK)
        else:
            record_failed_attempt(username, ip_address)
            return Response({
                'error': 'Usuario o contraseña incorrectos'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except json.JSONDecodeError:
        return Response({
            'error': 'Datos JSON inválidos'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': 'Error en el servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])  # Permitir logout incluso sin autenticación
def logout_view(request):
    """
    Vista de cierre de sesión - limpia completamente la sesión
    Similar a como lo hace Django Admin
    """
    # Obtener la sesión antes de hacer logout
    session_key = request.session.session_key if hasattr(request, 'session') else None
    
    # Limpiar la sesión del usuario usando la función de Django
    logout(request)
    
    # Forzar la eliminación de la sesión de la base de datos
    if session_key:
        from django.contrib.sessions.models import Session
        try:
            Session.objects.filter(session_key=session_key).delete()
        except Exception:
            pass
    
    # Forzar flush de la sesión actual
    if hasattr(request, 'session'):
        request.session.flush()
    
    # Crear respuesta
    response = Response({
        'success': True,
        'message': 'Sesión cerrada correctamente'
    }, status=status.HTTP_200_OK)
    
    # Eliminar cookies de sesión explícitamente con todas las variantes posibles
    response.delete_cookie('sessionid', path='/')
    response.delete_cookie('sessionid', path='/app/')
    response.delete_cookie('sessionid', path='/api/')
    response.delete_cookie('csrftoken', path='/')
    response.delete_cookie('csrftoken', path='/app/')
    response.delete_cookie('csrftoken', path='/api/')
    
    # Establecer cookies expiradas para forzar eliminación
    response.set_cookie('sessionid', '', max_age=0, path='/', expires='Thu, 01 Jan 1970 00:00:00 GMT')
    response.set_cookie('csrftoken', '', max_age=0, path='/', expires='Thu, 01 Jan 1970 00:00:00 GMT')
    
    return response


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def register_view(request):
    """
    Vista de registro de nuevos usuarios con validación de contraseña
    """
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        # Validaciones básicas
        if not username or not password:
            return Response({
                'error': 'Usuario y contraseña son requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Sanitizar username
        if not re.match(r'^[\w\-]+$', username):
            return Response({
                'error': 'El nombre de usuario solo puede contener letras, números, guiones y guiones bajos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(username) < 3 or len(username) > 30:
            return Response({
                'error': 'El nombre de usuario debe tener entre 3 y 30 caracteres'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar fortaleza de la contraseña
        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            return Response({
                'error': error_message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar si el usuario ya existe
        if User.objects.filter(username=username).exists():
            return Response({
                'error': 'El usuario ya existe'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if email and User.objects.filter(email=email).exists():
            return Response({
                'error': 'El email ya está registrado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear el nuevo usuario
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Iniciar sesión automáticamente
        login(request, user)
        
        return Response({
            'success': True,
            'message': 'Usuario registrado exitosamente',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }, status=status.HTTP_201_CREATED)
        
    except json.JSONDecodeError:
        return Response({
            'error': 'Datos JSON inválidos'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': 'Error en el servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_auth(request):
    """
    Verificar si el usuario está autenticado y su rol
    Verifica tanto la autenticación como la validez de la sesión
    """
    # Verificar que el usuario está autenticado Y que tiene una sesión válida
    if request.user.is_authenticated:
        # Verificar que la sesión existe en la base de datos
        session_key = request.session.session_key if hasattr(request, 'session') else None
        
        if session_key:
            from django.contrib.sessions.models import Session
            try:
                session_exists = Session.objects.filter(session_key=session_key).exists()
                if not session_exists:
                    # La sesión no existe, forzar logout
                    logout(request)
                    return Response({
                        'authenticated': False,
                        'reason': 'session_expired'
                    }, status=status.HTTP_401_UNAUTHORIZED)
            except Exception:
                pass
        
        # Determinar rol: admin si es staff o superuser, visitor si no
        role = 'admin' if (request.user.is_staff or request.user.is_superuser) else 'visitor'
        
        return Response({
            'authenticated': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'is_staff': request.user.is_staff,
                'role': role  # 'admin' o 'visitor'
            }
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'authenticated': False
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request):
    """
    Obtener token CSRF para el frontend
    """
    return Response({
        'success': True,
        'message': 'CSRF token set'
    }, status=status.HTTP_200_OK)
