from __future__ import annotations

import json
import math
import re
import secrets
import urllib.parse
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from communities import serializers as community_serializers
from communities import service as community_service
from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunKnowledgeBaseItem,
    ComunPostCategoryAssignment,
    ComunVote,
)
from editor.models import (
    PostPollVote,
    POST_TEMPLATE_TYPE_BASIC,
    normalize_allowed_post_templates,
    normalize_allowed_post_templates_override,
    normalize_post_template_type_code,
)
from editor import service as editor_service
from feeds.models import (
    Author,
    Post,
    PostComment,
    PostCommentLike,
    PostFavorite,
    PostLike,
    PostRead,
    Tag,
)
from rabotaem_backend.cache import anonymous_cache, bump_public_cache_prefix
from ratings.service import calculate_author_rating, format_rating_value, user_max_author_rating
from users.models import AuthorAdmin
from users import views as user_views

User = get_user_model()

_COMUN_CREATION_MIN_AUTHOR_RATING = 0.0
_COMUN_ACTIVITY_POINTS = {
    "post": 10,
    "comment": 5,
    "post_vote": 2,
    "comment_like": 1,
    "poll_vote": 2,
    "favorite": 2,
    "read": 1,
}
_EXTERNAL_URL_RE = re.compile(r"""https?://[^\s<>"')\]]+|www\.[^\s<>"')\]]+""", re.IGNORECASE)
_INTERNAL_COMUNA_HOSTS = {
    "comuna.ru",
    "www.comuna.ru",
    "tambur.pub",
    "www.tambur.pub",
    "localhost",
    "127.0.0.1",
}
_COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR = (
    "В этом сообществе запрещены внешние ссылки. Удалите ссылки из текста и шаблона публикации."
)
_COMUNS_CATALOG_DEFAULT_LIMIT = 20
_COMUNS_CATALOG_MAX_LIMIT = 50


def _fv():
    from feeds import views as feeds_views

    return feeds_views


def _normalize_comun_category_name(raw_name: object) -> str:
    return re.sub(r"\s+", " ", str(raw_name or "").strip())


def _generate_unique_comun_category_slug(comun: Comun, name: str) -> str:
    normalized_name = str(name or "").strip()
    base_slug = slugify(normalized_name)[:120]
    if not base_slug:
        base_slug = _fv()._slugify_title(normalized_name)[:120]
    if not base_slug:
        return ""
    slug = base_slug
    suffix = 2
    while ComunCategory.objects.filter(comun=comun, slug=slug).exists():
        suffix_literal = f"-{suffix}"
        max_base_length = max(120 - len(suffix_literal), 1)
        slug = f"{base_slug[:max_base_length]}{suffix_literal}"
        suffix += 1
    return slug


def _ensure_comun_category_by_name(
    comun: Comun,
    raw_name: object,
) -> tuple[ComunCategory | None, bool]:
    normalized_name = _normalize_comun_category_name(raw_name)
    if not normalized_name:
        return None, False
    category = (
        ComunCategory.objects.filter(comun=comun, name__iexact=normalized_name).order_by("sort_order", "name").first()
    )
    if category:
        if not category.is_active:
            category.is_active = True
            category.save(update_fields=["is_active"])
        if not comun.categories.filter(id=category.id).exists():
            comun.categories.add(category)
        return category, False
    slug = _generate_unique_comun_category_slug(comun, normalized_name)
    if not slug:
        return None, False
    category = ComunCategory.objects.create(comun=comun, name=normalized_name, slug=slug)
    comun.categories.add(category)
    return category, True


def _normalize_comun_glossary_term(raw_value: object) -> str:
    return re.sub(r"\s+", " ", str(raw_value or "").strip())[:180]


def _normalize_comun_glossary_definition(raw_value: object) -> str:
    return str(raw_value or "").strip()[:5000]


def _generate_unique_comun_glossary_term_slug(
    comun: Comun,
    term: str,
    *,
    exclude_term_id: int | None = None,
) -> str:
    normalized_term = str(term or "").strip()
    base_slug = slugify(normalized_term)[:180]
    if not base_slug:
        base_slug = _fv()._slugify_title(normalized_term)[:180]
    if not base_slug:
        base_slug = f"term-{secrets.token_hex(4)}"
    slug = base_slug
    suffix = 2
    queryset = ComunGlossaryTerm.objects.filter(comun=comun)
    if exclude_term_id:
        queryset = queryset.exclude(id=exclude_term_id)
    while queryset.filter(slug=slug).exists():
        suffix_literal = f"-{suffix}"
        max_base_length = max(180 - len(suffix_literal), 1)
        slug = f"{base_slug[:max_base_length]}{suffix_literal}"
        suffix += 1
    return slug


def _comun_glossary_queryset(comun: Comun):
    return ComunGlossaryTerm.objects.filter(comun=comun)


def _active_comun_glossary_queryset(comun: Comun):
    return _comun_glossary_queryset(comun).filter(is_active=True)


def _serialize_comun_glossary_term(term: ComunGlossaryTerm) -> dict:
    return {
        "id": term.id,
        "term": term.term,
        "slug": term.slug,
        "definition": term.definition,
        "sort_order": term.sort_order,
    }


def _post_public_path(post: Post) -> str:
    post_title = _fv()._post_display_title(post)
    post_slug = _fv()._slugify_title(post_title)
    return f"/b/post/{post.id}-{post_slug}" if post_slug else f"/b/post/{post.id}"


def _serialize_comun_knowledge_base_item(item: ComunKnowledgeBaseItem) -> dict:
    post = getattr(item, "post", None)
    title = (item.title or "").strip()
    if not title and post:
        title = _fv()._post_display_title(post)
    if not title:
        title = "Без названия"
    return {
        "id": item.id,
        "item_type": item.item_type,
        "title": title,
        "parent_id": item.parent_id,
        "post_id": item.post_id,
        "post_path": _post_public_path(post) if post else None,
        "sort_order": item.sort_order,
    }


def _serialize_comun_knowledge_base(items: list[ComunKnowledgeBaseItem]) -> dict:
    nodes = {
        item.id: {
            **_serialize_comun_knowledge_base_item(item),
            "children": [],
        }
        for item in items
    }
    roots: list[dict] = []
    for item in items:
        node = nodes[item.id]
        parent_id = item.parent_id
        if parent_id and parent_id in nodes and parent_id != item.id:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    flat_items: list[dict] = []

    def visit(node: dict, depth: int) -> None:
        flat_node = {**node, "depth": depth}
        children = flat_node.pop("children", [])
        flat_items.append(flat_node)
        for child in children:
            visit(child, depth + 1)

    for root in roots:
        visit(root, 0)
    return {"items": roots, "flat_items": flat_items}


