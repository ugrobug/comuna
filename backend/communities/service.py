from __future__ import annotations

import inspect
import base64
import json
import math
import re
import secrets
import urllib.parse
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

try:
    import pymorphy2
except ImportError:  # optional dependency for lemmatization
    pymorphy2 = None

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.http import HttpRequest
from django.utils import timezone
from django.utils.text import slugify

from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunMapPoint,
    ComunPostCategoryAssignment,
    ComunPostRatingContribution,
    ComunVote,
)
from editor.models import PostPollVote
from editor import service as editor_service
from feeds.post_paths import build_post_public_path, slugify_title
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
from rabotaem_backend.media_urls import public_url
from ratings.service import (
    calculate_author_rating,
    format_rating_value,
    get_rating_settings,
    user_max_author_rating,
)
from telegram_integration.media import safe_public_url
from users.avatar_media import public_cached_avatar_url
from users.models import AuthorAdmin

User = get_user_model()

_COMUN_CREATION_MIN_AUTHOR_RATING = 0.0
_COMUN_COMMENT_RATING_WEIGHT = Decimal("0.1")
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
_INTERNAL_COMUNA_HOSTS = frozenset(
    {
        "comuna.ru",
        "www.comuna.ru",
        "comuna.ru",
        "www.comuna.ru",
        "tambur.pub",
        "www.tambur.pub",
        "tambur.pub",
        "www.tambur.pub",
        "localhost",
        "127.0.0.1",
    }
)
_COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR = (
    "В этом сообществе запрещены внешние ссылки. Удалите ссылки из текста и шаблона публикации."
)
_MORPH_ANALYZER = None
_EDITOR_MODEL_BASE64_RE = re.compile(r"^[A-Za-z0-9+/_-]*={0,2}$")


def _feeds_views():
    from feeds import views as feeds_views

    return feeds_views


def _media_url(request: HttpRequest | None, field) -> str | None:
    if not field:
        return None
    try:
        return public_url(field.url, request=request)
    except Exception:
        return None


def _author_avatar_url(request: HttpRequest | None, author: Author) -> str | None:
    return _media_url(request, author.avatar_image) or safe_public_url(author.avatar_url)


def _author_avatar_logo_url(author: Author | None) -> str:
    if not author:
        return ""
    avatar_image = getattr(author, "avatar_image", None)
    if avatar_image:
        image_name = str(getattr(avatar_image, "name", "") or "").strip()
        if image_name:
            media_url = str(
                getattr(settings, "MEDIA_LEGACY_URL", "")
                or getattr(settings, "MEDIA_URL", "/media/")
                or "/media/"
            )
            if not media_url.endswith("/"):
                media_url = f"{media_url}/"
            image_url = f"{media_url}{image_name.lstrip('/')}"
        else:
            try:
                image_url = avatar_image.url
            except Exception:
                image_url = ""
        if image_url:
            site_base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
            if site_base and image_url.startswith("/"):
                image_url = f"{site_base}{image_url}"
            return image_url[:500]
    return str(safe_public_url(getattr(author, "avatar_url", "")) or "")[:500]


def _sync_comun_logo_from_author(comun: Comun | None, author: Author | None) -> bool:
    if not comun:
        return False
    current_logo_url = str(getattr(comun, "logo_url", "") or "").strip()
    logo_url = _author_avatar_logo_url(author)
    if not logo_url or current_logo_url == logo_url:
        return False
    if current_logo_url:
        generated_avatar_logo = (
            "api.telegram.org/file/" in current_logo_url
            or "/media/authors/avatars/" in current_logo_url
            or current_logo_url == str(safe_public_url(getattr(author, "avatar_url", "")) or "")
        )
        if not generated_avatar_logo:
            return False
    comun.logo_url = logo_url
    comun.save(update_fields=["logo_url", "updated_at"])
    return True


def _ensure_pymorphy2_compat():
    if pymorphy2 is None:
        return
    if not hasattr(inspect, "getargspec"):
        from collections import namedtuple

        arg_spec = namedtuple("ArgSpec", "args varargs keywords defaults")

        def getargspec(func):  # type: ignore
            spec = inspect.getfullargspec(func)
            return arg_spec(spec.args, spec.varargs, spec.varkw, spec.defaults)

        inspect.getargspec = getargspec  # type: ignore[attr-defined]


def _get_morph_analyzer():
    global _MORPH_ANALYZER
    if pymorphy2 is None:
        return None
    if _MORPH_ANALYZER is None:
        _ensure_pymorphy2_compat()
        try:
            _MORPH_ANALYZER = pymorphy2.MorphAnalyzer()
        except Exception:
            _MORPH_ANALYZER = None
    return _MORPH_ANALYZER


def _normalize_tag_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _lemmatize_tag(value: str) -> str:
    morph = _get_morph_analyzer()
    if not morph:
        return ""
    text = _normalize_tag_value(value).lower()
    if not text:
        return ""
    words = text.split()
    lemmas: list[str] = []
    for word in words:
        parts = [part for part in word.split("-") if part]
        if not parts:
            continue
        lemma_parts: list[str] = []
        for part in parts:
            parsed = morph.parse(part)
            if parsed:
                lemma_parts.append(parsed[0].normal_form)
            else:
                lemma_parts.append(part)
        lemmas.append("-".join(lemma_parts))
    return " ".join(lemmas).strip()


