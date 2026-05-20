from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from special_projects.models import PublicBookBlockedWord, PublicBookState, PublicBookWord

User = get_user_model()

PROJECT_SLUG = PublicBookState.PROJECT_SLUG
MAX_WORDS = 150_000
SUBMISSION_INTERVAL = timedelta(hours=24)
DISCUSSION_AUTHOR_USERNAME = "tambur-book"
DISCUSSION_AUTHOR_TITLE = "Книга одного слова"
DISCUSSION_AUTHOR_DESCRIPTION = (
    "https://tambur.pub/s/book/\n\n"
    "Ироничный спецпроект Tambur: каждый зарегистрированный пользователь может "
    "добавить одно слово в общую книгу не чаще раза в 24 часа."
)
DISCUSSION_MESSAGE_ID = 150000001


def _site_url(path: str) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        base_url = "http://localhost:5173"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def normalize_public_book_word(value: str) -> dict[str, str]:
    word = str(value or "").strip()
    if not word:
        raise ValueError("Введите одно слово.")
    if any(char.isspace() for char in word):
        raise ValueError("Можно отправить только одно слово без пробелов.")
    if len(word) > 64:
        raise ValueError("Слово слишком длинное.")
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


def can_submit_payload(user: User | None, now=None) -> dict[str, Any]:
    next_available_at = _next_available_at_for_user(user, now=now)
    return {
        "can_submit": bool(user is not None and next_available_at is None),
        "next_available_at": next_available_at.isoformat() if next_available_at else None,
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
        "Обсуждение спецпроекта «Книга одного слова». Здесь можно спорить о словах, "
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
            "title": "Обсуждение книги одного слова",
            "content": content,
            "source_url": _site_url("/s/book"),
            "is_pending": False,
            "is_blocked": False,
            "publish_at": None,
            "raw_data": raw_data,
        },
    )
    updates: list[str] = []
    if post.title != "Обсуждение книги одного слова":
        post.title = "Обсуждение книги одного слова"
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
        **can_submit_payload(user),
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
            raise ValueError("Книга уже набрала 150000 слов.")

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
