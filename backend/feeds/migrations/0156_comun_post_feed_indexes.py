from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("feeds", "0155_post_poll_options_gin_index"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS feeds_post_manual_comun_created_idx
            ON feeds_post (((raw_data -> 'comun_slug')), created_at DESC)
            WHERE (NOT is_blocked)
              AND (NOT is_pending)
              AND ((raw_data -> 'source') = '"manual_comun"'::jsonb)
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS feeds_post_manual_comun_created_idx
            """,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS compost_comun_cat_post_idx
                    ON feeds_comunpostcategoryassignment (comun_id, category_id, post_id)
                    """,
                    reverse_sql="""
                    DROP INDEX CONCURRENTLY IF EXISTS compost_comun_cat_post_idx
                    """,
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="comunpostcategoryassignment",
                    index=models.Index(
                        fields=["comun", "category", "post"],
                        name="compost_comun_cat_post_idx",
                    ),
                )
            ],
        ),
    ]
