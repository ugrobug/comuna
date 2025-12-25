from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0014_bot_session_pending_update"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="invite_url",
            field=models.URLField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="botsession",
            name="invite_url",
            field=models.URLField(blank=True, max_length=255),
        ),
    ]
