from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0170_post_and_comment_seo_text_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="telegram_ai_summary_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Разрешает участникам привязанного Telegram-чата создавать заявки "
                    "в базу знаний из ИИ-саммари пересланных сообщений."
                ),
                verbose_name="ИИ-саммари сообщений Telegram",
            ),
        ),
        migrations.AddField(
            model_name="botsession",
            name="pending_forward_action_message_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="botsession",
            name="pending_forward_comun",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="telegram_forward_sessions",
                to="feeds.comun",
            ),
        ),
        migrations.AddField(
            model_name="botsession",
            name="pending_forward_messages",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="botsession",
            name="pending_forward_processing",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="botsession",
            name="pending_forward_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="botsession",
            name="selected_comun",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="telegram_bot_sessions",
                to="feeds.comun",
            ),
        ),
    ]
