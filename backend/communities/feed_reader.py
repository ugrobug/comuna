"""Read a community feed without sorting or counting full post bodies."""

from django.db.models import Count, Exists, OuterRef, Q

from communities.models import ComunPostCategoryAssignment
from feeds.models import Post, PostTranslation, POST_TRANSLATION_STATUS_TRANSLATED


class CommunityFeedReader:
    def __init__(self, queryset, *, community, language):
        translations = PostTranslation.objects.filter(
            post_id=OuterRef("pk"),
            language=language,
            status=POST_TRANSLATION_STATUS_TRANSLATED,
        )
        self.community = community
        self.queryset = queryset.filter(
            Q(original_language=language) | Q(Exists(translations))
        )

    def filtered(self, category_ids=None):
        if category_ids is None:
            return self.queryset
        assignments = ComunPostCategoryAssignment.objects.filter(
            comun_id=self.community.pk,
            post_id=OuterRef("pk"),
            category_id__in=category_ids,
        )
        return self.queryset.filter(Exists(assignments))

    @staticmethod
    def count(queryset):
        return queryset.order_by().values("pk").distinct().count()

    def counts(self, categories, category_ids=None):
        total = self.count(self.queryset)
        rows = (
            ComunPostCategoryAssignment.objects.filter(
                comun_id=self.community.pk,
                category_id__isnull=False,
                post_id__in=self.queryset.order_by().values("pk"),
            )
            .values("category_id")
            .annotate(count=Count("post_id", distinct=True))
        )
        by_id = {row["category_id"]: row["count"] for row in rows}
        counts = [
            {"category_id": category.pk, "slug": category.slug, "count": by_id.get(category.pk, 0)}
            for category in categories
        ]
        return {
            "total_count": total if category_ids is None else sum(by_id.get(pk, 0) for pk in category_ids),
            "category_counts": counts,
            "uncategorized_count": max(total - sum(row["count"] for row in counts), 0),
        }

    def page(self, *, offset, limit, prefetches, category_ids=None):
        ids = list(
            self.filtered(category_ids)
            .order_by("-created_at", "-pk")
            .values_list("pk", flat=True)
            .distinct()[offset : offset + limit + 1]
        )
        # A post can be hidden/matched between the ID query and hydration.
        eligible_ids = self.filtered(category_ids).filter(pk__in=ids[:limit]).order_by().values("pk")
        posts = list(
            Post.objects.filter(pk__in=eligible_ids)
            .select_related("author", "author__telegram_source_comun")
            .prefetch_related(*prefetches)
            .order_by("-created_at", "-pk")
        )
        return posts, len(ids) > limit
