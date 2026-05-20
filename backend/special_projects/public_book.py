from __future__ import annotations

import logging
import re
import unicodedata
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from special_projects.models import (
    PublicBookBlockedWord,
    PublicBookFinalNotificationSubscription,
    PublicBookModerationState,
    PublicBookProjectSettings,
    PublicBookReminder,
    PublicBookState,
    PublicBookWord,
)
from users.models import SiteUserProfile

User = get_user_model()
logger = logging.getLogger(__name__)

PROJECT_SLUG = PublicBookState.PROJECT_SLUG
MAX_WORDS = 185_000
SUBMISSION_INTERVAL = timedelta(hours=24)
MODERATION_VIOLATION_LIMIT = 3
MODERATION_LOCK_INTERVAL = timedelta(hours=24)
BLOCKED_WORD_WARNING = "Кажется вы хотите вбить что-то недозволенное, ай-яй-яй."
DEFAULT_RULES_TEXT = (
    "Каждый зарегистрированный пользователь с привязанным Telegram или VK может добавить "
    "одно слово или знак препинания в сутки. Запись должна состоять только из букв "
    "и знаков препинания и быть не длиннее 30 символов. "
    "Слова из стоп-листа не принимаются. Финальная версия книги будет отцензурирована по "
    "нарушениям закона и выпущена в электронном виде бесплатно."
)
DISCUSSION_AUTHOR_USERNAME = "tambur-book"
DISCUSSION_AUTHOR_TITLE = "Книга интернет сообщества"
DISCUSSION_AUTHOR_DESCRIPTION = (
    "https://tambur.pub/s/book/\n\n"
    "Мы люди из интернет-сообщества совместно напишем книгу о том, что думаем, "
    "видим, чувствуем - это полная свобода самовыражения. Книга будет длинной "
    "185 000 слов, что примерно 500 страниц. Каждый пользователь пишет только "
    "одно слово в сутки. Финальная версия будет опубликована в PDF и доступна "
    "всем, а также будет возможность для печати бумажной версии. Проводится "
    "проверка публикации на законность и контент может быть отцензурирован."
)
DISCUSSION_MESSAGE_ID = 150000001
MAX_WORD_LENGTH = 30
REMINDER_EVENT_KEY = "public_book_reminder"
FINAL_PDF_EVENT_KEY = "public_book_final_pdf"
PUBLIC_BOOK_BANNED_PATTERNS = (
    r"путинлох",
    r"путинхуйло",
    r"смертьпутину",
)
MIN_CONSONANT_PATTERN_LENGTH = 4
INVISIBLE_UNICODE_RE = re.compile(r"[\u200B-\u200D\uFEFF]")
REPEATED_CHAR_RE = re.compile(r"(.)\1+")
LATIN_TO_CYRILLIC = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "k": "к",
        "m": "м",
        "h": "н",
        "o": "о",
        "p": "р",
        "t": "т",
        "x": "х",
        "y": "у",
        "0": "о",
        "3": "з",
        "4": "ч",
        "6": "б",
    }
)
TRANSLIT_DIGITS_TO_CYRILLIC = {
    "0": "о",
    "3": "з",
    "4": "ч",
    "6": "б",
}
TRANSLIT_MULTI_TO_CYRILLIC = (
    ("shch", "щ"),
    ("sch", "щ"),
    ("yo", "е"),
    ("jo", "е"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ju", "ю"),
    ("ya", "я"),
    ("ja", "я"),
    ("ye", "е"),
    ("je", "е"),
)
TRANSLIT_CHAR_TO_CYRILLIC = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "ы",
    "z": "з",
}
RUSSIAN_VOWELS = frozenset("аеёиоуыэюя")


def _site_url(path: str) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        base_url = "http://localhost:5173"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def _file_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return _site_url(path)


def project_settings() -> PublicBookProjectSettings:
    settings_obj, _created = PublicBookProjectSettings.objects.get_or_create(
        project_slug=PROJECT_SLUG,
    )
    return settings_obj


def settings_payload(settings_obj: PublicBookProjectSettings | None = None) -> dict[str, Any]:
    settings_obj = settings_obj or project_settings()
    final_pdf_url = _file_url(settings_obj.final_pdf.url) if settings_obj.final_pdf else ""
    return {
        "rules_text": (settings_obj.rules_text or DEFAULT_RULES_TEXT).strip(),
        "final_pdf": {
            "available": bool(settings_obj.final_pdf),
            "url": final_pdf_url or None,
            "uploaded_at": settings_obj.final_pdf_uploaded_at.isoformat()
            if settings_obj.final_pdf_uploaded_at
            else None,
            "announced_at": settings_obj.final_pdf_announced_at.isoformat()
            if settings_obj.final_pdf_announced_at
            else None,
        },
    }


