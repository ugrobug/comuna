# Generated manually on 2026-06-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0138_site_chat_reports"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteuserprofile",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="siteuserprofile",
            index=models.Index(fields=["deleted_at"], name="feeds_siteu_deleted_idx"),
        ),
    ]
