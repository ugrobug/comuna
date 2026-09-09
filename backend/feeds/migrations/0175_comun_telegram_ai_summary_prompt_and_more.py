from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0174_post_translation_text_length"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comun",
            name="telegram_ai_summary_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Разрешает участникам привязанного Telegram-чата создавать заявки "
                    "в базу знаний из ИИ-саммари пересланных сообщений."
                ),
                verbose_name="ИИ функции",
            ),
        ),
        migrations.AddField(
            model_name="comun",
            name="telegram_ai_summary_prompt",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Дополнительные инструкции создателя сообщества для саммари "
                    "сообщений из привязанного Telegram-чата."
                ),
                verbose_name="Промт для ИИ-саммари Telegram",
            ),
        ),
    ]
