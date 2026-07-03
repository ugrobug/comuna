from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("feeds", "0154_full_text_search_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS feeds_post_poll_options_gin_idx
            ON feeds_post
            USING GIN ((raw_data #> '{poll,options}') jsonb_path_ops)
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS feeds_post_poll_options_gin_idx
            """,
        ),
    ]
