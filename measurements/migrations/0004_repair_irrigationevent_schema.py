from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0003_sensorcalibrationsettings'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE measurements_irrigationevent
                ADD COLUMN IF NOT EXISTS device_id bigint NULL,
                ADD COLUMN IF NOT EXISTS relay smallint NULL,
                ADD COLUMN IF NOT EXISTS tipo_planta varchar(50) NULL,
                ADD COLUMN IF NOT EXISTS stop_requested boolean NOT NULL DEFAULT false,
                ADD COLUMN IF NOT EXISTS device_started_at timestamp with time zone NULL;

            CREATE INDEX IF NOT EXISTS measurements_irrigationevent_device_id_idx
                ON measurements_irrigationevent (device_id);

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'measurements_irrigati_device_id_fkey'
                ) THEN
                    ALTER TABLE measurements_irrigationevent
                    ADD CONSTRAINT measurements_irrigati_device_id_fkey
                    FOREIGN KEY (device_id)
                    REFERENCES measurements_esp32device (id)
                    DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END
            $$;
            """,
            reverse_sql="""
            DO $$ BEGIN END $$;
            """,
        ),
    ]
