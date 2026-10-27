from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0009_weather_forecast_snapshot'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='weatherforecastsnapshot',
            options={
                'ordering': ['-updated_at'],
                'verbose_name': 'Snapshot de previsión meteorológica',
                'verbose_name_plural': 'Snapshots de previsión meteorológica',
            },
        ),
        migrations.RenameIndex(
            model_name='weatherforecastsnapshot',
            new_name='measurement_municip_7a0268_idx',
            old_name='measurement_municip_a2b43e_idx',
        ),
        migrations.RenameIndex(
            model_name='weatherforecastsnapshot',
            new_name='measurement_updated_b46e3c_idx',
            old_name='measurement_updated_8a4ce8_idx',
        ),
        migrations.AlterField(
            model_name='weatherforecastsnapshot',
            name='dias',
            field=models.PositiveSmallIntegerField(default=5, help_text='Número de días incluidos en la previsión'),
        ),
        migrations.AlterField(
            model_name='weatherforecastsnapshot',
            name='elaborado',
            field=models.DateTimeField(blank=True, help_text='Fecha/hora de elaboración reportada por AEMET', null=True),
        ),
        migrations.AlterField(
            model_name='weatherforecastsnapshot',
            name='payload',
            field=models.JSONField(default=dict, help_text='Previsión normalizada completa'),
        ),
    ]
