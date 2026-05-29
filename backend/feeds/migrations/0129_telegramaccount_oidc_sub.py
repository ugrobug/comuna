from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0128_channel_comuns_moderator_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramaccount",
            name="oidc_sub",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
