from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RatingSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("post_vote_weight", models.DecimalField(decimal_places=3, default=1, max_digits=8)),
                ("post_comment_weight", models.DecimalField(decimal_places=3, default=1, max_digits=8)),
                ("post_comment_like_weight", models.DecimalField(decimal_places=3, default="0.5", max_digits=8)),
                ("post_community_rating_weight", models.DecimalField(decimal_places=3, default=1, max_digits=8)),
                ("post_author_rating_weight", models.DecimalField(decimal_places=3, default=1, max_digits=8)),
                ("community_post_rating_weight", models.DecimalField(decimal_places=3, default="0.1", max_digits=8)),
                ("community_post_rating_days", models.PositiveSmallIntegerField(default=7)),
                ("author_post_rating_weight", models.DecimalField(decimal_places=3, default=1, max_digits=8)),
                ("author_comment_like_weight", models.DecimalField(decimal_places=3, default="0.5", max_digits=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Настройки рейтинга",
                "verbose_name_plural": "Настройки рейтинга",
            },
        ),
    ]
