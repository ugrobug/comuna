from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0019_author_avatar_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="channel_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
