from __future__ import annotations

import json
import hmac
import hashlib
import os
import re
import secrets
import base64
import time
import inspect
try:
    import pymorphy2
except ImportError:  # optional dependency for lemmatization
    pymorphy2 = None
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import timedelta, timezone as dt_timezone
from math import ceil
from html import escape, unescape
from xml.sax.saxutils import escape as xml_escape
from django.db import transaction
from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, get_user_model

from .models import (
    Author,
    AuthorAdmin,
    AuthorVerificationCode,
    BotSession,
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    PostRead,
    Rubric,
    Tag,
    TelegramAccount,
    VkAccount,
)
from .telegram_media import download_telegram_file_by_path

User = get_user_model()

_BOT_ID: int | None = None
_TOKEN_SIGNER = TimestampSigner(salt="comuna-auth")
_TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def _issue_token(user: User) -> str:
    return _TOKEN_SIGNER.sign(str(user.id))


def _get_user_from_token(token: str) -> User | None:
    try:
        unsigned = _TOKEN_SIGNER.unsign(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return User.objects.get(id=int(unsigned))
    except (User.DoesNotExist, ValueError, TypeError):
        return None


def _get_user_from_request(request: HttpRequest) -> User | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    elif auth.lower().startswith("token "):
        token = auth.split(" ", 1)[1].strip()
    else:
        token = ""
    if not token:
        return None
    return _get_user_from_token(token)


_TELEGRAM_LOGIN_FIELDS = {
    "id",
    "first_name",
    "last_name",
    "username",
    "photo_url",
    "auth_date",
}


def _verify_telegram_login(payload: dict) -> tuple[bool, str | None]:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False, "telegram auth disabled"
    provided_hash = payload.get("hash")
    if not provided_hash:
        return False, "missing hash"
    data = {
        k: v
        for k, v in payload.items()
        if k in _TELEGRAM_LOGIN_FIELDS and v is not None
    }
    auth_date_raw = data.get("auth_date")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        return False, "invalid auth date"
    now_ts = int(timezone.now().timestamp())
    if now_ts - auth_date > 60 * 60 * 24:
        return False, "auth expired"
    for key, value in list(data.items()):
        data[key] = str(value)
    data_check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data.keys()))
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if computed_hash != provided_hash:
        return False, "invalid hash"
    return True, None


def _generate_unique_username(base: str, suffix: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", base).strip("_")
    if not base:
        base = "user"
    candidate = base
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}_{suffix}"
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f"tg_{suffix}"
    return candidate[:150]


def _is_comuna_rubric(rubric: Rubric | None) -> bool:
    if not rubric or not rubric.slug:
        return False
    return rubric.slug.strip().lower() == "comuna"


def _author_display_fields(
    author: Author,
    rubric: Rubric | None,
    post_channel_url: str | None = None,
) -> tuple[str | None, str]:
    channel_url = author.invite_url or author.channel_url
    title = author.title or author.username
    if _is_comuna_rubric(rubric):
        return "", "Admin"
    if not channel_url:
        channel_url = post_channel_url
    return channel_url, title


def _author_avatar_for_rubric(
    request: HttpRequest | None,
    author: Author,
    rubric: Rubric | None,
) -> str | None:
    if _is_comuna_rubric(rubric):
        return None
    return _author_avatar_url(request, author)


