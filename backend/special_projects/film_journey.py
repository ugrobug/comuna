from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import html
import json
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from notifications.service import create_user_notification
from rabotaem_backend.media_urls import public_url
from special_projects.models import (
    FilmJourneyEntry,
    FilmJourneyFilm,
    FilmJourneySubscription,
    SpecialProjectLetterImage,
)

User = get_user_model()

PROJECT_SLUG = FilmJourneyFilm.PROJECT_SLUG
PUBLIC_TOTAL_COUNT = 365
DAILY_EVENT_KEY = "film_journey_daily"
REMINDER_EVENT_KEY = "film_journey_reminder"
FIRST_REMINDER_AFTER = timedelta(days=2)
SECOND_REMINDER_AFTER = timedelta(days=5)
PAUSE_AFTER = timedelta(days=8)
PROJECT_TIME_ZONE = ZoneInfo("Europe/Moscow")
NEXT_DELIVERY_DEADLINE_HOUR = 18
DISCUSSION_AUTHOR_USERNAME = "tambur-1001-films"
DISCUSSION_AUTHOR_TITLE = "Проект 365 фильмов"
DISCUSSION_AUTHOR_DESCRIPTION = (
    "https://tambur.pub/s/365-films/\n\n"
    "Это челлендж без права выбора. Каждый день — один фильм. Посмотрели, "
    "оценили, перешли к следующему. Пропускать нельзя, выбирать нельзя — "
    "просто смотрите и открывайте для себя разные жанры, культуры и эпохи."
)
DISCUSSION_MESSAGE_ID_BASE = 1001000000
DISCUSSION_RATING_BLOCK_ID = "film-rating"
DISCUSSION_COMUN_SLUG = "after_the_credits"
LANDING_IMAGES_PROJECT_SLUG = "1001-films-landing"
LANDING_IMAGE_SLOTS = ("1", "2", "3")


@dataclass(frozen=True)
class DeliveryResult:
    delivered: int = 0
    reminders: int = 0
    paused: int = 0
    completed: int = 0


def _site_url(path: str) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        base_url = "http://localhost:5173"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def next_delivery_time(now=None):
    value = now or timezone.now()
    local_value = timezone.localtime(value, PROJECT_TIME_ZONE)
    candidate = local_value + timedelta(days=1)
    deadline = candidate.replace(
        hour=NEXT_DELIVERY_DEADLINE_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )
    if candidate > deadline:
        return deadline
    return candidate


def active_films_queryset():
    return FilmJourneyFilm.objects.filter(project_slug=PROJECT_SLUG, is_active=True).order_by(
        "sort_order", "id"
    )


def active_films_count() -> int:
    return active_films_queryset().count()


def serialize_landing_image_slot(slot: str, image: SpecialProjectLetterImage | None = None) -> dict[str, Any]:
    image_url = public_url(image.image_url) if image and image.image_url else ""
    return {
        "id": image.id if image else None,
        "slot": slot,
        "title": image.title if image else f"Кадр {slot}",
        "image_url": image_url,
        "source_url": image.source_url if image else "",
        "is_active": image.is_active if image else False,
    }


def landing_images_payload(*, include_inactive: bool = False) -> list[dict[str, Any]]:
    images = SpecialProjectLetterImage.objects.filter(
        project_slug=LANDING_IMAGES_PROJECT_SLUG,
        letter__in=LANDING_IMAGE_SLOTS,
    )
    if not include_inactive:
        images = images.filter(is_active=True)
    images_by_slot: dict[str, SpecialProjectLetterImage] = {}
    for image in images.order_by("letter", "sort_order", "id"):
        images_by_slot.setdefault(image.letter, image)
    return [
        serialize_landing_image_slot(slot, images_by_slot.get(slot))
        for slot in LANDING_IMAGE_SLOTS
    ]