def _parse_positive_int_param(value: object, *, default: int, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(parsed, 1)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _serialize_comun_catalog_item(request: HttpRequest, comun: Comun) -> dict:
    tags = [
        {
            "id": tag.id,
            "name": tag.name,
            "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
        }
        for tag in comun.tags.all()
        if getattr(tag, "is_active", True)
    ]
    try:
        rating_score = round(float(getattr(comun, "rating_score", 0) or 0), 2)
    except (TypeError, ValueError):
        rating_score = 0.0
    return {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "logo_url": _comun_logo_url(request, comun),
        "product_description": comun.product_description,
        "subscribers_count": int(getattr(comun, "subscribers_count", 0) or 0),
        "authors_count": int(getattr(comun, "authors_count", 0) or 0),
        "rating": {
            "score": rating_score,
            "upvotes": int(getattr(comun, "votes_up", 0) or 0),
            "downvotes": int(getattr(comun, "votes_down", 0) or 0),
        },
        "sort_order": int(getattr(comun, "sort_order", 0) or 0),
        "tags": tags,
    }


def _parse_post_reference_to_id(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.isdigit():
        parsed = int(raw)
        return parsed if parsed > 0 else None
    match = re.search(r"/b/post/(\d+)", raw)
    if match:
        return int(match.group(1))
    return None


def _sync_comun_glossary_terms(comun: Comun, raw_terms: object) -> None:
    if not isinstance(raw_terms, list):
        return

    existing_terms = {term.id: term for term in _comun_glossary_queryset(comun)}
    kept_ids: set[int] = set()

    for index, item in enumerate(raw_terms):
        if not isinstance(item, dict):
            continue

        term_name = _normalize_comun_glossary_term(item.get("term") or item.get("name"))
        definition = _normalize_comun_glossary_definition(item.get("definition") or item.get("description"))
        if not term_name or not definition:
            continue

        term_id = _parse_post_reference_to_id(item.get("id"))
        existing_term = existing_terms.get(term_id) if term_id else None
        next_slug = _generate_unique_comun_glossary_term_slug(
            comun,
            term_name,
            exclude_term_id=existing_term.id if existing_term else None,
        )

        if existing_term:
            existing_term.term = term_name
            existing_term.definition = definition
            existing_term.slug = next_slug
            existing_term.sort_order = index
            existing_term.is_active = True
            existing_term.save(
                update_fields=[
                    "term",
                    "definition",
                    "slug",
                    "sort_order",
                    "is_active",
                    "updated_at",
                ]
            )
            kept_ids.add(existing_term.id)
            continue

        created_term = ComunGlossaryTerm.objects.create(
            comun=comun,
            term=term_name,
            definition=definition,
            slug=next_slug,
            sort_order=index,
            is_active=True,
        )
        kept_ids.add(created_term.id)

    _comun_glossary_queryset(comun).exclude(id__in=list(kept_ids)).delete()


def _comun_category_queryset(comun: Comun):
    return ComunCategory.objects.filter(comun=comun)


def _active_comun_category_queryset(comun: Comun):
    return _comun_category_queryset(comun).filter(is_active=True)


def _normalize_telegram_channel_username(value: object) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    if raw_value.startswith("@"):
        raw_value = raw_value[1:]
    elif raw_value.startswith("https://") or raw_value.startswith("http://"):
        try:
            parsed = urllib.parse.urlparse(raw_value)
        except Exception:
            return ""
        path_parts = [part for part in (parsed.path or "").split("/") if part]
        raw_value = path_parts[0] if path_parts else ""
    raw_value = raw_value.strip().lstrip("@").split("/", 1)[0].strip()
    if not raw_value:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_]{4,64}", raw_value):
        return ""
    return raw_value


def _generate_unique_comun_name(base_name: str, fallback_username: str = "") -> str:
    candidate = str(base_name or "").strip()
    if not candidate:
        normalized_username = _normalize_telegram_channel_username(fallback_username)
        candidate = f"@{normalized_username}" if normalized_username else "Сообщество"
    if not Comun.objects.filter(name__iexact=candidate).exists():
        return candidate

    normalized_username = _normalize_telegram_channel_username(fallback_username)
    if normalized_username:
        username_candidate = f"@{normalized_username}"
        if not Comun.objects.filter(name__iexact=username_candidate).exists():
            return username_candidate

    suffix = 2
    while True:
        next_candidate = f"{candidate} {suffix}"
        if not Comun.objects.filter(name__iexact=next_candidate).exists():
            return next_candidate
        suffix += 1


def _normalize_comun_slug(value: str) -> str:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    base_slug = slugify(normalized_value)[:160]
    if not base_slug:
        base_slug = _fv()._slugify_title(normalized_value)[:160]
    return str(base_slug or "").strip("-")


def _generate_unique_comun_slug(name: str) -> str:
    base_slug = _normalize_comun_slug(name)
    if not base_slug:
        return ""
    slug = base_slug
    suffix = 2
    while Comun.objects.filter(slug=slug).exists():
        suffix_literal = f"-{suffix}"
        max_base_length = max(160 - len(suffix_literal), 1)
        slug = f"{base_slug[:max_base_length]}{suffix_literal}"
        suffix += 1
    return slug


def _comun_is_moderator(user: User | None, comun: Comun) -> bool:
    if not user:
        return False
    if comun.creator_id == user.id:
        return True
    return comun.moderators.filter(id=user.id).exists()


def _comun_can_manage_moderators(user: User | None, comun: Comun) -> bool:
    if not user:
        return False
    return comun.creator_id == user.id


def _serialize_author_source_summary(
    request: HttpRequest | None,
    author: Author | None,
) -> dict | None:
    if not author:
        return None
    return {
        "id": author.id,
        "username": author.username,
        "title": (author.title or "").strip() or None,
        "channel_url": (author.invite_url or author.channel_url or "").strip() or None,
        "avatar_url": _fv()._author_avatar_url(request, author),
    }


def _current_user_verified_telegram_authors(user: User | None) -> list[Author]:
    if not user:
        return []
    return list(
        Author.objects.filter(
            admin_links__user=user,
            admin_links__verified_at__isnull=False,
            is_blocked=False,
        )
        .distinct()
        .order_by("username")
    )


def _comun_team_user_ids(comun: Comun) -> list[int]:
    team_user_ids = {int(comun.creator_id or 0)}
    for moderator_id in comun.moderators.values_list("id", flat=True):
        team_user_ids.add(int(moderator_id or 0))
    return [user_id for user_id in team_user_ids if user_id > 0]


def _author_is_managed_by_comun_team(author: Author | None, comun: Comun) -> bool:
    if not author:
        return False
    team_user_ids = _comun_team_user_ids(comun)
    if not team_user_ids:
        return False
    return AuthorAdmin.objects.filter(
        author=author,
        user_id__in=team_user_ids,
        verified_at__isnull=False,
    ).exists()


def _author_telegram_source_comun(author: Author | None) -> Comun | None:
    if not author:
        return None
    try:
        return author.telegram_source_comun
    except Comun.DoesNotExist:
        return None


def _attach_pending_comuns_for_author(author: Author | None) -> None:
    if not author:
        return
    normalized_username = _normalize_telegram_channel_username(author.username)
    if not normalized_username:
        return

    verified_owner_ids = list(
        AuthorAdmin.objects.filter(author=author, verified_at__isnull=False)
        .order_by("verified_at", "created_at", "id")
        .values_list("user_id", flat=True)
    )

    def claim_unowned_comun(comun: Comun) -> None:
        if comun.creator_id or not verified_owner_ids:
            return
        owner_id = int(verified_owner_ids[0])
        comun.creator_id = owner_id
        comun.save(update_fields=["creator", "updated_at"])
        comun.moderators.add(owner_id)

    current_comun = _author_telegram_source_comun(author)
    if current_comun:
        claim_unowned_comun(current_comun)
        community_service._sync_comun_logo_from_author(current_comun, author)

    pending_comuns = (
        Comun.objects.filter(
            telegram_channel_username__iexact=normalized_username,
            is_active=True,
        )
        .exclude(telegram_source_author_id=author.id)
        .prefetch_related("moderators")
        .select_related("creator")
        .order_by("id")
    )
    for comun in pending_comuns:
        if current_comun and current_comun.id != comun.id:
            continue
        if comun.creator_id:
            if not _author_is_managed_by_comun_team(author, comun):
                continue
        elif not verified_owner_ids:
            continue
        claim_unowned_comun(comun)
        logo_synced = community_service._sync_comun_logo_from_author(comun, author)
        comun.telegram_source_author = author
        comun.telegram_channel_username = normalized_username
        update_fields = ["telegram_source_author", "telegram_channel_username", "updated_at"]
        if logo_synced:
            update_fields.append("logo_url")
        comun.save(update_fields=update_fields)
        current_comun = comun


def _allowed_templates_for_comun(comun: Comun | None) -> list[str]:
    if not comun:
        return normalize_allowed_post_templates(None)
    return normalize_allowed_post_templates(comun.allowed_post_templates)


def _allowed_template_overrides_for_comun_category(category: ComunCategory | None) -> list[str]:
    if not category:
        return []
    return normalize_allowed_post_templates_override(category.allowed_post_templates)


def _allowed_templates_for_comun_category(
    comun: Comun | None,
    category: ComunCategory | None,
) -> list[str]:
    category_overrides = _allowed_template_overrides_for_comun_category(category)
    if category_overrides:
        return category_overrides
    return _allowed_templates_for_comun(comun)


def _post_comun_slug(post: Post) -> str:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    return str(raw_data.get("comun_slug") or "").strip()


def _format_rating_value(value: float | int | None) -> str:
    return format_rating_value(value)


def _comun_creation_access_state(user: User | None) -> tuple[bool, float, float]:
    minimum_rating = round(_COMUN_CREATION_MIN_AUTHOR_RATING, 2)
    max_author_rating = user_max_author_rating(user)
    can_create = bool(user and user.is_staff) or max_author_rating >= 0
    return can_create, minimum_rating, max_author_rating


def _normalize_comun_minimum_author_rating(value: object) -> tuple[float | None, str | None]:
    if value in (None, ""):
        return 0.0, None
    raw_value = str(value).strip().replace(",", ".")
    try:
        normalized = round(float(raw_value), 2)
    except (TypeError, ValueError):
        return None, "invalid minimum author rating"
    if not math.isfinite(normalized) or normalized < 0:
        return None, "invalid minimum author rating"
    return normalized, None


def _comun_minimum_author_rating_value(comun: Comun) -> float:
    try:
        normalized = round(float(getattr(comun, "minimum_author_rating_to_post", 0) or 0), 2)
    except (TypeError, ValueError):
        normalized = 0.0
    if not math.isfinite(normalized) or normalized < 0:
        return 0.0
    return normalized


def _comun_post_access_state(
    user: User | None,
    comun: Comun,
    *,
    author: Author | None = None,
    category: ComunCategory | None = None,
) -> tuple[bool, float, float | None]:
    minimum_rating = _comun_minimum_author_rating_value(comun)
    if not user:
        return False, minimum_rating, None
    if _comun_is_moderator(user, comun):
        return True, minimum_rating, None
    if category is None and bool(getattr(comun, "only_moderators_can_post", False)):
        return False, minimum_rating, None
    if category is not None and bool(getattr(category, "only_moderators_can_post", False)):
        return False, minimum_rating, None
    if minimum_rating <= 0:
        return True, minimum_rating, None

    if author is not None:
        author_rating = round(float(calculate_author_rating(author)), 2)
        return author_rating >= minimum_rating, minimum_rating, author_rating

    author_ids, _author_links = _fv()._public_user_author_ids(user)
    if not author_ids:
        return False, minimum_rating, 0.0

    max_author_rating = 0.0
    for linked_author in Author.objects.filter(id__in=author_ids):
        max_author_rating = max(max_author_rating, round(float(calculate_author_rating(linked_author)), 2))
    return max_author_rating >= minimum_rating, minimum_rating, max_author_rating


def _comun_post_access_error_message(
    comun: Comun,
    *,
    author_rating: float | None = None,
    category: ComunCategory | None = None,
) -> str:
    if category is not None and bool(getattr(category, "only_moderators_can_post", False)):
        return (
            f'Публикация в категории "{category.name}" доступна только создателю и модераторам.'
        )
    if category is None and bool(getattr(comun, "only_moderators_can_post", False)):
        return "Публикация без категории доступна только создателю и модераторам."
    minimum_text = _format_rating_value(_comun_minimum_author_rating_value(comun))
    if author_rating is None:
        return f"Для публикации в этой комуне нужен рейтинг автора не ниже {minimum_text}."
    current_text = _format_rating_value(author_rating)
    return (
        f"Для публикации в этой комуне нужен рейтинг автора не ниже {minimum_text}. "
        f"У выбранного автора сейчас {current_text}."
    )


def _comun_logo_url(request: HttpRequest | None, comun: Comun | None) -> str | None:
    if not comun:
        return None
    explicit_logo = str(getattr(comun, "logo_url", "") or "").strip()
    if explicit_logo:
        return explicit_logo
    return None


def _serialize_comun_profile_card(
    request: HttpRequest,
    comun: Comun,
    *,
    current_user: User | None = None,
    role: str = "moderator",
) -> dict:
    tags = list(comun.tags.filter(is_active=True).order_by("name"))
    return {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "website_url": comun.website_url,
        "logo_url": _comun_logo_url(request, comun),
        "product_description": comun.product_description,
        "rules_text": comun.rules_text,
        "target_audience": comun.target_audience,
        "role": role,
        "can_moderate": _comun_is_moderator(current_user, comun),
        "tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in tags
        ],
        "categories_count": _comun_categories_count(comun),
    }


def _serialize_comun_category(category: ComunCategory, comun: Comun | None = None) -> dict:
    category_allowed_template_types = _allowed_template_overrides_for_comun_category(category)
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "sort_order": category.sort_order,
        "only_moderators_can_post": bool(getattr(category, "only_moderators_can_post", False)),
        "hide_from_home": bool(getattr(category, "hide_from_home", False)),
        "category_allowed_template_types": category_allowed_template_types,
        "allowed_template_types": _allowed_templates_for_comun_category(comun, category),
        "inherits_comun_template_types": not bool(category_allowed_template_types),
    }


def _comun_categories_list(comun: Comun) -> list[ComunCategory]:
    prefetched_objects_cache = getattr(comun, "_prefetched_objects_cache", {})
    cached = prefetched_objects_cache.get("owned_categories")
    if cached is not None:
        return sorted(
            [
                category
                for category in cached
                if getattr(category, "is_active", True) and getattr(category, "comun_id", None) == comun.id
            ],
            key=lambda category: (
                int(getattr(category, "sort_order", 0) or 0),
                str(getattr(category, "name", "") or "").lower(),
            ),
        )
    return list(_active_comun_category_queryset(comun).order_by("sort_order", "name"))


def _comun_categories_count(comun: Comun) -> int:
    return len(_comun_categories_list(comun))


def _recalculate_comun_rating(comun_id: int) -> tuple[int, int, int]:
    counts = ComunVote.objects.filter(comun_id=comun_id).aggregate(
        up=Count("id", filter=Q(value=1)),
        down=Count("id", filter=Q(value=-1)),
    )
    votes_up = int(counts.get("up") or 0)
    votes_down = int(counts.get("down") or 0)
    rating_score = votes_up - votes_down
    Comun.objects.filter(id=comun_id).update(
        votes_up=votes_up,
        votes_down=votes_down,
        rating_score=rating_score,
    )
    return votes_up, votes_down, rating_score


def _serialize_comun_rating(
    comun: Comun,
    *,
    current_user: User | None = None,
    user_vote: int | None = None,
) -> dict:
    if user_vote is None and current_user:
        user_vote = int(
            ComunVote.objects.filter(comun_id=comun.id, user_id=current_user.id).values_list("value", flat=True).first()
            or 0
        )
    return {
        "score": int(getattr(comun, "rating_score", 0) or 0),
        "upvotes": int(getattr(comun, "votes_up", 0) or 0),
        "downvotes": int(getattr(comun, "votes_down", 0) or 0),
        "user_vote": int(user_vote or 0),
    }


