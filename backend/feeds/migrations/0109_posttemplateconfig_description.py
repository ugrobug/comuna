from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0108_remove_comun_product_tag_source_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="posttemplateconfig",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Короткая подсказка для пользователей в списке выбора типа публикации.",
                verbose_name="Описание шаблона",
            ),
            preserve_default=False,
        ),
    ]
