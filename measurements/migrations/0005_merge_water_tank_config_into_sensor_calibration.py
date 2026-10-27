from django.db import migrations, models


def migrate_water_tank_config_to_sensor_calibration(apps, schema_editor):
    SensorCalibrationSettings = apps.get_model('measurements', 'SensorCalibrationSettings')
    WaterTankConfig = apps.get_model('measurements', 'WaterTankConfig')

    tank_config = WaterTankConfig.objects.order_by('pk').first()
    if not tank_config:
        return

    calibration, _ = SensorCalibrationSettings.objects.get_or_create(pk=1)
    calibration.distancia_minima_tanque = tank_config.distancia_minima
    calibration.distancia_maxima_tanque = tank_config.distancia_maxima
    calibration.capacidad_litros_tanque = tank_config.capacidad_litros
    calibration.save(update_fields=[
        'distancia_minima_tanque',
        'distancia_maxima_tanque',
        'capacidad_litros_tanque',
    ])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0004_repair_irrigationevent_schema'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensorcalibrationsettings',
            name='capacidad_litros_tanque',
            field=models.FloatField(default=10.0),
        ),
        migrations.RunPython(
            migrate_water_tank_config_to_sensor_calibration,
            reverse_code=noop_reverse,
        ),
        migrations.DeleteModel(
            name='WaterTankConfig',
        ),
    ]
