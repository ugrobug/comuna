from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from communities import views as community_views
from feeds.models import Author, Post, Rubric, Tag
from my_feed.models import ThematicFeed
from my_feed import serializers as my_feed_serializers
from my_feed import service as my_feed_service

User = get_user_model()


def _fv():
    from feeds import views as feeds_views

    return feeds_views


_serialize_thematic_feed = my_feed_serializers._serialize_thematic_feed
_serialize_feed_post_card = my_feed_serializers._serialize_feed_post_card
_thematic_feed_is_moderator = my_feed_service._thematic_feed_is_moderator
_parse_int_list = my_feed_service._parse_int_list
_normalize_thematic_feed_slug = my_feed_service._normalize_thematic_feed_slug
_can_access_thematic_folders_page = my_feed_service._can_access_thematic_folders_page
_apply_user_feed_settings_payload = my_feed_service._apply_user_feed_settings_payload
_feed_settings_have_customizations = my_feed_service._feed_settings_have_customizations
_get_or_create_user_feed_settings = my_feed_service._get_or_create_user_feed_settings
_serialize_user_feed_settings = my_feed_service._serialize_user_feed_settings


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

    source_rubric_id = getattr(comun, "source_rubric_id", None)
    if source_rubric_id:
        rubric_fallback = (
            Q(rubric_id=source_rubric_id)
            & Q(author__telegram_source_comun__isnull=True)
            & Q(comun_category_assignments__isnull=True)
            & ~Q(raw_data__source="manual_comun")
        )
        combined_filter |= rubric_fallback
        has_source = True

    return combined_filter if has_source else None


def thematic_feeds_list(request: HttpRequest) -> HttpResponse:
    feeds = (
        ThematicFeed.objects.filter(is_active=True)
        .prefetch_related("moderators", "authors", "excluded_authors", "rubrics", "tags", "blocked_tags")
        .order_by("sort_order", "name")
    )
    serialized = [_serialize_thematic_feed(feed) for feed in feeds]
    return JsonResponse({"ok": True, "feeds": serialized, "folders": serialized})


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

    settings = _apply_user_feed_settings_payload(settings, payload)
    return JsonResponse(
        {
            "ok": True,
            "settings": _serialize_user_feed_settings(settings),
            "has_customizations": _feed_settings_have_customizations(settings),
        }
    )


