from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0038_author_rating_total"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="notify_comments",
            field=models.BooleanField(default=False),
        ),
    ]