def _ensure_tag_by_name(raw_name: str) -> tuple[Tag | None, bool]:
    normalized = _normalize_tag_value(raw_name).lstrip("#").strip()
    if not normalized:
        return None, False
    lemma = _lemmatize_tag(normalized) or normalized
    tag = Tag.objects.filter(Q(name__iexact=normalized) | Q(lemma__iexact=lemma)).order_by("name").first()
    if tag:
        if not tag.is_active:
            tag.is_active = True
            tag.save(update_fields=["is_active"])
        if not tag.lemma:
            tag.lemma = lemma
            tag.save(update_fields=["lemma"])
        return tag, False
    return Tag.objects.create(name=normalized, lemma=lemma), True


def _parse_tag_payload(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,\n]", raw)
    elif isinstance(raw, (list, tuple)):
        parts = raw
    else:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part is None:
            continue
        value = _normalize_tag_value(str(part))
        if not value:
            continue
        lower = value.lower()
        if lower in seen:
            continue
        seen.add(lower)
        normalized.append(value)
    return normalized


def _parse_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    seen: set[int] = set()
    for item in value:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        result.append(parsed)
    return result


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


def _publish_ready_filter(now) -> Q:
    return Q(publish_at__isnull=True) | Q(publish_at__lte=now)


def _public_user_author_ids(user: User) -> tuple[list[int], list[AuthorAdmin]]:
    author_links = list(
        AuthorAdmin.objects.filter(user=user, verified_at__isnull=False)
        .select_related("author")
        .order_by("author__username")
    )
    author_ids = [link.author_id for link in author_links]
    personal_author = Author.objects.filter(
        username__iexact=(user.username or "").strip(),
        channel_url="",
        channel_id__isnull=True,
    ).first()
    if personal_author and personal_author.id not in author_ids:
        author_ids.append(personal_author.id)
    return author_ids, author_links


def _personal_user_author(user: User | None) -> Author | None:
    if not user:
        return None
    return (
        Author.objects.filter(
            username__iexact=(user.username or "").strip(),
            channel_url="",
            channel_id__isnull=True,
        )
        .order_by("id")
        .first()
    )


def _normalize_comun_category_name(raw_name: object) -> str:
    return re.sub(r"\s+", " ", str(raw_name or "").strip())


def _generate_unique_comun_category_slug(comun: Comun, name: str) -> str:
    normalized_name = str(name or "").strip()
    base_slug = slugify(normalized_name)[:120]
    if not base_slug:
        base_slug = slugify_title(normalized_name)[:120]
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


def _normalize_comun_glossary_term_en(raw_value: object) -> str:
    return re.sub(r"\s+", " ", str(raw_value or "").strip())[:180]


def _delete_comun_glossary_term_image(term: ComunGlossaryTerm) -> None:
    image = getattr(term, "image", None)
    if not image:
        return
    try:
        image.delete(save=False)
    except Exception:
        return


def _generate_unique_comun_glossary_term_slug(
    comun: Comun,
    term: str,
    *,
    exclude_term_id: int | None = None,
) -> str:
    normalized_term = str(term or "").strip()
    base_slug = slugify(normalized_term)[:180]
    if not base_slug:
        base_slug = slugify_title(normalized_term)[:180]
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


def _sync_comun_glossary_terms(comun: Comun, raw_terms: object) -> None:
    if not isinstance(raw_terms, list):
        return

    existing_terms = {term.id: term for term in _comun_glossary_queryset(comun)}
    kept_ids: set[int] = set()

    for index, item in enumerate(raw_terms):
        if not isinstance(item, dict):
            continue

        term_name = _normalize_comun_glossary_term(item.get("term") or item.get("name"))
        term_en = _normalize_comun_glossary_term_en(
            item.get("term_en") or item.get("english_term") or item.get("termEn")
        )
        definition = _normalize_comun_glossary_definition(item.get("definition") or item.get("description"))
        if not term_name or not definition:
            continue

        term_id = _parse_post_reference_to_id(item.get("id"))
        existing_term = existing_terms.get(term_id) if term_id else None
        image_path = str(item.get("image_path") or item.get("image") or "").strip()
        if image_path and not image_path.startswith("comuns/glossary/"):
            image_path = ""
        image_remove = bool(item.get("image_remove") or item.get("remove_image"))
        next_slug = _generate_unique_comun_glossary_term_slug(
            comun,
            term_name,
            exclude_term_id=existing_term.id if existing_term else None,
        )

        if existing_term:
            current_image_name = str(getattr(existing_term.image, "name", "") or "").strip()
            image_changed = False
            if image_remove:
                _delete_comun_glossary_term_image(existing_term)
                existing_term.image = ""
                image_changed = True
            elif image_path and image_path != current_image_name:
                _delete_comun_glossary_term_image(existing_term)
                existing_term.image = image_path
                image_changed = True
            existing_term.term = term_name
            existing_term.term_en = term_en
            existing_term.definition = definition
            existing_term.slug = next_slug
            existing_term.sort_order = index
            existing_term.is_active = True
            update_fields = [
                "term",
                "term_en",
                "definition",
                "slug",
                "sort_order",
                "is_active",
                "updated_at",
            ]
            if image_changed:
                update_fields.append("image")
            existing_term.save(update_fields=update_fields)
            kept_ids.add(existing_term.id)
            continue

        created_term = ComunGlossaryTerm.objects.create(
            comun=comun,
            term=term_name,
            term_en=term_en,
            definition=definition,
            image=image_path,
            slug=next_slug,
            sort_order=index,
            is_active=True,
        )
        kept_ids.add(created_term.id)

    terms_to_delete = list(_comun_glossary_queryset(comun).exclude(id__in=list(kept_ids)))
    for term in terms_to_delete:
        _delete_comun_glossary_term_image(term)
    if terms_to_delete:
        ComunGlossaryTerm.objects.filter(id__in=[term.id for term in terms_to_delete]).delete()


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
    raw_value = raw_value.split("?", 1)[0].split("#", 1)[0]
    return re.sub(r"[^A-Za-z0-9_]", "", raw_value).lower()


