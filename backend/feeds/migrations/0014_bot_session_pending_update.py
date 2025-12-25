from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0013_bot_session_instructions_sent"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsession",
            name="pending_update_post_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="botsession",
            name="pending_update_message",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
