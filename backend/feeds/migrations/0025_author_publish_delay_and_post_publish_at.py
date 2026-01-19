from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0024_postlike_value"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="publish_delay_days",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="post",
            name="publish_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="botsession",
            name="publish_delay_days",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="botsession",
            name="selected_author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bot_sessions",
                to="feeds.author",
            ),
        ),
    ]
