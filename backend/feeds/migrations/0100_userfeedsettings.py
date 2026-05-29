from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import my_feed.models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0099_comun_roadmap_category_ids"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserFeedSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("home_feed", models.CharField(default="hot", max_length=20)),
                ("hide_read_posts", models.BooleanField(default=False)),
                ("my_feed_rubrics", models.JSONField(blank=True, default=list)),
                ("my_feed_authors", models.JSONField(blank=True, default=list)),
                ("my_feed_tags", models.JSONField(blank=True, default=list)),
                ("my_feed_comuns", models.JSONField(blank=True, default=list)),
                ("my_feed_comun_categories", models.JSONField(blank=True, default=dict)),
                ("hidden_authors", models.JSONField(blank=True, default=list)),
                ("my_feed_hide_negative", models.BooleanField(default=True)),
                (
                    "tag_rules",
                    models.JSONField(
                        blank=True,
                        default=my_feed.models.default_feed_tag_rules,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feed_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Настройки ленты пользователя",
                "verbose_name_plural": "Настройки лент пользователей",
            },
        ),
    ]
