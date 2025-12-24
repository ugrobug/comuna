from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0009_author_description_subscribers"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubric",
            name="home_limit",
            field=models.PositiveIntegerField(default=3),
        ),
        migrations.AddField(
            model_name="post",
            name="rating",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="post",
            name="comments_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
