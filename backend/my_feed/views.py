from __future__ import annotations

import json
from datetime import timedelta

from django.db.models import Exists, OuterRef, Q
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from communities import service as community_service
from communities import views as community_views
from feeds.models import Author, Post, PostRead
from my_feed import serializers as my_feed_serializers
from my_feed import service as my_feed_service
from my_feed.models import FeedSourcePost
from rabotaem_backend.cache import bump_public_cache_prefix

def _fv():
    from feeds import views as feeds_views

    return feeds_views


_serialize_feed_post_card = my_feed_serializers._serialize_feed_post_card
_apply_user_feed_settings_payload = my_feed_service._apply_user_feed_settings_payload
_feed_settings_have_customizations = my_feed_service._feed_settings_have_customizations
_get_or_create_user_feed_settings = my_feed_service._get_or_create_user_feed_settings
_serialize_user_feed_settings = my_feed_service._serialize_user_feed_settings

_READ_FILTER_LOOKBACK_DAYS = 14


def _parse_string_csv(value: str, *, strip_prefix: str = "") -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in str(value or "").split(","):
        item = raw_value.strip()
        if strip_prefix:
            item = item.lstrip(strip_prefix)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _parse_comun_category_query(value: str) -> dict[str, list[str]]:
    if not value:
        return {}
    try:
        parsed_comun_categories = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed_comun_categories = {}
    return my_feed_service._normalize_comun_category_selection(parsed_comun_categories)


def _my_feed_comun_post_membership_filter(
    comun,
    *,
    selected_category_ids: list[int] | None = None,
) -> Q | None:
    if selected_category_ids is not None:
        if not selected_category_ids:
            return None
        return Q(
            comun_category_assignments__comun_id=comun.id,
            comun_category_assignments__category_id__in=selected_category_ids,
        )

    comun_slug = str(getattr(comun, "slug", "") or "").strip()
    combined_filter = Q()
    has_source = False
    if comun_slug:
        combined_filter |= Q(raw_data__source="manual_comun", raw_data__comun_slug=comun_slug)
        has_source = True

    combined_filter |= Q(comun_category_assignments__comun_id=comun.id)
    has_source = True

    telegram_source_author_id = getattr(comun, "telegram_source_author_id", None)
    if telegram_source_author_id:
        combined_filter |= Q(author_id=telegram_source_author_id)
        has_source = True

    return combined_filter if has_source else None


def _hidden_author_filter(usernames: list[str], *, prefix: str = "") -> Q:
    hidden_author_filter = Q()
    for username in usernames[:200]:
        field_name = f"{prefix}author__username__iexact"
        hidden_author_filter |= Q(**{field_name: username})
    return hidden_author_filter


def _hidden_tag_filter(values: list[str], *, prefix: str = "") -> Q:
    hidden_tag_filter = Q()
    for raw_tag in values[:200]:
        normalized = _fv()._normalize_tag_value(raw_tag)
        if not normalized:
            continue
        lemma = _fv()._lemmatize_tag(normalized) or normalized
        hidden_tag_filter |= Q(**{f"{prefix}tags__name__iexact": normalized}) | Q(
            **{f"{prefix}tags__lemma__iexact": lemma}
        )
    return hidden_tag_filter