def _serialize_comun(
    request: HttpRequest,
    comun: Comun,
    *,
    current_user: User | None = None,
    include_manage_fields: bool = False,
    include_options: bool = False,
    include_activity: bool = False,
) -> dict:
    categories = _comun_categories_list(comun)
    roadmap_category_ids = set(community_service._parse_int_list(getattr(comun, "roadmap_category_ids", [])))
    roadmap_categories = [category for category in categories if int(category.id) in roadmap_category_ids]
    moderators = list(comun.moderators.select_related("site_profile").order_by("username"))
    excluded_authors = list(comun.excluded_authors.filter(is_blocked=False).order_by("username"))
    telegram_source_author = getattr(comun, "telegram_source_author", None)
    tags = list(comun.tags.filter(is_active=True).order_by("name"))
    blocked_tags = list(comun.blocked_tags.filter(is_active=True).order_by("name"))
    glossary_terms = list(_active_comun_glossary_queryset(comun).order_by("sort_order", "term"))
    welcome_post_payload = None
    if comun.welcome_post_id:
        welcome_post = (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .filter(id=comun.welcome_post_id, is_blocked=False, author__is_blocked=False)
            .first()
        )
        if welcome_post and community_service._post_belongs_to_comun(comun, welcome_post):
            welcome_post_payload = editor_service._serialize_post_for_user(request, welcome_post, current_user)

    payload = {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "website_url": comun.website_url,
        "logo_url": _comun_logo_url(request, comun),
        "product_description": comun.product_description,
        "rules_text": comun.rules_text,
        "target_audience": comun.target_audience,
        "glossary_enabled": bool(getattr(comun, "glossary_enabled", False)),
        "roadmap_enabled": bool(getattr(comun, "roadmap_enabled", False)),
        "knowledge_base_enabled": bool(getattr(comun, "knowledge_base_enabled", False)),
        "roadmap_category_ids": [category.id for category in roadmap_categories],
        "roadmap_categories": [_serialize_comun_category(category, comun) for category in roadmap_categories],
        "glossary_terms": [_serialize_comun_glossary_term(term) for term in glossary_terms],
        "glossary_terms_count": len(glossary_terms),
        "minimum_author_rating_to_post": _comun_minimum_author_rating_value(comun),
        "only_moderators_can_post": bool(getattr(comun, "only_moderators_can_post", False)),
        "forbid_external_links": bool(getattr(comun, "forbid_external_links", False)),
        "rating": _serialize_comun_rating(comun, current_user=current_user),
        "hide_from_home": bool(comun.hide_from_home),
        "is_active": comun.is_active,
        "sort_order": comun.sort_order,
        "allowed_template_types": _allowed_templates_for_comun(comun),
        "template_type_options": editor_service._serialize_post_template_type_options(),
        "template_editor_blocks_by_template": editor_service._template_editor_blocks_by_template(),
        "custom_templates": editor_service._serialize_comun_custom_post_templates(comun),
        "creator": {
            "id": comun.creator_id,
            "username": comun.creator.username if getattr(comun, "creator", None) else None,
            "display_name": (
                (
                    getattr(
                        getattr(getattr(comun, "creator", None), "site_profile", None),
                        "display_name",
                        "",
                    )
                    or ""
                ).strip()
                or None
            ),
        },
        "moderators": [
            {
                "id": moderator.id,
                "username": moderator.username,
                "display_name": (
                    (getattr(getattr(moderator, "site_profile", None), "display_name", "") or "").strip() or None
                ),
            }
            for moderator in moderators
        ],
        "moderators_count": len(moderators),
        "excluded_authors_count": len(excluded_authors),
        "categories": [_serialize_comun_category(category, comun) for category in categories],
        "categories_count": len(categories),
        "telegram_source_author": _serialize_author_source_summary(request, telegram_source_author),
        "telegram_channel_username": (
            _normalize_telegram_channel_username(
                comun.telegram_channel_username or getattr(telegram_source_author, "username", "")
            )
            or None
        ),
        "tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in tags
        ],
        "blocked_tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in blocked_tags
        ],
        "excluded_tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in blocked_tags
        ],
        "excluded_authors": [
            {
                "id": author.id,
                "username": author.username,
                "title": author.title,
                "avatar_url": _fv()._author_avatar_url(request, author),
            }
            for author in excluded_authors
        ],
        "welcome_post_id": welcome_post_payload["id"] if welcome_post_payload else None,
        "welcome_post": welcome_post_payload,
        "can_moderate": _comun_is_moderator(current_user, comun),
        "can_manage_moderators": _comun_can_manage_moderators(current_user, comun),
        "can_post": _comun_post_access_state(current_user, comun)[0],
    }
    if include_activity:
        payload["activity"] = _serialize_comun_activity(request, comun)
    if include_manage_fields:
        payload["category_ids"] = [category.id for category in categories]
        payload["roadmap_category_ids"] = [category.id for category in roadmap_categories]
        payload["moderator_ids"] = [moderator.id for moderator in moderators]
        payload["tag_ids"] = [tag.id for tag in tags]
        payload["excluded_author_ids"] = [author.id for author in excluded_authors]
        payload["blocked_tag_ids"] = [tag.id for tag in blocked_tags]
        payload["excluded_tag_ids"] = [tag.id for tag in blocked_tags]
        payload["telegram_source_author_id"] = comun.telegram_source_author_id
        payload["welcome_post_ref"] = str(welcome_post_payload["id"] if welcome_post_payload else "")
    if include_options:
        verified_telegram_authors = _current_user_verified_telegram_authors(current_user)
        payload["options"] = {
            "categories": [_serialize_comun_category(category, comun) for category in categories],
            "tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
                }
                for tag in Tag.objects.filter(is_active=True).order_by("name")
            ],
            "authors": [
                {
                    "id": author.id,
                    "username": author.username,
                    "title": author.title,
                    "avatar_url": _fv()._author_avatar_url(request, author),
                }
                for author in Author.objects.filter(is_blocked=False).order_by("username")
            ],
            "telegram_channels": [
                _serialize_author_source_summary(request, author) for author in verified_telegram_authors
            ],
            "template_types": editor_service._serialize_post_template_type_options(),
            "template_editor_block_options_by_template": (
                editor_service._serialize_template_editor_block_options_by_template()
            ),
            "template_editor_blocks_by_template": editor_service._template_editor_blocks_by_template(),
            "custom_template_editor": editor_service._serialize_comun_custom_template_editor_options(),
        }
        if _comun_can_manage_moderators(current_user, comun):
            payload["options"]["users"] = [
                {
                    "id": user.id,
                    "username": user.username,
                    "display_name": (
                        (getattr(getattr(user, "site_profile", None), "display_name", "") or "").strip() or None
                    ),
                }
                for user in User.objects.filter(is_active=True).select_related("site_profile").order_by("username")
            ]
    return payload


def _serialize_comun_sidebar_item(request: HttpRequest, comun: Comun) -> dict:
    payload = _serialize_comun_catalog_item(request, comun)
    payload["can_moderate"] = bool(getattr(comun, "_sidebar_can_moderate", False))
    return payload


@anonymous_cache(prefix="comuns-sidebar", seconds=21_600, cache_authenticated=True)
def comuns_sidebar(request: HttpRequest) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    current_user = user_views._get_user_from_request(request)
    manageable_ids: set[int] = set()
    if current_user:
        manageable_ids = set(
            Comun.objects.filter(is_active=True)
            .filter(Q(creator_id=current_user.id) | Q(moderators=current_user))
            .values_list("id", flat=True)
            .distinct()
        )

    comuns = list(
        Comun.objects.filter(is_active=True)
        .exclude(slug__iexact="faq")
        .only(
            "id",
            "name",
            "slug",
            "logo_url",
            "product_description",
            "subscribers_count",
            "authors_count",
            "sort_order",
            "rating_score",
            "votes_up",
            "votes_down",
        )
        .prefetch_related(
            Prefetch(
                "tags",
                queryset=Tag.objects.filter(is_active=True)
                .only("id", "name", "lemma", "is_active")
                .order_by("name"),
            )
        )
        .order_by("-rating_score", "sort_order", "name", "id")
    )
    for comun in comuns:
        comun._sidebar_can_moderate = comun.id in manageable_ids
    return JsonResponse(
        {
            "ok": True,
            "comuns": [_serialize_comun_sidebar_item(request, comun) for comun in comuns],
        }
    )


def _comun_source_filter(comun: Comun) -> Q | None:
    combined_filter = Q()
    has_source = False

    telegram_source_author_id = getattr(comun, "telegram_source_author_id", None)
    if telegram_source_author_id:
        combined_filter |= Q(author_id=telegram_source_author_id)
        has_source = True

    return combined_filter if has_source else None


def _is_internal_comuna_url(url_value: str) -> bool:
    raw_value = str(url_value or "").strip()
    if not raw_value:
        return True
    normalized_value = raw_value if "://" in raw_value else f"https://{raw_value}"
    try:
        parsed = urllib.parse.urlparse(normalized_value)
    except Exception:
        return False
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return True
    return hostname in _INTERNAL_COMUNA_HOSTS


def _text_contains_external_links(value: str | None) -> bool:
    raw_value = str(value or "").strip()
    if not raw_value:
        return False
    for match in _EXTERNAL_URL_RE.finditer(raw_value):
        candidate = (match.group(0) or "").strip().rstrip(".,;:!?")
        if candidate and not _is_internal_comuna_url(candidate):
            return True
    return False


def _payload_contains_external_links(
    *,
    title: str | None = None,
    content: str | None = None,
    template_payload=None,
) -> bool:
    if _text_contains_external_links(title):
        return True
    if _text_contains_external_links(content):
        return True
    if template_payload:
        try:
            serialized_template = json.dumps(template_payload, ensure_ascii=False)
        except (TypeError, ValueError):
            serialized_template = str(template_payload)
        if _text_contains_external_links(serialized_template):
            return True
    return False


def _site_user_avatar_url(
    request: HttpRequest | None,
    user: User,
    *,
    fallback_author_avatars: dict[int, str | None] | None = None,
) -> str | None:
    try:
        site_profile = user.site_profile
        if site_profile and site_profile.avatar_url:
            return site_profile.avatar_url
    except Exception:
        pass
    try:
        tg = user.telegram_account
        if tg and tg.avatar_url:
            return tg.avatar_url
    except Exception:
        pass
    try:
        vk = user.vk_account
        if vk and vk.avatar_url:
            return vk.avatar_url
    except Exception:
        pass
    if fallback_author_avatars and user.id in fallback_author_avatars:
        return fallback_author_avatars.get(user.id)
    return None


