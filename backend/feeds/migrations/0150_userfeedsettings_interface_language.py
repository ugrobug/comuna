from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0149_posttranslation_more_languages"),
    ]

    operations = [
        migrations.AddField(
            model_name="userfeedsettings",
            name="interface_language",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
    ]
