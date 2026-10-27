# Generated migration for NotificationHistory model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('measurements', '0012_fcmtoken'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Título de la notificación', max_length=255)),
                ('body', models.TextField(help_text='Cuerpo/contenido de la notificación')),
                ('data', models.JSONField(blank=True, default=dict, help_text='Datos adicionales en formato JSON')),
                ('icon', models.CharField(blank=True, help_text='URL del ícono', max_length=255)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('sent', 'Enviada'), ('failed', 'Fallida'), ('read', 'Leída')], default='pending', help_text='Estado de envío de la notificación', max_length=20)),
                ('sent_at', models.DateTimeField(blank=True, help_text='Fecha y hora de envío', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Fecha de creación del registro')),
                ('error_message', models.TextField(blank=True, help_text='Mensaje de error si falló el envío')),
                ('num_tokens_sent', models.IntegerField(default=0, help_text='Número de tokens a los que se intentó enviar')),
                ('num_tokens_failed', models.IntegerField(default=0, help_text='Número de tokens en los que falló el envío')),
                ('sent_by', models.ForeignKey(blank=True, help_text='Usuario administrador que envió la notificación', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications_sent', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(help_text='Usuario destino de la notificación', on_delete=django.db.models.deletion.CASCADE, related_name='notification_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Historial de Notificaciones',
                'verbose_name_plural': 'Historial de Notificaciones',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notificationhistory',
            index=models.Index(fields=['user', '-created_at'], name='measurements_user_id_created_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationhistory',
            index=models.Index(fields=['-created_at'], name='measurements_created_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationhistory',
            index=models.Index(fields=['status'], name='measurements_status_idx'),
        ),
    ]
