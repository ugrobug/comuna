# Generated manually on 2026-06-11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0139_siteuserprofile_deleted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="glossary_auto_link_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Если включено, при публикации автору будут предложены найденные в тексте термины глоссария.",
                verbose_name="Автоматически искать термины в тексте",
            ),
        ),
    ]
