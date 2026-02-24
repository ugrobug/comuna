from __future__ import annotations

import random

from django.db import migrations, models

import feeds.models


def backfill_fake_views_targets(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    for post in Post.objects.all().only("id", "fake_views_target").iterator(chunk_size=500):
        if not getattr(post, "fake_views_target", 0):
            post.fake_views_target = random.randint(100, 2500)
            post.save(update_fields=["fake_views_target"])


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0042_postfavorite"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="fake_views_target",
            field=models.PositiveIntegerField(
                default=feeds.models.default_post_fake_views_target
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="real_views_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_fake_views_targets, migrations.RunPython.noop),
    ]
