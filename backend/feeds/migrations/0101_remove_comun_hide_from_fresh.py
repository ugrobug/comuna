from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0100_userfeedsettings"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="comun",
            name="hide_from_fresh",
        ),
    ]
