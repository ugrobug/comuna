from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0076_comuncategory_comun_alter_comuncategory_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="only_moderators_can_post",
            field=models.BooleanField(
                default=False,
                help_text="Если включено, писать в коммуну смогут только ее создатель, модераторы и администраторы сайта.",
                verbose_name="Публикация только для создателя и модераторов",
            ),
        ),
    ]
