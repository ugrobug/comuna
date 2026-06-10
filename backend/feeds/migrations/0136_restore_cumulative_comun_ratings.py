from decimal import Decimal, ROUND_HALF_UP
import json
import re

from django.db import migrations, models
from django.db.models import Count, Q
from django.utils import timezone


COMUN_COMMENT_RATING_WEIGHT = Decimal("0.1")
INTERNAL_COMUNA_HOSTS = {
    "tambur.pub",
    "www.tambur.pub",
    "comuna.ru",
    "www.comuna.ru",
    "comun.land",
    "www.comun.land",
}
EXTERNAL_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>{}\"']+", re.IGNORECASE)


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _rating(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _publish_ready_filter(now):
    return Q(publish_at__isnull=True) | Q(publish_at__lte=now)


def _is_internal_comuna_url(url_value):
    raw_value = str(url_value or "").strip()
    if not raw_value:
        return True
    normalized = raw_value if "://" in raw_value else f"https://{raw_value}"
    try:
        from urllib.parse import urlparse

        parsed = urlparse(normalized)
    except Exception:
        return False
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    return not hostname or hostname in INTERNAL_COMUNA_HOSTS


def _text_contains_external_links(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return False
    for match in EXTERNAL_URL_RE.finditer(raw_value):
        candidate = (match.group(0) or "").strip().rstrip(".,;:!?")
        if candidate and not _is_internal_comuna_url(candidate):
            return True
    return False


def _payload_contains_external_links(title=None, content=None, raw_data=None):
    if _text_contains_external_links(title) or _text_contains_external_links(content):
        return True
    if not isinstance(raw_data, dict):
        return False
    template_payload = raw_data.get("template")
    if not template_payload:
        return False
    try:
        serialized_template = json.dumps(template_payload, ensure_ascii=False)
    except (TypeError, ValueError):
        serialized_template = str(template_payload)
    return _text_contains_external_links(serialized_template)


def _comun_posts_queryset(Post, comun, now):
    membership_filter = Q()
    has_membership = False

    telegram_source_author_id = getattr(comun, "telegram_source_author_id", None)
    if telegram_source_author_id:
        membership_filter |= Q(author_id=telegram_source_author_id)
        has_membership = True

    comun_slug = str(getattr(comun, "slug", "") or "").strip()
    if comun_slug:
        membership_filter |= Q(raw_data__source="manual_comun", raw_data__comun_slug=comun_slug)
        has_membership = True

    if not has_membership:
        return Post.objects.none()

    queryset = (
        Post.objects.filter(
            membership_filter,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .distinct()
    )

    channel_author_filter = (
        Q(author__channel_id__isnull=False)
        | Q(author__channel_url__gt="")
        | Q(author__invite_url__gt="")
    )
    if telegram_source_author_id:
        queryset = queryset.exclude(channel_author_filter & ~Q(author_id=telegram_source_author_id))
    else:
        queryset = queryset.exclude(channel_author_filter)

    try:
        excluded_author_ids = list(comun.excluded_authors.values_list("id", flat=True))
    except Exception:
        excluded_author_ids = []
    if excluded_author_ids:
        queryset = queryset.exclude(author_id__in=excluded_author_ids)

    try:
        blocked_tags = list(comun.blocked_tags.filter(is_active=True))
    except Exception:
        blocked_tags = []
    blocked_tag_ids = [tag.id for tag in blocked_tags if tag.id]
    blocked_tag_lemmas = [
        str((tag.lemma or tag.name or "")).strip().lower()
        for tag in blocked_tags
        if str((tag.lemma or tag.name or "")).strip()
    ]
    if blocked_tag_ids or blocked_tag_lemmas:
        blocked_tags_filter = Q()
        if blocked_tag_ids:
            blocked_tags_filter |= Q(tags__id__in=blocked_tag_ids)
        if blocked_tag_lemmas:
            blocked_tags_filter |= Q(tags__lemma__in=blocked_tag_lemmas)
        queryset = queryset.exclude(blocked_tags_filter).distinct()

    if bool(getattr(comun, "forbid_external_links", False)):
        blocked_post_ids = []
        for row in queryset.values("id", "title", "content", "raw_data").iterator(chunk_size=200):
            if _payload_contains_external_links(
                title=row.get("title"),
                content=row.get("content"),
                raw_data=row.get("raw_data"),
            ):
                blocked_post_ids.append(int(row["id"]))
        if blocked_post_ids:
            queryset = queryset.exclude(id__in=blocked_post_ids)

    return queryset


def restore_cumulative_comun_ratings(apps, schema_editor):
    Comun = apps.get_model("feeds", "Comun")
    ComunPostRatingContribution = apps.get_model("feeds", "ComunPostRatingContribution")
    ComunVote = apps.get_model("feeds", "ComunVote")
    Post = apps.get_model("feeds", "Post")
    now = timezone.now()

    for comun in (
        Comun.objects.filter(is_active=True)
        .exclude(slug__iexact="faq")
        .prefetch_related("excluded_authors", "blocked_tags")
        .iterator(chunk_size=100)
    ):
        posts = _comun_posts_queryset(Post, comun, now)
        rating_score = Decimal("0.00")
        contribution_batch = []
        for row in posts.values("id", "rating", "comments_count").iterator(chunk_size=500):
            contribution_score = _rating(
                _decimal(row.get("rating"))
                + (_decimal(row.get("comments_count")) * COMUN_COMMENT_RATING_WEIGHT)
            )
            if not contribution_score:
                continue
            rating_score += contribution_score
            contribution_batch.append(
                ComunPostRatingContribution(
                    comun_id=comun.id,
                    post_id=row["id"],
                    score=contribution_score,
                )
            )
            if len(contribution_batch) >= 500:
                ComunPostRatingContribution.objects.bulk_create(
                    contribution_batch,
                    ignore_conflicts=True,
                )
                contribution_batch = []
        if contribution_batch:
            ComunPostRatingContribution.objects.bulk_create(
                contribution_batch,
                ignore_conflicts=True,
            )

        votes = ComunVote.objects.filter(comun_id=comun.id).aggregate(
            up=Count("id", filter=Q(value=1)),
            down=Count("id", filter=Q(value=-1)),
        )
        Comun.objects.filter(id=comun.id).update(
            rating_score=_rating(rating_score),
            votes_up=int(votes.get("up") or 0),
            votes_down=int(votes.get("down") or 0),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0135_feedsourcepost"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComunPostRatingContribution",
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
                ("score", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "comun",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="post_rating_contributions",
                        to="feeds.comun",
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="comun_rating_contributions",
                        to="feeds.post",
                    ),
                ),
            ],
            options={
                "verbose_name": "Вклад поста в рейтинг комуны",
                "verbose_name_plural": "Вклады постов в рейтинг коммун",
                "indexes": [
                    models.Index(fields=["comun", "-score"], name="comprc_comun_score_idx"),
                    models.Index(fields=["post", "comun"], name="comprc_post_comun_idx"),
                ],
                "unique_together": {("comun", "post")},
            },
        ),
        migrations.RunPython(restore_cumulative_comun_ratings, migrations.RunPython.noop),
    ]
