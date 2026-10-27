from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0002_repair_missing_irrigationnotification'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorCalibrationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('distancia_minima_tanque', models.FloatField(default=5.0)),
                ('distancia_maxima_tanque', models.FloatField(default=100.0)),
                ('ev1_litros_1s', models.FloatField(default=0.05)),
                ('ev1_litros_5s', models.FloatField(default=0.25)),
                ('ev1_litros_10s', models.FloatField(default=0.5)),
                ('ev2_litros_1s', models.FloatField(default=0.05)),
                ('ev2_litros_5s', models.FloatField(default=0.25)),
                ('ev2_litros_10s', models.FloatField(default=0.5)),
                ('suelo1_valor_seco', models.FloatField(default=4095.0)),
                ('suelo1_valor_mojado', models.FloatField(default=1200.0)),
                ('suelo2_valor_seco', models.FloatField(default=4095.0)),
                ('suelo2_valor_mojado', models.FloatField(default=1200.0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Calibración de Sensores',
                'verbose_name_plural': 'Calibración de Sensores',
            },
        ),
    ]
