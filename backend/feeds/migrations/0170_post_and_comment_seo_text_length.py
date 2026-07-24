from django.db import migrations, models


def backfill_seo_text_lengths(apps, schema_editor):
    from feeds.seo_indexing import plain_text_length

    Post = apps.get_model("feeds", "Post")
    PostComment = apps.get_model("feeds", "PostComment")

    post_batch = []
    for post in Post.objects.only("id", "content").iterator(chunk_size=500):
        post.seo_text_length = plain_text_length(post.content)
        post_batch.append(post)
        if len(post_batch) >= 500:
            Post.objects.bulk_update(post_batch, ["seo_text_length"], batch_size=500)
            post_batch.clear()
    if post_batch:
        Post.objects.bulk_update(post_batch, ["seo_text_length"], batch_size=500)

    comment_batch = []
    for comment in PostComment.objects.only("id", "body").iterator(chunk_size=500):
        comment.seo_text_length = plain_text_length(comment.body)
        comment_batch.append(comment)
        if len(comment_batch) >= 500:
            PostComment.objects.bulk_update(
                comment_batch,
                ["seo_text_length"],
                batch_size=500,
            )
            comment_batch.clear()
    if comment_batch:
        PostComment.objects.bulk_update(
            comment_batch,
            ["seo_text_length"],
            batch_size=500,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0169_post_original_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="seo_text_length",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="postcomment",
            name="seo_text_length",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(backfill_seo_text_lengths, migrations.RunPython.noop),
    ]