def _generate_unique_comun_name(base_name: str, fallback_username: str = "") -> str:
    normalized_name = re.sub(r"\s+", " ", str(base_name or "").strip())
    candidate = normalized_name[:160]
    if not candidate:
        fallback = _normalize_telegram_channel_username(fallback_username)
        candidate = fallback.replace("_", " ").title()[:160] if fallback else ""
    if not candidate:
        candidate = "Сообщество"

    if not Comun.objects.filter(name__iexact=candidate).exists():
        return candidate

    base_candidate = candidate[:140].rstrip()
    suffix = 2
    while True:
        next_candidate = f"{base_candidate} {suffix}".strip()[:160]
        if not Comun.objects.filter(name__iexact=next_candidate).exists():
            return next_candidate
        suffix += 1


def _normalize_comun_slug(value: str) -> str:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    base_slug = slugify(normalized_value)[:160]
    if not base_slug:
        base_slug = slugify_title(normalized_value)[:160]
    return base_slug


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


def _verified_author_owner_ids(author: Author | None) -> list[int]:
    if not author:
        return []
    return list(
        AuthorAdmin.objects.filter(author=author, verified_at__isnull=False)
        .order_by("verified_at", "created_at", "id")
        .values_list("user_id", flat=True)
    )


def _claim_unowned_comun_for_author(comun: Comun, author: Author | None) -> bool:
    if comun.creator_id:
        return False
    verified_owner_ids = _verified_author_owner_ids(author)
    if not verified_owner_ids:
        return False
    owner_id = int(verified_owner_ids[0])
    comun.creator_id = owner_id
    comun.save(update_fields=["creator", "updated_at"])
    comun.moderators.add(owner_id)
    return True


