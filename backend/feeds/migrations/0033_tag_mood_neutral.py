from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0032_tag_mood"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tag",
            name="mood",
            field=models.CharField(
                choices=[
                    ("neutral", "Нейтральный"),
                    ("serious", "Серьезный"),
                    ("funny", "Веселый"),
                    ("sad", "Грустный"),
                ],
                default="neutral",
                max_length=16,
            ),
        ),
    ]
