import random

from django.db import migrations
from django.db.models import Q


def rebalance_fake_views_targets(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    qs = Post.objects.filter(Q(fake_views_target__lt=30) | Q(fake_views_target__gt=400)).only(
        "id", "fake_views_target"
    )
    for post in qs.iterator(chunk_size=500):
        post.fake_views_target = random.randint(30, 400)
        post.save(update_fields=["fake_views_target"])


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0045_reduce_fake_views_target_range"),
    ]

    operations = [
        migrations.RunPython(rebalance_fake_views_targets, migrations.RunPython.noop),
    ]
