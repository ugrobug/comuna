from django.db import migrations


SQL_FIX_INCLUDE_IN_PUBLIC_FEEDS_DEFAULT = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'feeds_comun'
          AND column_name = 'include_in_public_feeds'
    ) THEN
        EXECUTE 'ALTER TABLE feeds_comun ALTER COLUMN include_in_public_feeds SET DEFAULT TRUE';
        EXECUTE 'UPDATE feeds_comun SET include_in_public_feeds = TRUE WHERE include_in_public_feeds IS NULL';
    END IF;
END
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0054_site_notifications"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_FIX_INCLUDE_IN_PUBLIC_FEEDS_DEFAULT,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

