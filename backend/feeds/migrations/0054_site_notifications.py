from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0053_comun_votes_and_rating"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteNotificationPreference",
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
                ("event_key", models.CharField(max_length=80)),
                ("site_enabled", models.BooleanField(default=True)),
                ("telegram_enabled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Настройка уведомления",
                "verbose_name_plural": "Настройки уведомлений",
                "unique_together": {("user", "event_key")},
            },
        ),
        migrations.CreateModel(
            name="SiteNotification",
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
                ("event_key", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField(blank=True)),
                ("link_url", models.CharField(blank=True, max_length=500)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("is_site", models.BooleanField(default=True)),
                ("is_telegram", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("telegram_sent_at", models.DateTimeField(blank=True, null=True)),
                ("telegram_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Уведомление",
                "verbose_name_plural": "Уведомления",
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="sitenotificationpreference",
            index=models.Index(fields=["user", "event_key"], name="feeds_siteno_user_id_aac9f6_idx"),
        ),
        migrations.AddIndex(
            model_name="sitenotification",
            index=models.Index(fields=["user", "created_at"], name="feeds_siteno_user_id_ca2769_idx"),
        ),
        migrations.AddIndex(
            model_name="sitenotification",
            index=models.Index(fields=["user", "read_at"], name="feeds_siteno_user_id_109bc3_idx"),
        ),
        migrations.AddIndex(
            model_name="sitenotification",
            index=models.Index(fields=["user", "is_site"], name="feeds_siteno_user_id_1be7a4_idx"),
        ),
    ]
