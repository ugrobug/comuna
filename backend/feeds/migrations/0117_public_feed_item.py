from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0116_public_read_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicFeedItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("feed", models.CharField(choices=[("home", "Главная")], default="home", max_length=32)),
                ("rank", models.PositiveIntegerField()),
                ("score", models.IntegerField(default=0)),
                ("post_created_at", models.DateTimeField()),
                ("author_id_snapshot", models.BigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="public_feed_items", to="feeds.post")),
            ],
            options={
                "ordering": ["feed", "rank"],
                "indexes": [
                    models.Index(fields=["feed", "rank"], name="pubfeed_feed_rank_idx"),
                    models.Index(fields=["feed", "-post_created_at"], name="pubfeed_feed_created_idx"),
                    models.Index(fields=["feed", "-score"], name="pubfeed_feed_score_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("feed", "post"), name="feeds_public_feed_unique_post"),
                    models.UniqueConstraint(fields=("feed", "rank"), name="feeds_public_feed_unique_rank"),
                ],
            },
        ),
    ]
