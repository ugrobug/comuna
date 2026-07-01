from django.db import migrations, models


def backfill_delivered_at(apps, schema_editor):
    site_chat_message = apps.get_model("feeds", "SiteChatMessage")
    site_chat_message.objects.filter(delivered_at__isnull=True).update(
        delivered_at=models.F("created_at")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0147_grouped_notification_delivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitechatmessage",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_delivered_at, migrations.RunPython.noop),
    ]
