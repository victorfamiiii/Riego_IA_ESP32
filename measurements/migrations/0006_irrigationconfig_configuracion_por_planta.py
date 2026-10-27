from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0005_merge_water_tank_config_into_sensor_calibration'),
    ]

    operations = [
        migrations.AddField(
            model_name='irrigationconfig',
            name='configuracion_por_planta',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Configuración específica por planta. Ejemplo: {'lechuga': {...}, 'fresa': {...}}",
            ),
        ),
    ]