def update_admin_settings(
    payload: dict[str, Any],
    user: User,
    *,
    final_pdf=None,
) -> dict[str, Any]:
    settings_obj = project_settings()
    update_fields = ["updated_by", "updated_at"]
    if "rules_text" in payload:
        settings_obj.rules_text = str(payload.get("rules_text") or "").strip()
        update_fields.append("rules_text")
    final_pdf_changed = final_pdf is not None
    if final_pdf_changed:
        settings_obj.final_pdf = final_pdf
        settings_obj.final_pdf_uploaded_at = timezone.now()
        update_fields.extend(("final_pdf", "final_pdf_uploaded_at"))
    settings_obj.updated_by = user
    settings_obj.save(update_fields=tuple(dict.fromkeys(update_fields)))
    if final_pdf_changed:
        notify_final_pdf_subscribers(settings_obj=settings_obj)
    return {"ok": True, "project": PROJECT_SLUG, **settings_payload(settings_obj)}


def serialize_blocked_word(item: PublicBookBlockedWord) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_slug": item.project_slug,
        "word": item.word,
        "normalized_word": item.normalized_word,
        "is_active": item.is_active,
        "note": item.note,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "created_by": {
            "id": item.created_by_id,
            "username": (getattr(item.created_by, "username", "") or "").strip()
            if item.created_by_id
            else "",
        },
    }


def admin_blocked_words_payload() -> dict[str, Any]:
    words = (
        PublicBookBlockedWord.objects.filter(project_slug=PROJECT_SLUG)
        .select_related("created_by")
        .order_by("-is_active", "normalized_word", "id")
    )
    return {
        "ok": True,
        "project": PROJECT_SLUG,
        "blocked_words": [serialize_blocked_word(item) for item in words],
    }


