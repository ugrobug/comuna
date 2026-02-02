from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0035_tag_relations_multi"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tag",
            name="synonym",
        ),
    ]
