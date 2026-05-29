from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ratings", "0001_ratingsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="ratingsettings",
            name="home_posts_per_community_per_day",
            field=models.PositiveSmallIntegerField(default=3),
        ),
    ]
