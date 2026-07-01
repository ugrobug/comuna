from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0148_sitechatmessage_delivered_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="posttranslation",
            name="language",
            field=models.CharField(
                choices=[
                    ("en", "Английский"),
                    ("es", "Испанский"),
                    ("pt", "Португальский"),
                    ("de", "Немецкий"),
                    ("fr", "Французский"),
                    ("tr", "Турецкий"),
                    ("id", "Индонезийский"),
                ],
                db_index=True,
                max_length=8,
            ),
        ),
    ]
