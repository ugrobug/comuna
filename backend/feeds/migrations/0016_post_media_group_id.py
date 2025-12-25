from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0015_author_invite_url_and_session_invite_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="media_group_id",
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
