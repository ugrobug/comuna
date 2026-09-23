from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("feeds", "0176_companion_search")]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY feeds_post_comun_sources_created_idx
                ON feeds_post ((raw_data -> 'comun_slug'), created_at DESC, id DESC)
                WHERE NOT is_blocked AND NOT is_pending
                  AND companion_matched_at IS NULL
                  AND (raw_data -> 'source') IN ('"manual_comun"'::jsonb, '"max"'::jsonb)
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS feeds_post_comun_sources_created_idx",
        ),
    ]
