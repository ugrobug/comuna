from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, F, IntegerField, OuterRef, Q, Value
from django.db.models.functions import Cast
from django.utils import timezone

from communities.models import Comun, ComunPostCategoryAssignment
from feeds.models import Author, Post, PublicFeedItem, Tag
from feeds.views import _publish_ready_filter
from ratings.service import author_rating_value


class Command(BaseCommand):
    help = "Rebuilds materialized public feeds used by anonymous read paths."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1000)
        parser.add_argument("--fetch-multiplier", type=int, default=5)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, int(options["limit"]))
        fetch_multiplier = max(1, int(options["fetch_multiplier"]))
        dry_run = bool(options["dry_run"])
        now = timezone.now()

        combined_scaled = Cast(F("rating"), IntegerField()) * Value(20) + Cast(
            F("author__rating_total"), IntegerField()
        )
        hidden_home_tag_qs = Tag.objects.filter(
            posts__id=OuterRef("pk"),
            hide_from_home=True,
        )
        hidden_home_comun_category_post_ids = ComunPostCategoryAssignment.objects.filter(
            category__hide_from_home=True,
        ).values("post_id")

        base_query = (
            Post.objects.filter(
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(_publish_ready_filter(now))
            .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
            .annotate(combined_scaled=combined_scaled)
            .annotate(has_hidden_home_tag=Exists(hidden_home_tag_qs))
            .filter(has_hidden_home_tag=False)
            .filter(combined_scaled__gte=0)
            .exclude(id__in=hidden_home_comun_category_post_ids)
        )

        hidden_home_comun_slugs = list(
            Comun.objects.filter(hide_from_home=True).values_list("slug", flat=True)
        )
        if hidden_home_comun_slugs:
            hidden_home_comun_post_ids = (
                Post.objects.filter(
                    raw_data__source="manual_comun",
                    raw_data__comun_slug__in=hidden_home_comun_slugs,
                )
                .exclude(comun_category_assignments__category_id__isnull=False)
                .values("id")
            )
            base_query = base_query.exclude(id__in=hidden_home_comun_post_ids)

        candidates = list(
            base_query.select_related("author")
            .order_by("-created_at")[: limit * fetch_multiplier]
        )

        author_rating_map = {
            row["id"]: author_rating_value(row["rating_total"])
            for row in Author.objects.filter(id__in={post.author_id for post in candidates}).values(
                "id", "rating_total"
            )
        }

        selected: list[Post] = []
        remaining = candidates[:]
        last_author_id = None
        while remaining and len(selected) < limit:
            next_index = None
            for index, candidate in enumerate(remaining):
                if candidate.author_id != last_author_id:
                    next_index = index
                    break
            if next_index is None:
                next_index = 0
            post = remaining.pop(next_index)
            if post.rating + author_rating_map.get(post.author_id, 0) < 0:
                continue
            selected.append(post)
            last_author_id = post.author_id

        items = [
            PublicFeedItem(
                feed=PublicFeedItem.FEED_HOME,
                post=post,
                rank=index + 1,
                score=int(post.rating + post.comments_count * 5 + author_rating_map.get(post.author_id, 0)),
                post_created_at=post.created_at,
                author_id_snapshot=post.author_id,
            )
            for index, post in enumerate(selected)
        ]

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Would rebuild {PublicFeedItem.FEED_HOME} feed with {len(items)} items from {len(candidates)} candidates."
                )
            )
            return

        with transaction.atomic():
            PublicFeedItem.objects.filter(feed=PublicFeedItem.FEED_HOME).delete()
            PublicFeedItem.objects.bulk_create(items, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt {PublicFeedItem.FEED_HOME} feed with {len(items)} items from {len(candidates)} candidates."
            )
        )
