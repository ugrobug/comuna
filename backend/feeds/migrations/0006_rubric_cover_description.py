from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0005_remove_post_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubric",
            name="cover_image_url",
            field=models.URLField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="rubric",
            name="description",
            field=models.TextField(blank=True),
        ),
    ]
