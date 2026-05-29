from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0131_comun_knowledge_base"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsession",
            name="channel_flow",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="botsession",
            name="verified_user_id",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
