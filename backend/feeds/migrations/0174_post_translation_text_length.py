import re

from django.db import migrations, models

from feeds.language_detection import post_language_text


_HASHTAG_RE = re.compile(r"(?<!\w)#[^\s#]+", flags=re.UNICODE)


def _post_translation_text_length(content):
    text = post_language_text("", content or "")
    text = _HASHTAG_RE.sub(" ", text)
    return len(re.sub(r"\s+", " ", text).strip())


def backfill_post_translation_text_lengths(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    batch = []
    for post in Post.objects.only("id", "content").iterator(chunk_size=500):
        post.translation_text_length = _post_translation_text_length(post.content)
        batch.append(post)
        if len(batch) >= 500:
            Post.objects.bulk_update(batch, ["translation_text_length"], batch_size=500)
            batch.clear()
    if batch:
        Post.objects.bulk_update(batch, ["translation_text_length"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0173_post_event_starts_at_posteventattendance"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="translation_text_length",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(
            backfill_post_translation_text_lengths,
            migrations.RunPython.noop,
        ),
    ]