def _payload_bool(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def upsert_admin_blocked_word(payload: dict[str, Any], user: User) -> PublicBookBlockedWord:
    word = str(payload.get("word") or "").strip()
    normalized_word = normalize_public_book_blocked_word_key(word)
    if not normalized_word:
        raise ValueError("Введите запрещенное слово или выражение.")
    item, created = PublicBookBlockedWord.objects.update_or_create(
        project_slug=PROJECT_SLUG,
        normalized_word=normalized_word,
        defaults={
            "word": word,
            "note": str(payload.get("note") or "").strip()[:240],
            "is_active": _payload_bool(payload, "is_active", default=True),
            "created_by": user,
        },
    )
    if not created and item.created_by_id is None:
        item.created_by = user
        item.save(update_fields=("created_by", "updated_at"))
    return item


def update_admin_blocked_word(item_id: int, payload: dict[str, Any], user: User) -> PublicBookBlockedWord:
    item = PublicBookBlockedWord.objects.get(id=item_id, project_slug=PROJECT_SLUG)
    if "word" in payload:
        item.word = str(payload.get("word") or "").strip()
    if "note" in payload:
        item.note = str(payload.get("note") or "").strip()[:240]
    if "is_active" in payload:
        item.is_active = _payload_bool(payload, "is_active", default=item.is_active)
    if item.created_by_id is None:
        item.created_by = user
    item.save()
    return item


def delete_admin_blocked_word(item_id: int) -> None:
    PublicBookBlockedWord.objects.filter(id=item_id, project_slug=PROJECT_SLUG).delete()


def normalize_public_book_moderation_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    text = INVISIBLE_UNICODE_RE.sub("", text)
    text = text.translate(LATIN_TO_CYRILLIC)
    text = "".join(
        char
        for char in text
        if char.isalnum() and unicodedata.category(char) not in {"Cf", "Mn"}
    )
    return REPEATED_CHAR_RE.sub(r"\1", text)


def normalize_public_book_translit_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    text = INVISIBLE_UNICODE_RE.sub("", text)
    result: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if not char.isalnum() or unicodedata.category(char) in {"Cf", "Mn"}:
            index += 1
            continue
        if char in TRANSLIT_DIGITS_TO_CYRILLIC:
            result.append(TRANSLIT_DIGITS_TO_CYRILLIC[char])
            index += 1
            continue
        if "a" <= char <= "z":
            matched = False
            for latin, cyrillic in TRANSLIT_MULTI_TO_CYRILLIC:
                if text.startswith(latin, index):
                    result.append(cyrillic)
                    index += len(latin)
                    matched = True
                    break
            if matched:
                continue
            result.append(TRANSLIT_CHAR_TO_CYRILLIC.get(char, char))
            index += 1
            continue
        result.append(char)
        index += 1
    return REPEATED_CHAR_RE.sub(r"\1", "".join(result))


def normalize_public_book_moderation_variants(value: str) -> set[str]:
    return {
        variant
        for variant in (
            normalize_public_book_moderation_text(value),
            normalize_public_book_translit_text(value),
        )
        if variant
    }


def normalize_public_book_blocked_word_key(value: str) -> str:
    normalized = normalize_public_book_moderation_text(value)
    if normalized and not any("a" <= char <= "z" for char in normalized):
        return normalized[:64]
    transliterated = normalize_public_book_translit_text(value)
    return (transliterated or normalized)[:64]


def _without_vowels(value: str) -> str:
    return "".join(char for char in value if char not in RUSSIAN_VOWELS)


def _consonant_pattern_allowed(value: str) -> bool:
    return len(value) >= MIN_CONSONANT_PATTERN_LENGTH


def _public_book_ban_match(raw_text: str) -> dict[str, str] | None:
    normalized_texts = normalize_public_book_moderation_variants(raw_text)
    if not normalized_texts:
        return None

    for normalized_text in normalized_texts:
        consonants_text = _without_vowels(normalized_text)
        for pattern in PUBLIC_BOOK_BANNED_PATTERNS:
            for normalized_pattern in normalize_public_book_moderation_variants(pattern):
                consonants_pattern = _without_vowels(normalized_pattern)
                if re.search(normalized_pattern, normalized_text) or (
                    consonants_text
                    and consonants_pattern
                    and _consonant_pattern_allowed(consonants_pattern)
                    and re.search(consonants_pattern, consonants_text)
                ):
                    return {
                        "normalized_text": normalized_text,
                        "pattern": normalized_pattern,
                    }

    blocked_words = PublicBookBlockedWord.objects.filter(
        project_slug=PROJECT_SLUG,
        is_active=True,
    ).values_list("normalized_word", flat=True)
    for normalized_text in normalized_texts:
        consonants_text = _without_vowels(normalized_text)
        for blocked_word in blocked_words:
            for blocked in normalize_public_book_moderation_variants(blocked_word):
                blocked_consonants = _without_vowels(blocked)
                if (
                    normalized_text == blocked
                    or blocked in normalized_text
                    or (
                        blocked_consonants
                        and _consonant_pattern_allowed(blocked_consonants)
                        and consonants_text == blocked_consonants
                    )
                    or (
                        blocked_consonants
                        and _consonant_pattern_allowed(blocked_consonants)
                        and blocked_consonants in consonants_text
                    )
                ):
                    return {
                        "normalized_text": normalized_text,
                        "pattern": blocked,
                    }
    return None


def _ensure_public_book_text_allowed(raw_text: str) -> None:
    match = _public_book_ban_match(raw_text)
    if match is None:
        return
    logger.warning(
        "public_book_blocked_text_detected",
        extra={
            "raw_text": str(raw_text or ""),
            "normalized_text": match["normalized_text"],
            "matched_pattern": match["pattern"],
        },
    )
    raise ValueError("Это слово нельзя добавить в книгу.")


def _previous_word_pair_text(previous_word: PublicBookWord | None, current_word: str) -> str:
    if previous_word is None:
        return current_word
    return f"{previous_word.word}{current_word}"


def _is_public_book_word_character(char: str) -> bool:
    return char.isalpha() or unicodedata.category(char).startswith("P")


def normalize_public_book_word(value: str) -> dict[str, str]:
    word = str(value or "").strip()
    if not word:
        raise ValueError("Введите одно слово.")
    if any(char.isspace() for char in word):
        raise ValueError("Можно отправить только одно слово без пробелов.")
    if len(word) > MAX_WORD_LENGTH:
        raise ValueError("Слово не должно быть длиннее 30 символов.")
    if not all(_is_public_book_word_character(char) for char in word):
        raise ValueError("Запись должна состоять только из букв и знаков препинания.")
    normalized = normalize_public_book_moderation_text(word)
    return {"word": word, "normalized_word": normalized}


def _book_state_for_update() -> PublicBookState:
    state = (
        PublicBookState.objects.select_for_update()
        .filter(project_slug=PROJECT_SLUG)
        .first()
    )
    if state is not None:
        return state
    total_words = PublicBookWord.objects.filter(project_slug=PROJECT_SLUG).count()
    return PublicBookState.objects.create(project_slug=PROJECT_SLUG, total_words=total_words)


def serialize_word(word: PublicBookWord) -> dict[str, Any]:
    return {
        "id": word.id,
        "position": word.position,
        "word": word.word,
        "is_censored": word.is_censored,
        "created_at": word.created_at.isoformat(),
        "submitted_by": {
            "id": word.submitted_by_id,
            "username": (getattr(word.submitted_by, "username", "") or "").strip(),
        },
    }


def _next_available_at_for_user(user: User | None, now=None):
    if user is None:
        return None
    latest = (
        PublicBookWord.objects.filter(project_slug=PROJECT_SLUG, submitted_by=user)
        .order_by("-created_at", "-id")
        .first()
    )
    if latest is None:
        return None
    candidate = latest.created_at + SUBMISSION_INTERVAL
    current = now or timezone.now()
    return candidate if candidate > current else None


def _latest_word_for_user(user: User | None) -> PublicBookWord | None:
    if user is None:
        return None
    return (
        PublicBookWord.objects.filter(project_slug=PROJECT_SLUG, submitted_by=user)
        .order_by("-created_at", "-id")
        .first()
    )


def moderation_lock_until_for_user(user: User | None, now=None):
    if user is None:
        return None
    current = now or timezone.now()
    locked_until = (
        PublicBookModerationState.objects.filter(project_slug=PROJECT_SLUG, user=user)
        .values_list("locked_until", flat=True)
        .first()
    )
    return locked_until if locked_until and locked_until > current else None


def _user_has_telegram(user: User | None) -> bool:
    return bool(user is not None and hasattr(user, "telegram_account"))


def _user_has_vk(user: User | None) -> bool:
    return bool(user is not None and hasattr(user, "vk_account"))


def _user_has_social_identity(user: User | None) -> bool:
    return _user_has_telegram(user) or _user_has_vk(user)


def reminder_payload_for_user(user: User | None, now=None) -> dict[str, Any]:
    latest = _latest_word_for_user(user)
    if user is None or latest is None:
        return {"scheduled": False, "scheduled_at": None, "sent_at": None}
    scheduled_at = latest.created_at + SUBMISSION_INTERVAL
    if scheduled_at <= (now or timezone.now()):
        return {"scheduled": False, "scheduled_at": None, "sent_at": None}
    reminder = (
        PublicBookReminder.objects.filter(
            project_slug=PROJECT_SLUG,
            user=user,
            scheduled_at=scheduled_at,
        )
        .order_by("-id")
        .first()
    )
    return {
        "scheduled": bool(reminder and reminder.sent_at is None),
        "scheduled_at": reminder.scheduled_at.isoformat() if reminder else None,
        "sent_at": reminder.sent_at.isoformat() if reminder and reminder.sent_at else None,
    }


def final_notification_payload_for_user(user: User | None) -> dict[str, Any]:
    if user is None:
        return {"subscribed": False, "notified_at": None}
    subscription = (
        PublicBookFinalNotificationSubscription.objects.filter(
            project_slug=PROJECT_SLUG,
            user=user,
        )
        .order_by("-id")
        .first()
    )
    return {
        "subscribed": bool(subscription),
        "notified_at": subscription.notified_at.isoformat()
        if subscription and subscription.notified_at
        else None,
    }


def can_submit_payload(user: User | None, now=None) -> dict[str, Any]:
    current = now or timezone.now()
    next_available_at = _next_available_at_for_user(user, now=now)
    moderation_locked_until = moderation_lock_until_for_user(user, now=current)
    has_social_identity = _user_has_social_identity(user)
    can_submit = bool(
        user is not None
        and has_social_identity
        and next_available_at is None
        and moderation_locked_until is None
    )
    if user is None:
        reason = "auth_required"
    elif moderation_locked_until is not None:
        reason = "moderation_lock"
    elif not has_social_identity:
        reason = "social_required"
    elif next_available_at is not None:
        reason = "cooldown"
    else:
        reason = ""
    return {
        "can_submit": can_submit,
        "submit_block_reason": reason,
        "next_available_at": next_available_at.isoformat() if next_available_at else None,
        "moderation_locked_until": moderation_locked_until.isoformat()
        if moderation_locked_until
        else None,
        "telegram_linked": _user_has_telegram(user),
        "vk_linked": _user_has_vk(user),
        "has_social_identity": has_social_identity,
        "reminder": reminder_payload_for_user(user, now=current),
        "final_notification": final_notification_payload_for_user(user),
    }


def _discussion_author():
    from feeds.models import Author

    author, _created = Author.objects.get_or_create(
        username=DISCUSSION_AUTHOR_USERNAME,
        defaults={
            "title": DISCUSSION_AUTHOR_TITLE,
            "description": DISCUSSION_AUTHOR_DESCRIPTION,
            "auto_publish": False,
            "notify_comments": False,
        },
    )
    updates: list[str] = []
    if author.title != DISCUSSION_AUTHOR_TITLE:
        author.title = DISCUSSION_AUTHOR_TITLE
        updates.append("title")
    if author.description != DISCUSSION_AUTHOR_DESCRIPTION:
        author.description = DISCUSSION_AUTHOR_DESCRIPTION
        updates.append("description")
    if updates:
        author.save(update_fields=(*updates, "updated_at"))
    return author


def ensure_public_book_discussion_post():
    from feeds.models import Post

    author = _discussion_author()
    content = (
        "Обсуждение «Книги интернет сообщества». Здесь можно спорить о словах, "
        "правилах, финальной редактуре и бумажной версии."
    )
    title = "Обсуждение книги интернет сообщества"
    raw_data = {
        "source": "special_project",
        "special_project": {
            "slug": PROJECT_SLUG,
        },
    }
    post, created = Post.objects.get_or_create(
        author=author,
        message_id=DISCUSSION_MESSAGE_ID,
        defaults={
            "title": title,
            "content": content,
            "source_url": _site_url("/s/book"),
            "is_pending": False,
            "is_blocked": False,
            "publish_at": None,
            "raw_data": raw_data,
        },
    )
    updates: list[str] = []
    if post.title != title:
        post.title = title
        updates.append("title")
    if post.content != content:
        post.content = content
        updates.append("content")
    if post.source_url != _site_url("/s/book"):
        post.source_url = _site_url("/s/book")
        updates.append("source_url")
    if post.raw_data != raw_data:
        post.raw_data = raw_data
        updates.append("raw_data")
    if post.is_pending:
        post.is_pending = False
        updates.append("is_pending")
    if post.is_blocked:
        post.is_blocked = False
        updates.append("is_blocked")
    if post.publish_at is not None:
        post.publish_at = None
        updates.append("publish_at")
    if updates and not created:
        post.save(update_fields=(*updates, "updated_at"))
    return post


def project_status_for_user(user: User | None) -> dict[str, Any]:
    state, _created = PublicBookState.objects.get_or_create(
        project_slug=PROJECT_SLUG,
        defaults={"total_words": PublicBookWord.objects.filter(project_slug=PROJECT_SLUG).count()},
    )
    discussion_post = ensure_public_book_discussion_post()
    settings_obj = project_settings()
    total_words = int(state.total_words or 0)
    return {
        "ok": True,
        "project": PROJECT_SLUG,
        "max_words": MAX_WORDS,
        "total_words": total_words,
        "remaining_words": max(MAX_WORDS - total_words, 0),
        "discussion_post": {
            "id": discussion_post.id,
            "comments_count": discussion_post.comments_count,
        },
        **settings_payload(settings_obj),
        **can_submit_payload(user),
    }


def admin_stats_payload() -> dict[str, Any]:
    words = PublicBookWord.objects.filter(project_slug=PROJECT_SLUG)
    total_words = words.count()
    contributors = (
        words.values(
            "submitted_by_id",
            "submitted_by__username",
            "submitted_by__first_name",
            "submitted_by__last_name",
        )
        .annotate(words_count=Count("id"))
        .order_by("-words_count", "submitted_by__username", "submitted_by_id")
    )
    contributors_count = contributors.count()
    top_users = list(contributors[:3])
    top_three_words = sum(int(row["words_count"] or 0) for row in top_users)
    return {
        "ok": True,
        "project": PROJECT_SLUG,
        "total_words": total_words,
        "contributors_count": contributors_count,
        "average_words_per_user": round(total_words / contributors_count, 2)
        if contributors_count
        else 0,
        "top_three_words": top_three_words,
        "top_users": [
            {
                "user": {
                    "id": row["submitted_by_id"],
                    "username": row["submitted_by__username"] or "",
                    "first_name": row["submitted_by__first_name"] or "",
                    "last_name": row["submitted_by__last_name"] or "",
                },
                "words_count": int(row["words_count"] or 0),
            }
            for row in top_users
        ],
        "registrations_from_page_count": SiteUserProfile.objects.filter(
            registration_source=PROJECT_SLUG,
        ).count(),
    }


def words_payload(*, offset: int = 0, limit: int = 500) -> dict[str, Any]:
    offset = max(int(offset or 0), 0)
    limit = min(max(int(limit or 1), 1), 2000)
    queryset = (
        PublicBookWord.objects.filter(project_slug=PROJECT_SLUG)
        .select_related("submitted_by")
        .order_by("position")
    )
    total_words = PublicBookState.objects.filter(project_slug=PROJECT_SLUG).values_list(
        "total_words",
        flat=True,
    ).first()
    if total_words is None:
        total_words = queryset.count()
    words = list(queryset[offset : offset + limit])
    return {
        "ok": True,
        "project": PROJECT_SLUG,
        "total_words": int(total_words or 0),
        "offset": offset,
        "limit": limit,
        "words": [serialize_word(word) for word in words],
    }


def admin_words_payload(*, offset: int = 0, limit: int = 500, query: str = "") -> dict[str, Any]:
    offset = max(int(offset or 0), 0)
    limit = min(max(int(limit or 1), 1), 1000)
    queryset = (
        PublicBookWord.objects.filter(project_slug=PROJECT_SLUG)
        .select_related("submitted_by", "censored_by")
        .order_by("position")
    )
    query = str(query or "").strip()
    if query:
        queryset = queryset.filter(word__icontains=query)
    total = queryset.count()
    words = list(queryset[offset : offset + limit])
    return {
        "ok": True,
        "project": PROJECT_SLUG,
        "total_words": total,
        "offset": offset,
        "limit": limit,
        "words": [serialize_word(word) for word in words],
    }


def censor_admin_word(word_id: int, user: User) -> PublicBookWord:
    word = PublicBookWord.objects.select_related("submitted_by").get(
        id=word_id,
        project_slug=PROJECT_SLUG,
    )
    if not word.is_censored:
        censored_length = max(1, min(MAX_WORD_LENGTH, len(word.word or "")))
        word.word = "█" * censored_length
        word.normalized_word = ""
        word.is_censored = True
        word.censored_at = timezone.now()
        word.censored_by = user
        word.save(
            update_fields=(
                "word",
                "normalized_word",
                "is_censored",
                "censored_at",
                "censored_by",
            )
        )
    return word


def _censor_text_range(value: str, start: int, end: int) -> str:
    chars = list(str(value or ""))
    for index in range(start, end):
        chars[index] = "█"
    return "".join(chars)


def censor_admin_selection(fragments: list[dict[str, Any]], user: User) -> list[PublicBookWord]:
    if not isinstance(fragments, list) or not fragments:
        raise ValueError("Не выбран фрагмент для цензуры.")
    if len(fragments) > 500:
        raise ValueError("Слишком большой фрагмент для одной операции.")

    ranges_by_word_id: dict[int, list[tuple[int, int]]] = {}
    for fragment in fragments:
        if not isinstance(fragment, dict):
            raise ValueError("Некорректный фрагмент для цензуры.")
        try:
            word_id = int(fragment.get("word_id"))
            start = int(fragment.get("start"))
            end = int(fragment.get("end"))
        except (TypeError, ValueError):
            raise ValueError("Некорректный фрагмент для цензуры.") from None
        if start < 0 or end <= start:
            raise ValueError("Некорректный диапазон цензуры.")
        ranges_by_word_id.setdefault(word_id, []).append((start, end))

    now = timezone.now()
    changed_words: list[PublicBookWord] = []
    with transaction.atomic():
        words = {
            item.id: item
            for item in PublicBookWord.objects.select_for_update()
            .select_related("submitted_by")
            .filter(project_slug=PROJECT_SLUG, id__in=ranges_by_word_id.keys())
            .order_by("position")
        }
        if len(words) != len(ranges_by_word_id):
            raise PublicBookWord.DoesNotExist

        for word_id in sorted(words, key=lambda key: words[key].position):
            word = words[word_id]
            text = str(word.word or "")
            text_length = len(text)
            merged_ranges: list[tuple[int, int]] = []
            for start, end in sorted(ranges_by_word_id[word_id]):
                if end > text_length:
                    raise ValueError("Диапазон цензуры выходит за границы слова.")
                if merged_ranges and start <= merged_ranges[-1][1]:
                    merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], end))
                else:
                    merged_ranges.append((start, end))

            censored_text = text
            for start, end in reversed(merged_ranges):
                censored_text = _censor_text_range(censored_text, start, end)
            if censored_text == text and word.is_censored:
                changed_words.append(word)
                continue

            word.word = censored_text
            word.normalized_word = normalize_public_book_moderation_text(censored_text)[:MAX_WORD_LENGTH]
            word.is_censored = True
            word.censored_at = now
            word.censored_by = user
            word.save(
                update_fields=(
                    "word",
                    "normalized_word",
                    "is_censored",
                    "censored_at",
                    "censored_by",
                )
            )
            changed_words.append(word)
    return changed_words


