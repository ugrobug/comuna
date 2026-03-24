from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0082_comun_forbid_external_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="comuncategory",
            name="allowed_post_templates",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Если список пустой, категория использует общие шаблоны сообщества.",
                verbose_name="Доступные шаблоны поста",
            ),
        ),
    ]
