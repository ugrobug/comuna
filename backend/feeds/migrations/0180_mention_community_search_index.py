from django.db import migrations


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('feeds', '0179_mention_delivery')]
    operations = [migrations.RunSQL(
        """CREATE INDEX CONCURRENTLY IF NOT EXISTS comun_mention_search_idx
        ON feeds_comun USING GIN (to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(slug, '')))
        WHERE is_active""",
        'DROP INDEX CONCURRENTLY IF EXISTS comun_mention_search_idx',
    )]
