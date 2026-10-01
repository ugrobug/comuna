from django.db import migrations, models, transaction


def prepare_galleries(apps, schema_editor):
    from feeds.preview import build_post_preview

    Post = apps.get_model("feeds", "Post")
    alias = schema_editor.connection.alias
    last_id = 0
    # Short transactions and row locks keep concurrent edits from being overwritten.
    while True:
        with transaction.atomic(using=alias):
            batch = list(Post.objects.using(alias).select_for_update().filter(pk__gt=last_id)
                         .order_by("pk").only("id", "content", "raw_data")[:100])
            if not batch:
                break
            for post in batch:
                post.preview_gallery = build_post_preview(post.content or "", post.raw_data)["preview_gallery"]
            populated = [post for post in batch if post.preview_gallery]
            if populated:
                Post.objects.using(alias).bulk_update(populated, ["preview_gallery"], batch_size=100)
            last_id = batch[-1].pk


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("feeds", "0177_comun_sources_feed_index")]
    operations = [
        migrations.AddField(model_name="post", name="preview_gallery",
                            field=models.JSONField(default=list, db_default=[], blank=True)),
        migrations.RunPython(prepare_galleries, migrations.RunPython.noop),
    ]