@csrf_exempt
def thematic_feeds_manage(request: HttpRequest) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not _can_access_thematic_folders_page(user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    if request.method == "GET":
        if user.is_staff:
            folders_qs = ThematicFeed.objects.all()
        else:
            folders_qs = ThematicFeed.objects.filter(moderators=user)
        folders = list(
            folders_qs.prefetch_related(
                "moderators", "authors", "excluded_authors", "rubrics", "tags", "blocked_tags"
            ).order_by("sort_order", "name")
        )
        authors = list(
            Author.objects.filter(is_blocked=False)
            .select_related("rubric")
            .order_by("username")
        )
        tags = list(Tag.objects.filter(is_active=True).order_by("name"))
        rubrics = list(Rubric.objects.filter(is_active=True, is_hidden=False).order_by("sort_order", "name"))
        users = list(User.objects.order_by("username").values("id", "username")) if user.is_staff else []
        return JsonResponse(
            {
                "ok": True,
                "folders": [
                    _serialize_thematic_feed(folder, include_manage_fields=True)
                    for folder in folders
                ],
                "options": {
                    "users": users,
                    "authors": [
                        {
                            "id": author.id,
                            "username": author.username,
                            "title": author.title,
                            "description": author.description,
                            "rubric": author.rubric.name if author.rubric else None,
                        }
                        for author in authors
                    ],
                    "tags": [
                        {
                            "id": tag.id,
                            "name": tag.name,
                            "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
                        }
                        for tag in tags
                    ],
                    "rubrics": [
                        {
                            "id": rubric.id,
                            "name": rubric.name,
                            "slug": rubric.slug,
                            "description": rubric.description,
                        }
                        for rubric in rubrics
                    ],
                },
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if not user.is_staff:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    slug_raw = str(payload.get("slug") or "").strip()
    folder_slug = _normalize_thematic_feed_slug(slug_raw or name)
    if not name:
        return JsonResponse({"ok": False, "error": "name required"}, status=400)
    if not folder_slug:
        return JsonResponse({"ok": False, "error": "slug required"}, status=400)
    if ThematicFeed.objects.filter(slug=folder_slug).exists():
        return JsonResponse({"ok": False, "error": "slug already exists"}, status=400)
    try:
        sort_order = max(int(payload.get("sort_order", 0)), 0)
    except (TypeError, ValueError):
        sort_order = 0
    is_active = bool(payload.get("is_active", True))
    moderator_ids = _parse_int_list(payload.get("moderator_ids"))

    folder = ThematicFeed.objects.create(
        name=name,
        slug=folder_slug,
        description=description,
        sort_order=sort_order,
        is_active=is_active,
    )
    if moderator_ids:
        folder.moderators.set(User.objects.filter(id__in=moderator_ids))
    folder = (
        ThematicFeed.objects.filter(id=folder.id)
        .prefetch_related("moderators", "authors", "excluded_authors", "rubrics", "tags", "blocked_tags")
        .get()
    )
    return JsonResponse({"ok": True, "folder": _serialize_thematic_feed(folder, include_manage_fields=True)})


@csrf_exempt
def thematic_feed_manage_detail(request: HttpRequest, slug: str) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        folder = (
            ThematicFeed.objects.filter(slug=slug)
            .prefetch_related("moderators", "authors", "excluded_authors", "rubrics", "tags", "blocked_tags")
            .get()
        )
    except ThematicFeed.DoesNotExist:
        return JsonResponse({"ok": False, "error": "folder not found"}, status=404)
    if not _thematic_feed_is_moderator(user, folder):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if user.is_staff:
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                return JsonResponse({"ok": False, "error": "name required"}, status=400)
            folder.name = name
        if "slug" in payload:
            next_slug = _normalize_thematic_feed_slug(str(payload.get("slug") or ""))
            if not next_slug:
                return JsonResponse({"ok": False, "error": "slug required"}, status=400)
            if ThematicFeed.objects.exclude(id=folder.id).filter(slug=next_slug).exists():
                return JsonResponse({"ok": False, "error": "slug already exists"}, status=400)
            folder.slug = next_slug
        if "description" in payload:
            folder.description = str(payload.get("description") or "").strip()
        if "sort_order" in payload:
            try:
                folder.sort_order = max(int(payload.get("sort_order", 0)), 0)
            except (TypeError, ValueError):
                pass
        if "is_active" in payload:
            folder.is_active = bool(payload.get("is_active"))
        folder.save()
        if "moderator_ids" in payload:
            folder.moderators.set(User.objects.filter(id__in=_parse_int_list(payload.get("moderator_ids"))))

    if "author_ids" in payload:
        folder.authors.set(Author.objects.filter(id__in=_parse_int_list(payload.get("author_ids")), is_blocked=False))
    if "excluded_author_ids" in payload:
        folder.excluded_authors.set(
            Author.objects.filter(id__in=_parse_int_list(payload.get("excluded_author_ids")), is_blocked=False)
        )
    if "rubric_ids" in payload:
        folder.rubrics.set(
            Rubric.objects.filter(id__in=_parse_int_list(payload.get("rubric_ids")), is_active=True, is_hidden=False)
        )
    if "tag_ids" in payload:
        folder.tags.set(Tag.objects.filter(id__in=_parse_int_list(payload.get("tag_ids")), is_active=True))
    if "excluded_tag_ids" in payload:
        folder.blocked_tags.set(
            Tag.objects.filter(id__in=_parse_int_list(payload.get("excluded_tag_ids")), is_active=True)
        )

    folder = (
        ThematicFeed.objects.filter(id=folder.id)
        .prefetch_related("moderators", "authors", "excluded_authors", "rubrics", "tags", "blocked_tags")
        .get()
    )
    return JsonResponse({"ok": True, "folder": _serialize_thematic_feed(folder, include_manage_fields=True)})


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
        rubric_slugs = []
        author_usernames = saved_feed_settings["my_feed_authors"]
        tag_values = []
        comun_slugs = saved_feed_settings["my_feed_comuns"]
        comun_category_selection = saved_feed_settings["my_feed_comun_categories"]
    else:
        rubric_slugs = []
        author_usernames = _parse_string_csv(request.GET.get("authors", ""), strip_prefix="@")
        tag_values = []
        comun_slugs = _parse_string_csv(request.GET.get("comuns", ""))
        comun_category_selection = _parse_comun_category_query(
            request.GET.get("comun_categories", "")
        )
    if not rubric_slugs and not author_usernames and not tag_values and not comun_slugs:
        return JsonResponse({"ok": True, "posts": []})

    if saved_feed_settings and "hide_negative" not in request.GET:
        hide_negative = bool(saved_feed_settings["my_feed_hide_negative"])
    else:
        hide_negative_raw = request.GET.get("hide_negative", "1").lower()
        hide_negative = hide_negative_raw not in ("0", "false", "no", "off")

    rubric_ids: list[int] = []
    if rubric_slugs:
        rubric_ids = list(
            Rubric.objects.filter(
                slug__in=rubric_slugs, is_active=True, is_hidden=False
            ).values_list("id", flat=True)
        )

    author_ids: list[int] = []
    if author_usernames:
        username_filter = Q()
        for username in author_usernames[:200]:
            username_filter |= Q(username__iexact=username)
        if username_filter:
            author_ids = list(
                Author.objects.filter(username_filter, is_blocked=False).values_list("id", flat=True)
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
    if comun_slugs:
        comuns = list(
            community_views.Comun.objects.filter(is_active=True, slug__in=comun_slugs)
            .only(
                "id",
                "slug",
                "source_rubric_id",
                "telegram_source_author_id",
            )
        )
        for comun in comuns:
            if comun.slug in comun_category_selection:
                selected_category_slugs = comun_category_selection.get(comun.slug) or []
                if not selected_category_slugs:
                    continue
                selected_category_ids = list(
                    community_views._active_comun_category_queryset(comun)
                    .filter(slug__in=selected_category_slugs)
                    .values_list("id", flat=True)
                )
                if not selected_category_ids:
                    continue
                comun_filter = _my_feed_comun_post_membership_filter(
                    comun,
                    selected_category_ids=selected_category_ids,
                )
            else:
                comun_filter = _my_feed_comun_post_membership_filter(comun)
            if comun_filter is None:
                continue
            comun_tag_selection_q |= comun_filter
            has_comun_selection = True

    if not rubric_ids and not author_ids and not has_tag_selection and not has_comun_selection:
        return JsonResponse({"ok": True, "posts": []})

    now = timezone.now()
    hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    only_read = request.GET.get("only_read") in ("1", "true", "yes")
    read_user = current_user if (hide_read or only_read) else None
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    selection_filter = Q()
    if rubric_ids:
        selection_filter |= Q(rubric_id__in=rubric_ids)
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
    if saved_feed_settings:
        hidden_author_usernames = saved_feed_settings.get("hidden_authors") or []
        if hidden_author_usernames:
            hidden_author_filter = Q()
            for username in hidden_author_usernames[:200]:
                hidden_author_filter |= Q(author__username__iexact=username)
            if hidden_author_filter:
                base_query = base_query.exclude(hidden_author_filter)
        hidden_tag_values = [
            tag
            for tag, rule in (saved_feed_settings.get("tag_rules") or {}).items()
            if rule == "hide"
        ]
        if hidden_tag_values:
            hidden_tag_filter = Q()
            for raw_tag in hidden_tag_values[:200]:
                normalized = _fv()._normalize_tag_value(raw_tag)
                if not normalized:
                    continue
                lemma = _fv()._lemmatize_tag(normalized) or normalized
                hidden_tag_filter |= Q(tags__name__iexact=normalized) | Q(tags__lemma__iexact=lemma)
            if hidden_tag_filter:
                base_query = base_query.exclude(hidden_tag_filter).distinct()

    hidden_read_count = 0
    if hide_read and read_user:
        hidden_read_count = base_query.filter(reads__user=read_user).count()

    posts_query = base_query
    if only_read:
        posts_query = posts_query.filter(reads__user=read_user)
    elif hide_read and read_user:
        posts_query = posts_query.exclude(reads__user=read_user)

    posts = list(
        posts_query.select_related("author", "rubric")
        .prefetch_related("tags")
        .order_by("-created_at")[offset : offset + limit]
    )
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

    return JsonResponse(
        {"ok": True, "posts": serialized, "hidden_read_count": hidden_read_count}
    )


def thematic_feed_posts(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        thematic_feed = (
            ThematicFeed.objects.filter(is_active=True)
            .prefetch_related(
                "moderators", "authors", "excluded_authors", "rubrics", "tags", "blocked_tags"
            )
            .get(slug=slug)
        )
    except ThematicFeed.DoesNotExist:
        return JsonResponse({"ok": False, "error": "thematic feed not found"}, status=404)

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

    include_author_ids = list(
        thematic_feed.authors.filter(is_blocked=False).values_list("id", flat=True)
    )
    include_rubric_ids = list(
        thematic_feed.rubrics.filter(is_active=True, is_hidden=False).values_list("id", flat=True)
    )
    excluded_author_ids = list(
        thematic_feed.excluded_authors.filter(is_blocked=False).values_list("id", flat=True)
    )
    include_tags = list(thematic_feed.tags.filter(is_active=True))
    include_tag_ids = [tag.id for tag in include_tags]
    include_tag_lemmas = [
        (tag.lemma or _fv()._lemmatize_tag(tag.name) or "").strip().lower()
        for tag in include_tags
        if (tag.lemma or _fv()._lemmatize_tag(tag.name) or "").strip()
    ]
    if not include_author_ids and not include_rubric_ids and not include_tag_ids and not include_tag_lemmas:
        return JsonResponse(
            {
                "ok": True,
                "thematic_feed": _serialize_thematic_feed(thematic_feed),
                "posts": [],
                "hidden_read_count": 0,
            }
        )

    blocked_tags = list(thematic_feed.blocked_tags.filter(is_active=True))
    blocked_tag_ids = [tag.id for tag in blocked_tags]
    blocked_tag_lemmas = [
        (tag.lemma or _fv()._lemmatize_tag(tag.name) or "").strip().lower()
        for tag in blocked_tags
        if (tag.lemma or _fv()._lemmatize_tag(tag.name) or "").strip()
    ]

    now = timezone.now()
    hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    only_read = request.GET.get("only_read") in ("1", "true", "yes")
    read_user = _fv()._get_user_from_request(request) if (hide_read or only_read) else None
    current_user = read_user or _fv()._get_user_from_request(request)
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    selection_filter = Q()
    if include_author_ids:
        selection_filter |= Q(author_id__in=include_author_ids)
    if include_rubric_ids:
        selection_filter |= Q(rubric_id__in=include_rubric_ids)
    if include_tag_ids:
        selection_filter |= Q(tags__id__in=include_tag_ids)
    if include_tag_lemmas:
        selection_filter |= Q(tags__lemma__in=include_tag_lemmas)

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
    if include_tag_ids or include_tag_lemmas:
        base_query = base_query.distinct()
    if excluded_author_ids:
        base_query = base_query.exclude(author_id__in=excluded_author_ids)
    if blocked_tag_ids or blocked_tag_lemmas:
        blocked_tags_filter = Q()
        if blocked_tag_ids:
            blocked_tags_filter |= Q(tags__id__in=blocked_tag_ids)
        if blocked_tag_lemmas:
            blocked_tags_filter |= Q(tags__lemma__in=blocked_tag_lemmas)
        base_query = base_query.exclude(blocked_tags_filter).distinct()

    hidden_read_count = 0
    if hide_read and read_user:
        hidden_read_count = base_query.filter(reads__user=read_user).count()

    posts_query = base_query
    if only_read:
        posts_query = posts_query.filter(reads__user=read_user)
    elif hide_read and read_user:
        posts_query = posts_query.exclude(reads__user=read_user)

    posts = list(
        posts_query.select_related("author", "rubric")
        .prefetch_related("tags")
        .order_by("-created_at")[offset : offset + limit]
    )
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

    return JsonResponse(
        {
            "ok": True,
            "thematic_feed": _serialize_thematic_feed(thematic_feed),
            "posts": serialized,
            "hidden_read_count": hidden_read_count,
        }
    )


__all__ = [
    "auth_feed_settings",
    "my_feed",
    "thematic_feed_manage_detail",
    "thematic_feed_posts",
    "thematic_feeds_list",
    "thematic_feeds_manage",
]