def _comun_posts_base_queryset(comun: Comun, now=None):
    now = now or timezone.now()
    source_filter = _comun_source_filter(comun)
    if not source_filter:
        return Post.objects.none()
    base_query = (
        Post.objects.filter(
            source_filter,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_fv()._publish_ready_filter(now))
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
        .distinct()
    )
    excluded_author_ids = list(comun.excluded_authors.filter(is_blocked=False).values_list("id", flat=True))
    if excluded_author_ids:
        base_query = base_query.exclude(author_id__in=excluded_author_ids)

    blocked_tags = list(comun.blocked_tags.filter(is_active=True))
    blocked_tag_ids = [tag.id for tag in blocked_tags]
    blocked_tag_lemmas = [
        (tag.lemma or _fv()._lemmatize_tag(tag.name) or "").strip().lower()
        for tag in blocked_tags
        if (tag.lemma or _fv()._lemmatize_tag(tag.name) or "").strip()
    ]
    if blocked_tag_ids or blocked_tag_lemmas:
        blocked_tags_filter = Q()
        if blocked_tag_ids:
            blocked_tags_filter |= Q(tags__id__in=blocked_tag_ids)
        if blocked_tag_lemmas:
            blocked_tags_filter |= Q(tags__lemma__in=blocked_tag_lemmas)
        base_query = base_query.exclude(blocked_tags_filter).distinct()
    if bool(getattr(comun, "forbid_external_links", False)):
        blocked_post_ids: list[int] = []
        for row in base_query.values("id", "title", "content", "raw_data").iterator(chunk_size=200):
            raw_data = row.get("raw_data") if isinstance(row, dict) else {}
            template_payload, _template_error = editor_service._normalize_post_template_payload(
                raw_data.get("template") if isinstance(raw_data, dict) else None
            )
            if _payload_contains_external_links(
                title=row.get("title") if isinstance(row, dict) else None,
                content=row.get("content") if isinstance(row, dict) else None,
                template_payload=template_payload,
            ):
                blocked_post_ids.append(int(row["id"]))
        if blocked_post_ids:
            base_query = base_query.exclude(id__in=blocked_post_ids)
    return base_query


def _serialize_comun_activity(
    request: HttpRequest,
    comun: Comun,
    *,
    top_limit: int = 8,
) -> dict:
    base_posts = _comun_posts_base_queryset(comun)
    if not base_posts.exists():
        return {
            "participants_count": 0,
            "top_members": [],
            "points": dict(_COMUN_ACTIVITY_POINTS),
        }

    points_by_user: dict[int, int] = defaultdict(int)
    stats_by_user: dict[int, dict[str, int]] = defaultdict(dict)

    def _add_points(user_id: int | None, key: str, count: int) -> None:
        if not user_id or count <= 0:
            return
        multiplier = int(_COMUN_ACTIVITY_POINTS.get(key, 0) or 0)
        if multiplier <= 0:
            return
        points_by_user[user_id] += count * multiplier
        stats_by_user[user_id][key] = stats_by_user[user_id].get(key, 0) + count

    for row in (
        PostComment.objects.filter(post__in=base_posts, is_deleted=False).values("user_id").annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "comment", int(row.get("count") or 0))

    for row in PostLike.objects.filter(post__in=base_posts).values("user_id").annotate(count=Count("id")):
        _add_points(row.get("user_id"), "post_vote", int(row.get("count") or 0))

    for row in (
        PostCommentLike.objects.filter(comment__post__in=base_posts).values("user_id").annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "comment_like", int(row.get("count") or 0))

    for row in PostPollVote.objects.filter(post__in=base_posts).values("user_id").annotate(count=Count("id")):
        _add_points(row.get("user_id"), "poll_vote", int(row.get("count") or 0))

    for row in PostFavorite.objects.filter(post__in=base_posts).values("user_id").annotate(count=Count("id")):
        _add_points(row.get("user_id"), "favorite", int(row.get("count") or 0))

    for row in PostRead.objects.filter(post__in=base_posts).values("user_id").annotate(count=Count("id")):
        _add_points(row.get("user_id"), "read", int(row.get("count") or 0))

    for row in (
        AuthorAdmin.objects.filter(verified_at__isnull=False, author__posts__in=base_posts)
        .values("user_id")
        .annotate(count=Count("author__posts", distinct=True))
    ):
        _add_points(row.get("user_id"), "post", int(row.get("count") or 0))

    if not points_by_user:
        return {
            "participants_count": 0,
            "top_members": [],
            "points": dict(_COMUN_ACTIVITY_POINTS),
        }

    user_ids_sorted = sorted(points_by_user.keys(), key=lambda uid: (-points_by_user[uid], uid))
    top_user_ids = user_ids_sorted[: max(int(top_limit or 0), 1)]

    users = list(
        User.objects.filter(id__in=top_user_ids).select_related("telegram_account", "vk_account").order_by("id")
    )
    users_by_id = {user.id: user for user in users}

    fallback_author_avatars: dict[int, str | None] = {}
    for link in (
        AuthorAdmin.objects.select_related("author")
        .filter(user_id__in=top_user_ids, verified_at__isnull=False)
        .order_by("user_id", "id")
    ):
        if link.user_id in fallback_author_avatars:
            continue
        fallback_author_avatars[link.user_id] = _fv()._author_avatar_url(request, link.author)

    top_members = []
    rank = 0
    last_points = None
    for index, user_id in enumerate(top_user_ids, start=1):
        user = users_by_id.get(user_id)
        if not user:
            continue
        points = int(points_by_user.get(user_id) or 0)
        if points <= 0:
            continue
        if last_points != points:
            rank = index
            last_points = points
        top_members.append(
            {
                "user_id": user.id,
                "username": user.username,
                "avatar_url": _site_user_avatar_url(request, user, fallback_author_avatars=fallback_author_avatars),
                "points": points,
                "rank": rank,
                "stats": stats_by_user.get(user_id, {}),
            }
        )

    return {
        "participants_count": len(points_by_user),
        "top_members": top_members,
        "points": dict(_COMUN_ACTIVITY_POINTS),
    }


