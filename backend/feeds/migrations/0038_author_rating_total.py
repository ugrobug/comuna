from django.db import migrations, models


def _backfill_author_rating_total(apps, schema_editor) -> None:
    Author = apps.get_model("feeds", "Author")
    Post = apps.get_model("feeds", "Post")
    PostCommentLike = apps.get_model("feeds", "PostCommentLike")

    from django.db.models import Count, Sum
    from django.db.models.functions import Coalesce

    post_totals = {
        row["author_id"]: int(row["total"] or 0)
        for row in Post.objects.values("author_id").annotate(total=Coalesce(Sum("rating"), 0))
        if row.get("author_id") is not None
    }

    comment_like_totals = {}
    for row in (
        PostCommentLike.objects.values("comment__post__author_id")
        .annotate(total=Count("id"))
        .iterator()
    ):
        author_id = row.get("comment__post__author_id")
        if author_id is None:
            continue
        comment_like_totals[int(author_id)] = int(row.get("total") or 0)

    author_ids = set(post_totals.keys()) | set(comment_like_totals.keys())
    if not author_ids:
        return

    batch_size = 500
    author_id_list = list(author_ids)
    for idx in range(0, len(author_id_list), batch_size):
        batch_ids = author_id_list[idx : idx + batch_size]
        authors = list(Author.objects.filter(id__in=batch_ids))
        for author in authors:
            author.rating_total = post_totals.get(author.id, 0) + comment_like_totals.get(
                author.id, 0
            )
        Author.objects.bulk_update(authors, ["rating_total"])


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0037_tagrelationtype_bidirectional"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="rating_total",
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(_backfill_author_rating_total, migrations.RunPython.noop),
    ]

