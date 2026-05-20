from __future__ import annotations

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
    PublicBookProjectSettings,
    PublicBookReminder,
    PublicBookState,
    PublicBookWord,
)
from users.models import SiteUserProfile

User = get_user_model()

PROJECT_SLUG = PublicBookState.PROJECT_SLUG
MAX_WORDS = 185_000
SUBMISSION_INTERVAL = timedelta(hours=24)
DEFAULT_RULES_TEXT = (
    "Каждый зарегистрированный пользователь с привязанным Telegram или VK может добавить "
    "одно слово в сутки. Слово должно состоять только из букв и быть не длиннее 30 символов. "
    "Слова из стоп-листа не принимаются. Финальная версия книги будет отцензурирована по "
    "нарушениям закона и выпущена в электронном виде бесплатно."
)
DISCUSSION_AUTHOR_USERNAME = "tambur-book"
DISCUSSION_AUTHOR_TITLE = "Книга сообщества интернет"
DISCUSSION_AUTHOR_DESCRIPTION = (
    "https://tambur.pub/s/book/\n\n"
    "Мы люди из интернет-сообщества вместе напишем книгу о том, что думаем, "
    "видим, чувствуем. После завершения книга будет отцензурирована и выпущена "
    "в электронном виде доступном бесплатно каждому и в печатном виде. Каждый "
    "может добавлять только одно слово в сутки."
)
DISCUSSION_MESSAGE_ID = 150000001
MAX_WORD_LENGTH = 30
REMINDER_EVENT_KEY = "public_book_reminder"
FINAL_PDF_EVENT_KEY = "public_book_final_pdf"


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


def update_admin_settings(payload: dict[str, Any], user: User) -> dict[str, Any]:
    settings_obj = project_settings()
    if "rules_text" in payload:
        settings_obj.rules_text = str(payload.get("rules_text") or "").strip()
    settings_obj.updated_by = user
    settings_obj.save(update_fields=("rules_text", "updated_by", "updated_at"))
    return {"ok": True, "project": PROJECT_SLUG, **settings_payload(settings_obj)}


def normalize_public_book_word(value: str) -> dict[str, str]:
    word = str(value or "").strip()
    if not word:
        raise ValueError("Введите одно слово.")
    if any(char.isspace() for char in word):
        raise ValueError("Можно отправить только одно слово без пробелов.")
    if len(word) > MAX_WORD_LENGTH:
        raise ValueError("Слово не должно быть длиннее 30 символов.")
    if not all(char.isalpha() for char in word):
        raise ValueError("Слово должно состоять только из букв.")
    normalized = word.casefold().replace("ё", "е")
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
    next_available_at = _next_available_at_for_user(user, now=now)
    has_social_identity = _user_has_social_identity(user)
    can_submit = bool(user is not None and has_social_identity and next_available_at is None)
    if user is None:
        reason = "auth_required"
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
        "telegram_linked": _user_has_telegram(user),
        "vk_linked": _user_has_vk(user),
        "has_social_identity": has_social_identity,
        "reminder": reminder_payload_for_user(user, now=now),
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
        "Обсуждение «Книги сообщества интернет». Здесь можно спорить о словах, "
        "правилах, финальной редактуре и бумажной версии."
    )
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
            "title": "Обсуждение книги сообщества интернет",
            "content": content,
            "source_url": _site_url("/s/book"),
            "is_pending": False,
            "is_blocked": False,
            "publish_at": None,
            "raw_data": raw_data,
        },
    )
    updates: list[str] = []
    if post.title != "Обсуждение книги сообщества интернет":
        post.title = "Обсуждение книги сообщества интернет"
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


def submit_word(user: User, raw_word: str) -> PublicBookWord:
    normalized = normalize_public_book_word(raw_word)
    now = timezone.now()

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

        is_blocked = PublicBookBlockedWord.objects.filter(
            project_slug=PROJECT_SLUG,
            normalized_word=normalized["normalized_word"],
            is_active=True,
        ).exists()
        if is_blocked:
            raise ValueError("Это слово нельзя добавить в книгу.")

        word = PublicBookWord.objects.create(
            project_slug=PROJECT_SLUG,
            position=state.total_words + 1,
            word=normalized["word"],
            normalized_word=normalized["normalized_word"],
            submitted_by=user,
        )
        state.total_words += 1
        state.save(update_fields=("total_words", "updated_at"))
        return word


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
            message="Прошли 24 часа. Добавьте следующее слово в «Книгу сообщества интернет».",
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
