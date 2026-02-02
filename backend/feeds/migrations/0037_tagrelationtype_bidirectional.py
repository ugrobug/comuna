from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0036_remove_tag_synonym"),
    ]

    operations = [
        migrations.AddField(
            model_name="tagrelationtype",
            name="is_bidirectional",
            field=models.BooleanField(default=False),
        ),
    ]
