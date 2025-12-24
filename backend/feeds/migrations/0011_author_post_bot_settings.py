from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0010_rubric_home_limit_post_scores"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="auto_publish",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="author",
            name="admin_chat_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="is_pending",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="BotSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("telegram_user_id", models.BigIntegerField(unique=True)),
                ("auto_publish", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
