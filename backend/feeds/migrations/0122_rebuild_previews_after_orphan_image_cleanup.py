from django.db import migrations


def rebuild_previews_after_orphan_image_cleanup(apps, schema_editor):
    from feeds.preview import build_post_preview

    Post = apps.get_model("feeds", "Post")
    batch = []
    for post in Post.objects.only("id", "content", "raw_data").iterator(chunk_size=500):
        preview = build_post_preview(post.content or "", post.raw_data)
        post.preview_content = preview["preview_content"]
        post.preview_image_url = preview["preview_image_url"]
        batch.append(post)
        if len(batch) >= 500:
            Post.objects.bulk_update(batch, ["preview_content", "preview_image_url"])
            batch.clear()
    if batch:
        Post.objects.bulk_update(batch, ["preview_content", "preview_image_url"])


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0121_rebuild_post_previews_without_media_text"),
    ]

    operations = [
        migrations.RunPython(rebuild_previews_after_orphan_image_cleanup, migrations.RunPython.noop),
    ]