def _reset_moderation_violations(user: User) -> None:
    PublicBookModerationState.objects.filter(project_slug=PROJECT_SLUG, user=user).update(
        consecutive_violations=0,
        locked_until=None,
        updated_at=timezone.now(),
    )


class PublicBookBlockedTextError(ValueError):
    def __init__(self, message: str = BLOCKED_WORD_WARNING):
        super().__init__(message)


class PublicBookModerationLockedError(ValueError):
    def __init__(self, locked_until):
        self.locked_until = locked_until
        super().__init__("Вы временно не можете добавлять слова. Попробуйте через 24 часа.")


def _record_moderation_violation(user: User, raw_text: str, match: dict[str, str], now) -> None:
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        state, _created = PublicBookModerationState.objects.select_for_update().get_or_create(
            project_slug=PROJECT_SLUG,
            user=user,
        )
        if state.locked_until and state.locked_until > now:
            raise PublicBookModerationLockedError(state.locked_until)
        if state.locked_until and state.locked_until <= now:
            state.consecutive_violations = 0
            state.locked_until = None
        state.consecutive_violations += 1
        state.last_violation_at = now
        if state.consecutive_violations >= MODERATION_VIOLATION_LIMIT:
            state.locked_until = now + MODERATION_LOCK_INTERVAL
        else:
            state.locked_until = None
        state.save(
            update_fields=(
                "consecutive_violations",
                "last_violation_at",
                "locked_until",
                "updated_at",
            )
        )
    logger.warning(
        "public_book_blocked_text_detected",
        extra={
            "user_id": user.id,
            "raw_text": str(raw_text or ""),
            "normalized_text": match["normalized_text"],
            "matched_pattern": match["pattern"],
            "consecutive_violations": state.consecutive_violations,
            "locked_until": state.locked_until.isoformat() if state.locked_until else "",
        },
    )
    if state.locked_until and state.locked_until > now:
        raise PublicBookBlockedTextError(
            f"{BLOCKED_WORD_WARNING} Возможность писать слово заблокирована на 24 часа."
        )
    raise PublicBookBlockedTextError()