def _fetch_vk_json(method: str, payload: dict) -> dict | None:
    url = f"https://api.vk.com/method/{method}"
    data = urllib.parse.urlencode(payload)
    try:
        with urllib.request.urlopen(f"{url}?{data}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _decode_jwt_payload(token: str) -> dict | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload_segment = parts[1]
    padding = "=" * (-len(payload_segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None


def _parse_vk_id_token(id_token: str, user_id_hint: int | None = None) -> dict | None:
    payload = _decode_jwt_payload(id_token)
    if not payload:
        return None

    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        return None

    vk_app_id = os.environ.get("VK_APP_ID")
    aud = payload.get("aud")
    if vk_app_id and aud and str(aud) != str(vk_app_id):
        return None

    sub = payload.get("sub") or payload.get("user_id") or user_id_hint
    try:
        vk_id = int(sub)
    except (TypeError, ValueError):
        return None

    screen_name = (payload.get("preferred_username") or payload.get("screen_name") or "").strip()
    full_name = (payload.get("name") or "").strip()
    first_name = (payload.get("given_name") or "").strip()
    last_name = (payload.get("family_name") or "").strip()
    if not first_name and full_name:
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        if len(parts) > 1:
            last_name = parts[1]
    avatar_url = (payload.get("picture") or payload.get("avatar") or "").strip()

    return {
        "vk_id": vk_id,
        "screen_name": screen_name,
        "first_name": first_name,
        "last_name": last_name,
        "avatar_url": avatar_url,
    }


@csrf_exempt
def vk_auth(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    access_token = (payload.get("access_token") or "").strip()
    id_token = (payload.get("id_token") or "").strip()
    user_id_hint = payload.get("user_id")
    vk_user = None

    if access_token:
        response = _fetch_vk_json(
            "users.get",
            {
                "access_token": access_token,
                "v": "5.131",
                "fields": "photo_200,screen_name",
            },
        )
        if response and "response" in response:
            users = response.get("response") or []
            if users:
                vk_user = {
                    "vk_id": users[0].get("id"),
                    "screen_name": (users[0].get("screen_name") or "").strip(),
                    "first_name": (users[0].get("first_name") or "").strip(),
                    "last_name": (users[0].get("last_name") or "").strip(),
                    "avatar_url": (users[0].get("photo_200") or "").strip(),
                }

    if not vk_user and id_token:
        vk_user = _parse_vk_id_token(id_token, user_id_hint=user_id_hint)

    if not vk_user:
        return JsonResponse({"ok": False, "error": "vk auth failed"}, status=400)

    try:
        vk_id = int(vk_user.get("vk_id"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid vk id"}, status=400)

    screen_name = (vk_user.get("screen_name") or "").strip()
    first_name = (vk_user.get("first_name") or "").strip()
    last_name = (vk_user.get("last_name") or "").strip()
    avatar_url = (vk_user.get("avatar_url") or "").strip()

    account = (
        VkAccount.objects.select_related("user")
        .filter(vk_id=vk_id)
        .first()
    )
    if account:
        user = account.user
    else:
        base_username = screen_name or first_name or "vk"
        candidate = _generate_unique_username(base_username, str(vk_id))
        user = User.objects.create_user(username=candidate)
        user.set_unusable_password()
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save(update_fields=["password", "first_name", "last_name"])
        account = VkAccount.objects.create(
            user=user,
            vk_id=vk_id,
            username=screen_name,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
        )

    account.username = screen_name
    account.first_name = first_name
    account.last_name = last_name
    account.avatar_url = avatar_url
    account.save(update_fields=["username", "first_name", "last_name", "avatar_url", "updated_at"])

    token = _issue_token(user)
    return JsonResponse({"ok": True, "token": token, "user": _serialize_user(user)})


def _serialize_user(user: User) -> dict:
    author_links = (
        AuthorAdmin.objects.select_related("author", "author__rubric")
        .filter(user=user, verified_at__isnull=False)
        .order_by("author__username")
    )
    authors = []
    avatar_url = None
    for link in author_links:
        author = link.author
        if not avatar_url:
            avatar_url = _author_avatar_url(None, author)
        authors.append(
            {
                "username": author.username,
                "title": author.title,
                "channel_url": author.invite_url or author.channel_url,
                "avatar_url": _author_avatar_url(None, author),
                "rubric": author.rubric.name if author.rubric else None,
                "rubric_slug": author.rubric.slug if author.rubric else None,
                "auto_publish": author.auto_publish,
                "publish_delay_days": author.publish_delay_days,
                "invite_url": author.invite_url,
                "author_rating": _author_rating_value(author.rating_total),
            }
        )
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": avatar_url,
        "is_staff": user.is_staff,
        "is_author": bool(authors),
        "authors": authors,
    }


@csrf_exempt
def telegram_auth(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        payload = dict(request.GET.items())
    elif request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    else:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    ok, error_message = _verify_telegram_login(payload)
    if not ok:
        return JsonResponse({"ok": False, "error": error_message or "invalid telegram auth"}, status=400)

    try:
        telegram_id = int(payload.get("id"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid telegram id"}, status=400)

    username = (payload.get("username") or "").strip()
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    avatar_url = (payload.get("photo_url") or "").strip()

    account = (
        TelegramAccount.objects.select_related("user")
        .filter(telegram_id=telegram_id)
        .first()
    )

    if account:
        user = account.user
    else:
        base_username = username or (first_name or "tg")
        candidate = _generate_unique_username(base_username, str(telegram_id))
        user = User.objects.create_user(username=candidate)
        user.set_unusable_password()
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save(update_fields=["password", "first_name", "last_name"])
        account = TelegramAccount.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
        )

    account.username = username
    account.first_name = first_name
    account.last_name = last_name
    account.avatar_url = avatar_url
    account.save(update_fields=["username", "first_name", "last_name", "avatar_url", "updated_at"])

    token = _issue_token(user)
    if request.method == "GET":
        next_url = request.GET.get("next") or "/"
        next_literal = json.dumps(next_url)
        html = (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<title>Telegram login</title></head><body>"
            "<script>"
            f"try{{localStorage.setItem('comuna.site.token','{token}');}}catch(e){{}}"
            f"window.location.replace({next_literal});"
            "</script>"
            "</body></html>"
        )
        return HttpResponse(html, content_type="text/html")
    return JsonResponse({"ok": True, "token": token, "user": _serialize_user(user)})


def _generate_verification_code() -> str:
    token = secrets.token_urlsafe(6).replace("_", "").replace("-", "").upper()
    return f"COMUNA-{token}"


def _generate_manual_message_id(author: Author) -> int:
    for _ in range(10):
        candidate = -secrets.randbelow(2_000_000_000) - 1
        if not Post.objects.filter(author=author, message_id=candidate).exists():
            return candidate
    raise ValueError("failed to generate message id")


def _maybe_notify_new_author(author: Author, post: Post) -> None:
    if author.first_post_notified:
        return
    if post.is_pending or post.is_blocked:
        return
    already_published = (
        Post.objects.filter(author=author, is_pending=False, is_blocked=False)
        .exclude(id=post.id)
        .exists()
    )
    if already_published:
        author.first_post_notified = True
        author.save(update_fields=["first_post_notified", "updated_at"])
        return

    admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID
    if not admin_chat:
        return

    site_base = settings.SITE_BASE_URL.rstrip("/")
    author_url = f"{site_base}/{author.username}"
    post_url = f"{site_base}/b/post/{post.id}"
    rubric = author.rubric.name if author.rubric else "—"
    _send_bot_message(
        int(admin_chat),
        "Новый автор опубликовал первый пост.\n"
        f"Канал: @{author.username}\n"
        f"Рубрика: {rubric}\n"
        f"Автор: {author_url}\n"
        f"Пост: {post_url}",
    )
    author.first_post_notified = True
    author.save(update_fields=["first_post_notified", "updated_at"])


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


def _author_rating_value(total_rating: int | None) -> float:
    return round((total_rating or 0) * 0.05, 2)


def _author_posts_rating_filter(now) -> Q:
    return (
        Q(posts__is_blocked=False, posts__is_pending=False)
        & (Q(posts__publish_at__isnull=True) | Q(posts__publish_at__lte=now))
    )


def _rubric_icon_url(request: HttpRequest | None, rubric: Rubric | None) -> str | None:
    if not rubric:
        return None
    return _media_url(request, rubric.icon_thumb) or _media_url(request, rubric.icon_url)


def _format_lastmod(value) -> str | None:
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).date().isoformat()


def _publish_ready_filter(now) -> Q:
    return Q(publish_at__isnull=True) | Q(publish_at__lte=now)


def _sitemap_base_url(request: HttpRequest) -> str:
    base = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if base:
        return base
    return request.build_absolute_uri("/").rstrip("/")


def _build_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().splitlines()[0].strip()
    positions = []
    for separator in (".", "!", "?"):
        idx = first_line.find(separator)
        if idx > 0:
            positions.append((idx, separator))
    if positions:
        idx, separator = min(positions, key=lambda item: item[0])
        if separator == ".":
            return first_line[:idx].strip()
        return first_line[: idx + 1].strip()
    if len(first_line) <= 120:
        return first_line
    return first_line[:117].strip() + "..."


def _post_display_title(post: Post) -> str:
    direct_title = (post.title or "").strip()
    if direct_title:
        return direct_title

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    poll = raw_data.get("poll") if isinstance(raw_data, dict) else None
    if isinstance(poll, dict):
        question = str(poll.get("question") or "").strip()
        if question:
            poll_title = _build_title(question)
            if poll_title:
                return poll_title

    content_text = _strip_html(post.content or "").strip()
    if content_text:
        content_title = _build_title(content_text)
        if content_title:
            return content_title

    return "Пост"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return unescape(re.sub(r"<[^>]+>", "", text))


def _normalize_tag_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


_MORPH_ANALYZER = None


def _ensure_pymorphy2_compat():
    if pymorphy2 is None:
        return
    if not hasattr(inspect, "getargspec"):
        from collections import namedtuple
        ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")

        def getargspec(func):  # type: ignore
            spec = inspect.getfullargspec(func)
            return ArgSpec(spec.args, spec.varargs, spec.varkw, spec.defaults)
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
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _count_tag_occurrences(text_lower: str, tag_lower: str) -> int:
    if not text_lower or not tag_lower:
        return 0
    if re.fullmatch(r"[\w\-]+", tag_lower):
        pattern = re.compile(rf"(?<!\w){re.escape(tag_lower)}(?!\w)")
        return len(pattern.findall(text_lower))
    return text_lower.count(tag_lower)


def _extract_hashtags(text: str) -> list[str]:
    if not text:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for match in re.findall(r"#([\w\-]+)", text, flags=re.UNICODE):
        value = _normalize_tag_value(match)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(value)
    return tags


def _tag_key(tag: Tag) -> str:
    if tag.lemma:
        return tag.lemma.strip().lower()
    lemma = _lemmatize_tag(tag.name)
    return (lemma or tag.name).strip().lower()


def _serialize_tag(tag: Tag) -> dict:
    lemma = tag.lemma or _lemmatize_tag(tag.name) or tag.name
    return {"name": tag.name, "lemma": lemma}


def _serialize_tags(tags) -> list[dict]:
    return [_serialize_tag(tag) for tag in tags]


def _apply_post_tags(post: Post, explicit_tags: list[str] | None = None) -> None:
    explicit_tags = explicit_tags or []
    existing_tags = {}
    for tag in Tag.objects.all():
        key = _tag_key(tag)
        if key and key not in existing_tags:
            existing_tags[key] = tag
    selected_tags: list[Tag] = []
    seen_ids: set[int] = set()

    for tag_name in explicit_tags:
        normalized = _normalize_tag_value(tag_name)
        if not normalized:
            continue
        lemma = _lemmatize_tag(normalized) or normalized
        key = lemma.lower()
        tag = existing_tags.get(key)
        if not tag:
            tag = Tag.objects.create(name=normalized, lemma=lemma)
            existing_tags[key] = tag
        if tag.id not in seen_ids:
            selected_tags.append(tag)
            seen_ids.add(tag.id)
            if len(selected_tags) >= 5:
                break

    if len(selected_tags) < 5 and existing_tags:
        text = _strip_html(f"{post.title} {post.content}").lower()
        candidates: list[tuple[int, int, str, Tag]] = []
        for tag in existing_tags.values():
            if not tag.is_active or tag.id in seen_ids:
                continue
            count = _count_tag_occurrences(text, tag.name.lower())
            if count:
                candidates.append((count, len(tag.name), tag.name.lower(), tag))
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
        for _, __, ___, tag in candidates:
            selected_tags.append(tag)
            if len(selected_tags) >= 5:
                break

    if selected_tags:
        post.tags.set(selected_tags)
    else:
        post.tags.clear()


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
    slug = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    return slug


def _extract_plain_text(message: dict) -> str:
    return (message.get("text") or message.get("caption") or "").strip()


def _is_telegram_service_message(message: dict) -> bool:
    service_keys = (
        "new_chat_members",
        "left_chat_member",
        "new_chat_title",
        "new_chat_photo",
        "delete_chat_photo",
        "group_chat_created",
        "supergroup_chat_created",
        "channel_chat_created",
        "message_auto_delete_timer_changed",
        "pinned_message",
        "video_chat_started",
        "video_chat_ended",
        "video_chat_participants_invited",
        "video_chat_scheduled",
        "forum_topic_created",
        "forum_topic_edited",
        "forum_topic_closed",
        "forum_topic_reopened",
        "general_forum_topic_hidden",
        "general_forum_topic_unhidden",
        "write_access_allowed",
        "giveaway",
        "giveaway_created",
        "giveaway_completed",
        "giveaway_winners",
        "chat_shared",
        "user_shared",
        "proximity_alert_triggered",
        "migrate_to_chat_id",
        "migrate_from_chat_id",
        "connected_website",
    )
    return any(key in message for key in service_keys)


def _extract_entities(message: dict) -> list[dict]:
    if message.get("text"):
        return message.get("entities") or []
    if message.get("caption"):
        return message.get("caption_entities") or []
    return []


def _utf16_offset_to_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    units = 0
    for index, ch in enumerate(text):
        codepoint = ord(ch)
        units += 2 if codepoint > 0xFFFF else 1
        if units > offset:
            return index + 1
        if units == offset:
            return index + 1
    return len(text)


def _entity_tags(entity: dict, segment: str) -> tuple[str, str] | None:
    entity_type = entity.get("type")
    if entity_type == "bold":
        return "<b>", "</b>"
    if entity_type == "italic":
        return "<i>", "</i>"
    if entity_type == "underline":
        return "<u>", "</u>"
    if entity_type == "strikethrough":
        return "<s>", "</s>"
    if entity_type == "spoiler":
        return '<span class="tg-spoiler">', "</span>"
    if entity_type == "code":
        return "<code>", "</code>"
    if entity_type == "pre":
        language = entity.get("language")
        class_attr = f' class="language-{escape(language)}"' if language else ""
        return f"<pre><code{class_attr}>", "</code></pre>"
    if entity_type == "blockquote":
        return "<blockquote>", "</blockquote>"
    if entity_type == "text_link":
        url = entity.get("url") or ""
        return f'<a href="{escape(url)}" target="_blank" rel="noopener">', "</a>"
    if entity_type == "url":
        href = segment.strip()
        return f'<a href="{escape(href)}" target="_blank" rel="noopener">', "</a>"
    if entity_type == "mention":
        username = segment.lstrip("@")
        return f'<a href="https://t.me/{escape(username)}" target="_blank" rel="noopener">', "</a>"
    return None


def _format_telegram_text(text: str, entities: list[dict]) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n")
    if not entities:
        return escape(normalized).replace("\n", "<br>")

    start_tags: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    end_tags: dict[int, list[tuple[int, str]]] = defaultdict(list)

    for entity in entities:
        offset = entity.get("offset")
        length = entity.get("length")
        if offset is None or length is None:
            continue
        start = _utf16_offset_to_index(normalized, offset)
        end = _utf16_offset_to_index(normalized, offset + length)
        if start >= end:
            continue
        segment = normalized[start:end]
        tags = _entity_tags(entity, segment)
        if not tags:
            continue
        open_tag, close_tag = tags
        start_tags[start].append((end, open_tag, close_tag))
        end_tags[end].append((start, close_tag))

    for index in start_tags:
        start_tags[index].sort(key=lambda item: item[0], reverse=True)
    for index in end_tags:
        end_tags[index].sort(key=lambda item: item[0], reverse=True)

    out: list[str] = []
    text_len = len(normalized)
    for index, ch in enumerate(normalized):
        if index in start_tags:
            for _, open_tag, _ in start_tags[index]:
                out.append(open_tag)
        out.append(escape(ch))
        if index + 1 in end_tags:
            for _, close_tag in end_tags[index + 1]:
                out.append(close_tag)

    return "".join(out).replace("\n", "<br>")


def _extract_photo_file_id(message: dict) -> str | None:
    photos = message.get("photo") or []
    if not photos:
        return None
    largest = max(
        photos,
        key=lambda item: (item.get("file_size", 0), item.get("width", 0) * item.get("height", 0)),
    )
    return largest.get("file_id")


def _extract_photo_url(message: dict, token: str) -> str | None:
    file_id = _extract_photo_file_id(message)
    if not file_id:
        return None
    file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
    if not file_info or not file_info.get("ok") or not file_info.get("result"):
        return None
    file_path = file_info["result"].get("file_path")
    if not file_path:
        return None
    return download_telegram_file_by_path(file_path, token)


def _build_content_with_images(
    text_html: str,
    image_urls: list[str],
    embed_html: str = "",
    poll_html: str = "",
) -> str:
    parts: list[str] = []
    if image_urls:
        if len(image_urls) == 1:
            media_html = f'<img src="{image_urls[0]}" alt="" />'
        else:
            gallery_imgs = "".join(f'<img src="{url}" alt="" />' for url in image_urls)
            media_html = f'<div class="post-gallery">{gallery_imgs}</div>'
        parts.append(media_html)
    if embed_html:
        parts.append(embed_html)
    if poll_html:
        parts.append(poll_html)
    if text_html:
        parts.append(text_html)
    return "<br><br>".join([part for part in parts if part])


def _build_telegram_embed_html(username: str, message_id: int, height: int) -> str:
    src = f"https://t.me/{username}/{message_id}?embed=1&single=1"
    return (
        '<div class="post-embed">'
        f'<iframe class="telegram-embed" src="{src}" '
        f'width="100%" height="{height}" frameborder="0" '
        'allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" '
        'allowfullscreen loading="lazy" referrerpolicy="no-referrer"></iframe>'
        "</div>"
    )


def _extract_telegram_embed(message: dict, username: str) -> tuple[str, str]:
    message_id = message.get("message_id")
    if not message_id or not username:
        return "", ""

    document = message.get("document") or {}
    mime_type = (document.get("mime_type") or "").lower()
    has_video = any(
        message.get(key) for key in ("video", "video_note", "animation")
    ) or mime_type.startswith("video/")
    has_audio = any(message.get(key) for key in ("audio", "voice")) or mime_type.startswith(
        "audio/"
    )

    if has_video:
        return _build_telegram_embed_html(username, message_id, 420), "Видео"
    if has_audio:
        return _build_telegram_embed_html(username, message_id, 200), "Аудио"
    return "", ""


def _extract_telegram_poll(message: dict) -> tuple[str, str]:
    poll = message.get("poll")
    if not isinstance(poll, dict):
        return "", ""

    question = str(poll.get("question") or "").strip()
    raw_options = poll.get("options") or []
    options: list[tuple[str, int]] = []
    if isinstance(raw_options, list):
        for option in raw_options:
            if not isinstance(option, dict):
                continue
            text = str(option.get("text") or "").strip()
            if not text:
                continue
            try:
                count = int(option.get("voter_count", 0))
            except (TypeError, ValueError):
                count = 0
            options.append((text, max(count, 0)))

    if not question and not options:
        return "", ""

    total_voters_raw = poll.get("total_voter_count")
    total_voters = (
        total_voters_raw if isinstance(total_voters_raw, int) and total_voters_raw >= 0 else None
    )

    option_items: list[str] = []
    for text, count in options:
        value_label = str(count)
        if total_voters and total_voters > 0:
            percent = round((count / total_voters) * 100)
            value_label = f"{count} ({percent}%)"
        option_items.append(
            f'<li class="post-poll-option">{escape(text)} <b>{value_label}</b></li>'
        )
    options_html = (
        f'<ul class="post-poll-options">{"".join(option_items)}</ul>' if option_items else ""
    )

    meta_parts: list[str] = []
    if poll.get("is_anonymous"):
        meta_parts.append("Анонимный опрос")
    if poll.get("allows_multiple_answers"):
        meta_parts.append("Можно выбрать несколько вариантов")
    if poll.get("is_closed"):
        meta_parts.append("Опрос завершен")
    if total_voters is not None:
        meta_parts.append(f"Голосов: {total_voters}")
    meta_html = f'<div class="post-poll-meta">{" · ".join(meta_parts)}</div>' if meta_parts else ""

    question_html = f'<div class="post-poll-question"><b>{escape(question)}</b></div>' if question else ""
    poll_html = (
        '<div class="post-poll">'
        + "".join(part for part in (question_html, options_html, meta_html) if part)
        + "</div>"
    )

    title = _build_title(question) if question else ""
    if not title:
        title = "Опрос"
    return poll_html, title


def _fetch_telegram_json(method: str, token: str, payload: dict) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        timeout = 30 if method == "getUpdates" else 5
        with urllib.request.urlopen(url, data=data, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _get_bot_id(token: str) -> int | None:
    global _BOT_ID
    if _BOT_ID:
        return _BOT_ID
    response = _fetch_telegram_json("getMe", token, {})
    if response and response.get("ok") and response.get("result"):
        bot_id = response["result"].get("id")
        if isinstance(bot_id, int):
            _BOT_ID = bot_id
            return bot_id
    return None


def _is_bot_admin(chat_id: int, token: str) -> bool:
    bot_id = _get_bot_id(token)
    if not bot_id:
        return False
    response = _fetch_telegram_json(
        "getChatMember", token, {"chat_id": chat_id, "user_id": bot_id}
    )
    if not response or not response.get("ok") or not response.get("result"):
        return False
    status = response["result"].get("status")
    return status in {"administrator", "creator"}


def _send_bot_message(chat_id: int, text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    _fetch_telegram_json("sendMessage", token, {"chat_id": chat_id, "text": text})


def _send_bot_message_with_keyboard(chat_id: int, text: str, keyboard: dict) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    payload = {"chat_id": chat_id, "text": text, "reply_markup": json.dumps(keyboard)}
    _fetch_telegram_json("sendMessage", token, payload)


def _answer_callback_query(callback_query_id: str, text: str = "") -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    _fetch_telegram_json("answerCallbackQuery", token, payload)


def _refresh_author_from_telegram(author: Author, chat_ref, token: str) -> None:
    chat = _fetch_telegram_json("getChat", token, {"chat_id": chat_ref})
    if not chat or not chat.get("ok") or not chat.get("result"):
        return

    result = chat["result"]
    if result.get("type") != "channel":
        return

    channel_id = result.get("id")
    if channel_id:
        author.channel_id = channel_id

    if result.get("title"):
        author.title = result["title"]
    if result.get("description"):
        author.description = result["description"]
    if result.get("username"):
        author.channel_url = f"https://t.me/{result['username']}"

    photo = result.get("photo")
    if photo and photo.get("big_file_id"):
        file_id = photo["big_file_id"]
        file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
        if file_info and file_info.get("ok") and file_info.get("result"):
            file_path = file_info["result"].get("file_path")
            if file_path:
                author.avatar_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                if file_id != author.avatar_file_id:
                    try:
                        with urllib.request.urlopen(author.avatar_url, timeout=10) as response:
                            data = response.read()
                        filename = os.path.basename(file_path) or f"{author.username}.jpg"
                        author.avatar_image.save(filename, ContentFile(data), save=False)
                        author.avatar_file_id = file_id
                    except Exception:
                        pass

    if channel_id:
        count = _fetch_telegram_json("getChatMemberCount", token, {"chat_id": channel_id})
        if count and count.get("ok") and isinstance(count.get("result"), int):
            author.subscribers_count = count["result"]

    author.save(
        update_fields=[
            "title",
            "description",
            "channel_id",
            "channel_url",
            "avatar_url",
            "avatar_image",
            "avatar_file_id",
            "subscribers_count",
            "updated_at",
        ]
    )


def _build_rubric_keyboard() -> list[list[dict]]:
    rubrics = list(
        Rubric.objects.filter(is_active=True, is_hidden=False).order_by(
            "sort_order", "name"
        )
    )
    keyboard: list[list[dict]] = []
    row: list[dict] = []
    for rubric in rubrics:
        row.append({"text": rubric.name, "callback_data": f"rubric:{rubric.id}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard


def _get_admin_authors(chat_id: int) -> list[Author]:
    return list(
        Author.objects.filter(admin_chat_id=chat_id, is_blocked=False)
        .select_related("rubric")
        .order_by("username")
    )


def _format_delay_label(days: int) -> str:
    if days <= 0:
        return "без задержки"
    return f"{days} дн."


def _send_channel_picker(chat_id: int, prompt: str) -> bool:
    authors = _get_admin_authors(chat_id)
    if not authors:
        _send_bot_message(
            chat_id,
            "Сначала добавьте бота администратором в канал и дайте права "
            "«Читать сообщения» и «Публиковать сообщения».",
        )
        return False
    keyboard: list[list[dict]] = []
    row: list[dict] = []
    for author in authors:
        row.append({"text": f"@{author.username}", "callback_data": f"channel:{author.id}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    _send_bot_message_with_keyboard(chat_id, prompt, {"inline_keyboard": keyboard})
    return True


def _send_channel_settings_menu(chat_id: int, author: Author) -> None:
    mode_label = "Автопубликация" if author.auto_publish else "Согласование"
    delay_label = _format_delay_label(author.publish_delay_days)
    rubric_label = author.rubric.name if author.rubric else "не выбрана"
    invite_label = "установлена" if author.invite_url else "не задана"
    _send_bot_message_with_keyboard(
        chat_id,
        "Настройки для канала "
        f"@{author.username}:\n"
        f"Режим: {mode_label}\n"
        f"Тематика: {rubric_label}\n"
        f"Задержка: {delay_label}\n"
        f"Ссылка: {invite_label}",
        {
            "inline_keyboard": [
                [{"text": "Режим публикации", "callback_data": "settings:mode"}],
                [{"text": "Тематика канала", "callback_data": "settings:rubric"}],
                [{"text": "Задержка публикации", "callback_data": "settings:delay"}],
                [{"text": "Ссылка для подписки", "callback_data": "settings:invite"}],
            ]
        },
    )


def _send_setup_options(chat_id: int) -> None:
    BotSession.objects.update_or_create(
        telegram_user_id=chat_id, defaults={"instructions_sent": False}
    )
    if _send_channel_picker(chat_id, "Выберите канал для настройки"):
        return
    _send_bot_message_with_keyboard(
        chat_id,
        "Будем публиковать все новые посты на сайте или ты хочешь каждый новый пост "
        "согласовывать в этом боте (удобно, если много постов картинок, видео, "
        "голосований, не подходящих для внешнего ресурса)",
        {
            "inline_keyboard": [
                [{"text": "Автопубликация", "callback_data": "mode:auto"}],
                [{"text": "Согласование", "callback_data": "mode:approval"}],
            ]
        },
    )
    rubric_keyboard = _build_rubric_keyboard()
    if rubric_keyboard:
        _send_bot_message_with_keyboard(
            chat_id,
            "Выберите тематику канала",
            {"inline_keyboard": rubric_keyboard},
        )
    _send_bot_message_with_keyboard(
        chat_id,
        "Выберите задержку публикации:",
        {
            "inline_keyboard": [
                [{"text": "Без задержки", "callback_data": "delay:0"}],
                [{"text": "1 день", "callback_data": "delay:1"}],
                [{"text": "3 дня", "callback_data": "delay:3"}],
                [{"text": "7 дней", "callback_data": "delay:7"}],
            ]
        },
    )


def _send_setup_instructions(chat_id: int, auto_publish: bool, delay_days: int) -> None:
    publish_line = (
        "Новые посты будут публиковаться автоматически."
        if auto_publish
        else "Новые посты будут отправляться на согласование в боте."
    )
    delay_line = (
        "Публикация будет с задержкой "
        f"{delay_days} дн."
        if delay_days
        else "Публикация без задержки."
    )
    _send_bot_message(
        chat_id,
        "Отлично! Теперь:\n"
        "1) Добавьте бота в админы канала.\n"
        "2) Дайте права: «Читать сообщения» и «Публиковать сообщения».\n"
        "3) По желанию добавьте ссылку приглашения на канал.\n"
        "4) Для старых постов — пересылайте их сюда, и они появятся на сайте.\n"
        f"{publish_line}\n"
        f"{delay_line}",
    )


def _maybe_send_setup_instructions(chat_id: int) -> None:
    session = BotSession.objects.filter(telegram_user_id=chat_id).first()
    if not session or session.instructions_sent:
        return
    if session.mode_selected and session.rubric:
        _send_setup_instructions(chat_id, session.auto_publish, session.publish_delay_days)
        session.instructions_sent = True
        session.save(update_fields=["instructions_sent", "updated_at"])


def _handle_channel_post(message: dict, force_publish: bool = False) -> None:
    chat = message.get("chat", {})
    username = chat.get("username")
    if not username:
        return

    message_id = message.get("message_id")
    if message_id is None:
        return
    if _is_telegram_service_message(message):
        return

    author, _ = Author.objects.get_or_create(
        username=username,
        defaults={
            "title": chat.get("title", ""),
            "channel_url": f"https://t.me/{username}",
            "channel_id": chat.get("id"),
        },
    )

    if author.is_blocked:
        return

    media_group_id = message.get("media_group_id") or ""

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = chat.get("id")
    if token and chat_id:
        if not _is_bot_admin(chat_id, token):
            return
        _refresh_author_from_telegram(author, chat_id, token)

    if not author.rubric:
        if author.admin_chat_id and token:
            _send_bot_message(
                author.admin_chat_id,
                "Перед первой публикацией необходимо выбрать тематику канала.",
            )
        return

    raw_text = _extract_plain_text(message)
    explicit_tags = _extract_hashtags(raw_text)
    formatted_text = _format_telegram_text(raw_text, _extract_entities(message))
    photo_file_id = _extract_photo_file_id(message)
    image_url = _extract_photo_url(message, token) if token else None
    gallery_urls = [image_url] if image_url else []
    embed_html, embed_label = _extract_telegram_embed(message, username)
    poll_html, poll_label = _extract_telegram_poll(message)
    if media_group_id:
        with transaction.atomic():
            Author.objects.select_for_update().filter(pk=author.pk)
            existing_group_post = (
                Post.objects.select_for_update()
                .filter(author=author, media_group_id=media_group_id)
                .first()
            )
            if not existing_group_post:
                existing_by_message = (
                    Post.objects.select_for_update()
                    .filter(author=author, message_id=message_id)
                    .first()
                )
                if existing_by_message and not existing_by_message.media_group_id:
                    existing_group_post = existing_by_message
                    existing_group_post.media_group_id = media_group_id

            if existing_group_post:
                raw_data = existing_group_post.raw_data or {}
                existing_urls = list(raw_data.get("gallery_urls") or [])
                if image_url and image_url not in existing_urls:
                    existing_urls.append(image_url)
                raw_data["gallery_urls"] = existing_urls
                if photo_file_id:
                    existing_file_ids = list(raw_data.get("gallery_file_ids") or [])
                    if photo_file_id not in existing_file_ids:
                        existing_file_ids.append(photo_file_id)
                    raw_data["gallery_file_ids"] = existing_file_ids
                raw_data["media_group_id"] = media_group_id
                if not raw_data.get("formatted_text") and formatted_text:
                    raw_data["formatted_text"] = formatted_text
                if embed_html and not raw_data.get("embed_html"):
                    raw_data["embed_html"] = embed_html
                if poll_html and not raw_data.get("poll_html"):
                    raw_data["poll_html"] = poll_html
                base_text = raw_data.get("formatted_text") or formatted_text
                content = _build_content_with_images(
                    base_text,
                    existing_urls,
                    raw_data.get("embed_html") or embed_html,
                    raw_data.get("poll_html") or poll_html,
                )
                existing_group_post.content = content
                existing_group_post.raw_data = raw_data
                existing_group_post.channel_url = f"https://t.me/{username}"
                existing_group_post.source_url = (
                    f"{existing_group_post.channel_url}/{existing_group_post.message_id}"
                )
                existing_group_post.save(
                    update_fields=[
                        "content",
                        "raw_data",
                        "channel_url",
                        "source_url",
                        "media_group_id",
                        "updated_at",
                    ]
                )
                if not explicit_tags:
                    explicit_tags = [tag.name for tag in existing_group_post.tags.all()]
                _apply_post_tags(existing_group_post, explicit_tags)
                return

    has_publishable_content = bool(formatted_text.strip() or gallery_urls or embed_html or poll_html)
    if not has_publishable_content:
        return

    content = _build_content_with_images(formatted_text, gallery_urls, embed_html, poll_html)
    title = _build_title(raw_text)
    if not title and poll_label:
        title = poll_label
    if not title and image_url:
        title = "Фото"
    if not title and embed_label:
        title = embed_label
    channel_url = f"https://t.me/{username}"
    source_url = f"{channel_url}/{message_id}"
    delay_days = max(int(author.publish_delay_days or 0), 0)
    publish_at = timezone.now() + timedelta(days=delay_days) if delay_days else None

    requires_approval = (not author.auto_publish and author.admin_chat_id) and not force_publish

    raw_data = dict(message)
    if photo_file_id:
        raw_data["photo_file_id"] = photo_file_id
    if media_group_id:
        raw_data["media_group_id"] = media_group_id
    if media_group_id and gallery_urls:
        raw_data["gallery_urls"] = gallery_urls
        raw_data["formatted_text"] = formatted_text
    if media_group_id and photo_file_id:
        raw_data["gallery_file_ids"] = [photo_file_id]
    if embed_html:
        raw_data["embed_html"] = embed_html
    if poll_html:
        raw_data["poll_html"] = poll_html
    post, created = Post.objects.get_or_create(
        author=author,
        message_id=message_id,
        defaults={
            "title": title,
            "content": content,
            "source_url": source_url,
            "channel_url": channel_url,
            "raw_data": raw_data,
            "is_pending": requires_approval,
            "rubric": author.rubric,
            "media_group_id": media_group_id,
            "publish_at": publish_at,
        },
    )

    if not created:
        post.title = title
        post.content = content
        post.source_url = source_url
        post.channel_url = channel_url
        post.raw_data = raw_data
        if media_group_id and not post.media_group_id:
            post.media_group_id = media_group_id
        post.save(
            update_fields=[
                "title",
                "content",
                "source_url",
                "channel_url",
                "raw_data",
                "media_group_id",
                "updated_at",
            ]
        )
    elif requires_approval:
        _send_bot_message_with_keyboard(
            author.admin_chat_id,
            f"Новый пост из канала @{author.username}:\n{title}\n\nОпубликуем?",
            {
                "inline_keyboard": [
                    [
                        {"text": "Публикуем", "callback_data": f"approve:{post.id}"},
                        {"text": "Этот пропустим", "callback_data": f"reject:{post.id}"},
                    ]
                ]
            },
        )
    elif created and not requires_approval:
        _maybe_notify_new_author(author, post)
    _apply_post_tags(post, explicit_tags)


def _handle_verification_code(chat_id: int, code: str) -> None:
    record = (
        AuthorVerificationCode.objects.select_related("user")
        .filter(code__iexact=code, used_at__isnull=True)
        .first()
    )
    if not record:
        _send_bot_message(chat_id, "Код не найден или уже использован.")
        return

    authors = Author.objects.filter(admin_chat_id=chat_id, is_blocked=False).order_by("-updated_at")
    if not authors:
        _send_bot_message(
            chat_id,
            "Сначала подключите канал в боте, затем отправьте код повторно.",
        )
        return

    now = timezone.now()
    linked = []
    for author in authors:
        link, _ = AuthorAdmin.objects.get_or_create(user=record.user, author=author)
        link.telegram_user_id = chat_id
        link.verified_at = now
        link.save(update_fields=["telegram_user_id", "verified_at"])
        linked.append(f"@{author.username}")

    record.used_at = now
    record.save(update_fields=["used_at"])

    _send_bot_message(chat_id, "Канал подтверждён: " + ", ".join(linked))


def _handle_private_message(message: dict) -> None:
    chat = message.get("chat", {})
    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")
    if not chat_id:
        return

    text = (message.get("text") or "").strip()
    if text == "/start":
        _send_bot_message_with_keyboard(
            chat_id,
            "Привет! Это бот Comuna.ru он публикует твои посты на сайте, они "
            "собирают аудиторию из поисковых систем и ведут ее к тебе в канал. "
            "Чтобы запустить бота добавь его администратором к себе в канал и "
            "выбери тематику канала и настройки публикации ниже",
            {"keyboard": [["Помощь", "Настройка"]], "resize_keyboard": True},
        )
        _send_setup_options(chat_id)
        return

    if text in {"/help", "Помощь"}:
        _send_bot_message(
            chat_id,
            "Как подключить канал:\n"
            "1) Выберите рубрику и режим публикации в настройке.\n"
            "2) Добавьте бота админом в канал.\n"
            "3) Дайте права: «Читать сообщения» и «Публиковать сообщения».\n"
            "4) По желанию добавьте ссылку приглашения на канал.\n"
            "5) Для старых постов — пересылайте их сюда.\n"
            "Сайт: https://comuna.ru/authors",
        )
        return

    if text.upper().startswith("COMUNA-"):
        _handle_verification_code(chat_id, text.strip())
        return

    if text == "Настройка":
        _send_setup_options(chat_id)
        return

    if text == "Ссылка для подписки":
        _send_channel_picker(chat_id, "Выберите канал для ссылки приглашения")
        return

    if text.startswith("https://t.me/") or text.startswith("http://t.me/"):
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if session and session.invite_waiting:
            author = session.selected_author
            if not author:
                _send_bot_message(chat_id, "Сначала выберите канал для настройки.")
                return
            invite_url = text.strip()
            session.invite_waiting = False
            session.save(update_fields=["invite_waiting", "updated_at"])
            author.invite_url = invite_url
            author.save(update_fields=["invite_url", "updated_at"])
            _send_bot_message(
                chat_id,
                "Ссылка сохранена. Мы будем использовать её для кнопок подписки.",
            )
            return


    forward_chat = message.get("forward_from_chat")
    forward_message_id = message.get("forward_from_message_id")
    if forward_chat and forward_chat.get("type") == "channel" and forward_message_id:
        if not forward_chat.get("username"):
            _send_bot_message(
                chat_id,
                "У канала нет публичного username. Сделайте канал публичным и повторите пересылку.",
            )
            return

        token = settings.TELEGRAM_BOT_TOKEN
        channel_id = forward_chat.get("id")
        if token and channel_id and not _is_bot_admin(channel_id, token):
            _send_bot_message(
                chat_id,
                "Бот не является админом этого канала. Добавьте бота в админы и "
                "дайте права на чтение/публикацию, затем повторите пересылку.",
            )
            return

        forwarded = {
            "chat": forward_chat,
            "message_id": forward_message_id,
            "text": message.get("text"),
            "caption": message.get("caption"),
            "photo": message.get("photo"),
            "video": message.get("video"),
            "video_note": message.get("video_note"),
            "audio": message.get("audio"),
            "voice": message.get("voice"),
            "animation": message.get("animation"),
            "document": message.get("document"),
            "entities": message.get("entities"),
            "caption_entities": message.get("caption_entities"),
            "media_group_id": message.get("media_group_id"),
        }

        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        author = Author.objects.filter(username__iexact=forward_chat.get("username")).first()

        if not author and session and session.rubric:
            author, _ = Author.objects.get_or_create(
                username=forward_chat.get("username"),
                defaults={
                    "title": forward_chat.get("title", ""),
                    "channel_url": f"https://t.me/{forward_chat.get('username')}",
                    "channel_id": forward_chat.get("id"),
                },
            )

        if author and not author.rubric:
            _send_bot_message(
                chat_id,
                "Перед первой публикацией необходимо выбрать тематику канала.",
            )
            return

        apply_session = False
        if session and author:
            apply_session = session.selected_author is None or session.selected_author_id == author.id
            if apply_session:
                author.auto_publish = session.auto_publish
                author.admin_chat_id = chat_id
                if session.rubric:
                    author.rubric = session.rubric
                if session.invite_url:
                    author.invite_url = session.invite_url
                if session.publish_delay_days:
                    author.publish_delay_days = session.publish_delay_days
                update_fields = [
                    "auto_publish",
                    "admin_chat_id",
                    "rubric",
                    "invite_url",
                    "publish_delay_days",
                    "updated_at",
                ]
                author.save(update_fields=update_fields)
                if author.rubric:
                    Post.objects.filter(author=author).update(rubric=author.rubric)
                if session.selected_author is None:
                    session.delete()

        existing_post = Post.objects.filter(
            author__username__iexact=forward_chat.get("username"),
            message_id=forward_message_id,
        ).first()
        if existing_post:
            BotSession.objects.update_or_create(
                telegram_user_id=chat_id,
                defaults={
                    "pending_update_post_id": existing_post.id,
                    "pending_update_message": forwarded,
                },
            )
            _send_bot_message_with_keyboard(
                chat_id,
                "Этот пост уже был опубликован, вы хотите его обновить?",
                {
                    "inline_keyboard": [
                        [
                            {"text": "Да", "callback_data": f"update:{existing_post.id}"},
                            {"text": "Нет", "callback_data": f"skip_update:{existing_post.id}"},
                        ]
                    ]
                },
            )
            return

        _handle_channel_post(forwarded)
        _send_bot_message(chat_id, "Пост добавлен на сайт.")
        return

    _send_bot_message(
        chat_id,
        "Перешлите пост из канала, чтобы добавить его на сайт. Для помощи — /help.",
    )


def _handle_my_chat_member(update: dict) -> None:
    chat = update.get("chat", {})
    if chat.get("type") != "channel":
        return

    new_member = update.get("new_chat_member", {})
    status = new_member.get("status")
    if status not in {"administrator", "member"}:
        return

    actor = update.get("from", {})
    admin_chat_id = actor.get("id")
    if not admin_chat_id:
        return

    username = chat.get("username")
    if not username:
        _send_bot_message(
            admin_chat_id,
            "У канала нет публичного username. Сделайте канал публичным и повторите.",
        )
        return

    author = Author.objects.filter(username__iexact=username).first()
    if not author:
        author = Author.objects.create(
            username=username,
            title=chat.get("title", ""),
            channel_id=chat.get("id"),
            channel_url=f"https://t.me/{username}",
        )

    session = BotSession.objects.filter(telegram_user_id=admin_chat_id).first()
    author.admin_chat_id = admin_chat_id
    author.channel_id = chat.get("id") or author.channel_id
    if chat.get("title"):
        author.title = chat["title"]

    update_fields = ["admin_chat_id", "channel_id", "updated_at"]
    if chat.get("title"):
        update_fields.append("title")

    if session:
        if session.selected_author is None:
            author.auto_publish = session.auto_publish
            update_fields.append("auto_publish")
            if session.rubric:
                author.rubric = session.rubric
                update_fields.append("rubric")
            if session.invite_url:
                author.invite_url = session.invite_url
                update_fields.append("invite_url")
            if session.publish_delay_days:
                author.publish_delay_days = session.publish_delay_days
                update_fields.append("publish_delay_days")

    author.save(update_fields=update_fields)

    if session and author.rubric:
        Post.objects.filter(author=author).update(rubric=author.rubric)

    token = settings.TELEGRAM_BOT_TOKEN
    if token:
        _refresh_author_from_telegram(author, f"@{username}", token)

    _send_bot_message(
        admin_chat_id,
        f"Канал @{author.username} подключён. Настройки применены.",
    )


def _handle_callback_query(callback_query: dict) -> None:
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    session = None
    if chat_id:
        session = (
            BotSession.objects.filter(telegram_user_id=chat_id)
            .select_related("selected_author", "rubric")
            .first()
        )

    if data.startswith("mode:") and chat_id:
        mode = data.split(":", 1)[1]
        auto_publish = mode == "auto"
        if session and session.selected_author:
            author = session.selected_author
            author.auto_publish = auto_publish
            author.save(update_fields=["auto_publish", "updated_at"])
            _answer_callback_query(callback_id, "Настройка сохранена")
            _send_bot_message(chat_id, f"Режим обновлён для @{author.username}.")
            return
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id,
            defaults={"auto_publish": auto_publish, "mode_selected": True},
        )
        _answer_callback_query(callback_id, "Настройка сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("rubric:") and chat_id:
        try:
            rubric_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректная рубрика")
            return
        rubric = Rubric.objects.filter(id=rubric_id, is_active=True).first()
        if not rubric:
            _answer_callback_query(callback_id, "Рубрика не найдена")
            return
        if session and session.selected_author:
            author = session.selected_author
            author.rubric = rubric
            author.save(update_fields=["rubric", "updated_at"])
            Post.objects.filter(author=author).update(rubric=rubric)
            _answer_callback_query(callback_id, "Рубрика сохранена")
            _send_bot_message(chat_id, f"Тематика обновлена для @{author.username}.")
            return
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id, defaults={"rubric": rubric}
        )
        _answer_callback_query(callback_id, "Рубрика сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("delay:") and chat_id:
        try:
            delay_days = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректная задержка")
            return
        if delay_days not in (0, 1, 3, 7):
            _answer_callback_query(callback_id, "Некорректная задержка")
            return
        if session and session.selected_author:
            author = session.selected_author
            author.publish_delay_days = delay_days
            author.save(update_fields=["publish_delay_days", "updated_at"])
            _answer_callback_query(callback_id, "Задержка сохранена")
            _send_bot_message(
                chat_id,
                f"Задержка публикации обновлена для @{author.username}.",
            )
            return
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id, defaults={"publish_delay_days": delay_days}
        )
        _answer_callback_query(callback_id, "Задержка сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("channel:") and chat_id:
        try:
            author_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный канал")
            return
        author = Author.objects.filter(id=author_id, admin_chat_id=chat_id).first()
        if not author:
            _answer_callback_query(callback_id, "Канал не найден")
            return
        if session:
            session.selected_author = author
            session.invite_waiting = False
            session.save(update_fields=["selected_author", "invite_waiting", "updated_at"])
        else:
            BotSession.objects.update_or_create(
                telegram_user_id=chat_id,
                defaults={"selected_author": author, "invite_waiting": False},
            )
        _answer_callback_query(callback_id, "Канал выбран")
        _send_channel_settings_menu(chat_id, author)
        return

    if data.startswith("settings:") and chat_id:
        action = data.split(":", 1)[1]
        if not session or not session.selected_author:
            _answer_callback_query(callback_id, "Сначала выберите канал")
            _send_channel_picker(chat_id, "Выберите канал для настройки")
            return
        if action == "mode":
            _answer_callback_query(callback_id, "Выберите режим")
            _send_bot_message_with_keyboard(
                chat_id,
                "Выберите режим публикации:",
                {
                    "inline_keyboard": [
                        [{"text": "Автопубликация", "callback_data": "mode:auto"}],
                        [{"text": "Согласование", "callback_data": "mode:approval"}],
                    ]
                },
            )
            return
        if action == "rubric":
            rubric_keyboard = _build_rubric_keyboard()
            if rubric_keyboard:
                _answer_callback_query(callback_id, "Выберите тематику")
                _send_bot_message_with_keyboard(
                    chat_id,
                    "Выберите тематику канала",
                    {"inline_keyboard": rubric_keyboard},
                )
            else:
                _answer_callback_query(callback_id, "Нет доступных рубрик")
            return
        if action == "delay":
            _answer_callback_query(callback_id, "Выберите задержку")
            _send_bot_message_with_keyboard(
                chat_id,
                "Выберите задержку публикации:",
                {
                    "inline_keyboard": [
                        [{"text": "Без задержки", "callback_data": "delay:0"}],
                        [{"text": "1 день", "callback_data": "delay:1"}],
                        [{"text": "3 дня", "callback_data": "delay:3"}],
                        [{"text": "7 дней", "callback_data": "delay:7"}],
                    ]
                },
            )
            return
        if action == "invite":
            _answer_callback_query(callback_id, "Ожидаю ссылку")
            _send_bot_message(
                chat_id,
                "Пришлите ссылку приглашения на канал (например, https://t.me/+xxxx).",
            )
            session.invite_waiting = True
            session.save(update_fields=["invite_waiting", "updated_at"])
            return

    if data.startswith("approve:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        post = Post.objects.filter(id=post_id).first()
        if not post:
            _answer_callback_query(callback_id, "Пост не найден")
            return
        if post.is_pending:
            post.is_pending = False
            post.save(update_fields=["is_pending", "updated_at"])
            _maybe_notify_new_author(post.author, post)
            _answer_callback_query(callback_id, "Опубликовано")
            return
        if post.is_blocked:
            _answer_callback_query(callback_id, "Пост уже отклонён")
        else:
            _answer_callback_query(callback_id, "Пост уже опубликован")
        return

    if data.startswith("reject:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        post = Post.objects.filter(id=post_id).first()
        if not post:
            _answer_callback_query(callback_id, "Пост не найден")
            return
        if post.is_pending:
            post.is_pending = False
            post.is_blocked = True
            post.save(update_fields=["is_pending", "is_blocked", "updated_at"])
            _answer_callback_query(callback_id, "Пропущено")
            return
        if post.is_blocked:
            _answer_callback_query(callback_id, "Пост уже отклонён")
        else:
            _answer_callback_query(callback_id, "Пост уже опубликован")
        return

    if data.startswith("update:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if not session or session.pending_update_post_id != post_id or not session.pending_update_message:
            _answer_callback_query(callback_id, "Обновление не найдено")
            return
        _handle_channel_post(session.pending_update_message, force_publish=True)
        session.pending_update_post_id = None
        session.pending_update_message = None
        session.save(update_fields=["pending_update_post_id", "pending_update_message", "updated_at"])
        _answer_callback_query(callback_id, "Пост обновлён")
        _send_bot_message(chat_id, "Пост обновлён на сайте.")
        return

    if data.startswith("skip_update:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if session and session.pending_update_post_id == post_id:
            session.pending_update_post_id = None
            session.pending_update_message = None
            session.save(update_fields=["pending_update_post_id", "pending_update_message", "updated_at"])
        _answer_callback_query(callback_id, "Отменено")
        return


@csrf_exempt
def telegram_webhook(request: HttpRequest, token: str) -> HttpResponse:
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected_secret:
        return JsonResponse({"ok": False, "error": "TELEGRAM_WEBHOOK_SECRET not set"}, status=500)

    if token != expected_secret:
        return JsonResponse({"ok": False, "error": "invalid token"}, status=403)

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret != expected_secret:
        return JsonResponse({"ok": False, "error": "invalid secret"}, status=403)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if "channel_post" in payload:
        _handle_channel_post(payload["channel_post"])
    elif "edited_channel_post" in payload:
        _handle_channel_post(payload["edited_channel_post"])
    elif "my_chat_member" in payload:
        _handle_my_chat_member(payload["my_chat_member"])
    elif "message" in payload:
        _handle_private_message(payload["message"])
    elif "callback_query" in payload:
        _handle_callback_query(payload["callback_query"])

    return JsonResponse({"ok": True})


@csrf_exempt
def register_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if not getattr(settings, "ALLOW_PASSWORD_REGISTRATION", False):
        return JsonResponse(
            {"ok": False, "error": "Регистрация по почте отключена. Используйте Telegram."},
            status=403,
        )
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()

    if not username or not password:
        return JsonResponse({"ok": False, "error": "username and password are required"}, status=400)
    if len(password) < 8:
        return JsonResponse({"ok": False, "error": "пароль слишком короткий"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"ok": False, "error": "username already exists"}, status=400)
    if email and User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"ok": False, "error": "email already exists"}, status=400)

    user = User.objects.create_user(username=username, email=email or None, password=password)
    token = _issue_token(user)
    return JsonResponse({"ok": True, "token": token, "user": _serialize_user(user)})


@csrf_exempt
def login_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    username_or_email = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username_or_email or not password:
        return JsonResponse({"ok": False, "error": "invalid credentials"}, status=400)

    user = None
    if "@" in username_or_email:
        user = User.objects.filter(email__iexact=username_or_email).first()
        if user and not user.check_password(password):
            user = None
    else:
        user = authenticate(username=username_or_email, password=password)

    if not user:
        return JsonResponse({"ok": False, "error": "invalid credentials"}, status=401)

    token = _issue_token(user)
    return JsonResponse({"ok": True, "token": token, "user": _serialize_user(user)})


def auth_me(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    return JsonResponse({"ok": True, "user": _serialize_user(user)})


@csrf_exempt
def author_verification_code(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    active = (
        AuthorVerificationCode.objects.filter(user=user, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if active and active.created_at >= timezone.now() - timedelta(days=1):
        return JsonResponse({"ok": True, "code": active.code})

    code = _generate_verification_code()
    while AuthorVerificationCode.objects.filter(code=code).exists():
        code = _generate_verification_code()

    AuthorVerificationCode.objects.create(user=user, code=code)
    return JsonResponse({"ok": True, "code": code})


def _serialize_post_for_user(request: HttpRequest, post: Post) -> dict:
    rubric = post.rubric
    author_channel_url, author_title = _author_display_fields(
        post.author, rubric, post.channel_url
    )
    return {
        "id": post.id,
        "title": _post_display_title(post),
        "content": post.content,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "is_pending": post.is_pending,
        "publish_at": post.publish_at.isoformat() if post.publish_at else None,
        "rubric": rubric.name if rubric else None,
        "rubric_slug": rubric.slug if rubric else None,
        "rubric_icon_url": _rubric_icon_url(request, rubric),
        "tags": _serialize_tags(post.tags.all()),
        "author": {
            "username": post.author.username,
            "title": author_title,
            "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
        },
    }


def _get_or_create_personal_author(user: User) -> tuple[Author | None, str | None]:
    username = (getattr(user, "username", "") or "").strip()
    if not username:
        return None, "invalid username"
    existing = Author.objects.filter(username__iexact=username).first()
    if existing:
        if existing.channel_url or existing.channel_id:
            return None, "Этот ник уже занят Telegram-каналом. Подключите канал через бота или смените логин."
        return existing, None
    author = Author.objects.create(username=username, title=username)
    return author, None


@csrf_exempt
def user_posts(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    author_links = (
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
    personal_author_error = None

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

        title = (payload.get("title") or "").strip()
        content = (payload.get("content") or "").strip()
        author_username = (payload.get("author_username") or "").strip()
        rubric_slug = (payload.get("rubric_slug") or "").strip()
        explicit_tags = _parse_tag_payload(payload.get("tags"))

        if not title:
            return JsonResponse({"ok": False, "error": "title is required"}, status=400)
        if not content:
            return JsonResponse({"ok": False, "error": "content is required"}, status=400)

        author = None
        if author_username:
            author = (
                Author.objects.filter(id__in=author_ids, username__iexact=author_username).first()
            )
            if not author:
                return JsonResponse({"ok": False, "error": "author not found"}, status=404)
        elif len(author_links) == 1:
            author = author_links[0].author
        elif not author_links:
            personal_author, personal_author_error = _get_or_create_personal_author(user)
            if personal_author_error:
                return JsonResponse({"ok": False, "error": personal_author_error}, status=400)
            if personal_author:
                author = personal_author
        else:
            return JsonResponse({"ok": False, "error": "author required"}, status=400)

        rubric = None
        if rubric_slug:
            rubric = Rubric.objects.filter(slug__iexact=rubric_slug, is_active=True).first()
            if not rubric:
                return JsonResponse({"ok": False, "error": "rubric not found"}, status=404)
        if not rubric:
            rubric = author.rubric if author else None
        if not rubric:
            return JsonResponse({"ok": False, "error": "rubric required"}, status=400)
        if rubric.is_hidden and not user.is_staff:
            return JsonResponse({"ok": False, "error": "rubric not allowed"}, status=403)
        if _is_comuna_rubric(rubric):
            personal_author, personal_author_error = _get_or_create_personal_author(user)
            if personal_author_error:
                return JsonResponse({"ok": False, "error": personal_author_error}, status=400)
            if personal_author:
                author = personal_author

        channel_url = author.invite_url or author.channel_url
        try:
            message_id = _generate_manual_message_id(author)
        except ValueError:
            return JsonResponse({"ok": False, "error": "unable to create post"}, status=500)
        delay_days = max(int(author.publish_delay_days or 0), 0)
        publish_at = timezone.now() + timedelta(days=delay_days) if delay_days else None

        post = Post.objects.create(
            author=author,
            message_id=message_id,
            title=title,
            content=content,
            rubric=rubric,
            channel_url=channel_url,
            source_url=channel_url,
            raw_data={"source": "manual"},
            is_pending=False,
            is_blocked=False,
            publish_at=publish_at,
        )
        _apply_post_tags(post, explicit_tags)
        _maybe_notify_new_author(author, post)
        return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post)})

    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    limit_raw = request.GET.get("limit", "20")
    offset_raw = request.GET.get("offset", "0")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    if not author_ids:
        return JsonResponse({"ok": True, "posts": [], "total": 0})

    posts_qs = (
        Post.objects.filter(author_id__in=author_ids, is_blocked=False, author__is_blocked=False)
        .select_related("author", "rubric")
        .prefetch_related("tags")
        .order_by("-created_at")
    )

    total = posts_qs.count()
    posts = posts_qs[offset : offset + limit]
    serialized = [_serialize_post_for_user(request, post) for post in posts]
    return JsonResponse({"ok": True, "posts": serialized, "total": total})


@csrf_exempt
def user_upload(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    upload = (
        request.FILES.get("image")
        or request.FILES.get("file")
        or request.FILES.get("images[]")
    )
    if not upload:
        return JsonResponse({"ok": False, "error": "image is required"}, status=400)

    content_type = (getattr(upload, "content_type", "") or "").lower()
    if not content_type.startswith("image/"):
        return JsonResponse({"ok": False, "error": "unsupported file type"}, status=400)

    max_bytes = getattr(settings, "USER_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
    if upload.size and upload.size > max_bytes:
        return JsonResponse({"ok": False, "error": "file is too large"}, status=400)

    base_name = get_valid_filename(os.path.splitext(upload.name or "image")[0])
    ext = os.path.splitext(upload.name or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    filename = f"uploads/manual/{base_name}-{secrets.token_hex(8)}{ext}"
    saved_path = default_storage.save(filename, upload)
    relative_url = default_storage.url(saved_path)
    site_base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    if site_base:
        url = f"{site_base}{relative_url}"
    else:
        url = request.build_absolute_uri(relative_url)

    return JsonResponse({"ok": True, "url": url})


@csrf_exempt
def user_post_update(request: HttpRequest, post_id: int) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in {"PATCH", "PUT"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        post = Post.objects.select_related("author", "rubric").get(
            id=post_id, is_blocked=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    is_linked = AuthorAdmin.objects.filter(
        user=user, author=post.author, verified_at__isnull=False
    ).exists()
    if not is_linked:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    title = payload.get("title") if "title" in payload else None
    content = payload.get("content") if "content" in payload else None
    tags_payload = payload.get("tags") if "tags" in payload else None

    if title is None and content is None and tags_payload is None:
        return JsonResponse({"ok": False, "error": "nothing to update"}, status=400)

    if content is not None:
        content = str(content).strip()
        if not content:
            return JsonResponse({"ok": False, "error": "content is empty"}, status=400)
        if len(content) > 100000:
            return JsonResponse({"ok": False, "error": "content too long"}, status=400)
        post.content = content
        raw_data = dict(post.raw_data or {})
        raw_data["manual_edit"] = True
        raw_data["manual_updated_at"] = timezone.now().isoformat()
        post.raw_data = raw_data

    if title is not None:
        title = str(title).strip()
        if title:
            post.title = title[:255]
        else:
            source_text = _strip_html(post.content)
            post.title = _build_title(source_text)

    post.save(update_fields=["title", "content", "raw_data", "updated_at"])
    if tags_payload is not None:
        explicit_tags = _parse_tag_payload(tags_payload)
    else:
        explicit_tags = [tag.name for tag in post.tags.all()]
    _apply_post_tags(post, explicit_tags)
    return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post)})


@csrf_exempt
def post_comments(request: HttpRequest, post_id: int) -> HttpResponse:
    try:
        now = timezone.now()
        post = (
            Post.objects.select_related("author")
            .filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    if request.method == "GET":
        user = _get_user_from_request(request)
        comments = (
            PostComment.objects.filter(post=post)
            .select_related("user")
            .annotate(likes_count=Count("likes", distinct=True))
            .order_by("created_at")
        )
        liked_ids = set()
        if user:
            liked_ids = set(
                PostCommentLike.objects.filter(user=user, comment__post=post).values_list(
                    "comment_id", flat=True
                )
            )
        serialized = [
            {
                "id": comment.id,
                "body": "" if comment.is_deleted else comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "parent_id": comment.parent_id,
                "is_deleted": comment.is_deleted,
                "likes_count": comment.likes_count,
                "liked_by_me": comment.id in liked_ids,
                "can_edit": bool(user and comment.user_id == user.id and not comment.is_deleted),
                "user": {"username": comment.user.username},
            }
            for comment in comments
        ]
        return JsonResponse({"ok": True, "comments": serialized})

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    body = (payload.get("body") or "").strip()
    parent_id = payload.get("parent_id")
    if not body:
        return JsonResponse({"ok": False, "error": "comment is empty"}, status=400)
    if len(body) > 2000:
        return JsonResponse({"ok": False, "error": "comment too long"}, status=400)

    parent = None
    if parent_id:
        try:
            parent = PostComment.objects.get(id=int(parent_id), post=post, is_deleted=False)
        except (PostComment.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "parent comment not found"}, status=404)

    comment = PostComment.objects.create(post=post, user=user, body=body, parent=parent)
    Post.objects.filter(id=post.id).update(comments_count=F("comments_count") + 1)
    post.refresh_from_db(fields=["comments_count"])

    return JsonResponse(
        {
            "ok": True,
            "comment": {
                "id": comment.id,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "parent_id": comment.parent_id,
                "is_deleted": comment.is_deleted,
                "likes_count": 0,
                "liked_by_me": False,
                "can_edit": True,
                "user": {"username": user.username},
            },
            "comments_count": post.comments_count,
        }
    )


@csrf_exempt
def comment_detail(request: HttpRequest, comment_id: int) -> HttpResponse:
    if request.method not in ("PATCH", "DELETE"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        comment = PostComment.objects.select_related("post", "user").get(id=comment_id)
    except PostComment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    if comment.is_deleted:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    if comment.user_id != user.id:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    if request.method == "PATCH":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

        body = (payload.get("body") or "").strip()
        if not body:
            return JsonResponse({"ok": False, "error": "comment is empty"}, status=400)
        if len(body) > 2000:
            return JsonResponse({"ok": False, "error": "comment too long"}, status=400)

        comment.body = body
        comment.save(update_fields=["body", "updated_at"])
        likes_count = PostCommentLike.objects.filter(comment=comment).count()
        liked_by_me = PostCommentLike.objects.filter(comment=comment, user=user).exists()

        return JsonResponse(
            {
                "ok": True,
                "comment": {
                    "id": comment.id,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat(),
                    "parent_id": comment.parent_id,
                    "is_deleted": comment.is_deleted,
                    "likes_count": likes_count,
                    "liked_by_me": liked_by_me,
                    "can_edit": True,
                    "user": {"username": comment.user.username},
                },
            }
        )

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])
    Post.objects.filter(id=comment.post_id, comments_count__gt=0).update(
        comments_count=F("comments_count") - 1
    )

    return JsonResponse({"ok": True, "comment_id": comment.id})


@csrf_exempt
def comment_like(request: HttpRequest, comment_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        comment = (
            PostComment.objects.select_related("post", "post__author")
            .filter(
                id=comment_id,
                is_deleted=False,
                post__is_blocked=False,
                post__is_pending=False,
                post__author__is_blocked=False,
            )
            .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
            .get()
        )
    except PostComment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    existing = PostCommentLike.objects.filter(comment=comment, user=user).first()
    delta = 0
    if existing:
        existing.delete()
        liked = False
        delta = -1
    else:
        PostCommentLike.objects.create(comment=comment, user=user)
        liked = True
        delta = 1

    if delta:
        Author.objects.filter(id=comment.post.author_id).update(
            rating_total=F("rating_total") + delta
        )

    likes_count = PostCommentLike.objects.filter(comment=comment).count()

    return JsonResponse({"ok": True, "liked": liked, "likes_count": likes_count})


@csrf_exempt
def post_like(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        post = (
            Post.objects.select_related("author")
            .filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    vote_value = 1
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            vote_value = int(payload.get("value", payload.get("vote", payload.get("score", 1))))

    if vote_value not in (-1, 0, 1):
        return JsonResponse({"ok": False, "error": "invalid vote value"}, status=400)

    existing = PostLike.objects.filter(post=post, user=user).first()
    delta = 0
    new_vote = 0
    if existing:
        if vote_value == 0 or existing.value == vote_value:
            delta = -existing.value
            existing.delete()
            new_vote = 0
        else:
            delta = vote_value - existing.value
            existing.value = vote_value
            existing.save(update_fields=["value"])
            new_vote = vote_value
    else:
        if vote_value != 0:
            PostLike.objects.create(post=post, user=user, value=vote_value)
            delta = vote_value
            new_vote = vote_value

    if delta:
        Post.objects.filter(id=post.id).update(rating=F("rating") + delta)
        Author.objects.filter(id=post.author_id).update(rating_total=F("rating_total") + delta)

    liked = new_vote == 1

    post.refresh_from_db(fields=["rating"])
    return JsonResponse(
        {
            "ok": True,
            "liked": liked,
            "vote": new_vote,
            "likes_count": post.rating,
        }
    )


def recent_comments(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "5")
    try:
        limit = min(max(int(limit_raw), 1), 20)
    except ValueError:
        limit = 5

    now = timezone.now()
    comments = (
        PostComment.objects.filter(
            is_deleted=False,
            post__is_blocked=False,
            post__is_pending=False,
            post__author__is_blocked=False,
        )
        .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
        .select_related("user", "post")
        .order_by("-created_at")[:limit]
    )

    serialized = [
        {
            "id": comment.id,
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
            "user": {"username": comment.user.username},
            "post": {"id": comment.post_id, "title": _post_display_title(comment.post)},
        }
        for comment in comments
    ]

    return JsonResponse({"ok": True, "comments": serialized})


def author_posts(request: HttpRequest, username: str) -> HttpResponse:
    try:
        author = Author.objects.get(username__iexact=username)
    except Author.DoesNotExist:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    if author.is_blocked:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    now = timezone.now()
    posts = (
        Post.objects.filter(author=author, is_blocked=False, is_pending=False)
        .filter(_publish_ready_filter(now))
        .filter(Q(rubric__isnull=True) | Q(rubric__is_hidden=False))
        .prefetch_related("tags")
        .order_by("-created_at")
        .all()[offset : offset + limit]
    )

    posts_count = (
        Post.objects.filter(author=author, is_blocked=False, is_pending=False)
        .filter(_publish_ready_filter(now))
        .filter(Q(rubric__isnull=True) | Q(rubric__is_hidden=False))
        .count()
    )
    author_channel_url = author.invite_url or author.channel_url
    serialized = []
    for post in posts:
        rubric = post.rubric
        author_channel_url, author_title = _author_display_fields(
            author, rubric, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _rubric_icon_url(request, rubric),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "tags": _serialize_tags(post.tags.all()),
                "author": {
                    "username": author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, author, rubric),
                    "description": author.description,
                    "subscribers_count": author.subscribers_count,
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "author": {
                "username": author.username,
                "title": author.title,
                "channel_url": author_channel_url,
                "avatar_url": _author_avatar_url(request, author),
                "description": author.description,
                "subscribers_count": author.subscribers_count,
                "posts_count": posts_count,
                "author_rating": _author_rating_value(author.rating_total),
            },
            "posts": serialized,
        }
    )


def rubrics_list(request: HttpRequest) -> HttpResponse:
    include_hidden = request.GET.get("include_hidden") in ("1", "true", "yes")
    rubrics = Rubric.objects.filter(is_active=True)
    if include_hidden:
        user = _get_user_from_request(request)
        if not user or not user.is_staff:
            rubrics = rubrics.filter(is_hidden=False)
    else:
        rubrics = rubrics.filter(is_hidden=False)
    rubrics = rubrics.order_by("sort_order", "name")
    serialized = [
        {
            "id": rubric.id,
            "name": rubric.name,
            "slug": rubric.slug,
            "icon_url": _media_url(request, rubric.icon_url),
            "icon_thumb_url": _media_url(request, rubric.icon_thumb),
            "cover_image_url": _media_url(request, rubric.cover_image_url),
            "description": rubric.description,
            "subscribe_url": rubric.subscribe_url,
        }
        for rubric in rubrics
    ]
    return JsonResponse({"ok": True, "rubrics": serialized})


def rubric_posts(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        rubric = Rubric.objects.get(slug=slug, is_active=True)
    except Rubric.DoesNotExist:
        return JsonResponse({"ok": False, "error": "rubric not found"}, status=404)

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    now = timezone.now()
    posts = (
        Post.objects.filter(
            rubric=rubric,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .prefetch_related("tags")
        .order_by("-created_at")
        .all()[offset : offset + limit]
    )

    serialized = []
    for post in posts:
        author_channel_url, author_title = _author_display_fields(
            post.author, rubric, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name,
                "rubric_slug": rubric.slug,
                "rubric_icon_url": _rubric_icon_url(request, rubric),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "tags": _serialize_tags(post.tags.all()),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "rubric": {
                "name": rubric.name,
                "slug": rubric.slug,
                "icon_url": _media_url(request, rubric.icon_url),
                "icon_thumb_url": _media_url(request, rubric.icon_thumb),
                "cover_image_url": _media_url(request, rubric.cover_image_url),
                "description": rubric.description,
                "subscribe_url": rubric.subscribe_url,
            },
            "posts": serialized,
        }
    )


def tags_list(request: HttpRequest) -> HttpResponse:
    tags = Tag.objects.filter(is_active=True).order_by("name")
    return JsonResponse(
        {
            "ok": True,
            "tags": [
                {"name": tag.name, "lemma": tag.lemma or _lemmatize_tag(tag.name) or tag.name, "mood": tag.mood}
                for tag in tags
            ],
        }
    )


def tag_posts(request: HttpRequest, tag: str) -> HttpResponse:
    if not tag:
        return JsonResponse({"ok": False, "error": "tag not found"}, status=404)

    normalized = _normalize_tag_value(tag)
    lemma = _lemmatize_tag(normalized) or normalized
    tags_qs = Tag.objects.filter(is_active=True).filter(
        Q(lemma__iexact=lemma) | Q(name__iexact=normalized)
    )
    if not tags_qs.exists():
        return JsonResponse({"ok": False, "error": "tag not found"}, status=404)
    tag_obj = (
        tags_qs.filter(name__iexact=normalized).first()
        or tags_qs.filter(lemma__iexact=lemma).first()
        or tags_qs.first()
    )

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    now = timezone.now()
    posts = (
        Post.objects.filter(
            tags__in=tags_qs,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .prefetch_related("tags")
        .select_related("rubric", "author")
        .order_by("-created_at")
        .all()[offset : offset + limit]
    )

    serialized = []
    for post in posts:
        rubric = post.rubric
        author_channel_url, author_title = _author_display_fields(
            post.author, rubric, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _rubric_icon_url(request, rubric)
                if rubric
                else None,
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "tags": _serialize_tags(post.tags.all()),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(
                        request, post.author, rubric
                    ),
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "tag": {
                "name": tag_obj.name,
                "lemma": tag_obj.lemma or _lemmatize_tag(tag_obj.name) or tag_obj.name,
            },
            "posts": serialized,
        }
    )


def post_detail(request: HttpRequest, post_id: int) -> HttpResponse:
    try:
        now = timezone.now()
        post = (
            Post.objects.select_related("author", "rubric")
            .prefetch_related("tags")
            .filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    rubric = post.rubric
    author_channel_url, author_title = _author_display_fields(
        post.author, rubric, post.channel_url
    )
    return JsonResponse(
        {
            "ok": True,
            "post": {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _rubric_icon_url(request, rubric),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "tags": _serialize_tags(post.tags.all()),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                },
            },
        }
    )


@csrf_exempt
def post_read(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        post = Post.objects.get(id=post_id, is_blocked=False, author__is_blocked=False)
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)
    PostRead.objects.get_or_create(post=post, user=user)
    return JsonResponse({"ok": True})


def home_feed(request: HttpRequest) -> HttpResponse:
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

    now = timezone.now()
    hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    only_read = request.GET.get("only_read") in ("1", "true", "yes")
    read_user = (
        _get_user_from_request(request) if (hide_read or only_read) else None
    )
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    target_count = limit + offset
    fetch_size = max(target_count * 5, limit * 5)
    combined_scaled = Cast(F("rating"), IntegerField()) * Value(20) + Cast(
        F("author__rating_total"), IntegerField()
    )
    base_query = (
        Post.objects.filter(
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
        .filter(Q(rubric__isnull=True) | Q(rubric__is_hidden=False))
        .annotate(combined_scaled=combined_scaled)
        .filter(combined_scaled__gte=0)
    )
    hidden_read_count = 0
    if hide_read and read_user:
        hidden_read_count = base_query.filter(reads__user=read_user).count()

    if only_read:
        posts_page = (
            base_query.filter(reads__user=read_user)
            .select_related("author", "rubric")
            .prefetch_related("tags")
            .order_by("-created_at")[offset : offset + limit]
        )
        serialized = []
        for post in posts_page:
            rubric = post.rubric
            author_rating = _author_rating_value(post.author.rating_total)
            author_channel_url, author_title = _author_display_fields(
                post.author, rubric, post.channel_url
            )
            serialized.append(
                {
                    "id": post.id,
                    "title": _post_display_title(post),
                    "rubric": rubric.name if rubric else None,
                    "rubric_slug": rubric.slug if rubric else None,
                    "rubric_icon_url": _rubric_icon_url(request, rubric),
                    "content": post.content,
                    "source_url": post.source_url,
                    "channel_url": author_channel_url,
                    "created_at": post.created_at.isoformat(),
                    "author": {
                        "username": post.author.username,
                        "title": author_title,
                        "channel_url": author_channel_url,
                        "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                    },
                    "tags": _serialize_tags(post.tags.all()),
                    "score": post.rating + post.comments_count * 5 + author_rating,
                    "rating": post.rating,
                    "comments_count": post.comments_count,
                    "likes_count": post.rating,
                }
            )
        return JsonResponse(
            {"ok": True, "posts": serialized, "hidden_read_count": hidden_read_count}
        )

    posts_query = base_query
    if hide_read and read_user:
        posts_query = posts_query.exclude(reads__user=read_user)
    posts = list(
        posts_query.select_related("author", "rubric")
        .prefetch_related("tags")
        .order_by("-created_at")[:fetch_size]
    )
    author_ids = {post.author_id for post in posts}
    author_rating_map = {}
    if author_ids:
        author_rating_map = {
            row["id"]: _author_rating_value(row["rating_total"])
            for row in Author.objects.filter(id__in=author_ids).values(
                "id", "rating_total"
            )
        }

    serialized_posts = []
    remaining = posts[:]
    last_author_id = None
    rubric_daily_counts = {}
    forced_daily_counts = {}

    while remaining and len(serialized_posts) < target_count:
        next_index = None
        for idx, candidate in enumerate(remaining):
            if candidate.author_id != last_author_id:
                next_index = idx
                break
        if next_index is None:
            next_index = 0
        post = remaining.pop(next_index)
        rubric = post.rubric
        author_rating = author_rating_map.get(post.author_id, 0)
        combined_rating = post.rating + author_rating
        if combined_rating < 0:
            continue
        day_key = timezone.localtime(post.created_at).date()
        rubric_limit = rubric.home_limit if rubric else None
        rubric_key = (rubric.id, day_key) if rubric else None
        rubric_count = rubric_daily_counts.get(rubric_key, 0) if rubric_key else 0
        allow_by_rubric = True
        if rubric_key is not None and rubric_limit is not None:
            allow_by_rubric = rubric_count < rubric_limit
        forced_key = (post.author_id, day_key)
        forced_used = forced_daily_counts.get(forced_key, 0)
        force_slot_available = post.author.force_home and forced_used < 1
        if not (allow_by_rubric or force_slot_available):
            continue
        if allow_by_rubric and rubric_key is not None:
            rubric_daily_counts[rubric_key] = rubric_count + 1
        elif force_slot_available:
            forced_daily_counts[forced_key] = forced_used + 1
        author_channel_url, author_title = _author_display_fields(
            post.author, rubric, post.channel_url
        )
        serialized_posts.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _rubric_icon_url(request, rubric),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                },
                "tags": _serialize_tags(post.tags.all()),
                "score": post.rating + post.comments_count * 5 + author_rating,
                "rating": post.rating,
                "comments_count": post.comments_count,
                "likes_count": post.rating,
            }
        )
        last_author_id = post.author_id

    return JsonResponse(
        {
            "ok": True,
            "posts": serialized_posts[offset : offset + limit],
            "hidden_read_count": hidden_read_count,
        }
    )


def fresh_feed(request: HttpRequest) -> HttpResponse:
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

    now = timezone.now()
    hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    only_read = request.GET.get("only_read") in ("1", "true", "yes")
    read_user = (
        _get_user_from_request(request) if (hide_read or only_read) else None
    )
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    base_query = (
        Post.objects.filter(
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
        .filter(Q(rubric__isnull=True) | Q(rubric__is_hidden=False))
    )

    hidden_read_count = 0
    if hide_read and read_user:
        hidden_read_count = base_query.filter(reads__user=read_user).count()

    posts_query = base_query
    if only_read:
        posts_query = posts_query.filter(reads__user=read_user)
    elif hide_read and read_user:
        posts_query = posts_query.exclude(reads__user=read_user)
    posts = (
        posts_query.select_related("author", "rubric")
        .prefetch_related("tags")
        .order_by("-created_at")[offset : offset + limit]
    )

    serialized = []
    for post in posts:
        rubric = post.rubric
        author_channel_url, author_title = _author_display_fields(
            post.author, rubric, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _rubric_icon_url(request, rubric),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                },
                "tags": _serialize_tags(post.tags.all()),
                "score": post.rating + post.comments_count * 5,
                "rating": post.rating,
                "comments_count": post.comments_count,
                "likes_count": post.rating,
            }
        )

    return JsonResponse(
        {"ok": True, "posts": serialized, "hidden_read_count": hidden_read_count}
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

    rubrics_raw = request.GET.get("rubrics", "")
    rubric_slugs = [slug.strip() for slug in rubrics_raw.split(",") if slug.strip()]
    if not rubric_slugs:
        return JsonResponse({"ok": True, "posts": []})

    hide_negative_raw = request.GET.get("hide_negative", "1").lower()
    hide_negative = hide_negative_raw not in ("0", "false", "no", "off")

    rubric_ids = list(
        Rubric.objects.filter(
            slug__in=rubric_slugs, is_active=True, is_hidden=False
        ).values_list("id", flat=True)
    )
    if not rubric_ids:
        return JsonResponse({"ok": True, "posts": []})

    now = timezone.now()
    hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    only_read = request.GET.get("only_read") in ("1", "true", "yes")
    read_user = (
        _get_user_from_request(request) if (hide_read or only_read) else None
    )
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    base_query = (
        Post.objects.filter(
            rubric_id__in=rubric_ids,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
    )
    if hide_negative:
        base_query = base_query.filter(rating__gte=0)

    hidden_read_count = 0
    if hide_read and read_user:
        hidden_read_count = base_query.filter(reads__user=read_user).count()

    posts_query = base_query
    if only_read:
        posts_query = posts_query.filter(reads__user=read_user)
    elif hide_read and read_user:
        posts_query = posts_query.exclude(reads__user=read_user)

    posts = (
        posts_query.select_related("author", "rubric")
        .prefetch_related("tags")
        .order_by("-created_at")[offset : offset + limit]
    )

    serialized = []
    for post in posts:
        rubric = post.rubric
        author_channel_url, author_title = _author_display_fields(
            post.author, rubric, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _rubric_icon_url(request, rubric),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                },
                "tags": _serialize_tags(post.tags.all()),
                "score": post.rating + post.comments_count * 5,
                "rating": post.rating,
                "comments_count": post.comments_count,
                "likes_count": post.rating,
            }
        )

    return JsonResponse(
        {"ok": True, "posts": serialized, "hidden_read_count": hidden_read_count}
    )


def top_authors_month(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "5")
    try:
        limit = min(max(int(limit_raw), 1), 20)
    except ValueError:
        limit = 5

    cutoff = timezone.now() - timedelta(days=30)
    now = timezone.now()
    score_expr = Cast(F("posts__rating"), IntegerField()) + Cast(
        F("posts__comments_count"), IntegerField()
    ) * Value(5)
    posts_filter = Q(
        posts__created_at__gte=cutoff,
        posts__is_blocked=False,
        posts__is_pending=False,
    ) & (Q(posts__publish_at__isnull=True) | Q(posts__publish_at__lte=now))

    authors = (
        Author.objects.filter(is_blocked=False)
        .filter(Q(shadow_banned=False) | Q(force_home=True))
        .annotate(
            month_score=Sum(score_expr, filter=posts_filter),
            month_posts=Count("posts", filter=posts_filter),
        )
        .filter(month_posts__gt=0)
        .order_by("-month_score", "-month_posts", "username")[:limit]
    )

    serialized = []
    for author in authors:
        serialized.append(
            {
                "username": author.username,
                "title": author.title,
                "avatar_url": _author_avatar_url(request, author),
                "channel_url": author.invite_url or author.channel_url,
                "month_score": author.month_score or 0,
                "month_posts": author.month_posts or 0,
                "author_rating": _author_rating_value(author.rating_total),
            }
        )

    return JsonResponse({"ok": True, "authors": serialized})


def search_content(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse(
            {
                "ok": True,
                "query": "",
                "page": 1,
                "limit": 0,
                "posts": [],
                "authors": [],
                "total_posts": 0,
                "total_authors": 0,
            }
        )

    type_filter = (request.GET.get("type") or "All").lower()
    sort = (request.GET.get("sort") or "New").lower()

    limit_raw = request.GET.get("limit", "20")
    page_raw = request.GET.get("page", "1")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20
    try:
        page = max(int(page_raw), 1)
    except ValueError:
        page = 1

    offset = (page - 1) * limit

    posts: list[dict] = []
    authors: list[dict] = []
    total_posts = 0
    total_authors = 0

    if type_filter in ("all", "posts"):
        post_query = Q(title__icontains=query) | Q(content__icontains=query)
        post_query |= Q(author__username__icontains=query) | Q(
            author__title__icontains=query
        )
        now = timezone.now()
        posts_qs = (
            Post.objects.filter(
                post_query,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(_publish_ready_filter(now))
            .select_related("author", "rubric")
            .prefetch_related("tags")
            .order_by("-created_at" if sort == "new" else "-created_at")
        )
        total_posts = posts_qs.count()
        for post in posts_qs[offset : offset + limit]:
            rubric = post.rubric
            author_channel_url, author_title = _author_display_fields(
                post.author, rubric, post.channel_url
            )
            posts.append(
                {
                    "id": post.id,
                    "title": _post_display_title(post),
                    "rubric": rubric.name if rubric else None,
                    "rubric_slug": rubric.slug if rubric else None,
                    "rubric_icon_url": _rubric_icon_url(request, rubric)
                    if rubric
                    else None,
                    "content": post.content,
                    "source_url": post.source_url,
                    "channel_url": author_channel_url,
                    "created_at": post.created_at.isoformat(),
                    "comments_count": post.comments_count,
                    "likes_count": post.rating,
                    "tags": _serialize_tags(post.tags.all()),
                    "author": {
                        "username": post.author.username,
                        "title": author_title,
                        "channel_url": author_channel_url,
                        "avatar_url": _author_avatar_for_rubric(request, post.author, rubric),
                        "description": post.author.description,
                        "subscribers_count": post.author.subscribers_count,
                    },
                }
            )

    if type_filter in ("all", "users", "authors"):
        authors_qs = (
            Author.objects.filter(is_blocked=False)
            .filter(
                Q(username__icontains=query)
                | Q(title__icontains=query)
                | Q(description__icontains=query)
            )
        )
        total_authors = authors_qs.count()
        for author in authors_qs[offset : offset + limit]:
            authors.append(
                {
                    "username": author.username,
                    "title": author.title,
                    "avatar_url": _author_avatar_url(request, author),
                    "description": author.description,
                    "channel_url": author.invite_url or author.channel_url,
                    "subscribers_count": author.subscribers_count,
                    "author_rating": _author_rating_value(author.rating_total),
                }
            )

    return JsonResponse(
        {
            "ok": True,
            "query": query,
            "page": page,
            "limit": limit,
            "posts": posts,
            "authors": authors,
            "total_posts": total_posts,
            "total_authors": total_authors,
        }
    )


SITEMAP_PAGE_SIZE = 5000


def _sitemap_urlset(entries: list[tuple[str, str | None]]) -> HttpResponse:
    urls = []
    for loc, lastmod in entries:
        entry = f"<url><loc>{xml_escape(loc)}</loc>"
        if lastmod:
            entry += f"<lastmod>{xml_escape(lastmod)}</lastmod>"
        entry += "</url>"
        urls.append(entry)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(body, content_type="application/xml")


def _sitemap_index(entries: list[tuple[str, str | None]]) -> HttpResponse:
    items = []
    for loc, lastmod in entries:
        entry = f"<sitemap><loc>{xml_escape(loc)}</loc>"
        if lastmod:
            entry += f"<lastmod>{xml_escape(lastmod)}</lastmod>"
        entry += "</sitemap>"
        items.append(entry)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(items)
        + "</sitemapindex>"
    )
    return HttpResponse(body, content_type="application/xml")


def sitemap_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    now = timezone.now()

    def full(path: str) -> str:
        return f"{base_url}{path}"

    rubrics_lastmod = (
        Rubric.objects.filter(is_hidden=False)
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    authors_lastmod = Author.objects.order_by("-updated_at").values_list("updated_at", flat=True).first()
    posts_lastmod = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(_publish_ready_filter(now))
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    posts_count = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(_publish_ready_filter(now))
        .count()
    )
    pages = max(1, ceil(posts_count / SITEMAP_PAGE_SIZE))

    entries: list[tuple[str, str | None]] = [
        (full("/sitemap-static.xml"), None),
        (full("/sitemap-rubrics.xml"), _format_lastmod(rubrics_lastmod) if rubrics_lastmod else None),
        (full("/sitemap-authors.xml"), _format_lastmod(authors_lastmod) if authors_lastmod else None),
    ]

    for page in range(1, pages + 1):
        entries.append(
            (
                full(f"/sitemap-posts-{page}.xml"),
                _format_lastmod(posts_lastmod) if posts_lastmod else None,
            )
        )

    return _sitemap_index(entries)


def sitemap_static_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    static_paths = [
        "/",
        "/authors",
        "/rubrics",
        "/about",
        "/advertisement",
        "/rules",
    ]
    entries = [(f"{base_url}{path}", None) for path in static_paths]
    return _sitemap_urlset(entries)


def sitemap_rubrics_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    rubrics = Rubric.objects.filter(is_active=True, is_hidden=False).order_by("slug")
    entries = [
        (f"{base_url}/rubrics/{rubric.slug}/posts", _format_lastmod(rubric.updated_at))
        for rubric in rubrics
    ]
    return _sitemap_urlset(entries)


def sitemap_authors_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    authors = Author.objects.filter(is_blocked=False).order_by("username")
    entries = [
        (f"{base_url}/{author.username}", _format_lastmod(author.updated_at))
        for author in authors
    ]
    return _sitemap_urlset(entries)


def sitemap_posts_xml(request: HttpRequest, page: int) -> HttpResponse:
    if page < 1:
        return HttpResponse(status=404)

    base_url = _sitemap_base_url(request)
    now = timezone.now()
    qs = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(_publish_ready_filter(now))
    )
    total = qs.count()
    total_pages = max(1, ceil(total / SITEMAP_PAGE_SIZE))
    if page > total_pages:
        return HttpResponse(status=404)

    offset = (page - 1) * SITEMAP_PAGE_SIZE
    posts = (
        qs.only("id", "title", "updated_at", "created_at")
        .order_by("-updated_at", "-id")[offset : offset + SITEMAP_PAGE_SIZE]
    )

    entries = []
    for post in posts:
        lastmod = _format_lastmod(post.updated_at or post.created_at)
        slug = _slugify_title(post.title)
        path = f"/b/post/{post.id}-{slug}" if slug else f"/b/post/{post.id}"
        entries.append((f"{base_url}{path}", lastmod))

    return _sitemap_urlset(entries)
