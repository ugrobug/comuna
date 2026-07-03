from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("feeds", "0153_userfeedsettings_keyboard_hint"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS feeds_post_search_fts_idx
                ON feeds_post
                USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')))
                """,
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS feeds_author_search_fts_idx
                ON feeds_author
                USING GIN (to_tsvector('simple', coalesce(username, '') || ' ' || coalesce(title, '') || ' ' || coalesce(description, '')))
                """,
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS feeds_comun_search_fts_idx
                ON feeds_comun
                USING GIN (to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(slug, '') || ' ' || coalesce(product_description, '') || ' ' || coalesce(target_audience, '') || ' ' || coalesce(rules_text, '')))
                """,
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS auth_user_search_fts_idx
                ON auth_user
                USING GIN (to_tsvector('simple', coalesce(username, '') || ' ' || coalesce(first_name, '') || ' ' || coalesce(last_name, '')))
                """,
            ],
            reverse_sql=[
                "DROP INDEX CONCURRENTLY IF EXISTS auth_user_search_fts_idx",
                "DROP INDEX CONCURRENTLY IF EXISTS feeds_comun_search_fts_idx",
                "DROP INDEX CONCURRENTLY IF EXISTS feeds_author_search_fts_idx",
                "DROP INDEX CONCURRENTLY IF EXISTS feeds_post_search_fts_idx",
            ],
        ),
    ]
