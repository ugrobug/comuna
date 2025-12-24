from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0008_rubric_images_to_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="author",
            name="subscribers_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
