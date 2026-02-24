from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0043_post_views"),
    ]

    operations = [
        migrations.AddField(
            model_name="postcomment",
            name="persona_key",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="postcomment",
            name="persona_username",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]

