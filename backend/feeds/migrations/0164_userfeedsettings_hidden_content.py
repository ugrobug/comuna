from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0163_contentreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="userfeedsettings",
            name="hidden_comuns",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="userfeedsettings",
            name="hidden_post_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
