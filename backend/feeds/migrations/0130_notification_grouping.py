from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0129_telegramaccount_oidc_sub"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitenotificationpreference",
            name="grouping_period",
            field=models.CharField(
                choices=[
                    ("none", "Не группировать"),
                    ("day", "За день"),
                    ("week", "За неделю"),
                ],
                default="none",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="sitenotification",
            name="group_count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="sitenotification",
            name="group_key",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddIndex(
            model_name="sitenotification",
            index=models.Index(
                fields=["user", "event_key", "group_key"],
                name="feeds_siten_user_id_2de827_idx",
            ),
        ),
    ]
