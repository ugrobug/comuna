from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0046_reduce_fake_views_target_range_to_400"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ThematicFeed",
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
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "authors",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Авторы, посты которых будут показаны в тематической ленте.",
                        related_name="thematic_feeds",
                        to="feeds.author",
                    ),
                ),
                (
                    "blocked_tags",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Посты с этими тегами будут скрыты в папке.",
                        related_name="thematic_feeds_blocked",
                        to="feeds.tag",
                        verbose_name="Исключенные теги",
                    ),
                ),
                (
                    "excluded_authors",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Авторы, посты которых будут исключены из папки.",
                        related_name="thematic_feeds_excluded",
                        to="feeds.author",
                    ),
                ),
                (
                    "moderators",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Пользователи, которые могут редактировать состав папки.",
                        related_name="thematic_feed_moderation",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Посты с этими тегами будут добавляться в папку.",
                        related_name="thematic_feeds_included",
                        to="feeds.tag",
                        verbose_name="Теги",
                    ),
                ),
            ],
            options={
                "verbose_name": "Папка",
                "verbose_name_plural": "Папки",
                "ordering": ["sort_order", "name"],
            },
        ),
    ]
