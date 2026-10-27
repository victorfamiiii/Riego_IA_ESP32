from django.db import migrations


def create_missing_irrigation_notification_table(apps, schema_editor):
    IrrigationNotification = apps.get_model('measurements', 'IrrigationNotification')
    table_name = IrrigationNotification._meta.db_table

    existing_tables = schema_editor.connection.introspection.table_names()
    if table_name not in existing_tables:
        schema_editor.create_model(IrrigationNotification)


def noop_reverse(apps, schema_editor):
    """No-op reverse to avoid accidental data loss."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_missing_irrigation_notification_table,
            reverse_code=noop_reverse,
        ),
    ]
