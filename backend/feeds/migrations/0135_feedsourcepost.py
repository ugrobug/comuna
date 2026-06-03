from django.db import migrations, models
import django.db.models.deletion


def backfill_feed_source_posts(apps, schema_editor):
    FeedSourcePost = apps.get_model("feeds", "FeedSourcePost")
    Post = apps.get_model("feeds", "Post")
    PostTag = apps.get_model("feeds", "Post_tags")
    Comun = apps.get_model("feeds", "Comun")
    ComunPostCategoryAssignment = apps.get_model("feeds", "ComunPostCategoryAssignment")

    batch = []

    def flush():
        nonlocal batch
        if not batch:
            return
        FeedSourcePost.objects.bulk_create(
            batch,
            batch_size=1000,
            ignore_conflicts=True,
        )
        batch = []

    def add(source_type, source_id, post_id, post_created_at):
        if not source_id or not post_id or not post_created_at:
            return
        batch.append(
            FeedSourcePost(
                source_type=source_type,
                source_id=int(source_id),
                post_id=int(post_id),
                post_created_at=post_created_at,
            )
        )
        if len(batch) >= 1000:
            flush()

    for post_id, author_id, post_created_at in Post.objects.values_list(
        "id",
        "author_id",
        "created_at",
    ).iterator(chunk_size=2000):
        add("author", author_id, post_id, post_created_at)
    flush()

    comun_by_slug = {
        slug: comun_id
        for comun_id, slug in Comun.objects.exclude(slug="")
        .values_list("id", "slug")
        .iterator(chunk_size=1000)
    }
    for post_id, raw_data, post_created_at in Post.objects.values_list(
        "id",
        "raw_data",
        "created_at",
    ).iterator(chunk_size=2000):
        if not isinstance(raw_data, dict):
            continue
        if raw_data.get("source") != "manual_comun":
            continue
        comun_slug = str(raw_data.get("comun_slug") or "").strip()
        add("comun", comun_by_slug.get(comun_slug), post_id, post_created_at)
    flush()

    author_to_comun_ids = {}
    for comun_id, author_id in Comun.objects.filter(
        telegram_source_author_id__isnull=False
    ).values_list("id", "telegram_source_author_id"):
        author_to_comun_ids.setdefault(int(author_id), []).append(int(comun_id))
    if author_to_comun_ids:
        for post_id, author_id, post_created_at in Post.objects.filter(
            author_id__in=author_to_comun_ids.keys()
        ).values_list("id", "author_id", "created_at").iterator(chunk_size=2000):
            for comun_id in author_to_comun_ids.get(int(author_id), []):
                add("comun", comun_id, post_id, post_created_at)
        flush()

    for post_id, comun_id, category_id, post_created_at in (
        ComunPostCategoryAssignment.objects.select_related("post")
        .values_list("post_id", "comun_id", "category_id", "post__created_at")
        .iterator(chunk_size=2000)
    ):
        add("comun", comun_id, post_id, post_created_at)
        add("comun_category", category_id, post_id, post_created_at)
    flush()

    for post_id, tag_id, post_created_at in (
        PostTag.objects.select_related("post")
        .values_list("post_id", "tag_id", "post__created_at")
        .iterator(chunk_size=2000)
    ):
        add("tag", tag_id, post_id, post_created_at)
    flush()


def clear_feed_source_posts(apps, schema_editor):
    FeedSourcePost = apps.get_model("feeds", "FeedSourcePost")
    FeedSourcePost.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0134_comun_cached_counts"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeedSourcePost",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("author", "Автор"),
                            ("comun", "Комуна"),
                            ("comun_category", "Категория комуны"),
                            ("tag", "Тег"),
                        ],
                        max_length=32,
                    ),
                ),
                ("source_id", models.BigIntegerField()),
                ("post_created_at", models.DateTimeField()),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feed_source_links",
                        to="feeds.post",
                    ),
                ),
            ],
            options={
                "verbose_name": "Пост в источнике ленты",
                "verbose_name_plural": "Посты в источниках ленты",
            },
        ),
        migrations.AddConstraint(
            model_name="feedsourcepost",
            constraint=models.UniqueConstraint(
                fields=("source_type", "source_id", "post"),
                name="feeds_feedsourcepost_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="feedsourcepost",
            index=models.Index(
                fields=["source_type", "source_id", "-post_created_at", "post"],
                name="feedsrc_source_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="feedsourcepost",
            index=models.Index(
                fields=["post", "source_type"],
                name="feedsrc_post_type_idx",
            ),
        ),
        migrations.RunPython(backfill_feed_source_posts, clear_feed_source_posts),
    ]