def submit_word(user: User, raw_word: str) -> PublicBookWord:
    now = timezone.now()
    locked_until = moderation_lock_until_for_user(user, now=now)
    if locked_until is not None:
        raise PublicBookModerationLockedError(locked_until)

    match = _public_book_ban_match(raw_word)
    if match is not None:
        _record_moderation_violation(user, raw_word, match, now)

    normalized = normalize_public_book_word(raw_word)

    blocked_pair: tuple[str, dict[str, str]] | None = None
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        state = _book_state_for_update()

        if state.total_words >= MAX_WORDS:
            raise ValueError("Книга уже набрала 185000 слов.")

        if not _user_has_social_identity(user):
            raise ValueError("Чтобы добавить слово, привяжите Telegram или VK к учетной записи.")

        next_available_at = _next_available_at_for_user(user, now=now)
        if next_available_at is not None:
            raise ValueError("Следующее слово можно будет добавить через 24 часа после предыдущего.")

        previous_word = (
            PublicBookWord.objects.filter(project_slug=PROJECT_SLUG)
            .order_by("-position")
            .first()
        )
        pair_text = _previous_word_pair_text(previous_word, normalized["word"])
        pair_match = _public_book_ban_match(pair_text)
        if pair_match is not None:
            blocked_pair = (pair_text, pair_match)
        else:
            word = PublicBookWord.objects.create(
                project_slug=PROJECT_SLUG,
                position=state.total_words + 1,
                word=normalized["word"],
                normalized_word=normalized["normalized_word"],
                submitted_by=user,
            )
            state.total_words += 1
            state.save(update_fields=("total_words", "updated_at"))
            _reset_moderation_violations(user)
            return word

    if blocked_pair is not None:
        pair_text, pair_match = blocked_pair
        _record_moderation_violation(user, pair_text, pair_match, now)

    raise RuntimeError("Public book word submission finished without a result.")


