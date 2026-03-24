from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0083_comuncategory_allowed_post_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="rules_text",
            field=models.TextField(blank=True, verbose_name="Правила сообщества"),
        ),
    ]
