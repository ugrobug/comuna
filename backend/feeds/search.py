"""Bounded search selection, separate from card hydration and presentation."""
from dataclasses import dataclass
import re

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import FloatField, Value
from django.utils import timezone

from feeds.models import Author, Comun, Post


@dataclass(frozen=True)
class SearchOptions:
    query: str
    page: int = 1
    limit: int = 20
    kind: str = "all"
    sort: str = "new"
    suggestions: bool = False

    @property
    def offset(self):
        return (self.page - 1) * self.limit

    @classmethod
    def parse(cls, params, *, suggestions=False):
        query = (params.get("q") or "").strip()
        if len(query) > 512:
            raise ValueError("Поисковый запрос не должен превышать 512 символов")
        def number(key, default, maximum=None):
            try:
                value = max(int(params.get(key, default)), 1)
            except (TypeError, ValueError):
                value = default
            return min(value, maximum) if maximum else value
        options = cls(query, 1 if suggestions else number("page", 1),
                      5 if suggestions else number("limit", 20, 50),
                      "all" if suggestions else (params.get("type") or "All").lower(),
                      "new" if suggestions else (params.get("sort") or "New").lower(), suggestions)
        if options.offset + options.limit > 5000:
            raise ValueError("Уточните запрос: доступны первые 5000 результатов поиска")
        return options


class SearchReader:
    """Select narrow, ordered candidates; hydrate only the requested page."""
    def __init__(self, options, *, publish_ready_filter):
        self.options = options
        self.publish_ready_filter = publish_ready_filter
        self.now = timezone.now()
        terms = re.findall(r"\w+", options.query.lower(), flags=re.UNICODE)[:8]
        self.query = SearchQuery(" & ".join(f"{term}:*" for term in terms), config="simple", search_type="raw") if terms else None

    @staticmethod
    def vector(*fields):
        return SearchVector(*fields, config="simple")

    def authors(self):
        vector = self.vector("username", "title", "description")
        return (Author.objects.filter(is_blocked=False).alias(search_vector=vector)
                .filter(search_vector=self.query)
                .annotate(search_rank=SearchRank(vector, self.query))
                .order_by("-search_rank", "username", "id"))

    def visible_posts(self):
        return Post.objects.filter(is_blocked=False, is_pending=False,
                                   companion_matched_at__isnull=True, author__is_blocked=False).filter(
                                       self.publish_ready_filter(timezone.now()))

    def post_ids(self, offset, limit):
        base = self.visible_posts()
        vector = self.vector("title", "content")
        text = base.alias(search_vector=vector).filter(search_vector=self.query)
        by_author = base.filter(author_id__in=self.authors().order_by().values("pk"))
        end = offset + limit + 1
        if self.options.sort == "new":
            order = ("-created_at", "-id")
            # UNION on narrow rows deduplicates text/author matches before pagination.
            text_rows = text.order_by(*order).values_list("id", "created_at")[:end]
            author_rows = by_author.order_by(*order).values_list("id", "created_at")[:end]
            rows = list(text_rows.union(author_rows).order_by(*order)[offset:end])
            return [row[0] for row in rows]
        # A text match has its rank even when its author also matches. Exclude it
        # from the zero-ranked author branch so UNION has one row per post.
        text_rows = text.annotate(search_rank=SearchRank(vector, self.query))
        author_rows = by_author.exclude(pk__in=text.order_by().values("pk")).annotate(
            search_rank=Value(0.0, output_field=FloatField()))
        order = ("-search_rank", "-created_at", "-id")
        fields = ("id", "created_at", "search_rank")
        rows = list(text_rows.order_by(*order).values_list(*fields)[:end].union(
            author_rows.order_by(*order).values_list(*fields)[:end]).order_by(*order)[offset:end])
        return [row[0] for row in rows]

    def posts(self):
        options = self.options
        ids = self.post_ids(options.offset, options.limit)
        hint = options.offset + len(ids)
        selected = ids[:options.limit]
        # Recheck visibility after ID selection (publication, moderation, matching).
        queryset = self.visible_posts().filter(pk__in=selected).select_related("author")
        if not options.suggestions:
            queryset = queryset.prefetch_related("tags")
        posts = {post.pk: post for post in queryset}
        return [posts[pk] for pk in selected if pk in posts], hint

    def communities(self):
        options = self.options
        limit = 3 if options.suggestions else options.limit
        vector = self.vector("name", "slug", "product_description", "target_audience", "rules_text")
        rows = list(Comun.objects.filter(is_active=True).alias(search_vector=vector)
                    .filter(search_vector=self.query).annotate(search_rank=SearchRank(vector, self.query))
                    .order_by("-search_rank", "-rating_score", "name", "id")
                    [options.offset:options.offset + limit + 1])
        return rows[:limit], options.offset + len(rows)

    def people(self):
        options = self.options
        limit = 3 if options.suggestions else options.limit
        end = options.offset + limit + 1
        users = get_user_model().objects.none()
        if options.kind in ("all", "users"):
            vector = self.vector("username", "first_name", "last_name")
            users = (get_user_model().objects.filter(is_active=True).alias(search_vector=vector)
                     .filter(search_vector=self.query).annotate(search_rank=SearchRank(vector, self.query))
                     .order_by("-search_rank", "username", "id"))
        picked, seen = [], set()
        # Keep the established author-first ordering and case-insensitive dedupe.
        # Narrow chunks avoid hydrating discarded pages/profiles or computing ratings.
        for kind, queryset in (("author", self.authors()), ("user", users)):
            start = 0
            while len(picked) < end:
                rows = list(queryset.values_list("pk", "username")[start:start + 64])
                for pk, username in rows:
                    name = (username or "").strip().lower()
                    if name and name not in seen:
                        seen.add(name)
                        picked.append((kind, pk))
                        if len(picked) == end:
                            break
                if len(rows) < 64:
                    break
                start += 64
        selected = picked[options.offset:options.offset + limit]
        authors = Author.objects.filter(is_blocked=False).in_bulk(pk for kind, pk in selected if kind == "author")
        site_users = get_user_model().objects.filter(is_active=True, pk__in=[pk for kind, pk in selected if kind == "user"]).select_related(
            "site_profile", "telegram_account", "vk_account").in_bulk()
        return [(kind, (authors if kind == "author" else site_users)[pk]) for kind, pk in selected
                if pk in (authors if kind == "author" else site_users)], options.offset + len(picked[options.offset:])


class SearchService:
    def __init__(self, reader, presenter):
        self.reader = reader
        self.presenter = presenter

    def execute(self):
        options = self.reader.options
        result = dict(ok=True, query=options.query, page=options.page, limit=options.limit,
                      posts=[], authors=[], communities=[], total_posts=0, total_authors=0, total_communities=0)
        if not options.query:
            result.update(page=1, limit=0)
        if self.reader.query is None or (options.suggestions and len(options.query) < 2):
            return result
        if options.kind in ("all", "communities"):
            rows, result["total_communities"] = self.reader.communities()
            result["communities"] = self.presenter.communities(rows)
        if options.kind in ("all", "posts"):
            rows, result["total_posts"] = self.reader.posts()
            result["posts"] = self.presenter.posts(rows, now=self.reader.now)
        if options.kind in ("all", "authors", "users"):
            rows, result["total_authors"] = self.reader.people()
            result["authors"] = self.presenter.people(rows)
        for key in ("total_posts", "total_authors", "total_communities"):
            result[key] = min(result[key], 5000)
        return result
