from __future__ import annotations

import inspect
import json
import math
import re
import secrets
import urllib.parse
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

try:
    import pymorphy2
except ImportError:  # optional dependency for lemmatization
    pymorphy2 = None

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import HttpRequest
from django.utils import timezone
from django.utils.text import slugify

from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunPostCategoryAssignment,
    ComunVote,
)
from editor.models import PostPollVote
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
from ratings.service import author_rating_value, format_rating_value, user_max_author_rating
from users.models import AuthorAdmin

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
_COMUN_COMMENT_RATING_WEIGHT = Decimal("0.1")
_MORPH_ANALYZER = None


def _feeds_views():
    from feeds import views as feeds_views

    return feeds_views


def _media_url(request: HttpRequest | None, field) -> str | None:
    if not field:
        return None
    site_base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if site_base:
        try:
            return f"{site_base}{field.url}"
        except Exception:
            pass
    if request is None:
        return None
    try:
        return request.build_absolute_uri(field.url)
    except Exception:
        return None


def _author_avatar_url(request: HttpRequest | None, author: Author) -> str | None:
    return _media_url(request, author.avatar_image) or author.avatar_url


def _author_avatar_logo_url(author: Author | None) -> str:
    if not author:
        return ""
    avatar_image = getattr(author, "avatar_image", None)
    if avatar_image:
        try:
            image_url = avatar_image.url
        except Exception:
            image_url = ""
        if image_url:
            site_base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
            if site_base and image_url.startswith("/"):
                image_url = f"{site_base}{image_url}"
            return image_url[:500]
    return str(getattr(author, "avatar_url", "") or "").strip()[:500]


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
            or current_logo_url == str(getattr(author, "avatar_url", "") or "").strip()
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


def _slugify_title(text: str) -> str:
    if not text:
        return ""
    translit_map = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ъ": "",
        "ь": "",
    }
    lowered = text.lower()
    translit = "".join(translit_map.get(ch, ch) for ch in lowered)
    return re.sub(r"[^a-z0-9]+", "-", translit).strip("-")


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
        base_slug = _slugify_title(normalized_name)[:120]
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
        base_slug = _slugify_title(normalized_term)[:180]
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
        base_slug = _slugify_title(normalized_value)[:160]
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


def _serialize_post_comun(request: HttpRequest | None, post: Post) -> dict | None:
    comun = _post_comun(post)
    if not comun:
        return None
    return {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "logo_url": _comun_logo_url(request, comun),
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
    if minimum_rating <= 0:
        return True, minimum_rating, None

    if author is not None:
        author_rating = author_rating_value(getattr(author, "rating_total", 0))
        return author_rating >= minimum_rating, minimum_rating, author_rating

    personal_author = _personal_user_author(user)
    if not personal_author:
        return False, minimum_rating, 0.0

    personal_author_rating = author_rating_value(getattr(personal_author, "rating_total", 0))
    return personal_author_rating >= minimum_rating, minimum_rating, personal_author_rating


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


def _comun_source_filter(comun: Comun) -> Q | None:
    combined_filter = Q()
    has_source = False

    telegram_source_author_id = getattr(comun, "telegram_source_author_id", None)
    if telegram_source_author_id:
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
        | Q(author__telegram_source_comun__isnull=False)
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


def _comun_rating_value(post_rating_total: int | None, comments_total: int | None) -> Decimal:
    rating = Decimal(int(post_rating_total or 0)) + (
        Decimal(int(comments_total or 0)) * _COMUN_COMMENT_RATING_WEIGHT
    )
    return rating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _recalculate_comun_rating(comun_id: int) -> tuple[int, int, Decimal]:
    comun = (
        Comun.objects.filter(id=comun_id)
        .select_related("telegram_source_author")
        .prefetch_related("excluded_authors", "blocked_tags")
        .first()
    )
    if not comun:
        return 0, 0, Decimal("0.00")
    counts = ComunVote.objects.filter(comun_id=comun_id).aggregate(
        up=Count("id", filter=Q(value=1)),
        down=Count("id", filter=Q(value=-1)),
    )
    votes_up = int(counts.get("up") or 0)
    votes_down = int(counts.get("down") or 0)
    post_totals = _comun_posts_base_queryset(comun).aggregate(
        post_rating_total=Sum("rating"),
        comments_total=Sum("comments_count"),
    )
    rating_score = _comun_rating_value(
        post_totals.get("post_rating_total"),
        post_totals.get("comments_total"),
    )
    Comun.objects.filter(id=comun_id).update(
        votes_up=votes_up,
        votes_down=votes_down,
        rating_score=rating_score,
    )
    return votes_up, votes_down, rating_score


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
    if getattr(post, "author_id", None):
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
    if bool(getattr(comun, "forbid_external_links", False)):
        blocked_post_ids: list[int] = []
        for row in base_query.values("id", "title", "content", "raw_data").iterator(chunk_size=200):
            raw_data = row.get("raw_data") if isinstance(row, dict) else {}
            template_payload = raw_data.get("template") if isinstance(raw_data, dict) else None
            if _payload_contains_external_links(
                title=row.get("title") if isinstance(row, dict) else None,
                content=row.get("content") if isinstance(row, dict) else None,
                template_payload=template_payload,
            ):
                blocked_post_ids.append(int(row["id"]))
        if blocked_post_ids:
            base_query = base_query.exclude(id__in=blocked_post_ids)
    return base_query


def _generate_manual_message_id(author: Author) -> int:
    return _feeds_views()._generate_manual_message_id(author)


def _apply_post_tags(post: Post, explicit_tags: list[str] | None = None) -> None:
    _feeds_views()._apply_post_tags(post, explicit_tags)


def _favorite_post_ids_for_user(posts: list[Post], user: User | None) -> set[int]:
    return _feeds_views()._favorite_post_ids_for_user(posts, user)


def _serialize_backend_post_card(
    request: HttpRequest,
    post: Post,
    user: User | None = None,
    *,
    now=None,
    is_favorite: bool = False,
) -> dict:
    return _feeds_views()._serialize_backend_post_card(
        request,
        post,
        user,
        now=now,
        is_favorite=is_favorite,
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


__all__ = [
    "_COMUN_ACTIVITY_POINTS",
    "_COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR",
    "_COMUN_COMMENT_RATING_WEIGHT",
    "_active_comun_category_queryset",
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
    "_maybe_notify_post_added_to_voting",
    "_normalize_comun_category_name",
    "_normalize_comun_glossary_definition",
    "_normalize_comun_glossary_term",
    "_normalize_comun_minimum_author_rating",
    "_normalize_comun_slug",
    "_normalize_tag_value",
    "_normalize_telegram_channel_username",
    "_parse_int_list",
    "_parse_post_reference_to_id",
    "_parse_tag_payload",
    "_payload_contains_external_links",
    "_post_comun",
    "_post_comun_slug",
    "_public_user_author_ids",
    "_publish_ready_filter",
    "_recalculate_comun_rating",
    "_recalculate_comun_ratings_for_post",
    "_serialize_backend_post_card",
    "_serialize_post_comun",
    "_site_user_avatar_url",
    "_slugify_title",
    "_sync_comun_glossary_terms",
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
