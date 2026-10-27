from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0006_irrigationconfig_configuracion_por_planta'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE measurements_irrigationconfig "
                        "ADD COLUMN IF NOT EXISTS tipo_planta varchar(20) NOT NULL DEFAULT 'general';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE measurements_irrigationconfig "
                        "DROP COLUMN IF EXISTS tipo_planta;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='irrigationconfig',
                    name='tipo_planta',
                    field=models.CharField(
                        choices=[('lechuga', 'Lechuga'), ('fresa', 'Fresa'), ('general', 'General')],
                        default='general',
                        help_text='Tipo de planta para la que aplica esta configuración',
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name='soilmoisture',
            name='humedad_suelo',
            field=models.FloatField(
                help_text='Lectura cruda ADC de humedad del suelo enviada por la ESP32',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='irrigationconfig',
            unique_together={('tipo_planta', 'activo')},
        ),
    ]
