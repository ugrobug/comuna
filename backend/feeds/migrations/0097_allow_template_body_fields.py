from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0096_comuncustomposttemplatefield_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comuncustomposttemplatefield",
            name="placement",
            field=models.CharField(
                choices=[
                    ("available", "Текст"),
                    ("header", "Хедер"),
                    ("footer", "Футер"),
                ],
                default="header",
                max_length=16,
                verbose_name="Расположение",
            ),
        ),
    ]
