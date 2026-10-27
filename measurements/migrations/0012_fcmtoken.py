# Generated migration for FCMToken model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('measurements', '0011_irrigationconfig_mediciones_para_media'),
    ]

    operations = [
        migrations.CreateModel(
            name='FCMToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, help_text='Token FCM único del dispositivo', max_length=500, unique=True)),
                ('device_name', models.CharField(blank=True, help_text='Nombre/descripción del dispositivo (ej: iPhone 12, Chrome)', max_length=255)),
                ('user_agent', models.TextField(blank=True, help_text='User-Agent del navegador/dispositivo')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Fecha de registro del token')),
                ('last_used', models.DateTimeField(auto_now=True, help_text='Última vez que se usó este token')),
                ('is_active', models.BooleanField(default=True, help_text='Token activo o desactivado')),
                ('user', models.ForeignKey(help_text='Usuario propietario del token', on_delete=django.db.models.deletion.CASCADE, related_name='fcm_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Token FCM',
                'verbose_name_plural': 'Tokens FCM',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='fcmtoken',
            index=models.Index(fields=['user', 'is_active'], name='measurements_user_id_is_act_idx'),
        ),
        migrations.AddIndex(
            model_name='fcmtoken',
            index=models.Index(fields=['-created_at'], name='measurements_created__idx'),
        ),
    ]
