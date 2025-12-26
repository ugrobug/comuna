from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0017_bot_session_invite_waiting"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="first_post_notified",
            field=models.BooleanField(default=False),
        ),
    ]
