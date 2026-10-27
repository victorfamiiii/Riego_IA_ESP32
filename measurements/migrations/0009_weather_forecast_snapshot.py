from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0007_sync_measurements_schema'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeatherForecastSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('municipio_id', models.CharField(db_index=True, help_text='ID del municipio de AEMET', max_length=20)),
                ('municipio_nombre', models.CharField(blank=True, help_text='Nombre del municipio', max_length=200)),
                ('dias', models.PositiveSmallIntegerField(default=5, help_text='Numero de dias incluidos en la prevision')),
                ('elaborado', models.DateTimeField(blank=True, help_text='Fecha/hora de elaboracion reportada por AEMET', null=True)),
                ('payload', models.JSONField(default=dict, help_text='Prevision normalizada completa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Snapshot de prevision meteorologica',
                'verbose_name_plural': 'Snapshots de prevision meteorologica',
                'ordering': ['-updated_at'],
                'unique_together': {('municipio_id', 'dias')},
            },
        ),
        migrations.AddIndex(
            model_name='weatherforecastsnapshot',
            index=models.Index(fields=['municipio_id', 'dias'], name='measurement_municip_a2b43e_idx'),
        ),
        migrations.AddIndex(
            model_name='weatherforecastsnapshot',
            index=models.Index(fields=['-updated_at'], name='measurement_updated_8a4ce8_idx'),
        ),
    ]
