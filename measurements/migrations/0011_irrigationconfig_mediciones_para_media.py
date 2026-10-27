from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0010_alter_weatherforecastsnapshot_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='irrigationconfig',
            name='mediciones_para_media',
            field=models.PositiveSmallIntegerField(default=4, help_text='Número de mediciones usadas para calcular la media del riego automático'),
        ),
    ]
