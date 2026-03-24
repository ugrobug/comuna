from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0084_comun_rules_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="comuncategory",
            name="only_moderators_can_post",
            field=models.BooleanField(
                default=False,
                help_text="Если включено, писать в эту категорию смогут только создатель сообщества, модераторы и администраторы сайта.",
                verbose_name="Публикация только для создателя и модераторов",
            ),
        ),
    ]
