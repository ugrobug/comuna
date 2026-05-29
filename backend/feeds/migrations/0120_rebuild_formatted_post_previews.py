from django.db import migrations


def rebuild_formatted_post_previews(apps, schema_editor):
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
        ("feeds", "0119_post_preview_content_post_preview_image_url"),
    ]

    operations = [
        migrations.RunPython(rebuild_formatted_post_previews, migrations.RunPython.noop),
    ]
