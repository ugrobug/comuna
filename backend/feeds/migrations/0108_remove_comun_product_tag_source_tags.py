from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0107_comuncategory_hide_from_home"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="comun",
            name="product_tag",
        ),
        migrations.RemoveField(
            model_name="comun",
            name="source_tags",
        ),
    ]
