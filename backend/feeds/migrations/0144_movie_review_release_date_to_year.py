from __future__ import annotations

import re

from django.db import migrations


def _release_year(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", raw)
    return match.group(1) if match else ""


def movie_review_release_date_to_year(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    posts = Post.objects.filter(raw_data__template__type="movie_review").only("id", "raw_data")
    for post in posts.iterator(chunk_size=500):
        raw_data = post.raw_data
        if not isinstance(raw_data, dict):
            continue
        template = raw_data.get("template")
        if not isinstance(template, dict):
            continue
        data = template.get("data")
        if not isinstance(data, dict):
            continue
        current_release_date = data.get("release_date")
        release_year = _release_year(current_release_date)
        if not release_year or current_release_date == release_year:
            continue

        next_data = {**data, "release_date": release_year}
        next_template = {**template, "data": next_data}
        post.raw_data = {**raw_data, "template": next_template}
        post.save(update_fields=["raw_data"])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0143_posttranslation"),
    ]

    operations = [
        migrations.RunPython(movie_review_release_date_to_year, noop_reverse),
    ]
