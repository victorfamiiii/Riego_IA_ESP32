from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0015_alter_fcmtoken_user'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='irrigationconfig',
                    name='modo_riego',
                    field=models.CharField(default='umbral', max_length=20),
                ),
            ],
        ),
        migrations.CreateModel(
            name='GeminiAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('irrigation', 'Decision de riego'), ('chat', 'Chat con usuario')], default='irrigation', max_length=20)),
                ('tipo_planta', models.CharField(blank=True, max_length=50, null=True)),
                ('prompt', models.TextField()),
                ('modelo', models.CharField(default='gemini-2.5-flash', max_length=50)),
                ('respuesta_raw', models.TextField(blank=True)),
                ('respuesta_json', models.JSONField(blank=True, null=True)),
                ('decision_regar', models.BooleanField(blank=True, null=True)),
                ('decision_duracion_s', models.IntegerField(blank=True, null=True)),
                ('decision_razon', models.TextField(blank=True)),
                ('tokens_entrada', models.IntegerField(blank=True, null=True)),
                ('tokens_salida', models.IntegerField(blank=True, null=True)),
                ('latencia_ms', models.IntegerField(blank=True, null=True)),
                ('exito', models.BooleanField(default=True)),
                ('error_mensaje', models.TextField(blank=True)),
                ('evento_riego', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gemini_logs', to='measurements.irrigationevent')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Log de Gemini',
                'verbose_name_plural': 'Logs de Gemini',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['-created_at'], name='measuremen_created_gemini_idx'),
                    models.Index(fields=['tipo_planta', '-created_at'], name='measuremen_planta_gemini_idx'),
                    models.Index(fields=['exito'], name='measuremen_exito_gemini_idx'),
                ],
            },
        ),
    ]