def schedule_reminder_for_user(user: User) -> PublicBookReminder:
    if not _user_has_telegram(user):
        raise ValueError("Чтобы получить напоминание, привяжите Telegram к учетной записи.")

    latest = _latest_word_for_user(user)
    if latest is None:
        raise ValueError("Сначала добавьте слово в книгу.")

    scheduled_at = latest.created_at + SUBMISSION_INTERVAL
    if scheduled_at <= timezone.now():
        raise ValueError("Вы уже можете добавить следующее слово.")

    reminder, _created = PublicBookReminder.objects.get_or_create(
        project_slug=PROJECT_SLUG,
        user=user,
        scheduled_at=scheduled_at,
    )
    return reminder


def serialize_reminder(reminder: PublicBookReminder) -> dict[str, Any]:
    return {
        "scheduled": reminder.sent_at is None,
        "scheduled_at": reminder.scheduled_at.isoformat(),
        "sent_at": reminder.sent_at.isoformat() if reminder.sent_at else None,
    }


def subscribe_final_pdf_notification(user: User) -> PublicBookFinalNotificationSubscription:
    subscription, _created = PublicBookFinalNotificationSubscription.objects.get_or_create(
        project_slug=PROJECT_SLUG,
        user=user,
    )
    settings_obj = project_settings()
    if settings_obj.final_pdf and subscription.notified_at is None:
        notify_final_pdf_subscribers(settings_obj=settings_obj, user_ids=[user.id])
        subscription.refresh_from_db(fields=("notified_at", "updated_at"))
    return subscription