def _source_candidate_queryset(
    *,
    source_type: str,
    source_ids: list[int],
    now,
    hide_negative: bool,
    hidden_author_usernames: list[str],
    hidden_tag_values: list[str],
    read_user,
    only_read: bool,
    hide_read: bool,
):
    if not source_ids:
        return None
    qs = (
        FeedSourcePost.objects.filter(source_type=source_type, source_id__in=source_ids)
        .filter(
            post__is_blocked=False,
            post__is_pending=False,
            post__author__is_blocked=False,
        )
        .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
        .filter(Q(post__author__shadow_banned=False) | Q(post__author__force_home=True))
    )
    if hide_negative:
        qs = qs.filter(post__rating__gte=0)

    hidden_author_q = _hidden_author_filter(hidden_author_usernames, prefix="post__")
    if hidden_author_q:
        qs = qs.exclude(hidden_author_q)

    hidden_tag_q = _hidden_tag_filter(hidden_tag_values, prefix="post__")
    if hidden_tag_q:
        qs = qs.exclude(hidden_tag_q)

    if read_user and (only_read or hide_read):
        recent_read_marker = PostRead.objects.filter(
            post_id=OuterRef("post_id"),
            user=read_user,
            read_at__gte=now - timedelta(days=_READ_FILTER_LOOKBACK_DAYS),
        )
        qs = qs.annotate(recently_read=Exists(recent_read_marker))
        if only_read:
            qs = qs.filter(recently_read=True)
        elif hide_read:
            qs = qs.filter(recently_read=False)

    return qs.values("post_id", "post_created_at").distinct()


def _my_feed_posts_from_source_index(
    *,
    author_ids: list[int],
    comun_ids: list[int],
    comun_category_ids: list[int],
    has_tag_selection: bool,
    now,
    hide_negative: bool,
    hidden_author_usernames: list[str],
    hidden_tag_values: list[str],
    read_user,
    only_read: bool,
    hide_read: bool,
    offset: int,
    limit: int,
) -> list[Post] | None:
    if has_tag_selection:
        return None

    candidate_querysets = [
        queryset
        for queryset in (
            _source_candidate_queryset(
                source_type=FeedSourcePost.SOURCE_AUTHOR,
                source_ids=author_ids,
                now=now,
                hide_negative=hide_negative,
                hidden_author_usernames=hidden_author_usernames,
                hidden_tag_values=hidden_tag_values,
                read_user=read_user,
                only_read=only_read,
                hide_read=hide_read,
            ),
            _source_candidate_queryset(
                source_type=FeedSourcePost.SOURCE_COMUN,
                source_ids=comun_ids,
                now=now,
                hide_negative=hide_negative,
                hidden_author_usernames=hidden_author_usernames,
                hidden_tag_values=hidden_tag_values,
                read_user=read_user,
                only_read=only_read,
                hide_read=hide_read,
            ),
            _source_candidate_queryset(
                source_type=FeedSourcePost.SOURCE_COMUN_CATEGORY,
                source_ids=comun_category_ids,
                now=now,
                hide_negative=hide_negative,
                hidden_author_usernames=hidden_author_usernames,
                hidden_tag_values=hidden_tag_values,
                read_user=read_user,
                only_read=only_read,
                hide_read=hide_read,
            ),
        )
        if queryset is not None
    ]
    if not candidate_querysets:
        return []

    combined_queryset = candidate_querysets[0]
    if len(candidate_querysets) > 1:
        combined_queryset = combined_queryset.union(*candidate_querysets[1:])

    try:
        rows = list(
            combined_queryset.order_by("-post_created_at", "-post_id")[
                offset : offset + limit
            ]
        )
        if not rows and not FeedSourcePost.objects.exists():
            return None
    except (OperationalError, ProgrammingError):
        return None
    post_ids = [int(row["post_id"]) for row in rows]
    if not post_ids:
        return []

    posts_by_id = {
        post.id: post
        for post in Post.objects.filter(id__in=post_ids)
        .select_related("author")
        .prefetch_related("tags")
    }
    return [posts_by_id[post_id] for post_id in post_ids if post_id in posts_by_id]