@csrf_exempt
def comun_create_from_telegram_channel(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    current_user = user_views._get_user_from_request(request)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    can_create_comun, minimum_rating, max_author_rating = _comun_creation_access_state(current_user)
    if not can_create_comun:
        return JsonResponse(
            {
                "ok": False,
                "error": "insufficient author rating",
                "reason": "insufficient_author_rating",
                "minimum_author_rating": minimum_rating,
                "max_author_rating": max_author_rating,
            },
            status=403,
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    author_id = _parse_post_reference_to_id(body.get("author_id"))
    author_username = _normalize_telegram_channel_username(
        body.get("author_username") or body.get("telegram_channel_username")
    )

    author_queryset = Author.objects.filter(is_blocked=False)
    if author_id:
        author_queryset = author_queryset.filter(id=author_id)
    elif author_username:
        author_queryset = author_queryset.filter(username__iexact=author_username)
    else:
        return JsonResponse({"ok": False, "error": "author required"}, status=400)

    author = author_queryset.first()
    if not author:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    if (
        not current_user.is_staff
        and not AuthorAdmin.objects.filter(
            user=current_user,
            author=author,
            verified_at__isnull=False,
        ).exists()
    ):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    _attach_pending_comuns_for_author(author)
    existing_comun = _author_telegram_source_comun(author)
    if existing_comun and existing_comun.is_active:
        existing_comun = (
            Comun.objects.filter(id=existing_comun.id)
            .select_related("creator", "welcome_post", "telegram_source_author")
            .prefetch_related("moderators", "excluded_authors", "categories", "tags", "blocked_tags")
            .first()
        )
        return JsonResponse(
            {
                "ok": True,
                "created": False,
                "comun": _serialize_comun(
                    request,
                    existing_comun,
                    current_user=current_user,
                    include_manage_fields=True,
                    include_options=True,
                    include_activity=True,
                ),
            }
        )

    base_name = (author.title or "").strip() or f"@{author.username}"
    comun_name = _generate_unique_comun_name(base_name, author.username)
    comun_slug = _generate_unique_comun_slug(author.username or comun_name)
    if not comun_slug:
        comun_slug = _generate_unique_comun_slug(comun_name)
    if not comun_slug:
        return JsonResponse({"ok": False, "error": "unable to generate comun slug"}, status=400)

    comun = Comun.objects.create(
        name=comun_name,
        slug=comun_slug,
        creator=current_user,
        logo_url=_fv()._author_avatar_url(request, author) or "",
        product_description=(author.description or "").strip(),
        telegram_source_author=author,
        telegram_channel_username=_normalize_telegram_channel_username(author.username),
        only_moderators_can_post=True,
    )
    comun.moderators.add(current_user)
    bump_public_cache_prefix("comuns-catalog")
    bump_public_cache_prefix("comuns-sidebar")
    bump_public_cache_prefix("top-comuns")
    comun = (
        Comun.objects.filter(id=comun.id)
        .select_related("creator", "welcome_post", "telegram_source_author")
        .prefetch_related("moderators", "excluded_authors", "categories", "tags", "blocked_tags")
        .get()
    )
    return JsonResponse(
        {
            "ok": True,
            "created": True,
            "comun": _serialize_comun(
                request,
                comun,
                current_user=current_user,
                include_manage_fields=True,
                include_options=True,
                include_activity=True,
            ),
        }
    )


def _comuns_catalog_queryset(query: str = ""):
    queryset = (
        Comun.objects.filter(is_active=True)
        .exclude(slug__iexact="faq")
        .only(
            "id",
            "name",
            "slug",
            "logo_url",
            "product_description",
            "subscribers_count",
            "authors_count",
            "rating_score",
            "votes_up",
            "votes_down",
            "sort_order",
            "is_active",
        )
        .prefetch_related(
            Prefetch(
                "tags",
                queryset=Tag.objects.filter(is_active=True)
                .only("id", "name", "lemma", "is_active")
                .order_by("name"),
            )
        )
        .order_by("-rating_score", "sort_order", "name", "id")
    )
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(product_description__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(tags__lemma__icontains=query)
        ).distinct()
    return queryset


def _comuns_catalog_response(
    request: HttpRequest,
    queryset,
    *,
    page: int,
    limit: int,
    query: str,
) -> HttpResponse:
    total_comuns = queryset.count()
    total_pages = math.ceil(total_comuns / limit) if total_comuns else 0
    offset = (page - 1) * limit
    comuns = list(queryset[offset : offset + limit])

    return JsonResponse(
        {
            "ok": True,
            "comuns": [_serialize_comun_catalog_item(request, comun) for comun in comuns],
            "page": page,
            "limit": limit,
            "total_comuns": total_comuns,
            "total_pages": total_pages,
            "has_next": bool(offset + limit < total_comuns),
            "has_previous": page > 1 and total_comuns > 0,
            "query": query,
        }
    )


@anonymous_cache(prefix="comuns-catalog", seconds=21_600, cache_authenticated=True)
def comuns_catalog(request: HttpRequest) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    page = _parse_positive_int_param(request.GET.get("page"), default=1)
    limit = _parse_positive_int_param(
        request.GET.get("limit"),
        default=_COMUNS_CATALOG_DEFAULT_LIMIT,
        maximum=_COMUNS_CATALOG_MAX_LIMIT,
    )
    query = re.sub(r"\s+", " ", str(request.GET.get("q") or "").strip())[:120]
    return _comuns_catalog_response(
        request,
        _comuns_catalog_queryset(query),
        page=page,
        limit=limit,
        query=query,
    )


@csrf_exempt
@anonymous_cache(prefix="comuns-list", seconds=120)
def comuns_list_create(request: HttpRequest) -> HttpResponse:
    current_user = user_views._get_user_from_request(request)

    if request.method == "GET":
        comuns = list(
            Comun.objects.filter(is_active=True).exclude(slug__iexact="faq")
            .select_related("creator", "telegram_source_author")
            .prefetch_related("moderators", "excluded_authors", "categories", "tags", "blocked_tags")
            .order_by("-rating_score", "sort_order", "name")
        )
        payload = [
            _serialize_comun(
                request,
                comun,
                current_user=current_user,
            )
            for comun in comuns
        ]
        return JsonResponse(
            {
                "ok": True,
                "comuns": payload,
                "template_type_options": editor_service._serialize_post_template_type_options(),
                "template_editor_blocks_by_template": editor_service._template_editor_blocks_by_template(),
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    can_create_comun, minimum_rating, max_author_rating = _comun_creation_access_state(current_user)
    if not can_create_comun:
        return JsonResponse(
            {
                "ok": False,
                "error": "insufficient author rating",
                "reason": "insufficient_author_rating",
                "minimum_author_rating": minimum_rating,
                "max_author_rating": max_author_rating,
            },
            status=403,
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    name = str(body.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "name required"}, status=400)
    slug = _generate_unique_comun_slug(name)
    if not slug:
        return JsonResponse({"ok": False, "error": "slug required"}, status=400)
    if Comun.objects.filter(name__iexact=name).exists():
        return JsonResponse({"ok": False, "error": "name already exists"}, status=400)

    website_url = str(body.get("website_url") or "").strip()
    logo_url = str(body.get("logo_url") or "").strip()
    product_description = str(body.get("description") or body.get("product_description") or "").strip()
    rules_text = str(body.get("rules_text") or body.get("rules") or "").strip()
    target_audience = str(body.get("target_audience") or "").strip()
    allowed_template_types = normalize_allowed_post_templates(body.get("allowed_template_types"))
    tag_ids = community_service._parse_int_list(body.get("tag_ids"))[:5]
    raw_tag_names = body.get("tag_names") if isinstance(body.get("tag_names"), list) else []
    category_ids = community_service._parse_int_list(body.get("category_ids"))
    welcome_post_id = _parse_post_reference_to_id(body.get("welcome_post_id") or body.get("welcome_post_ref"))
    selected_tag_ids: list[int] = []
    seen_tag_ids: set[int] = set()
    for tag_id in tag_ids:
        if tag_id in seen_tag_ids:
            continue
        seen_tag_ids.add(tag_id)
        selected_tag_ids.append(tag_id)
    for raw_tag_name in raw_tag_names:
        tag, _created = community_service._ensure_tag_by_name(str(raw_tag_name or ""))
        if not tag or tag.id in seen_tag_ids:
            continue
        seen_tag_ids.add(tag.id)
        selected_tag_ids.append(tag.id)
        if len(selected_tag_ids) >= 5:
            break
    comun = Comun.objects.create(
        name=name,
        slug=slug,
        creator=current_user,
        website_url=website_url,
        logo_url=logo_url,
        product_description=product_description,
        rules_text=rules_text,
        target_audience=target_audience,
        allowed_post_templates=allowed_template_types,
    )
    comun.moderators.add(current_user)
    if category_ids:
        comun.categories.set(ComunCategory.objects.filter(id__in=category_ids, is_active=True, comun=comun))
    if selected_tag_ids:
        comun.tags.set(Tag.objects.filter(id__in=selected_tag_ids, is_active=True))
    if welcome_post_id:
        welcome_post = Post.objects.filter(id=welcome_post_id, is_blocked=False, author__is_blocked=False).first()
        if welcome_post and community_service._post_belongs_to_comun(comun, welcome_post):
            comun.welcome_post = welcome_post
    comun.save()
    bump_public_cache_prefix("comuns-catalog")
    bump_public_cache_prefix("comuns-sidebar")
    bump_public_cache_prefix("top-comuns")

    comun = (
        Comun.objects.filter(id=comun.id)
        .select_related("creator", "welcome_post", "telegram_source_author")
        .prefetch_related("moderators", "excluded_authors", "categories", "tags", "blocked_tags")
        .get()
    )
    return JsonResponse(
        {"ok": True, "comun": _serialize_comun(request, comun, current_user=current_user, include_manage_fields=True)}
    )


def _normalize_composer_allowed_templates(
    raw_value: object,
    available_values: list[str],
    *,
    fallback_to_default: bool,
) -> list[str]:
    if isinstance(raw_value, str):
        candidates = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = list(raw_value)
    else:
        candidates = []

    available_set = set(available_values)
    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = normalize_post_template_type_code(candidate)
        if not value or value not in available_set or value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    if normalized or not fallback_to_default:
        return normalized
    if POST_TEMPLATE_TYPE_BASIC in available_set:
        return [POST_TEMPLATE_TYPE_BASIC]
    return available_values[:1]


def _composer_prefetched_user_is_moderator(user: User, comun: Comun) -> bool:
    if comun.creator_id == user.id:
        return True
    moderators = getattr(comun, "_prefetched_objects_cache", {}).get("moderators")
    if moderators is None:
        return comun.moderators.filter(id=user.id).exists()
    return any(moderator.id == user.id for moderator in moderators)


@csrf_exempt
def comuns_composer(request: HttpRequest) -> HttpResponse:
    current_user = user_views._get_user_from_request(request)
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    template_type_options = editor_service._serialize_post_template_type_options()
    template_editor_blocks_by_template = editor_service._template_editor_blocks_by_template()
    available_template_values = [
        normalize_post_template_type_code(option.get("value"))
        for option in template_type_options
        if normalize_post_template_type_code(option.get("value"))
    ]
    subscribed_comun_slugs = community_serializers._subscribed_comun_slugs_for_user(current_user)
    personal_author_rating_loaded = False
    personal_author_rating = 0.0

    def current_author_rating() -> float:
        nonlocal personal_author_rating_loaded, personal_author_rating
        if personal_author_rating_loaded:
            return personal_author_rating
        personal_author_rating_loaded = True
        personal_author = community_service._personal_user_author(current_user)
        if not personal_author:
            return personal_author_rating
        personal_author_rating = round(float(calculate_author_rating(personal_author)), 2)
        return personal_author_rating

    def can_post_to(
        comun: Comun,
        *,
        category: ComunCategory | None = None,
        can_moderate: bool,
    ) -> bool:
        if can_moderate:
            return True
        if category is None and bool(getattr(comun, "only_moderators_can_post", False)):
            return False
        if category is not None and bool(getattr(category, "only_moderators_can_post", False)):
            return False
        minimum_rating = _comun_minimum_author_rating_value(comun)
        if minimum_rating <= 0:
            return True
        return current_author_rating() >= minimum_rating

    def serialize_category(
        comun: Comun,
        category: ComunCategory,
        comun_allowed_template_types: list[str],
        *,
        can_post: bool,
    ) -> dict:
        category_allowed_template_types = _normalize_composer_allowed_templates(
            getattr(category, "allowed_post_templates", []),
            available_template_values,
            fallback_to_default=False,
        )
        return {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "sort_order": category.sort_order,
            "only_moderators_can_post": bool(getattr(category, "only_moderators_can_post", False)),
            "hide_from_home": bool(getattr(category, "hide_from_home", False)),
            "category_allowed_template_types": category_allowed_template_types,
            "allowed_template_types": category_allowed_template_types or comun_allowed_template_types,
            "inherits_comun_template_types": not bool(category_allowed_template_types),
            "can_post": bool(can_post),
        }

    composer_scope_filter = (
        Q(slug__in=subscribed_comun_slugs)
        | Q(creator_id=current_user.id)
        | Q(moderators__id=current_user.id)
    )
    queryset = (
        Comun.objects.filter(is_active=True)
        .exclude(slug__iexact="faq")
        .filter(composer_scope_filter)
        .only(
            "id",
            "name",
            "slug",
            "creator_id",
            "logo_url",
            "product_description",
            "rules_text",
            "glossary_enabled",
            "minimum_author_rating_to_post",
            "only_moderators_can_post",
            "forbid_external_links",
            "allowed_post_templates",
            "rating_score",
            "sort_order",
            "is_active",
        )
        .prefetch_related(
            Prefetch("moderators", queryset=User.objects.only("id")),
            Prefetch(
                "owned_categories",
                queryset=ComunCategory.objects.filter(is_active=True).order_by("sort_order", "name"),
            ),
        )
        .distinct()
        .order_by("-rating_score", "sort_order", "name")
    )

    payload: list[dict] = []
    glossary_comun_ids: list[int] = []
    for comun in queryset:
        can_moderate = _composer_prefetched_user_is_moderator(current_user, comun)
        is_subscribed = comun.slug in subscribed_comun_slugs
        comun_allowed_template_types = _normalize_composer_allowed_templates(
            getattr(comun, "allowed_post_templates", []),
            available_template_values,
            fallback_to_default=True,
        )
        categories = _comun_categories_list(comun)
        can_post_without_category = can_post_to(comun, can_moderate=can_moderate)
        category_can_post_by_id = {
            category.id: can_post_to(comun, category=category, can_moderate=can_moderate)
            for category in categories
        }
        can_post_category_ids = [
            category.id for category in categories if category_can_post_by_id.get(category.id)
        ]
        can_start_post = bool(can_post_without_category or can_post_category_ids)
        if not can_moderate and (not is_subscribed or not can_start_post):
            continue

        if getattr(comun, "glossary_enabled", False):
            glossary_comun_ids.append(comun.id)

        payload.append(
            {
                "id": comun.id,
                "name": comun.name,
                "slug": comun.slug,
                "logo_url": _comun_logo_url(request, comun),
                "product_description": comun.product_description,
                "rules_text": comun.rules_text,
                "glossary_enabled": bool(getattr(comun, "glossary_enabled", False)),
                "glossary_terms": [],
                "glossary_terms_count": 0,
                "minimum_author_rating_to_post": _comun_minimum_author_rating_value(comun),
                "only_moderators_can_post": bool(getattr(comun, "only_moderators_can_post", False)),
                "forbid_external_links": bool(getattr(comun, "forbid_external_links", False)),
                "allowed_template_types": comun_allowed_template_types,
                "is_subscribed": is_subscribed,
                "can_moderate": can_moderate,
                "can_post": can_post_without_category,
                "can_post_without_category": can_post_without_category,
                "can_post_category_ids": can_post_category_ids,
                "can_start_post": can_start_post,
                "categories": [
                    serialize_category(
                        comun,
                        category,
                        comun_allowed_template_types,
                        can_post=category_can_post_by_id.get(category.id, False),
                    )
                    for category in categories
                ],
                "categories_count": len(categories),
            }
        )

    if glossary_comun_ids:
        glossary_terms_by_comun_id: dict[int, list[dict]] = defaultdict(list)
        for term in (
            ComunGlossaryTerm.objects.filter(comun_id__in=glossary_comun_ids, is_active=True)
            .order_by("comun_id", "sort_order", "term")
        ):
            glossary_terms_by_comun_id[term.comun_id].append(_serialize_comun_glossary_term(term))
        for item in payload:
            glossary_terms = glossary_terms_by_comun_id.get(item["id"], [])
            if glossary_terms:
                item["glossary_terms"] = glossary_terms
                item["glossary_terms_count"] = len(glossary_terms)

    return JsonResponse(
        {
            "ok": True,
            "comuns": payload,
            "template_type_options": template_type_options,
            "template_editor_blocks_by_template": template_editor_blocks_by_template,
        }
    )


@csrf_exempt
def comun_detail_manage(request: HttpRequest, slug: str) -> HttpResponse:
    current_user = user_views._get_user_from_request(request)
    try:
        comun = (
            Comun.objects.filter(slug=slug)
            .select_related("creator", "welcome_post", "telegram_source_author")
            .prefetch_related("moderators", "excluded_authors", "categories", "tags", "blocked_tags")
            .get()
        )
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    if not comun.is_active and not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "comun": _serialize_comun(
                    request,
                    comun,
                    current_user=current_user,
                    include_manage_fields=True,
                    include_options=_comun_is_moderator(current_user, comun),
                    include_activity=True,
                ),
            }
        )

    if request.method == "DELETE":
        if not _comun_can_manage_moderators(current_user, comun):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        comun.delete()
        return JsonResponse({"ok": True, "deleted": True, "posts_kept": True})

    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if "name" in body:
        if not _comun_can_manage_moderators(current_user, comun):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        name = str(body.get("name") or "").strip()
        if not name:
            return JsonResponse({"ok": False, "error": "name required"}, status=400)
        if Comun.objects.exclude(id=comun.id).filter(name__iexact=name).exists():
            return JsonResponse({"ok": False, "error": "name already exists"}, status=400)
        comun.name = name
    if "slug" in body and (current_user and current_user.is_staff):
        next_slug = _normalize_comun_slug(str(body.get("slug") or ""))
        if not next_slug:
            return JsonResponse({"ok": False, "error": "slug required"}, status=400)
        if Comun.objects.exclude(id=comun.id).filter(slug=next_slug).exists():
            return JsonResponse({"ok": False, "error": "slug already exists"}, status=400)
        comun.slug = next_slug
    if "website_url" in body:
        comun.website_url = str(body.get("website_url") or "").strip()
    if "logo_url" in body:
        comun.logo_url = str(body.get("logo_url") or "").strip()
    if "product_description" in body:
        comun.product_description = str(body.get("product_description") or "").strip()
    if "rules_text" in body or "rules" in body:
        comun.rules_text = str(body.get("rules_text") or body.get("rules") or "").strip()
    if "target_audience" in body:
        comun.target_audience = str(body.get("target_audience") or "").strip()
    if "glossary_enabled" in body:
        comun.glossary_enabled = bool(body.get("glossary_enabled"))
    if "roadmap_enabled" in body:
        comun.roadmap_enabled = bool(body.get("roadmap_enabled"))
    if "knowledge_base_enabled" in body:
        comun.knowledge_base_enabled = bool(body.get("knowledge_base_enabled"))
    if "roadmap_category_ids" in body:
        requested_roadmap_category_ids = community_service._parse_int_list(body.get("roadmap_category_ids"))
        active_category_ids = set(
            ComunCategory.objects.filter(
                comun=comun,
                is_active=True,
                id__in=requested_roadmap_category_ids,
            ).values_list("id", flat=True)
        )
        comun.roadmap_category_ids = [
            category_id for category_id in requested_roadmap_category_ids if category_id in active_category_ids
        ]
    if "minimum_author_rating_to_post" in body:
        minimum_author_rating_to_post, minimum_author_rating_error = _normalize_comun_minimum_author_rating(
            body.get("minimum_author_rating_to_post")
        )
        if minimum_author_rating_error:
            return JsonResponse({"ok": False, "error": minimum_author_rating_error}, status=400)
        comun.minimum_author_rating_to_post = minimum_author_rating_to_post or 0
    if "only_moderators_can_post" in body:
        comun.only_moderators_can_post = bool(body.get("only_moderators_can_post"))
    if "forbid_external_links" in body:
        comun.forbid_external_links = bool(body.get("forbid_external_links"))
    if "allowed_template_types" in body:
        comun.allowed_post_templates = normalize_allowed_post_templates(
            body.get("allowed_template_types")
        )
    if "hide_from_home" in body:
        if not _comun_can_manage_moderators(current_user, comun):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        comun.hide_from_home = bool(body.get("hide_from_home"))
    if "is_active" in body and (current_user and current_user.is_staff):
        comun.is_active = bool(body.get("is_active"))
    if "sort_order" in body and (current_user and current_user.is_staff):
        try:
            comun.sort_order = max(int(body.get("sort_order", 0)), 0)
        except (TypeError, ValueError):
            pass

    if "moderator_ids" in body:
        if not _comun_can_manage_moderators(current_user, comun):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        moderator_ids = set(community_service._parse_int_list(body.get("moderator_ids")))
        moderator_ids.add(comun.creator_id)
        moderator_ids = {int(user_id) for user_id in moderator_ids if int(user_id) > 0}
        comun.moderators.set(User.objects.filter(id__in=moderator_ids, is_active=True))

    if "tag_ids" in body:
        tag_ids = community_service._parse_int_list(body.get("tag_ids"))[:5]
        comun.tags.set(Tag.objects.filter(id__in=tag_ids, is_active=True))

    if "excluded_author_ids" in body:
        comun.excluded_authors.set(
            Author.objects.filter(
                id__in=community_service._parse_int_list(body.get("excluded_author_ids")),
                is_blocked=False,
            )
        )

    if "telegram_source_author_id" in body or "telegram_channel_username" in body:
        telegram_source_author_id = _parse_post_reference_to_id(body.get("telegram_source_author_id"))
        requested_channel_username = _normalize_telegram_channel_username(body.get("telegram_channel_username"))
        next_telegram_author = None

        if telegram_source_author_id:
            next_telegram_author = Author.objects.filter(
                id=telegram_source_author_id,
                is_blocked=False,
            ).first()
            if not next_telegram_author:
                return JsonResponse({"ok": False, "error": "telegram channel not found"}, status=400)
            linked_comun = _author_telegram_source_comun(next_telegram_author)
            if linked_comun and linked_comun.id != comun.id:
                return JsonResponse(
                    {"ok": False, "error": "telegram channel already linked to another comun"},
                    status=400,
                )
            if not (
                (current_user and current_user.is_staff)
                or _author_is_managed_by_comun_team(next_telegram_author, comun)
            ):
                return JsonResponse(
                    {"ok": False, "error": "telegram channel is not managed by comun team"},
                    status=403,
                )
            requested_channel_username = _normalize_telegram_channel_username(next_telegram_author.username)
        elif requested_channel_username:
            candidate_author = Author.objects.filter(
                username__iexact=requested_channel_username,
                is_blocked=False,
            ).first()
            linked_comun = _author_telegram_source_comun(candidate_author) if candidate_author else None
            if linked_comun and linked_comun.id != comun.id:
                return JsonResponse(
                    {"ok": False, "error": "telegram channel already linked to another comun"},
                    status=400,
                )
            if candidate_author and (
                (current_user and current_user.is_staff) or _author_is_managed_by_comun_team(candidate_author, comun)
            ):
                next_telegram_author = candidate_author
                requested_channel_username = _normalize_telegram_channel_username(candidate_author.username)

        comun.telegram_source_author = next_telegram_author
        comun.telegram_channel_username = requested_channel_username

    if "welcome_post_id" in body or "welcome_post_ref" in body:
        welcome_post_id = _parse_post_reference_to_id(
            body.get("welcome_post_id") if "welcome_post_id" in body else body.get("welcome_post_ref")
        )
        if welcome_post_id:
            now = timezone.now()
            welcome_post = (
                Post.objects.filter(id=welcome_post_id, is_blocked=False, author__is_blocked=False)
                .filter(community_service._publish_ready_filter(now))
                .first()
            )
            if not welcome_post:
                return JsonResponse({"ok": False, "error": "post not found"}, status=400)
            if not community_service._post_belongs_to_comun(comun, welcome_post, now=now):
                return JsonResponse({"ok": False, "error": "post does not belong to comun"}, status=400)
            comun.welcome_post = welcome_post
        else:
            comun.welcome_post = None

    comun.save()

    if "category_ids" in body or "category_names" in body:
        if "category_ids" in body:
            selected_categories: dict[int, ComunCategory] = {
                category.id: category
                for category in _comun_category_queryset(comun).filter(
                    id__in=community_service._parse_int_list(body.get("category_ids")),
                )
            }
        else:
            selected_categories = {category.id: category for category in _active_comun_category_queryset(comun)}

        raw_category_names = body.get("category_names") if isinstance(body.get("category_names"), list) else []
        for raw_category_name in raw_category_names:
            category, _created = _ensure_comun_category_by_name(comun, raw_category_name)
            if not category:
                continue
            if not category.is_active:
                category.is_active = True
                category.save(update_fields=["is_active", "updated_at"])
            selected_categories[category.id] = category

        selected_category_ids = list(selected_categories.keys())
        if "category_ids" in body:
            _comun_category_queryset(comun).exclude(id__in=selected_category_ids).filter(is_active=True).update(
                is_active=False
            )
            if selected_category_ids:
                _comun_category_queryset(comun).filter(id__in=selected_category_ids).exclude(is_active=True).update(
                    is_active=True
                )
            comun.categories.set(_active_comun_category_queryset(comun).filter(id__in=selected_category_ids))
        elif selected_category_ids:
            comun.categories.add(*selected_category_ids)

    if "category_template_types_by_id" in body:
        raw_category_templates = body.get("category_template_types_by_id")
        if not isinstance(raw_category_templates, dict):
            return JsonResponse(
                {"ok": False, "error": "category_template_types_by_id must be an object"},
                status=400,
            )
        category_updates: dict[int, list[str]] = {}
        for raw_category_id, raw_template_types in raw_category_templates.items():
            category_id = _parse_post_reference_to_id(raw_category_id)
            if not category_id:
                continue
            category_updates[category_id] = normalize_allowed_post_templates_override(raw_template_types)
        for category in ComunCategory.objects.filter(
            comun=comun,
            is_active=True,
            id__in=list(category_updates.keys()),
        ):
            next_allowed_templates = category_updates.get(category.id, [])
            if category.allowed_post_templates == next_allowed_templates:
                continue
            category.allowed_post_templates = next_allowed_templates
            category.save(update_fields=["allowed_post_templates", "updated_at"])

    if "category_only_moderators_can_post_ids" in body:
        category_only_moderators_can_post_ids = set(
            community_service._parse_int_list(body.get("category_only_moderators_can_post_ids"))
        )
        for category in ComunCategory.objects.filter(
            comun=comun,
            is_active=True,
        ):
            next_only_moderators_can_post = category.id in category_only_moderators_can_post_ids
            if bool(category.only_moderators_can_post) == next_only_moderators_can_post:
                continue
            category.only_moderators_can_post = next_only_moderators_can_post
            category.save(update_fields=["only_moderators_can_post", "updated_at"])

    if "category_hide_from_home_ids" in body:
        if not _comun_can_manage_moderators(current_user, comun):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        category_hide_from_home_ids = set(
            community_service._parse_int_list(body.get("category_hide_from_home_ids"))
        )
        for category in ComunCategory.objects.filter(
            comun=comun,
            is_active=True,
        ):
            next_hide_from_home = category.id in category_hide_from_home_ids
            if bool(getattr(category, "hide_from_home", False)) == next_hide_from_home:
                continue
            category.hide_from_home = next_hide_from_home
            category.save(update_fields=["hide_from_home", "updated_at"])

    if "blocked_tag_ids" in body or "excluded_tag_ids" in body:
        blocked_tag_ids = community_service._parse_int_list(
            body.get("blocked_tag_ids") if "blocked_tag_ids" in body else body.get("excluded_tag_ids")
        )
        comun.blocked_tags.set(Tag.objects.filter(id__in=blocked_tag_ids, is_active=True))

    if "glossary_terms" in body:
        _sync_comun_glossary_terms(comun, body.get("glossary_terms"))

    if "custom_templates" in body:
        if not _comun_can_manage_moderators(current_user, comun):
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        custom_templates_error = editor_service._sync_comun_custom_post_templates(
            comun,
            body.get("custom_templates"),
        )
        if custom_templates_error:
            return JsonResponse({"ok": False, "error": custom_templates_error}, status=400)

    comun = (
        Comun.objects.filter(id=comun.id)
        .select_related("creator", "welcome_post", "telegram_source_author")
        .prefetch_related("moderators", "excluded_authors", "categories", "tags", "blocked_tags")
        .get()
    )
    return JsonResponse(
        {
            "ok": True,
            "comun": _serialize_comun(
                request,
                comun,
                current_user=current_user,
                include_manage_fields=True,
                include_options=True,
                include_activity=True,
            ),
        }
    )


def comun_welcome_post_options(request: HttpRequest, slug: str) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    current_user = user_views._get_user_from_request(request)
    try:
        comun = (
            Comun.objects.filter(slug=slug)
            .select_related("creator", "telegram_source_author")
            .prefetch_related("moderators", "excluded_authors", "blocked_tags")
            .get()
        )
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    if not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 10)
    except (TypeError, ValueError):
        limit = 10

    query = str(request.GET.get("q") or "").strip()
    posts_query = community_service._comun_posts_base_queryset(comun, timezone.now()).only(
        "id",
        "title",
        "created_at",
    )
    if query:
        posts_query = posts_query.filter(title__icontains=query)

    posts = [
        {
            "id": post.id,
            "title": post.title or f"Пост {post.id}",
        }
        for post in posts_query.order_by("-created_at", "-id")[:limit]
    ]
    return JsonResponse({"ok": True, "posts": posts})


@csrf_exempt
def comun_vote(request: HttpRequest, slug: str) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    current_user = user_views._get_user_from_request(request)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        comun = Comun.objects.filter(slug=slug).select_related("creator").get()
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    if not comun.is_active and not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    vote_value = 1
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            try:
                vote_value = int(payload.get("value", 1))
            except (TypeError, ValueError):
                vote_value = 99

    if vote_value not in (-1, 0, 1):
        return JsonResponse({"ok": False, "error": "invalid vote value"}, status=400)

    new_vote = 0
    with transaction.atomic():
        existing = ComunVote.objects.select_for_update().filter(comun_id=comun.id, user_id=current_user.id).first()
        if existing:
            if vote_value == 0 or existing.value == vote_value:
                existing.delete()
                new_vote = 0
            else:
                existing.value = vote_value
                existing.save(update_fields=["value", "updated_at"])
                new_vote = vote_value
        elif vote_value != 0:
            ComunVote.objects.create(comun_id=comun.id, user_id=current_user.id, value=vote_value)
            new_vote = vote_value

        votes_up, votes_down = community_service._sync_comun_vote_counts(comun.id)

    comun.votes_up = votes_up
    comun.votes_down = votes_down
    comun.refresh_from_db(fields=["rating_score"])

    return JsonResponse(
        {
            "ok": True,
            "rating": _serialize_comun_rating(comun, current_user=current_user, user_vote=new_vote),
        }
    )


@csrf_exempt
@anonymous_cache(prefix="comun-posts", seconds=45)
def comun_posts(request: HttpRequest, slug: str) -> HttpResponse:
    current_user = user_views._get_user_from_request(request)
    try:
        comun = (
            Comun.objects.filter(slug=slug)
            .select_related("creator", "welcome_post", "telegram_source_author")
            .prefetch_related("moderators", "excluded_authors", "categories", "blocked_tags")
            .get()
        )
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    if not comun.is_active and not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    if request.method == "POST":
        if not current_user:
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "").strip()
        template_payload, template_error = editor_service._normalize_post_template_payload(
            payload.get("template"),
            resolve_post_refs=True,
        )
        if template_error:
            return JsonResponse({"ok": False, "error": template_error}, status=400)
        template_content_error = editor_service._validate_template_content_constraints(
            template_payload,
            content,
        )
        if template_content_error:
            return JsonResponse({"ok": False, "error": template_content_error}, status=400)
        if not title:
            return JsonResponse({"ok": False, "error": "title is required"}, status=400)
        if not content:
            return JsonResponse({"ok": False, "error": "content is required"}, status=400)
        if bool(getattr(comun, "forbid_external_links", False)) and _payload_contains_external_links(
            title=title,
            content=content,
            template_payload=template_payload,
        ):
            return JsonResponse(
                {"ok": False, "error": _COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR},
                status=400,
            )

        category_id = _parse_post_reference_to_id(payload.get("comun_category_id") or payload.get("category_id"))
        category = None
        if category_id:
            category = _active_comun_category_queryset(comun).filter(id=category_id).first()
            if not category:
                return JsonResponse(
                    {"ok": False, "error": "category not found"},
                    status=400,
                )

        requested_template_type = editor_service._requested_template_type(template_payload)
        template_access_error = editor_service._template_not_allowed_error(
            requested_template_type,
            _allowed_templates_for_comun_category(comun, category),
            scope="comun category" if category else "comun",
        )
        if template_access_error:
            return JsonResponse({"ok": False, "error": template_access_error}, status=400)

        author, personal_author_error = editor_service._get_or_create_personal_author(current_user)
        if personal_author_error:
            return JsonResponse({"ok": False, "error": personal_author_error}, status=400)
        if not author:
            return JsonResponse({"ok": False, "error": "author not found"}, status=400)

        can_post, _minimum_rating, author_rating = _comun_post_access_state(
            current_user,
            comun,
            author=author,
            category=category,
        )
        if not can_post:
            return JsonResponse(
                {
                    "ok": False,
                    "error": _comun_post_access_error_message(
                        comun,
                        author_rating=author_rating,
                        category=category,
                    ),
                },
                status=403,
            )

        try:
            message_id = community_service._generate_manual_message_id(author)
        except ValueError:
            return JsonResponse({"ok": False, "error": "unable to create post"}, status=500)

        explicit_tags = community_service._parse_tag_payload(payload.get("tags"))

        raw_data = {
            "source": "manual_comun",
            "comun_slug": comun.slug,
            "comun_category_id": category.id if category else None,
            **({"template": template_payload} if template_payload else {}),
        }
        editor_service._sync_template_derived_raw_data(raw_data, template_payload, content)

        post = Post.objects.create(
            author=author,
            message_id=message_id,
            title=title,
            content=content,
            channel_url=(author.invite_url or author.channel_url or ""),
            source_url=(author.invite_url or author.channel_url or ""),
            raw_data=raw_data,
            is_pending=False,
            is_blocked=False,
            publish_at=None,
        )
        community_service._apply_post_tags(post, explicit_tags)
        if category:
            ComunPostCategoryAssignment.objects.update_or_create(
                comun=comun,
                post=post,
                defaults={"category": category, "assigned_by": current_user},
            )
            community_service._maybe_notify_post_added_to_voting(
                post=post,
                comun=comun,
                category=category,
                actor=current_user,
                previous_category=None,
            )
        community_service._maybe_notify_new_author(author, post)
        community_service._maybe_notify_post_published_to_subscribers(
            post,
            actor=current_user,
            comun=comun,
            category=category,
        )
        community_service._maybe_increment_comun_author_count_for_post(post, comun=comun)
        if post.rating:
            community_service._apply_comun_rating_delta_for_post(
                post,
                value_delta=post.rating,
                event_type="post_vote",
            )
        serialized_post = editor_service._serialize_post_for_user(request, post, current_user)
        serialized_post["comun_category_id"] = category.id if category else None
        serialized_post["comun_category"] = _serialize_comun_category(category, comun) if category else None
        return JsonResponse({"ok": True, "post": serialized_post})

    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

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

    selected_category_slug = str(request.GET.get("category") or "").strip()
    selected_category = None
    if selected_category_slug:
        selected_category = _active_comun_category_queryset(comun).filter(slug=selected_category_slug).first()
        if not selected_category:
            return JsonResponse({"ok": False, "error": "category not found"}, status=404)

    now = timezone.now()
    visible_categories = _comun_categories_list(comun)
    all_posts_query = _comun_posts_base_queryset(comun, now)
    if comun.welcome_post_id:
        all_posts_query = all_posts_query.exclude(id=comun.welcome_post_id)

    all_total_count = all_posts_query.count()
    category_count_rows = (
        ComunPostCategoryAssignment.objects.filter(
            comun_id=comun.id,
            category_id__isnull=False,
            post_id__in=all_posts_query.values("id"),
        )
        .values("category_id")
        .annotate(count=Count("post_id", distinct=True))
    )
    category_counts_map = {
        int(row["category_id"]): int(row["count"] or 0) for row in category_count_rows if row.get("category_id")
    }
    category_counts_payload = [
        {
            "category_id": category.id,
            "slug": category.slug,
            "count": category_counts_map.get(category.id, 0),
        }
        for category in visible_categories
    ]
    uncategorized_count = max(
        all_total_count - sum(item["count"] for item in category_counts_payload),
        0,
    )

    base_query = all_posts_query
    if selected_category:
        base_query = base_query.filter(
            comun_category_assignments__comun_id=comun.id,
            comun_category_assignments__category_id=selected_category.id,
        )

    total_count = base_query.count()

    posts = list(
        base_query.select_related("author")
        .prefetch_related("tags")
        .distinct()
        .order_by("-created_at")[offset : offset + limit]
    )

    favorite_post_ids = community_service._favorite_post_ids_for_user(posts, current_user)
    assignments = {
        assignment.post_id: assignment
        for assignment in ComunPostCategoryAssignment.objects.select_related("category").filter(
            comun_id=comun.id, post_id__in=[post.id for post in posts]
        )
    }

    serialized_posts = []
    for post in posts:
        item = community_service._serialize_backend_post_card(
            request,
            post,
            current_user,
            now=now,
            is_favorite=post.id in favorite_post_ids,
        )
        assignment = assignments.get(post.id)
        if assignment and assignment.category_id:
            item["comun_category"] = _serialize_comun_category(assignment.category, comun)
            item["comun_category_id"] = assignment.category_id
        else:
            item["comun_category"] = None
            item["comun_category_id"] = None
        serialized_posts.append(item)

    return JsonResponse(
        {
            "ok": True,
            "comun": _serialize_comun(request, comun, current_user=current_user, include_activity=True),
            "posts": serialized_posts,
            "selected_category": (_serialize_comun_category(selected_category, comun) if selected_category else None),
            "total_count": total_count,
            "category_counts": category_counts_payload,
            "uncategorized_count": uncategorized_count,
        }
    )


