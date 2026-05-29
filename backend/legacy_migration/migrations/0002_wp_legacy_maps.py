# Таблицы маппинга (Postgres). Если они уже созданы через 0001 — пометьте:
#   python manage.py migrate legacy_migration 0002_wp_legacy_maps --fake

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0099_comun_roadmap_category_ids"),
        ("legacy_migration", "0001_wp_legacy_maps"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LegacyWpCommentMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("wp_comment_id", models.PositiveBigIntegerField(db_index=True, unique=True)),
                ("wp_post_id", models.PositiveBigIntegerField(db_index=True)),
                ("imported_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "comment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="legacy_wp_maps",
                        to="feeds.postcomment",
                    ),
                ),
            ],
            options={
                "verbose_name": "Маппинг WP comment",
                "verbose_name_plural": "Маппинги WP comments",
            },
        ),
        migrations.CreateModel(
            name="LegacyWpPostMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("wp_post_id", models.PositiveBigIntegerField(db_index=True, unique=True)),
                ("legacy_slug", models.CharField(blank=True, db_index=True, max_length=200)),
                ("legacy_url", models.URLField(blank=True, max_length=500)),
                ("imported_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "post",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="legacy_wp_maps",
                        to="feeds.post",
                    ),
                ),
            ],
            options={
                "verbose_name": "Маппинг WP post",
                "verbose_name_plural": "Маппинги WP posts",
            },
        ),
        migrations.CreateModel(
            name="LegacyWpUserMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("wp_user_id", models.PositiveBigIntegerField(db_index=True, unique=True)),
                ("wp_login", models.CharField(blank=True, max_length=60)),
                ("wp_email", models.CharField(blank=True, max_length=100)),
                ("wp_display_name", models.CharField(blank=True, max_length=250)),
                ("imported_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="legacy_wp_maps",
                        to="feeds.author",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="legacy_wp_maps",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Маппинг WP user",
                "verbose_name_plural": "Маппинги WP users",
            },
        ),
    ]
