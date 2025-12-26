from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0016_post_media_group_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsession",
            name="invite_waiting",
            field=models.BooleanField(default=False),
        ),
    ]
