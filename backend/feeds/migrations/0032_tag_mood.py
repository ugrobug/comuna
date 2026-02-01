from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0031_post_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="tag",
            name="mood",
            field=models.CharField(
                choices=[
                    ("serious", "Серьезный"),
                    ("funny", "Веселый"),
                    ("sad", "Грустный"),
                ],
                default="serious",
                max_length=16,
            ),
        ),
    ]
