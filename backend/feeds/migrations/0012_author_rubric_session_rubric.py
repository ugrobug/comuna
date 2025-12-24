from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0011_author_post_bot_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="rubric",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="authors",
                to="feeds.rubric",
            ),
        ),
        migrations.AddField(
            model_name="botsession",
            name="rubric",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="bot_sessions",
                to="feeds.rubric",
            ),
        ),
    ]
