from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0110_remove_legacy_rubrics"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ThematicFeed",
        ),
    ]