def serialize_film(film: FilmJourneyFilm) -> dict[str, Any]:
    return {
        "id": film.id,
        "title": film.title,
        "original_title": film.original_title,
        "year": film.year,
        "category": film.category,
        "description": film.description,
        "imdb_url": film.imdb_url,
        "imdb_rating": str(film.imdb_rating) if film.imdb_rating is not None else "",
        "poster_url": film.poster_url,
        "runtime_minutes": film.runtime_minutes,
        "director": film.director,
        "country": film.country,
        "genres": film.genres,
        "sort_order": film.sort_order,
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


def _film_genre_for_template(film: FilmJourneyFilm) -> str:
    value = (film.genres or film.category or "").strip().lower()
    if any(token in value for token in ("хоррор", "ужас")):
        return "horror"
    if any(token in value for token in ("comedy", "комед", "юмор")):
        return "comedy"
    if any(token in value for token in ("drama", "драм", "мелодрам")):
        return "drama"
    if any(token in value for token in ("thriller", "триллер")):
        return "thriller"
    if any(token in value for token in ("mystery", "детектив")):
        return "mystery"
    if any(token in value for token in ("sci_fi", "фантаст", "sci-fi")):
        return "sci_fi"
    if any(token in value for token in ("fantasy", "фэнтези")):
        return "fantasy"
    if any(token in value for token in ("боев", "экшен", "action")):
        return "action"
    if any(token in value for token in ("документ", "document")):
        return "documentary"
    if any(token in value for token in ("анимац", "мульт")):
        return "animation"
    return ""


def movie_review_autofill_data_from_imdb(imdb_input: str) -> dict[str, Any]:
    from editor.service import movie_review_autofill_template_from_imdb

    normalized_data, template_error, _, _, _ = movie_review_autofill_template_from_imdb(imdb_input)
    if template_error or not normalized_data:
        return {}
    return normalized_data


def _autofill_release_year(data: dict[str, Any]) -> int | None:
    release_date = str(data.get("release_date") or "").strip()
    if len(release_date) < 4:
        return None
    try:
        year = int(release_date[:4])
    except ValueError:
        return None
    if year < 1880 or year > 3000:
        return None
    return year


def apply_imdb_autofill_to_film_payload(data: dict[str, Any]) -> dict[str, Any]:
    imdb_url = str(data.get("imdb_url") or "").strip()
    if not imdb_url:
        return data

    template_data = movie_review_autofill_data_from_imdb(imdb_url)
    if not template_data:
        return data

    canonical_imdb_url = str(template_data.get("imdb_url") or "").strip()
    if canonical_imdb_url:
        data["imdb_url"] = canonical_imdb_url

    poster_url = str(template_data.get("poster_url") or "").strip()
    if poster_url and not data.get("poster_url"):
        data["poster_url"] = poster_url[:700]

    release_year = _autofill_release_year(template_data)
    if release_year and not data.get("year"):
        data["year"] = release_year

    genre = str(template_data.get("genre") or "").strip()
    if genre and not data.get("genres"):
        data["genres"] = genre[:240]
    if genre and not data.get("category"):
        data["category"] = genre[:120]

    original_title = str(template_data.get("original_title") or "").strip()
    template_title = str(template_data.get("title") or "").strip()
    if not original_title and template_title and template_title != data.get("title"):
        original_title = template_title
    if original_title and not data.get("original_title"):
        data["original_title"] = original_title[:220]

    return data


def _film_review_template_data(film: FilmJourneyFilm) -> dict[str, Any]:
    data = {
        "imdb_url": film.imdb_url,
        "poster_url": film.poster_url,
        "genre": _film_genre_for_template(film),
        "content_kind": "movie",
        "title": film.title,
        "original_title": film.original_title,
        "release_date": f"{film.year}-01-01" if film.year else "",
        "watch_where": [],
        "author_rating": "",
    }
    return {
        key: value
        for key, value in data.items()
        if (isinstance(value, str) and value.strip()) or (isinstance(value, list) and value)
    }


def _film_review_content(film: FilmJourneyFilm) -> str:
    blocks: list[dict[str, Any]] = []
    if film.description:
        blocks.append(
            {
                "id": "film-description",
                "type": "paragraph",
                "data": {
                    "text": html.escape(film.description).replace("\n", "<br>"),
                },
            }
        )
    blocks.append(
        {
            "id": DISCUSSION_RATING_BLOCK_ID,
            "type": "post_rating",
            "data": {"block_id": DISCUSSION_RATING_BLOCK_ID},
        }
    )
    return json.dumps(
        {
            "time": 0,
            "blocks": blocks,
            "version": "2.31.0",
        },
        ensure_ascii=False,
    )


def _film_discussion_title(film: FilmJourneyFilm) -> str:
    year_part = f" {film.year} года" if film.year else ""
    return f'Как вам фильм "{film.title}"{year_part}?'[:255]


def _film_discussion_message_id(film: FilmJourneyFilm) -> int:
    return DISCUSSION_MESSAGE_ID_BASE + int(film.id)


def _film_discussion_raw_data(film: FilmJourneyFilm) -> dict[str, Any]:
    return {
        "source": "manual_comun",
        "comun_slug": DISCUSSION_COMUN_SLUG,
        "special_project": {
            "slug": PROJECT_SLUG,
            "film_id": film.id,
        },
        "template": {
            "type": "movie_review",
            "version": 1,
            "data": _film_review_template_data(film),
        },
    }


def get_film_discussion_post(film: FilmJourneyFilm):
    from feeds.models import Author, Post

    author = Author.objects.filter(username=DISCUSSION_AUTHOR_USERNAME).first()
    if author is None:
        return None
    return Post.objects.filter(
        author=author,
        message_id=_film_discussion_message_id(film),
    ).first()


def ensure_film_discussion_post(film: FilmJourneyFilm):
    from feeds.models import Post

    author = _discussion_author()
    message_id = _film_discussion_message_id(film)
    raw_data = _film_discussion_raw_data(film)
    title = _film_discussion_title(film)
    content = _film_review_content(film)
    post, created = Post.objects.get_or_create(
        author=author,
        message_id=message_id,
        defaults={
            "title": title,
            "content": content,
            "source_url": film.imdb_url,
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
    if post.source_url != film.imdb_url:
        post.source_url = film.imdb_url
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
    if created or updates:
        from communities.service import _recalculate_comun_ratings_for_post

        _recalculate_comun_ratings_for_post(post)
    return post


def serialize_discussion_post(post, user: User | None = None) -> dict[str, Any]:
    from editor.service import _serialize_post_ratings, _serialize_post_template

    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "template": _serialize_post_template(post),
        "post_ratings": _serialize_post_ratings(post, user),
        "comments_count": post.comments_count,
    }


def serialize_film_discussion_preview(film: FilmJourneyFilm) -> dict[str, Any]:
    from editor.service import _normalize_post_template_payload

    raw_data = _film_discussion_raw_data(film)
    template, _template_error = _normalize_post_template_payload(raw_data.get("template"))
    return {
        "id": None,
        "title": _film_discussion_title(film),
        "content": _film_review_content(film),
        "template": template,
        "post_ratings": {},
        "comments_count": 0,
    }


def special_project_post_filter(post) -> bool:
    raw_data = post.raw_data if isinstance(getattr(post, "raw_data", None), dict) else {}
    project = raw_data.get("special_project") if isinstance(raw_data.get("special_project"), dict) else {}
    return project.get("slug") == PROJECT_SLUG


def entry_public_path(entry: FilmJourneyEntry) -> str:
    return f"/s/365-films/watch/{entry.access_token}"


def entry_absolute_url(entry: FilmJourneyEntry) -> str:
    return _site_url(entry_public_path(entry))


def serialize_entry(
    entry: FilmJourneyEntry,
    *,
    include_film: bool = True,
    include_discussion: bool = False,
    user: User | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": entry.id,
        "position": entry.position,
        "access_token": entry.access_token,
        "path": entry_public_path(entry),
        "url": entry_absolute_url(entry),
        "available_at": entry.available_at.isoformat(),
        "notification_sent_at": entry.notification_sent_at.isoformat()
        if entry.notification_sent_at
        else None,
        "first_reminder_sent_at": entry.first_reminder_sent_at.isoformat()
        if entry.first_reminder_sent_at
        else None,
        "second_reminder_sent_at": entry.second_reminder_sent_at.isoformat()
        if entry.second_reminder_sent_at
        else None,
        "rating": entry.rating,
        "comment": entry.comment,
        "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
    }
    if include_film:
        payload["film"] = serialize_film(entry.film)
    if include_discussion:
        post = get_film_discussion_post(entry.film)
        payload["discussion_post"] = serialize_discussion_post(post, user) if post else None
    return payload


def latest_entry(subscription: FilmJourneySubscription) -> FilmJourneyEntry | None:
    return (
        subscription.entries.select_related("film")
        .order_by("-position", "-id")
        .first()
    )


def serialize_subscription(subscription: FilmJourneySubscription | None) -> dict[str, Any] | None:
    if subscription is None:
        return None
    completed_count = subscription.entries.filter(completed_at__isnull=False).count()
    current = latest_entry(subscription)
    return {
        "id": subscription.id,
        "status": subscription.status,
        "started_at": subscription.started_at.isoformat(),
        "next_delivery_at": subscription.next_delivery_at.isoformat(),
        "last_delivered_at": subscription.last_delivered_at.isoformat()
        if subscription.last_delivered_at
        else None,
        "paused_at": subscription.paused_at.isoformat() if subscription.paused_at else None,
        "pause_reason": subscription.pause_reason,
        "completed_at": subscription.completed_at.isoformat() if subscription.completed_at else None,
        "completed_count": completed_count,
        "total_count": PUBLIC_TOTAL_COUNT,
        "current_entry": serialize_entry(current, include_film=True) if current else None,
    }


def project_status_for_user(user: User | None) -> dict[str, Any]:
    subscription = None
    if user is not None:
        subscription = FilmJourneySubscription.objects.filter(
            project_slug=PROJECT_SLUG,
            user=user,
        ).first()
    return {
        "ok": True,
        "project": PROJECT_SLUG,
        "total_count": PUBLIC_TOTAL_COUNT,
        "landing_images": landing_images_payload(),
        "subscription": serialize_subscription(subscription),
    }


def start_subscription(user: User) -> FilmJourneySubscription:
    now = timezone.now()
    subscription, created = FilmJourneySubscription.objects.get_or_create(
        project_slug=PROJECT_SLUG,
        user=user,
        defaults={
            "status": FilmJourneySubscription.STATUS_ACTIVE,
            "started_at": now,
            "next_delivery_at": now,
        },
    )
    if not created and subscription.status == FilmJourneySubscription.STATUS_PAUSED:
        resume_subscription(subscription)
        subscription.refresh_from_db()
    if (
        subscription.status == FilmJourneySubscription.STATUS_ACTIVE
        and latest_entry(subscription) is None
    ):
        if subscription.next_delivery_at > now:
            subscription.next_delivery_at = now
            subscription.save(update_fields=("next_delivery_at", "updated_at"))
        deliver_next_film(subscription, now=now, force=True)
        subscription.refresh_from_db()
    return subscription


def resume_subscription(subscription: FilmJourneySubscription) -> FilmJourneySubscription:
    if subscription.status == FilmJourneySubscription.STATUS_COMPLETED:
        return subscription
    subscription.status = FilmJourneySubscription.STATUS_ACTIVE
    subscription.paused_at = None
    subscription.pause_reason = ""
    if subscription.next_delivery_at < timezone.now():
        subscription.next_delivery_at = timezone.now()
    subscription.save(update_fields=("status", "paused_at", "pause_reason", "next_delivery_at", "updated_at"))
    return subscription


def _film_for_position(position: int) -> FilmJourneyFilm | None:
    if position < 1:
        return None
    return active_films_queryset()[position - 1 : position].first()


def _notify_entry(entry: FilmJourneyEntry, *, reminder: bool = False) -> None:
    film = entry.film
    if reminder:
        title = "Напоминание: фильм ждёт оценки"
        message = (
            f"Чтобы получить следующий фильм, поставьте оценку к «{film.title}»."
        )
        event_key = REMINDER_EVENT_KEY
    else:
        title = f"Фильм дня: {film.title}"
        message = "Откройте секретную ссылку, посмотрите фильм и вернитесь с оценкой."
        event_key = DAILY_EVENT_KEY
    create_user_notification(
        user=entry.subscription.user,
        event_key=event_key,
        title=title,
        message=message,
        link_url=entry_public_path(entry),
        payload={"entry_id": entry.id, "film_id": film.id, "position": entry.position},
        force_site=True,
        force_telegram=True,
    )


@transaction.atomic
def deliver_next_film(
    subscription: FilmJourneySubscription,
    *,
    now=None,
    force: bool = False,
) -> FilmJourneyEntry | None:
    current_time = now or timezone.now()
    locked = FilmJourneySubscription.objects.select_for_update().get(id=subscription.id)
    if locked.status != FilmJourneySubscription.STATUS_ACTIVE:
        return None
    if locked.next_delivery_at > current_time and not force:
        return None

    current = latest_entry(locked)
    if current and current.completed_at is None:
        return None

    next_position = (current.position + 1) if current else 1
    film = _film_for_position(next_position)
    if film is None:
        locked.status = FilmJourneySubscription.STATUS_COMPLETED
        locked.completed_at = current_time
        locked.save(update_fields=("status", "completed_at", "updated_at"))
        return None

    entry = FilmJourneyEntry.objects.create(
        subscription=locked,
        film=film,
        position=next_position,
        available_at=current_time,
        notification_sent_at=current_time,
    )
    ensure_film_discussion_post(film)
    locked.last_delivered_at = current_time
    locked.next_delivery_at = next_delivery_time(current_time)
    locked.save(update_fields=("last_delivered_at", "next_delivery_at", "updated_at"))
    _notify_entry(entry)
    return entry


def submit_entry_review(entry: FilmJourneyEntry, *, rating: int, comment: str) -> FilmJourneyEntry:
    clean_comment = (comment or "").strip()
    if rating < 1 or rating > 10:
        raise ValueError("Поставьте оценку от 1 до 10.")

    now = timezone.now()
    entry.rating = rating
    entry.comment = clean_comment[:5000]
    entry.completed_at = entry.completed_at or now
    entry.save(update_fields=("rating", "comment", "completed_at", "updated_at"))

    subscription = entry.subscription
    if entry.position >= active_films_count():
        subscription.status = FilmJourneySubscription.STATUS_COMPLETED
        subscription.completed_at = now
        subscription.save(update_fields=("status", "completed_at", "updated_at"))
    elif subscription.status != FilmJourneySubscription.STATUS_COMPLETED:
        subscription.status = FilmJourneySubscription.STATUS_ACTIVE
        subscription.paused_at = None
        subscription.pause_reason = ""
        subscription.next_delivery_at = next_delivery_time(now)
        subscription.save(
            update_fields=(
                "status",
                "paused_at",
                "pause_reason",
                "next_delivery_at",
                "updated_at",
            )
        )
    return entry


def complete_entry_from_discussion_if_ready(entry: FilmJourneyEntry, user: User) -> FilmJourneyEntry:
    from editor.models import PostRatingVote
    from feeds.models import PostComment

    post = ensure_film_discussion_post(entry.film)
    vote = (
        PostRatingVote.objects.filter(
            post=post,
            user=user,
            block_id=DISCUSSION_RATING_BLOCK_ID,
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    comment = (
        PostComment.objects.filter(post=post, user=user, is_deleted=False)
        .order_by("created_at", "id")
        .first()
    )
    if vote is None:
        return entry
    return submit_entry_review(entry, rating=int(vote.value), comment=comment.body if comment else "")


def send_due_deliveries(*, now=None, force: bool = False) -> DeliveryResult:
    current_time = now or timezone.now()
    delivered = 0
    reminders = 0
    paused = 0
    completed = 0

    subscriptions = FilmJourneySubscription.objects.select_related("user").filter(
        project_slug=PROJECT_SLUG,
        status=FilmJourneySubscription.STATUS_ACTIVE,
    )

    for subscription in subscriptions.order_by("next_delivery_at", "id"):
        current = latest_entry(subscription)
        should_force_first_delivery = current is None
        if (
            not force
            and not should_force_first_delivery
            and subscription.next_delivery_at > current_time
        ):
            continue

        entry = deliver_next_film(
            subscription,
            now=current_time,
            force=force or should_force_first_delivery,
        )
        if entry:
            delivered += 1
            continue
        subscription.refresh_from_db()
        current = latest_entry(subscription)
        if not current:
            continue
        if current.completed_at is not None:
            if subscription.status == FilmJourneySubscription.STATUS_COMPLETED:
                completed += 1
            continue
        sent_at = current.notification_sent_at or current.available_at
        age = current_time - sent_at
        if age >= PAUSE_AFTER and current.second_reminder_sent_at is not None:
            subscription.status = FilmJourneySubscription.STATUS_PAUSED
            subscription.paused_at = current_time
            subscription.pause_reason = "Нет оценки после двух напоминаний."
            subscription.save(update_fields=("status", "paused_at", "pause_reason", "updated_at"))
            paused += 1
        elif age >= SECOND_REMINDER_AFTER and current.second_reminder_sent_at is None:
            current.second_reminder_sent_at = current_time
            current.save(update_fields=("second_reminder_sent_at", "updated_at"))
            _notify_entry(current, reminder=True)
            reminders += 1
        elif age >= FIRST_REMINDER_AFTER and current.first_reminder_sent_at is None:
            current.first_reminder_sent_at = current_time
            current.save(update_fields=("first_reminder_sent_at", "updated_at"))
            _notify_entry(current, reminder=True)
            reminders += 1

    return DeliveryResult(
        delivered=delivered,
        reminders=reminders,
        paused=paused,
        completed=completed,
    )


def entry_for_token_and_user(access_token: str, user: User) -> FilmJourneyEntry | None:
    token = (access_token or "").strip()
    if not token:
        return None
    return (
        FilmJourneyEntry.objects.select_related("film", "subscription", "subscription__user")
        .filter(access_token=token, subscription__user=user, subscription__project_slug=PROJECT_SLUG)
        .first()
    )
