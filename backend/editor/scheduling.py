"""Scheduling for posts submitted from the editor (draft dates do not arm publication)."""
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def parse_publish_at(value, *, require_future=True):
    if value is None or value == "":
        return None
    try:
        date = parse_datetime(value) if isinstance(value, str) else None
    except (ValueError, TypeError):
        date = None
    if date is None or timezone.is_naive(date):
        raise ValueError("Укажите дату и время публикации с часовым поясом.")
    if require_future and date <= timezone.now():
        raise ValueError("Дата публикации должна быть в будущем.")
    return date


def is_scheduled(post):
    return bool((post.raw_data or {}).get("scheduled_publication"))


def set_schedule_state(raw_data, *, publish_at, is_draft, actor_id):
    raw_data = dict(raw_data or {})
    if publish_at is not None and not is_draft:
        raw_data["scheduled_publication"] = True
        raw_data["scheduled_by_user_id"] = actor_id
    else:
        raw_data.pop("scheduled_publication", None)
        raw_data.pop("scheduled_by_user_id", None)
    return raw_data
