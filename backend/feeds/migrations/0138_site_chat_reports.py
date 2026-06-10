# Generated manually on 2026-06-09

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0137_site_chats"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteChatParticipantState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_blocked", models.BooleanField(default=False)),
                ("hidden_at", models.DateTimeField(blank=True, null=True)),
                ("blocked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participant_states",
                        to="feeds.sitechat",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_chat_participant_states",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Состояние участника чата",
                "verbose_name_plural": "Состояния участников чатов",
            },
        ),
        migrations.CreateModel(
            name="SiteChatReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message_body_snapshot", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Новая"),
                            ("reviewed", "Обработана"),
                            ("dismissed", "Отклонена"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="feeds.sitechat",
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reports",
                        to="feeds.sitechatmessage",
                    ),
                ),
                (
                    "reported_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_chat_reports_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reporter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_chat_reports_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_site_chat_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Жалоба на сообщение чата",
                "verbose_name_plural": "Жалобы на сообщения чатов",
            },
        ),
        migrations.AddIndex(
            model_name="sitechatparticipantstate",
            index=models.Index(fields=["user", "hidden_at"], name="feeds_schatst_user_hid_idx"),
        ),
        migrations.AddIndex(
            model_name="sitechatparticipantstate",
            index=models.Index(fields=["chat", "user"], name="feeds_schatst_chat_usr_idx"),
        ),
        migrations.AddIndex(
            model_name="sitechatparticipantstate",
            index=models.Index(fields=["is_blocked", "updated_at"], name="feeds_schatst_block_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="sitechatparticipantstate",
            unique_together={("chat", "user")},
        ),
        migrations.AddIndex(
            model_name="sitechatreport",
            index=models.Index(fields=["status", "created_at"], name="feeds_schatrep_status_idx"),
        ),
        migrations.AddIndex(
            model_name="sitechatreport",
            index=models.Index(fields=["reporter", "created_at"], name="feeds_schatrep_reporter_idx"),
        ),
        migrations.AddIndex(
            model_name="sitechatreport",
            index=models.Index(fields=["reported_user", "created_at"], name="feeds_schatrep_target_idx"),
        ),
    ]
