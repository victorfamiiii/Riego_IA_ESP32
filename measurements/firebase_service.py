"""
Servicio centralizado de Firebase Cloud Messaging (FCM)
Maneja envío de notificaciones push a usuarios registrados.
"""

import os
import logging
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class FirebaseService:
    """
    Servicio para enviar notificaciones FCM.
    Singleton que inicializa Firebase una sola vez.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialize_firebase()
            FirebaseService._initialized = True
    
    @staticmethod
    def _initialize_firebase():
        """Inicializa Firebase Admin SDK con las credenciales."""
        try:
            # Buscar archivo de credenciales
            creds_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
            
            if not creds_path:
                # Ruta por defecto relativa al proyecto
                creds_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'firebase-adminsdk.json'
                )
            
            if not os.path.exists(creds_path):
                logger.warning(f"Firebase credentials not found at {creds_path}")
                return False
            
            # Si Firebase ya está inicializado, skip
            if firebase_admin._apps:
                logger.info("Firebase already initialized")
                return True
            
            # Inicializar con credenciales
            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
            logger.info("✅ Firebase initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"❌ Firebase initialization error: {e}")
            return False
    
    def send_to_user(self, user_id: int, title: str, body: str, data: dict = None, icon: str = None, sent_by_user_id: int = None):
        """
        Envía notificación a todos los dispositivos activos de un usuario.
        
        Args:
            user_id: ID del usuario Django
            title: Título de la notificación
            body: Cuerpo/mensaje de la notificación
            data: Dict con datos adicionales (JSON)
            icon: URL del icono (opcional)
            sent_by_user_id: ID del usuario admin que envía (para historial)
        
        Returns:
            dict con resultado: {'success': bool, 'sent': int, 'failed': int, 'errors': [], 'notification_id': id}
        """
        from measurements.models import FCMToken, NotificationHistory
        
        try:
            # Obtener tokens activos del usuario
            tokens = FCMToken.objects.filter(
                user_id=user_id,
                is_active=True
            ).values_list('token', flat=True)
            
            tokens_list = list(tokens)
            
            # Crear registro en historial (antes de enviar)
            notification = NotificationHistory.objects.create(
                user_id=user_id,
                title=title,
                body=body,
                data=data or {},
                icon=icon or '',
                status='pending',
                sent_by_id=sent_by_user_id,
                num_tokens_sent=len(tokens_list)
            )
            
            if not tokens_list:
                logger.warning(f"No active FCM tokens for user {user_id}")
                notification.status = 'failed'
                notification.error_message = 'No active tokens'
                notification.save()
                return {'success': False, 'sent': 0, 'failed': 0, 'errors': ['No active tokens'], 'notification_id': notification.id}
            
            result = self._send_multicast(tokens_list, title, body, data, icon)
            
            # Actualizar historial con resultado
            notification.status = 'sent' if result['success'] else 'failed'
            notification.sent_at = timezone.now()
            notification.num_tokens_failed = result['failed']
            if result.get('errors'):
                notification.error_message = '\n'.join(result['errors'][:5])  # Primeros 5 errores
            notification.save()
            
            logger.info(f"FCM notification {notification.id} sent to user {user_id}: {result['sent']} sent, {result['failed']} failed")
            result['notification_id'] = notification.id
            return result
        
        except Exception as e:
            logger.error(f"Error sending FCM to user {user_id}: {e}")
            return {'success': False, 'sent': 0, 'failed': 0, 'errors': [str(e)]}
    
    def send_to_token(self, token: str, title: str, body: str, data: dict = None, icon: str = None):
        """
        Envía notificación a un token específico.
        
        Args:
            token: Token FCM
            title: Título
            body: Cuerpo
            data: Dict adicional
            icon: URL del icono
        
        Returns:
            dict con resultado
        """
        return self._send_multicast([token], title, body, data, icon)
    
    def _send_multicast(self, tokens: list, title: str, body: str, data: dict = None, icon: str = None):
        from measurements.models import FCMToken
        """
        Envía notificación a múltiples tokens de forma eficiente.
        
        Returns:
            {'success': bool, 'sent': int, 'failed': int, 'errors': []}
        """
        if not tokens:
            return {'success': False, 'sent': 0, 'failed': 0, 'errors': ['Empty token list']}
        
        if not firebase_admin._apps:
            logger.error("Firebase not initialized")
            return {'success': False, 'sent': 0, 'failed': 0, 'errors': ['Firebase not initialized']}
        
        try:
            # Construir mensaje
            notification = messaging.Notification(
                title=title,
                body=body,
                image=icon
            )
            
            # send_each requiere lista de Message individuales (firebase-admin >= 6)
            messages = [
                messaging.Message(
                    notification=notification,
                    data={k: str(v) for k, v in (data or {}).items()},
                    token=token
                )
                for token in tokens
            ]
            response = messaging.send_each(messages)
            
            # Procesar respuestas
            errors = []
            failed_tokens = []
            
            for idx, send_result in enumerate(response.responses):
                if not send_result.success:
                    error = send_result.exception
                    errors.append(f"Token {idx}: {str(error)}")
                    failed_tokens.append(tokens[idx])
            
            # Desactivar tokens inválidos
            if failed_tokens:
                FCMToken.objects.filter(token__in=failed_tokens).update(is_active=False)
            
            result = {
                'success': response.failure_count == 0,
                'sent': response.success_count,
                'failed': response.failure_count,
                'errors': errors
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error in _send_multicast: {e}")
            return {'success': False, 'sent': 0, 'failed': 0, 'errors': [str(e)]}
    
    def send_to_all_users(self, title: str, body: str, data: dict = None, icon: str = None):
        """
        Envía notificación a TODOS los usuarios activos.
        Úsalo con cuidado.
        
        Returns:
            dict con totales
        """
        from measurements.models import FCMToken
        from django.contrib.auth.models import User
        
        try:
            users = User.objects.filter(fcm_tokens__is_active=True).distinct()
            
            total_sent = 0
            total_failed = 0
            all_errors = []
            
            for user in users:
                result = self.send_to_user(
                    user.id,
                    title=title,
                    body=body,
                    data=data,
                    icon=icon
                )
                total_sent += result['sent']
                total_failed += result['failed']
                all_errors.extend(result['errors'])
            
            return {
                'success': total_failed == 0,
                'total_sent': total_sent,
                'total_failed': total_failed,
                'users_targeted': users.count(),
                'errors': all_errors
            }
        
        except Exception as e:
            logger.error(f"Error in send_to_all_users: {e}")
            return {
                'success': False,
                'total_sent': 0,
                'total_failed': 0,
                'users_targeted': 0,
                'errors': [str(e)]
            }


# Singleton global
firebase_service = FirebaseService()
