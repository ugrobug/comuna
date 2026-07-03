from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0152_contenttranslationsettings_contenttranslationrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="userfeedsettings",
            name="keyboard_shortcuts_hint_dismissed",
            field=models.BooleanField(default=False),
        ),
    ]