def _comun_knowledge_base_queryset(comun: Comun):
    return (
        ComunKnowledgeBaseItem.objects.filter(comun=comun, is_active=True)
        .select_related("post", "post__author", "parent")
        .order_by("parent_id", "sort_order", "title", "id")
    )


def _next_knowledge_base_sort_order(comun: Comun, parent_id: int | None = None) -> int:
    siblings = ComunKnowledgeBaseItem.objects.filter(comun=comun, is_active=True, parent_id=parent_id)
    last_sort_order = siblings.order_by("-sort_order", "-id").values_list("sort_order", flat=True).first()
    return int(last_sort_order or 0) + 10


def _knowledge_base_parent(comun: Comun, parent_id: int | None, *, item_id: int | None = None):
    if not parent_id:
        return None
    parent = ComunKnowledgeBaseItem.objects.filter(comun=comun, is_active=True, id=parent_id).first()
    if not parent:
        raise ValueError("parent not found")
    if item_id and parent.id == item_id:
        raise ValueError("item cannot be its own parent")
    cursor = parent
    seen = {int(item_id or 0)}
    while cursor and cursor.parent_id:
        if cursor.parent_id in seen:
            raise ValueError("parent cycle is not allowed")
        seen.add(cursor.parent_id)
        cursor = cursor.parent
    return parent