def notify_final_pdf_subscribers(
    *,
    settings_obj: PublicBookProjectSettings | None = None,
    user_ids: list[int] | None = None,
) -> int:
    from notifications.service import create_user_notification

    settings_obj = settings_obj or project_settings()
    if not settings_obj.final_pdf:
        return 0

    pdf_url = _file_url(settings_obj.final_pdf.url)
    subscriptions = PublicBookFinalNotificationSubscription.objects.select_related("user").filter(
        project_slug=PROJECT_SLUG,
        notified_at__isnull=True,
    )
    if user_ids is not None:
        subscriptions = subscriptions.filter(user_id__in=user_ids)

    now = timezone.now()
    sent = 0
    for subscription in subscriptions.order_by("created_at", "id"):
        create_user_notification(
            user=subscription.user,
            event_key=FINAL_PDF_EVENT_KEY,
            title="Книга сообщества доступна в PDF",
            message="Финальная отцензурированная версия книги готова к скачиванию.",
            link_url=pdf_url or "/s/book",
            payload={"project": PROJECT_SLUG, "pdf_url": pdf_url},
            force_site=True,
            force_telegram=True,
            force_push=True,
        )
        subscription.notified_at = now
        subscription.save(update_fields=("notified_at", "updated_at"))
        sent += 1

    if sent and settings_obj.final_pdf_announced_at is None:
        settings_obj.final_pdf_announced_at = now
        settings_obj.save(update_fields=("final_pdf_announced_at", "updated_at"))
    return sent


def send_due_reminders(*, now=None, limit: int = 500) -> int:
    from notifications.service import create_user_notification

    current_time = now or timezone.now()
    sent = 0
    reminders = list(
        PublicBookReminder.objects.select_related("user")
        .filter(project_slug=PROJECT_SLUG, sent_at__isnull=True, scheduled_at__lte=current_time)
        .order_by("scheduled_at", "id")[: max(int(limit or 1), 1)]
    )
    for reminder in reminders:
        if not _user_has_telegram(reminder.user):
            reminder.sent_at = current_time
            reminder.save(update_fields=("sent_at", "updated_at"))
            continue
        create_user_notification(
            user=reminder.user,
            event_key=REMINDER_EVENT_KEY,
            title="Можно добавить слово в книгу",
            message="Прошли 24 часа. Добавьте следующее слово в «Книгу интернет сообщества».",
            link_url="/s/book",
            payload={"project": PROJECT_SLUG, "reminder_id": reminder.id},
            force_site=False,
            force_telegram=True,
            force_push=False,
        )
        reminder.sent_at = current_time
        reminder.save(update_fields=("sent_at", "updated_at"))
        sent += 1
    return sent
