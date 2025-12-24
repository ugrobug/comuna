from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0007_rubric_subscribe_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rubric",
            name="icon_url",
            field=models.ImageField(blank=True, upload_to="rubrics/icons/"),
        ),
        migrations.AlterField(
            model_name="rubric",
            name="cover_image_url",
            field=models.ImageField(blank=True, upload_to="rubrics/covers/"),
        ),
    ]