def _knowledge_base_post_for_comun(comun: Comun, post_id: int | None) -> Post | None:
    if not post_id:
        return None
    membership_filter = _comun_post_membership_filter(comun)
    if not membership_filter:
        return None
    return (
        Post.objects.filter(id=post_id, is_blocked=False, author__is_blocked=False)
        .filter(membership_filter)
        .select_related("author")
        .first()
    )


@csrf_exempt
def comun_knowledge_base(request: HttpRequest, slug: str) -> HttpResponse:
    current_user = user_views._get_user_from_request(request)
    try:
        comun = (
            Comun.objects.filter(slug=slug)
            .select_related("creator", "telegram_source_author")
            .prefetch_related("moderators")
            .get()
        )
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)

    can_moderate = _comun_is_moderator(current_user, comun)
    if not comun.is_active and not can_moderate:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)
    if not comun.knowledge_base_enabled and not can_moderate:
        return JsonResponse({"ok": False, "error": "knowledge base disabled"}, status=404)

    if request.method in ("GET", "HEAD"):
        serialized = _serialize_comun_knowledge_base(list(_comun_knowledge_base_queryset(comun)))
        return JsonResponse(
            {
                "ok": True,
                "comun": _serialize_comun(request, comun, current_user=current_user),
                **serialized,
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not can_moderate:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    parent_id = _parse_post_reference_to_id(body.get("parent_id"))
    try:
        parent = _knowledge_base_parent(comun, parent_id)
    except ValueError as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=400)

    post_id = _parse_post_reference_to_id(body.get("post_id"))
    title = str(body.get("title") or "").strip()
    if post_id:
        post = _knowledge_base_post_for_comun(comun, post_id)
        if not post:
            return JsonResponse({"ok": False, "error": "post not found in comun"}, status=404)
        item, created = ComunKnowledgeBaseItem.objects.get_or_create(
            comun=comun,
            post=post,
            defaults={
                "item_type": ComunKnowledgeBaseItem.TYPE_POST,
                "title": title[:255],
                "parent": parent,
                "sort_order": _next_knowledge_base_sort_order(comun, parent.id if parent else None),
                "created_by": current_user,
                "is_active": True,
            },
        )
        if not created:
            item.is_active = True
            if title:
                item.title = title[:255]
            if parent_id is not None:
                item.parent = parent
            item.save(update_fields=["is_active", "title", "parent", "updated_at"])
    else:
        if not title:
            return JsonResponse({"ok": False, "error": "title required"}, status=400)
        item = ComunKnowledgeBaseItem.objects.create(
            comun=comun,
            item_type=ComunKnowledgeBaseItem.TYPE_GROUP,
            title=title[:255],
            parent=parent,
            sort_order=_next_knowledge_base_sort_order(comun, parent.id if parent else None),
            created_by=current_user,
        )

    serialized = _serialize_comun_knowledge_base(list(_comun_knowledge_base_queryset(comun)))
    return JsonResponse({"ok": True, "item": _serialize_comun_knowledge_base_item(item), **serialized})


@csrf_exempt
def comun_knowledge_base_item(request: HttpRequest, slug: str, item_id: int) -> HttpResponse:
    if request.method not in ("PATCH", "DELETE"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    current_user = user_views._get_user_from_request(request)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        comun = Comun.objects.filter(slug=slug).prefetch_related("moderators").get()
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)
    if not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    item = ComunKnowledgeBaseItem.objects.filter(comun=comun, id=item_id, is_active=True).first()
    if not item:
        return JsonResponse({"ok": False, "error": "item not found"}, status=404)

    if request.method == "DELETE":
        if item.item_type == ComunKnowledgeBaseItem.TYPE_GROUP:
            ComunKnowledgeBaseItem.objects.filter(comun=comun, is_active=True, parent=item).update(
                parent=item.parent
            )
        item.is_active = False
        item.save(update_fields=["is_active", "updated_at"])
        serialized = _serialize_comun_knowledge_base(list(_comun_knowledge_base_queryset(comun)))
        return JsonResponse({"ok": True, **serialized})

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if "title" in body:
        item.title = str(body.get("title") or "").strip()[:255]
    if "sort_order" in body:
        try:
            item.sort_order = int(body.get("sort_order") or 0)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid sort order"}, status=400)
    if "parent_id" in body:
        parent_id = _parse_post_reference_to_id(body.get("parent_id"))
        try:
            item.parent = _knowledge_base_parent(comun, parent_id, item_id=item.id)
        except ValueError as error:
            return JsonResponse({"ok": False, "error": str(error)}, status=400)
    item.save(update_fields=["title", "sort_order", "parent", "updated_at"])
    serialized = _serialize_comun_knowledge_base(list(_comun_knowledge_base_queryset(comun)))
    return JsonResponse({"ok": True, "item": _serialize_comun_knowledge_base_item(item), **serialized})


@csrf_exempt
def comun_post_category_update(request: HttpRequest, slug: str, post_id: int) -> HttpResponse:
    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    current_user = user_views._get_user_from_request(request)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        comun = (
            Comun.objects.filter(slug=slug)
            .select_related("creator", "telegram_source_author")
            .prefetch_related("moderators", "categories")
            .get()
        )
    except Comun.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comun not found"}, status=404)
    if not _comun_is_moderator(current_user, comun):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    category_id = _parse_post_reference_to_id(body.get("category_id"))
    category = None
    if category_id:
        category = _active_comun_category_queryset(comun).filter(id=category_id).first()
        if not category:
            return JsonResponse({"ok": False, "error": "category not found"}, status=400)

    membership_filter = _comun_post_membership_filter(comun)
    if not membership_filter:
        return JsonResponse({"ok": False, "error": "post not found in comun"}, status=404)

    post = (
        Post.objects.filter(id=post_id, is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(community_service._publish_ready_filter(timezone.now()))
        .filter(membership_filter)
        .distinct()
        .first()
    )
    if not post:
        return JsonResponse({"ok": False, "error": "post not found in comun"}, status=404)

    previous_assignment = (
        ComunPostCategoryAssignment.objects.select_related("category").filter(comun=comun, post=post).first()
    )
    previous_category = previous_assignment.category if previous_assignment else None

    if category is None:
        ComunPostCategoryAssignment.objects.filter(comun=comun, post=post).delete()
        return JsonResponse({"ok": True, "assignment": None})

    assignment, _ = ComunPostCategoryAssignment.objects.update_or_create(
        comun=comun,
        post=post,
        defaults={"category": category, "assigned_by": current_user},
    )
    community_service._maybe_notify_post_added_to_voting(
        post=post,
        comun=comun,
        category=category,
        actor=current_user,
        previous_category=previous_category,
    )
    return JsonResponse(
        {
            "ok": True,
            "assignment": {
                "post_id": post.id,
                "category_id": assignment.category_id,
                "category": _serialize_comun_category(category, comun),
            },
        }
    )


_normalize_comun_category_name = community_service._normalize_comun_category_name
_generate_unique_comun_category_slug = community_service._generate_unique_comun_category_slug
_ensure_comun_category_by_name = community_service._ensure_comun_category_by_name
_normalize_comun_glossary_term = community_service._normalize_comun_glossary_term
_normalize_comun_glossary_definition = community_service._normalize_comun_glossary_definition
_generate_unique_comun_glossary_term_slug = community_service._generate_unique_comun_glossary_term_slug
_comun_glossary_queryset = community_service._comun_glossary_queryset
_active_comun_glossary_queryset = community_service._active_comun_glossary_queryset
_parse_post_reference_to_id = community_service._parse_post_reference_to_id
_sync_comun_glossary_terms = community_service._sync_comun_glossary_terms
_comun_category_queryset = community_service._comun_category_queryset
_active_comun_category_queryset = community_service._active_comun_category_queryset
_normalize_telegram_channel_username = community_service._normalize_telegram_channel_username
_generate_unique_comun_name = community_service._generate_unique_comun_name
_normalize_comun_slug = community_service._normalize_comun_slug
_generate_unique_comun_slug = community_service._generate_unique_comun_slug
_comun_is_moderator = community_service._comun_is_moderator
_comun_can_manage_moderators = community_service._comun_can_manage_moderators
_current_user_verified_telegram_authors = community_service._current_user_verified_telegram_authors
_comun_team_user_ids = community_service._comun_team_user_ids
_author_is_managed_by_comun_team = community_service._author_is_managed_by_comun_team
_author_telegram_source_comun = community_service._author_telegram_source_comun
_attach_pending_comuns_for_author = community_service._attach_pending_comuns_for_author
_allowed_templates_for_comun = community_service._allowed_templates_for_comun
_allowed_template_overrides_for_comun_category = community_service._allowed_template_overrides_for_comun_category
_allowed_templates_for_comun_category = community_service._allowed_templates_for_comun_category
_post_comun_slug = community_service._post_comun_slug
_format_rating_value = community_service._format_rating_value
_comun_creation_access_state = community_service._comun_creation_access_state
_normalize_comun_minimum_author_rating = community_service._normalize_comun_minimum_author_rating
_comun_minimum_author_rating_value = community_service._comun_minimum_author_rating_value
_comun_post_access_state = community_service._comun_post_access_state
_comun_post_access_error_message = community_service._comun_post_access_error_message
_comun_logo_url = community_service._comun_logo_url
_comun_source_filter = community_service._comun_source_filter
_comun_post_membership_filter = community_service._comun_post_membership_filter
_is_internal_comuna_url = community_service._is_internal_comuna_url
_text_contains_external_links = community_service._text_contains_external_links
_payload_contains_external_links = community_service._payload_contains_external_links
_site_user_avatar_url = community_service._site_user_avatar_url
_comun_categories_list = community_service._comun_categories_list
_comun_categories_count = community_service._comun_categories_count
_recalculate_comun_rating = community_service._recalculate_comun_rating
_comun_posts_base_queryset = community_service._comun_posts_base_queryset
_serialize_author_source_summary = community_serializers._serialize_author_source_summary
_serialize_comun_glossary_term = community_serializers._serialize_comun_glossary_term
_serialize_comun_profile_card = community_serializers._serialize_comun_profile_card
_serialize_comun_category = community_serializers._serialize_comun_category
_serialize_comun_rating = community_serializers._serialize_comun_rating
_serialize_comun = community_serializers._serialize_comun
_serialize_comun_activity = community_serializers._serialize_comun_activity


__all__ = [
    "_allowed_templates_for_comun",
    "_allowed_templates_for_comun_category",
    "_attach_pending_comuns_for_author",
    "_author_telegram_source_comun",
    "_comun_creation_access_state",
    "_comun_post_membership_filter",
    "_comun_source_filter",
    "_post_comun_slug",
    "_serialize_comun_profile_card",
    "comun_create_from_telegram_channel",
    "comun_detail_manage",
    "comun_post_category_update",
    "comun_posts",
    "comun_welcome_post_options",
    "comun_vote",
    "comuns_catalog",
    "comuns_composer",
    "comuns_list_create",
]
