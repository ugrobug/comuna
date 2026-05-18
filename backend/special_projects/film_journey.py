from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from notifications.service import create_user_notification
from special_projects.models import (
    FilmJourneyEntry,
    FilmJourneyFilm,
    FilmJourneySubscription,
)

User = get_user_model()

PROJECT_SLUG = FilmJourneyFilm.PROJECT_SLUG
DAILY_EVENT_KEY = "film_journey_daily"
REMINDER_EVENT_KEY = "film_journey_reminder"
FIRST_REMINDER_AFTER = timedelta(days=2)
SECOND_REMINDER_AFTER = timedelta(days=5)
PAUSE_AFTER = timedelta(days=8)


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
    return value + timedelta(days=1)


def active_films_queryset():
    return FilmJourneyFilm.objects.filter(project_slug=PROJECT_SLUG, is_active=True).order_by(
        "sort_order", "id"
    )


def active_films_count() -> int:
    return active_films_queryset().count()


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


def entry_public_path(entry: FilmJourneyEntry) -> str:
    return f"/s/1001-films/watch/{entry.access_token}"


def entry_absolute_url(entry: FilmJourneyEntry) -> str:
    return _site_url(entry_public_path(entry))


def serialize_entry(entry: FilmJourneyEntry, *, include_film: bool = True) -> dict[str, Any]:
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
    total = active_films_count()
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
        "total_count": total,
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
        "total_count": active_films_count(),
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
            "next_delivery_at": next_delivery_time(now),
        },
    )
    if not created and subscription.status == FilmJourneySubscription.STATUS_PAUSED:
        resume_subscription(subscription)
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
            f"Чтобы получить следующий фильм, поставьте оценку и оставьте комментарий к «{film.title}»."
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
    locked.last_delivered_at = current_time
    locked.save(update_fields=("last_delivered_at", "updated_at"))
    _notify_entry(entry)
    return entry


def submit_entry_review(entry: FilmJourneyEntry, *, rating: int, comment: str) -> FilmJourneyEntry:
    clean_comment = (comment or "").strip()
    if rating < 1 or rating > 10:
        raise ValueError("Поставьте оценку от 1 до 10.")
    if len(clean_comment) < 3:
        raise ValueError("Оставьте комментарий к фильму.")

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
    if not force:
        subscriptions = subscriptions.filter(next_delivery_at__lte=current_time)

    for subscription in subscriptions.order_by("next_delivery_at", "id"):
        entry = deliver_next_film(subscription, now=current_time, force=force)
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
            subscription.pause_reason = "Нет оценки и комментария после двух напоминаний."
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