@csrf_exempt
def auth_feed_settings(request: HttpRequest) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    settings = _get_or_create_user_feed_settings(user)

    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "settings": _serialize_user_feed_settings(settings),
                "has_customizations": _feed_settings_have_customizations(settings),
            }
        )

    if request.method not in ("PATCH", "POST", "PUT"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "invalid payload"}, status=400)

    previous_settings = _serialize_user_feed_settings(settings)
    settings = _apply_user_feed_settings_payload(settings, payload)
    next_settings = _serialize_user_feed_settings(settings)
    if (
        previous_settings.get("my_feed_comuns") != next_settings.get("my_feed_comuns")
        or previous_settings.get("my_feed_comun_categories")
        != next_settings.get("my_feed_comun_categories")
    ):
        community_service._sync_comun_subscriber_counts(previous_settings, next_settings)
        bump_public_cache_prefix("comuns-sidebar")
        bump_public_cache_prefix("top-comuns")
    return JsonResponse(
        {
            "ok": True,
            "settings": next_settings,
            "has_customizations": _feed_settings_have_customizations(settings),
        }
    )


def my_feed(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 200)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    current_user = _fv()._get_user_from_request(request)
    saved_feed_settings = None
    if current_user:
        saved_feed_settings = _serialize_user_feed_settings(
            _get_or_create_user_feed_settings(current_user)
        )

    if saved_feed_settings:
        author_usernames = saved_feed_settings["my_feed_authors"]
        tag_values = []
        comun_slugs = saved_feed_settings["my_feed_comuns"]
        comun_category_selection = saved_feed_settings["my_feed_comun_categories"]
    else:
        author_usernames = _parse_string_csv(request.GET.get("authors", ""), strip_prefix="@")
        tag_values = []
        comun_slugs = _parse_string_csv(request.GET.get("comuns", ""))
        comun_category_selection = _parse_comun_category_query(
            request.GET.get("comun_categories", "")
        )
    if not author_usernames and not tag_values and not comun_slugs:
        return JsonResponse({"ok": True, "posts": []})

    if saved_feed_settings and "hide_negative" not in request.GET:
        hide_negative = bool(saved_feed_settings["my_feed_hide_negative"])
    else:
        hide_negative_raw = request.GET.get("hide_negative", "1").lower()
        hide_negative = hide_negative_raw not in ("0", "false", "no", "off")

    author_ids: list[int] = []
    if author_usernames:
        username_filter = Q()
        for username in author_usernames[:200]:
            username_filter |= Q(username__iexact=username)
        if username_filter:
            author_ids = list(
                Author.objects.filter(username_filter, is_blocked=False).values_list(
                    "id",
                    flat=True,
                )
            )

    tag_selection_q = Q()
    has_tag_selection = False
    for raw_tag in tag_values[:200]:
        normalized = _fv()._normalize_tag_value(raw_tag)
        if not normalized:
            continue
        lemma = _fv()._lemmatize_tag(normalized) or normalized
        tag_selection_q |= Q(tags__name__iexact=normalized) | Q(tags__lemma__iexact=lemma)
        has_tag_selection = True

    comun_tag_selection_q = Q()
    has_comun_selection = False
    index_comun_ids: list[int] = []
    index_comun_category_ids: list[int] = []
    if comun_slugs:
        comuns = list(
            community_views.Comun.objects.filter(is_active=True, slug__in=comun_slugs)
            .only(
                "id",
                "slug",
                "telegram_source_author_id",
            )
        )
        for comun in comuns:
            if comun.slug in comun_category_selection:
                selected_category_slugs = comun_category_selection.get(comun.slug) or []
                if not selected_category_slugs:
                    continue
                active_categories = list(
                    community_views._active_comun_category_queryset(comun).values_list(
                        "slug",
                        "id",
                    )
                )
                active_category_ids = {category_id for _slug, category_id in active_categories}
                selected_category_ids = [
                    category_id
                    for slug, category_id in active_categories
                    if slug in selected_category_slugs
                ]
                if not selected_category_ids:
                    continue
                if active_category_ids and set(selected_category_ids) == active_category_ids:
                    comun_filter = _my_feed_comun_post_membership_filter(comun)
                    index_comun_ids.append(int(comun.id))
                else:
                    comun_filter = _my_feed_comun_post_membership_filter(
                        comun,
                        selected_category_ids=selected_category_ids,
                    )
                    index_comun_category_ids.extend(
                        int(category_id) for category_id in selected_category_ids
                    )
            else:
                comun_filter = _my_feed_comun_post_membership_filter(comun)
                index_comun_ids.append(int(comun.id))
            if comun_filter is None:
                continue
            comun_tag_selection_q |= comun_filter
            has_comun_selection = True

    if not author_ids and not has_tag_selection and not has_comun_selection:
        return JsonResponse({"ok": True, "posts": []})

    now = timezone.now()
    only_read = request.GET.get("only_read") in ("1", "true", "yes")
    if only_read:
        hide_read = False
    elif saved_feed_settings and "hide_read" not in request.GET:
        hide_read = bool(saved_feed_settings["hide_read_posts"])
    else:
        hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    read_user = current_user if (hide_read or only_read) else None
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    selection_filter = Q()
    if author_ids:
        selection_filter |= Q(author_id__in=author_ids)
    if has_tag_selection:
        selection_filter |= tag_selection_q
    if has_comun_selection:
        selection_filter |= comun_tag_selection_q

    base_query = (
        Post.objects.filter(
            selection_filter,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_fv()._publish_ready_filter(now))
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
    )
    if hide_negative:
        base_query = base_query.filter(rating__gte=0)
    if has_tag_selection or has_comun_selection:
        base_query = base_query.distinct()
    hidden_author_usernames: list[str] = []
    hidden_tag_values: list[str] = []
    if saved_feed_settings:
        hidden_author_usernames = saved_feed_settings.get("hidden_authors") or []
        if hidden_author_usernames:
            hidden_author_filter = _hidden_author_filter(hidden_author_usernames)
            if hidden_author_filter:
                base_query = base_query.exclude(hidden_author_filter)
        hidden_tag_values = [
            tag
            for tag, rule in (saved_feed_settings.get("tag_rules") or {}).items()
            if rule == "hide"
        ]
        if hidden_tag_values:
            hidden_tag_filter = _hidden_tag_filter(hidden_tag_values)
            if hidden_tag_filter:
                base_query = base_query.exclude(hidden_tag_filter).distinct()

    posts_query = base_query
    if read_user and (only_read or hide_read):
        recent_read_marker = PostRead.objects.filter(
            post_id=OuterRef("pk"),
            user=read_user,
            read_at__gte=now - timedelta(days=_READ_FILTER_LOOKBACK_DAYS),
        )
        posts_query = posts_query.annotate(recently_read=Exists(recent_read_marker))
        if only_read:
            posts_query = posts_query.filter(recently_read=True)
        elif hide_read:
            posts_query = posts_query.filter(recently_read=False)

    index_posts = _my_feed_posts_from_source_index(
        author_ids=sorted(set(author_ids)),
        comun_ids=sorted(set(index_comun_ids)),
        comun_category_ids=sorted(set(index_comun_category_ids)),
        has_tag_selection=has_tag_selection,
        now=now,
        hide_negative=hide_negative,
        hidden_author_usernames=hidden_author_usernames,
        hidden_tag_values=hidden_tag_values,
        read_user=read_user,
        only_read=only_read,
        hide_read=hide_read,
        offset=offset,
        limit=limit,
    )
    if index_posts is None:
        posts = list(
            posts_query.select_related("author")
            .prefetch_related("tags")
            .order_by("-created_at")[offset : offset + limit]
        )
    else:
        posts = index_posts
    favorite_post_ids = _fv()._favorite_post_ids_for_user(posts, current_user)

    serialized = [
        _serialize_feed_post_card(
            request,
            post,
            current_user,
            now=now,
            is_favorite=post.id in favorite_post_ids,
        )
        for post in posts
    ]

    return JsonResponse({"ok": True, "posts": serialized})


__all__ = [
    "auth_feed_settings",
    "my_feed",
]
