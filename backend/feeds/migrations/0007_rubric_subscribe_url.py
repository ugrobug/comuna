from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0006_rubric_cover_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubric",
            name="subscribe_url",
            field=models.URLField(blank=True, max_length=255),
        ),
    ]