def _ensure_telegram_channel_comun_for_author(author: Author | None) -> Comun | None:
    if not author:
        return None
    normalized_username = _normalize_telegram_channel_username(author.username)
    if not normalized_username:
        return None

    current_comun = _author_telegram_source_comun(author)
    if current_comun:
        _claim_unowned_comun_for_author(current_comun, author)
        _sync_comun_logo_from_author(current_comun, author)
        return current_comun

    comun = (
        Comun.objects.filter(
            telegram_channel_username__iexact=normalized_username,
            telegram_source_author__isnull=True,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if comun:
        _claim_unowned_comun_for_author(comun, author)
        logo_synced = _sync_comun_logo_from_author(comun, author)
        comun.telegram_source_author = author
        comun.telegram_channel_username = normalized_username
        update_fields = ["telegram_source_author", "telegram_channel_username", "updated_at"]
        if logo_synced:
            update_fields.append("logo_url")
        comun.save(update_fields=update_fields)
        return comun

    verified_owner_ids = _verified_author_owner_ids(author)
    owner_id = int(verified_owner_ids[0]) if verified_owner_ids else None
    base_name = (author.title or "").strip() or f"@{author.username}"
    comun_name = _generate_unique_comun_name(base_name, author.username)
    comun_slug = _generate_unique_comun_slug(author.username or comun_name)
    if not comun_slug:
        comun_slug = _generate_unique_comun_slug(comun_name)
    if not comun_slug:
        return None
    comun = Comun.objects.create(
        name=comun_name,
        slug=comun_slug,
        creator_id=owner_id,
        logo_url=_author_avatar_logo_url(author),
        product_description=(author.description or "").strip(),
        telegram_source_author=author,
        telegram_channel_username=normalized_username,
        only_moderators_can_post=True,
    )
    if owner_id:
        comun.moderators.add(owner_id)
    return comun


def _attach_pending_comuns_for_author(author: Author | None) -> None:
    if not author:
        return
    normalized_username = _normalize_telegram_channel_username(author.username)
    if not normalized_username:
        return

    verified_owner_ids = _verified_author_owner_ids(author)

    current_comun = _author_telegram_source_comun(author)
    if current_comun:
        _claim_unowned_comun_for_author(current_comun, author)
        _sync_comun_logo_from_author(current_comun, author)

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
        _claim_unowned_comun_for_author(comun, author)
        logo_synced = _sync_comun_logo_from_author(comun, author)
        comun.telegram_source_author = author
        comun.telegram_channel_username = normalized_username
        update_fields = ["telegram_source_author", "telegram_channel_username", "updated_at"]
        if logo_synced:
            update_fields.append("logo_url")
        comun.save(update_fields=update_fields)
        current_comun = comun


_allowed_templates_for_comun = editor_service._allowed_templates_for_comun
_allowed_template_overrides_for_comun_category = editor_service._allowed_template_overrides_for_comun_category
_allowed_templates_for_comun_category = editor_service._allowed_templates_for_comun_category


def _post_comun_slug(post: Post) -> str:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    return str(raw_data.get("comun_slug") or "").strip()


def _is_telegram_channel_author(author: Author | None) -> bool:
    if not author:
        return False
    if getattr(author, "channel_id", None) is not None:
        return True
    if str(getattr(author, "channel_url", "") or "").strip():
        return True
    if str(getattr(author, "invite_url", "") or "").strip():
        return True
    return _author_telegram_source_comun(author) is not None


def _post_comun(post: Post) -> Comun | None:
    comun_slug = _post_comun_slug(post)
    if comun_slug:
        comun = Comun.objects.filter(slug=comun_slug, is_active=True).first()
        if comun:
            return comun

    assignment = (
        ComunPostCategoryAssignment.objects.select_related("comun")
        .filter(post=post, comun__is_active=True)
        .order_by("comun__sort_order", "comun__name")
        .first()
    )
    if assignment:
        return assignment.comun

    author = getattr(post, "author", None)
    author_comun = _author_telegram_source_comun(author)
    if author_comun and author_comun.is_active:
        return author_comun

    if _is_telegram_channel_author(author):
        return None

    return None


def _serialize_post_comun(
    request: HttpRequest | None,
    post: Post,
    current_user: User | None = None,
) -> dict | None:
    comun = _post_comun(post)
    if not comun:
        return None
    return {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "logo_url": _comun_logo_url(request, comun),
        "knowledge_base_enabled": bool(getattr(comun, "knowledge_base_enabled", False)),
        "can_moderate": _comun_is_moderator(current_user, comun),
    }


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
    if author is not None and comun.excluded_authors.filter(id=author.id).exists():
        return False, minimum_rating, None
    personal_author = None
    if author is None:
        personal_author = _personal_user_author(user)
        if personal_author and comun.excluded_authors.filter(id=personal_author.id).exists():
            return False, minimum_rating, None
    if minimum_rating <= 0:
        return True, minimum_rating, None

    if author is not None:
        author_rating = round(float(calculate_author_rating(author)), 2)
        return author_rating >= minimum_rating, minimum_rating, author_rating

    if not personal_author:
        return False, minimum_rating, 0.0

    personal_author_rating = round(float(calculate_author_rating(personal_author)), 2)
    return personal_author_rating >= minimum_rating, minimum_rating, personal_author_rating


def _comun_post_access_error_message(
    comun: Comun,
    *,
    author_rating: float | None = None,
    category: ComunCategory | None = None,
    author: Author | None = None,
) -> str:
    if author is not None and comun.excluded_authors.filter(id=author.id).exists():
        return "Этот автор не может публиковать в этом сообществе."
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
        return safe_public_url(explicit_logo)
    return None


def _author_is_telegram_channel_source(author: Author | None) -> bool:
    if not author:
        return False
    return bool(
        getattr(author, "channel_url", "")
        or getattr(author, "invite_url", "")
        or getattr(author, "channel_id", None) is not None
    )


def _post_author_is_telegram_channel_source(post: Post | None) -> bool:
    if not post or not getattr(post, "author_id", None):
        return False
    author = getattr(post, "author", None)
    if author is None:
        author = (
            Author.objects.only("id", "channel_url", "invite_url", "channel_id")
            .filter(id=post.author_id)
            .first()
        )
    return _author_is_telegram_channel_source(author)


def _comun_source_filter(comun: Comun) -> Q | None:
    combined_filter = Q()
    has_source = False

    telegram_source_author = getattr(comun, "telegram_source_author", None)
    telegram_source_author_id = getattr(telegram_source_author, "id", None)
    if telegram_source_author_id and _author_is_telegram_channel_source(telegram_source_author):
        combined_filter |= Q(author_id=telegram_source_author_id)
        has_source = True

    return combined_filter if has_source else None


def _comun_manual_posts_filter(comun: Comun) -> Q | None:
    comun_slug = str(getattr(comun, "slug", "") or "").strip()
    if not comun_slug:
        return None
    return Q(raw_data__source="manual_comun", raw_data__comun_slug=comun_slug)


def _telegram_channel_author_filter() -> Q:
    return (
        Q(author__channel_id__isnull=False)
        | Q(author__channel_url__gt="")
        | Q(author__invite_url__gt="")
    )


def _comun_post_membership_filter(comun: Comun) -> Q | None:
    source_filter = _comun_source_filter(comun)
    manual_filter = _comun_manual_posts_filter(comun)
    if source_filter and manual_filter:
        return source_filter | manual_filter
    return source_filter or manual_filter


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


def _parse_serialized_editor_model(raw_value: object) -> dict | None:
    raw = str(raw_value or "").strip() if isinstance(raw_value, str) else ""
    if not raw:
        return None
    if raw.startswith("<") and raw.endswith(">"):
        return None

    candidates: list[str] = []
    if raw.startswith("{") and raw.endswith("}"):
        candidates.append(raw)
    elif len(raw) >= 16 and _EDITOR_MODEL_BASE64_RE.match(raw):
        encoded = raw.replace("-", "+").replace("_", "/")
        padding = (-len(encoded)) % 4
        encoded = f"{encoded}{'=' * padding}"
        try:
            candidates.append(base64.b64decode(encoded).decode("utf-8"))
        except Exception:
            candidates = []

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("blocks"), list):
            return parsed
    return None


def _finite_float(value: object) -> float | None:
    try:
        number = float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_map_zoom(value: object) -> int:
    try:
        zoom = int(float(str(value).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return 14
    return min(max(zoom, 1), 19)


def _extract_editor_map_points(raw_content: object) -> list[dict]:
    editor_model = _parse_serialized_editor_model(raw_content)
    if not editor_model:
        return []
    points: list[dict] = []
    for block_index, block in enumerate(editor_model.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        if str(block.get("type") or "").strip().lower() != "map":
            continue
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        lat = _finite_float(data.get("lat"))
        lng = _finite_float(data.get("lng"))
        if lat is None or lng is None:
            continue
        if lat < -90 or lat > 90 or lng < -180 or lng > 180:
            continue
        points.append(
            {
                "block_index": block_index,
                "lat": Decimal(str(lat)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                "lng": Decimal(str(lng)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                "zoom": _normalize_map_zoom(data.get("zoom")),
                "raw": str(data.get("raw") or "").strip()[:255],
            }
        )
    return points


def sync_comun_map_points_for_post(
    post: Post | None,
    *,
    comun: Comun | None = None,
) -> int:
    if not post or not getattr(post, "id", None):
        return 0

    ComunMapPoint.objects.filter(post=post).delete()
    if bool(getattr(post, "is_pending", False)) or bool(getattr(post, "is_blocked", False)):
        return 0

    comun = comun or _post_comun(post)
    if not comun or not bool(getattr(comun, "community_map_enabled", False)):
        return 0

    points = _extract_editor_map_points(getattr(post, "content", ""))
    if not points:
        return 0
    objects = [
        ComunMapPoint(
            comun=comun,
            post=post,
            block_index=point["block_index"],
            lat=point["lat"],
            lng=point["lng"],
            zoom=point["zoom"],
            raw=point["raw"],
        )
        for point in points
    ]
    ComunMapPoint.objects.bulk_create(objects)
    return len(objects)


def sync_comun_map_points_for_comun(comun: Comun | None) -> int:
    if not comun or not getattr(comun, "id", None):
        return 0
    ComunMapPoint.objects.filter(comun=comun).delete()
    if not bool(getattr(comun, "community_map_enabled", False)):
        return 0
    synced_count = 0
    for post in _comun_posts_base_queryset(comun).select_related("author").iterator(chunk_size=200):
        synced_count += sync_comun_map_points_for_post(post, comun=comun)
    return synced_count


def serialize_comun_map_point(point: ComunMapPoint) -> dict:
    post = getattr(point, "post", None)
    return {
        "id": point.id,
        "post_id": point.post_id,
        "post_title": getattr(post, "title", "") or "",
        "post_path": build_post_public_path(point.post_id, getattr(post, "title", "") or ""),
        "block_index": point.block_index,
        "lat": float(point.lat),
        "lng": float(point.lng),
        "zoom": point.zoom,
        "raw": point.raw,
        "created_at": point.created_at.isoformat() if point.created_at else None,
        "updated_at": point.updated_at.isoformat() if point.updated_at else None,
    }


def _site_user_avatar_url(
    request: HttpRequest | None,
    user: User,
    *,
    fallback_author_avatars: dict[int, str | None] | None = None,
) -> str | None:
    if not user or not getattr(user, "is_active", True):
        return None
    try:
        if getattr(user.site_profile, "deleted_at", None):
            return None
    except Exception:
        pass
    try:
        site_profile = user.site_profile
        if site_profile and site_profile.avatar_url:
            cached_avatar_url = public_cached_avatar_url(site_profile.avatar_url)
            if cached_avatar_url:
                return cached_avatar_url
    except Exception:
        pass
    try:
        tg = user.telegram_account
        if tg and tg.avatar_url:
            cached_avatar_url = public_cached_avatar_url(tg.avatar_url)
            if cached_avatar_url:
                return cached_avatar_url
    except Exception:
        pass
    try:
        vk = user.vk_account
        if vk and vk.avatar_url:
            cached_avatar_url = public_cached_avatar_url(vk.avatar_url)
            if cached_avatar_url:
                return cached_avatar_url
    except Exception:
        pass
    if fallback_author_avatars and user.id in fallback_author_avatars:
        return fallback_author_avatars.get(user.id)
    return None


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


def _decimal_rating(value: object, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _quantize_rating(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sync_comun_vote_counts(comun_id: int) -> tuple[int, int]:
    counts = ComunVote.objects.filter(comun_id=comun_id).aggregate(
        up=Count("id", filter=Q(value=1)),
        down=Count("id", filter=Q(value=-1)),
    )
    votes_up = int(counts.get("up") or 0)
    votes_down = int(counts.get("down") or 0)
    Comun.objects.filter(id=comun_id).update(
        votes_up=votes_up,
        votes_down=votes_down,
    )
    return votes_up, votes_down


def _comun_rating_window_days(settings=None) -> int:
    settings = settings or get_rating_settings()
    try:
        return max(int(settings.community_post_rating_days or 7), 1)
    except (TypeError, ValueError):
        return 7


def _post_in_comun_rating_window(post: Post, *, settings=None, now=None) -> bool:
    created_at = getattr(post, "created_at", None)
    if not created_at:
        return False
    current_time = now or timezone.now()
    return created_at >= current_time - timedelta(days=_comun_rating_window_days(settings))


def _comun_post_rating_delta(value_delta: int | Decimal, event_type: str, *, settings=None) -> Decimal:
    if not value_delta:
        return Decimal("0.00")
    settings = settings or get_rating_settings()
    if event_type == "post_vote":
        weight = _decimal_rating(getattr(settings, "post_vote_weight", 1), "1")
    elif event_type == "post_comment":
        weight = _COMUN_COMMENT_RATING_WEIGHT
    elif event_type == "comment_like":
        weight = _decimal_rating(getattr(settings, "post_comment_like_weight", "0.5"), "0.5") * _COMUN_COMMENT_RATING_WEIGHT
    else:
        weight = Decimal("0")
    return _quantize_rating(_decimal_rating(value_delta) * weight)


def _comun_contribution_rating(comun_id: int) -> Decimal:
    totals = ComunPostRatingContribution.objects.filter(comun_id=comun_id).aggregate(
        score_total=Sum("score")
    )
    return _quantize_rating(_decimal_rating(totals.get("score_total")))


def _recalculate_comun_rating(comun_id: int) -> tuple[int, int, Decimal]:
    comun = (
        Comun.objects.filter(id=comun_id)
        .select_related("telegram_source_author")
        .prefetch_related("excluded_authors", "blocked_tags")
        .first()
    )
    if not comun:
        return 0, 0, Decimal("0.00")
    votes_up, votes_down = _sync_comun_vote_counts(comun_id)
    rating_score = _comun_contribution_rating(comun_id)
    Comun.objects.filter(id=comun_id).update(
        votes_up=votes_up,
        votes_down=votes_down,
        rating_score=rating_score,
    )
    return votes_up, votes_down, rating_score


def _apply_comun_rating_delta_for_post(
    post_or_id: Post | int | None,
    *,
    value_delta: int | Decimal,
    event_type: str,
) -> Decimal:
    if not post_or_id or not value_delta:
        return Decimal("0.00")
    if isinstance(post_or_id, Post):
        post = post_or_id
    else:
        post = Post.objects.filter(id=post_or_id).first()
    if not post:
        return Decimal("0.00")
    settings = get_rating_settings()
    if not _post_in_comun_rating_window(post, settings=settings):
        return Decimal("0.00")
    rating_delta = _comun_post_rating_delta(value_delta, event_type, settings=settings)
    if not rating_delta:
        return Decimal("0.00")
    comun_ids = _candidate_comun_ids_for_post(post)
    if not comun_ids:
        return Decimal("0.00")
    with transaction.atomic():
        for comun_id in comun_ids:
            contribution, _created = (
                ComunPostRatingContribution.objects.select_for_update()
                .get_or_create(
                    comun_id=comun_id,
                    post_id=post.id,
                    defaults={"score": Decimal("0.00")},
                )
            )
            contribution.score = _quantize_rating(_decimal_rating(contribution.score) + rating_delta)
            contribution.save(update_fields=["score", "updated_at"])
        Comun.objects.filter(id__in=comun_ids).update(rating_score=F("rating_score") + rating_delta)
    return rating_delta


def _subscribed_comun_slugs_from_settings(settings: dict | None) -> set[str]:
    if not isinstance(settings, dict):
        return set()
    subscribed_slugs = {
        str(slug or "").strip()
        for slug in (settings.get("my_feed_comuns", []) or [])
        if str(slug or "").strip()
    }
    category_selection = settings.get("my_feed_comun_categories", {}) or {}
    if isinstance(category_selection, dict):
        subscribed_slugs.update(
            str(slug or "").strip()
            for slug in category_selection.keys()
            if str(slug or "").strip()
        )
    return subscribed_slugs


def _record_comun_subscription_events(
    *,
    user_id: int | None,
    slugs: set[str],
    source: str = "feed_settings",
    action: str = "subscribe",
) -> None:
    if not user_id or not slugs:
        return

    from my_feed.models import ComunSubscriptionEvent

    events = [
        ComunSubscriptionEvent(
            user_id=user_id,
            comun_id=comun_id,
            comun_slug=slug,
            source=source,
            action=action,
        )
        for comun_id, slug in Comun.objects.filter(slug__in=slugs).values_list("id", "slug")
    ]
    if events:
        ComunSubscriptionEvent.objects.bulk_create(events, batch_size=1000)


def _sync_comun_subscriber_counts(
    previous_settings: dict,
    next_settings: dict,
    *,
    user_id: int | None = None,
) -> None:
    previous_slugs = _subscribed_comun_slugs_from_settings(previous_settings)
    next_slugs = _subscribed_comun_slugs_from_settings(next_settings)
    added_slugs = next_slugs - previous_slugs
    removed_slugs = previous_slugs - next_slugs
    if added_slugs:
        Comun.objects.filter(slug__in=added_slugs).update(subscribers_count=F("subscribers_count") + 1)
        _record_comun_subscription_events(user_id=user_id, slugs=added_slugs)
    if removed_slugs:
        Comun.objects.filter(slug__in=removed_slugs).update(
            subscribers_count=Case(
                When(subscribers_count__gt=0, then=F("subscribers_count") - 1),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        _record_comun_subscription_events(
            user_id=user_id,
            slugs=removed_slugs,
            action="unsubscribe",
        )


def _ensure_users_subscribed_to_comun(comun: Comun, user_ids: object) -> int:
    slug = str(getattr(comun, "slug", "") or "").strip()
    if not slug:
        return 0

    normalized_user_ids: list[int] = []
    seen_user_ids: set[int] = set()
    raw_user_ids = user_ids if isinstance(user_ids, (list, tuple, set)) else []
    for raw_user_id in raw_user_ids:
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        normalized_user_ids.append(user_id)
    if not normalized_user_ids:
        return 0

    from my_feed.models import ComunSubscriptionEvent, UserFeedSettings

    active_user_ids = set(
        User.objects.filter(id__in=normalized_user_ids, is_active=True).values_list("id", flat=True)
    )
    if not active_user_ids:
        return 0

    new_subscribers_count = 0
    new_subscriber_user_ids: list[int] = []
    with transaction.atomic():
        settings_by_user_id = {
            settings.user_id: settings
            for settings in UserFeedSettings.objects.select_for_update().filter(user_id__in=active_user_ids)
        }
        for user_id in sorted(active_user_ids):
            settings = settings_by_user_id.get(user_id)
            is_new_settings = settings is None
            if settings is None:
                settings = UserFeedSettings(user_id=user_id)

            current_slugs: list[str] = []
            current_slug_set: set[str] = set()
            for raw_slug in settings.my_feed_comuns or []:
                current_slug = str(raw_slug or "").strip()
                if not current_slug or current_slug in current_slug_set:
                    continue
                current_slug_set.add(current_slug)
                current_slugs.append(current_slug)

            category_selection = settings.my_feed_comun_categories or {}
            was_subscribed = slug in current_slug_set or (
                isinstance(category_selection, dict) and slug in category_selection
            )
            if slug in current_slug_set:
                continue

            settings.my_feed_comuns = [*current_slugs, slug]
            if is_new_settings:
                settings.save()
            else:
                settings.save(update_fields=["my_feed_comuns", "updated_at"])
            if not was_subscribed:
                new_subscribers_count += 1
                new_subscriber_user_ids.append(user_id)

        if new_subscribers_count:
            Comun.objects.filter(id=comun.id).update(
                subscribers_count=F("subscribers_count") + new_subscribers_count
            )
            ComunSubscriptionEvent.objects.bulk_create(
                [
                    ComunSubscriptionEvent(
                        user_id=user_id,
                        comun_id=comun.id,
                        comun_slug=slug,
                        source=ComunSubscriptionEvent.SOURCE_MODERATOR_SYNC,
                    )
                    for user_id in new_subscriber_user_ids
                ],
                batch_size=1000,
            )
    return new_subscribers_count


def _ensure_comun_moderators_subscribed(comun: Comun) -> int:
    user_ids = set(comun.moderators.values_list("id", flat=True))
    if getattr(comun, "creator_id", None):
        user_ids.add(comun.creator_id)
    return _ensure_users_subscribed_to_comun(comun, user_ids)


def _post_author_is_site_user(post: Post) -> bool:
    author = getattr(post, "author", None)
    if author is None and getattr(post, "author_id", None):
        author = Author.objects.filter(id=post.author_id).first()
    if not author:
        return False
    if getattr(author, "channel_id", None) or getattr(author, "channel_url", "") or getattr(author, "invite_url", ""):
        return False
    username = str(getattr(author, "username", "") or "").strip()
    if not username:
        return False
    return User.objects.filter(username__iexact=username, is_active=True).exists()


def _comun_site_user_posts_queryset(comun: Comun):
    return (
        _comun_posts_base_queryset(comun)
        .filter(
            author__channel_id__isnull=True,
            author__channel_url="",
            author__invite_url="",
            author__username__in=User.objects.filter(is_active=True).values("username"),
        )
    )


def _maybe_increment_comun_author_count_for_post(
    post: Post | None,
    *,
    comun: Comun | None = None,
) -> bool:
    if not post or not getattr(post, "author_id", None):
        return False
    if bool(getattr(post, "is_pending", False)) or bool(getattr(post, "is_blocked", False)):
        return False
    if not _post_author_is_site_user(post):
        return False
    comun = comun or _post_comun(post)
    if not comun:
        return False
    previous_site_posts = _comun_site_user_posts_queryset(comun).exclude(id=post.id)
    if previous_site_posts.filter(author_id=post.author_id).exists():
        return False
    if previous_site_posts.exists():
        Comun.objects.filter(id=comun.id).update(authors_count=F("authors_count") + 1)
    else:
        Comun.objects.filter(id=comun.id).update(
            authors_count=Case(
                When(authors_count__lt=1, then=Value(1)),
                default=F("authors_count"),
                output_field=IntegerField(),
            )
        )
    return True


def _candidate_comun_ids_for_post(post: Post | None) -> list[int]:
    if not post:
        return []

    combined_filter = Q()
    has_filter = False
    raw_data = post.raw_data if isinstance(getattr(post, "raw_data", None), dict) else {}
    comun_slug = str(raw_data.get("comun_slug") or "").strip()
    if comun_slug:
        combined_filter |= Q(slug=comun_slug)
        has_filter = True
    if getattr(post, "author_id", None) and _post_author_is_telegram_channel_source(post):
        combined_filter |= Q(telegram_source_author_id=post.author_id)
        has_filter = True

    if not has_filter:
        return []

    return list(
        Comun.objects.filter(combined_filter, is_active=True)
        .exclude(slug__iexact="faq")
        .values_list("id", flat=True)
        .distinct()
    )


def _recalculate_comun_ratings_for_post(post_or_id: Post | int | None) -> None:
    """Full rebuild for maintenance paths. Live post events must use rating deltas."""
    if not post_or_id:
        return
    if isinstance(post_or_id, Post):
        post = post_or_id
    else:
        post = Post.objects.filter(id=post_or_id).prefetch_related("tags").first()
    if not post:
        return
    for comun_id in _candidate_comun_ids_for_post(post):
        _recalculate_comun_rating(comun_id)


def _comun_posts_base_queryset(comun: Comun, now=None):
    now = now or timezone.now()
    membership_filter = _comun_post_membership_filter(comun)
    if not membership_filter:
        return Post.objects.none()
    base_query = (
        Post.objects.filter(
            membership_filter,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .distinct()
    )
    telegram_source_author_id = getattr(comun, "telegram_source_author_id", None)
    channel_author_filter = _telegram_channel_author_filter()
    if telegram_source_author_id:
        base_query = base_query.exclude(channel_author_filter & ~Q(author_id=telegram_source_author_id))
    else:
        base_query = base_query.exclude(channel_author_filter)
    excluded_author_ids = list(comun.excluded_authors.values_list("id", flat=True))
    if excluded_author_ids:
        base_query = base_query.exclude(author_id__in=excluded_author_ids)
    blocked_tags = list(comun.blocked_tags.filter(is_active=True))
    blocked_tag_ids = [tag.id for tag in blocked_tags if tag.id]
    blocked_tag_lemmas = [
        (tag.lemma or _lemmatize_tag(tag.name) or "").strip().lower()
        for tag in blocked_tags
        if (tag.lemma or _lemmatize_tag(tag.name) or "").strip()
    ]
    if blocked_tag_ids or blocked_tag_lemmas:
        blocked_tags_filter = Q()
        if blocked_tag_ids:
            blocked_tags_filter |= Q(tags__id__in=blocked_tag_ids)
        if blocked_tag_lemmas:
            blocked_tags_filter |= Q(tags__lemma__in=blocked_tag_lemmas)
        base_query = base_query.exclude(blocked_tags_filter).distinct()
    blocked_post_ids: list[int] = []
    if bool(getattr(comun, "forbid_external_links", False)):
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


def _post_belongs_to_comun(comun: Comun, post_or_id: Post | int | None, now=None) -> bool:
    if not comun or not post_or_id:
        return False
    post_id = getattr(post_or_id, "id", post_or_id)
    try:
        post_id = int(post_id)
    except (TypeError, ValueError):
        return False
    if post_id <= 0:
        return False
    return _comun_posts_base_queryset(comun, now=now).filter(id=post_id).exists()


def _generate_manual_message_id(author: Author) -> int:
    return _feeds_views()._generate_manual_message_id(author)


def _apply_post_tags(post: Post, explicit_tags: list[str] | None = None) -> None:
    _feeds_views()._apply_post_tags(post, explicit_tags)


def _favorite_post_ids_for_user(posts: list[Post], user: User | None) -> set[int]:
    return _feeds_views()._favorite_post_ids_for_user(posts, user)


def _filter_posts_for_language(queryset, language: str):
    return _feeds_views()._filter_posts_for_language(queryset, language)


def _post_translation_prefetch(language: str):
    return _feeds_views()._post_translation_prefetch(language)


def _serialize_backend_post_card(
    request: HttpRequest,
    post: Post,
    user: User | None = None,
    *,
    now=None,
    is_favorite: bool = False,
    language: str = "ru",
) -> dict:
    return _feeds_views()._serialize_backend_post_card(
        request,
        post,
        user,
        now=now,
        is_favorite=is_favorite,
        language=language,
    )


def _maybe_notify_post_added_to_voting(
    *,
    post: Post,
    comun: Comun,
    category: ComunCategory | None,
    actor: User | None,
    previous_category: ComunCategory | None = None,
) -> None:
    _feeds_views()._maybe_notify_post_added_to_voting(
        post=post,
        comun=comun,
        category=category,
        actor=actor,
        previous_category=previous_category,
    )


def _maybe_notify_new_author(author: Author, post: Post) -> None:
    _feeds_views()._maybe_notify_new_author(author, post)


def _maybe_notify_post_published_to_subscribers(
    post: Post,
    *,
    actor: User | None = None,
    comun: Comun | None = None,
    category: ComunCategory | None = None,
) -> None:
    _feeds_views()._maybe_notify_post_published_to_subscribers(
        post,
        actor=actor,
        comun=comun,
        category=category,
    )


__all__ = [
    "_COMUN_ACTIVITY_POINTS",
    "_COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR",
    "_COMUN_COMMENT_RATING_WEIGHT",
    "_active_comun_category_queryset",
    "_apply_comun_rating_delta_for_post",
    "_active_comun_glossary_queryset",
    "_allowed_template_overrides_for_comun_category",
    "_allowed_templates_for_comun",
    "_allowed_templates_for_comun_category",
    "_apply_post_tags",
    "_attach_pending_comuns_for_author",
    "_author_avatar_logo_url",
    "_author_avatar_url",
    "_author_telegram_source_comun",
    "_candidate_comun_ids_for_post",
    "_comun_can_manage_moderators",
    "_comun_categories_count",
    "_comun_categories_list",
    "_comun_category_queryset",
    "_comun_creation_access_state",
    "_comun_glossary_queryset",
    "_comun_is_moderator",
    "_comun_logo_url",
    "_comun_manual_posts_filter",
    "_comun_minimum_author_rating_value",
    "_comun_post_membership_filter",
    "_comun_post_access_error_message",
    "_comun_post_access_state",
    "_comun_posts_base_queryset",
    "_comun_source_filter",
    "_current_user_verified_telegram_authors",
    "_ensure_comun_category_by_name",
    "_ensure_telegram_channel_comun_for_author",
    "_ensure_tag_by_name",
    "_favorite_post_ids_for_user",
    "_format_rating_value",
    "_generate_manual_message_id",
    "_generate_unique_comun_category_slug",
    "_generate_unique_comun_glossary_term_slug",
    "_generate_unique_comun_name",
    "_generate_unique_comun_slug",
    "_is_internal_comuna_url",
    "_lemmatize_tag",
    "_maybe_notify_new_author",
    "_maybe_notify_post_published_to_subscribers",
    "_maybe_notify_post_added_to_voting",
    "_maybe_increment_comun_author_count_for_post",
    "_normalize_comun_category_name",
    "_normalize_comun_glossary_definition",
    "_normalize_comun_glossary_term",
    "_normalize_comun_glossary_term_en",
    "_normalize_comun_minimum_author_rating",
    "_normalize_comun_slug",
    "_normalize_tag_value",
    "_normalize_telegram_channel_username",
    "_parse_int_list",
    "_parse_post_reference_to_id",
    "_parse_tag_payload",
    "_payload_contains_external_links",
    "_post_belongs_to_comun",
    "_post_comun",
    "_post_comun_slug",
    "_public_user_author_ids",
    "_publish_ready_filter",
    "_recalculate_comun_rating",
    "_recalculate_comun_ratings_for_post",
    "_sync_comun_vote_counts",
    "_serialize_backend_post_card",
    "_serialize_post_comun",
    "_site_user_avatar_url",
    "_sync_comun_glossary_terms",
    "_sync_comun_subscriber_counts",
    "_sync_comun_logo_from_author",
    "_text_contains_external_links",
]


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
