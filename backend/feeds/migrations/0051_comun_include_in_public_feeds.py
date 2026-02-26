from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0050_siteuserprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="include_in_public_feeds",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Если выключено, посты, созданные внутри этой комуны, не попадут в "
                    "Горячее и Свежее (останутся в ленте комуны и персональных лентах)."
                ),
                verbose_name="Показывать посты комуны в Горячем и Свежее",
            ),
        ),
    ]
