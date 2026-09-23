"""Bounded hydration for the existing hot-feed selection rules."""

from django.db.models import Exists, OuterRef, Q, prefetch_related_objects

from feeds.models import PostTranslation, POST_TRANSLATION_STATUS_TRANSLATED


class HomeFeedReader:
    def __init__(self, *, language):
        self.language = language

    def for_language(self, queryset, *, prefix=""):
        translations = PostTranslation.objects.filter(
            post_id=OuterRef(f"{prefix}pk"),
            language=self.language,
            status=POST_TRANSLATION_STATUS_TRANSLATED,
        )
        return queryset.filter(
            Q(**{f"{prefix}original_language": self.language}) | Q(Exists(translations))
        )

    def load(self, queryset, *, offset=0, limit, ordering, related, prefetches):
        # DISTINCT applies only to identifiers and ordering columns, never bodies/JSON.
        ids = list(
            queryset.order_by(*ordering).values_list("pk", flat=True)
            .distinct()[offset : offset + limit]
        )
        if not ids:
            return []
        # Re-evaluate all eligibility rules: a post may be hidden/read/matched meanwhile.
        eligible_ids = queryset.filter(pk__in=ids).order_by().values("pk")
        return list(
            queryset.model.objects.filter(pk__in=eligible_ids)
            .select_related(*related)
            .prefetch_related(*prefetches)
            .order_by(*ordering)
        )


class HomeFeedCardBatch:
    """Prepare references only for cards that will actually be serialized."""

    def __init__(self, *, prepare_authors, prepare_communities):
        self.prepare_authors = prepare_authors
        self.prepare_communities = prepare_communities

    def prepare(self, request, posts, user):
        if not posts:
            return
        self.prepare_authors(request, posts)
        prefetch_related_objects(posts, "author__telegram_source_comun")
        self.prepare_communities(posts)
        if user:
            # Slug/assignment communities may already have roles prefetched.
            communities = [post._card_comun for post in posts if post._card_comun]
            prefetch_related_objects(communities, "moderators")
