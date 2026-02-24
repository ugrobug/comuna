import random

from django.db import migrations


def rebalance_fake_views_targets(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    qs = Post.objects.filter(fake_views_target__gt=700).only("id", "fake_views_target")
    for post in qs.iterator(chunk_size=500):
        post.fake_views_target = random.randint(100, 700)
        post.save(update_fields=["fake_views_target"])


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0044_postcomment_persona_fields"),
    ]

    operations = [
        migrations.RunPython(rebalance_fake_views_targets, migrations.RunPython.noop),
    ]

