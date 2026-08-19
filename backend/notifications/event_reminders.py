from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from feeds.models import PostEventAttendance
from feeds.post_paths import build_post_public_path
from notifications.service import create_user_notification


def send_event_reminders_due(*, limit: int = 500) -> int:
    now = timezone.now()
    reminder_boundary = now + timedelta(days=1)
    due_ids = list(
        PostEventAttendance.objects.filter(
            reminder_sent_at__isnull=True,
            post__event_starts_at__gt=now,
            post__event_starts_at__lte=reminder_boundary,
            post__is_blocked=False,
            post__is_pending=False,
            post__author__is_blocked=False,
        )
        .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
        .order_by("post__event_starts_at", "id")
        .values_list("id", flat=True)[: max(int(limit), 1)]
    )

    sent = 0
    for attendance_id in due_ids:
        with transaction.atomic():
            attendance = (
                PostEventAttendance.objects.select_for_update()
                .select_related("user", "post")
                .filter(id=attendance_id, reminder_sent_at__isnull=True)
                .first()
            )
            if not attendance:
                continue
            post = attendance.post
            if not post.event_starts_at or post.event_starts_at <= timezone.now():
                continue

            starts_at_local = timezone.localtime(post.event_starts_at)
            post_path = build_post_public_path(post.id, post.title)
            if post.original_language and post.original_language != "ru":
                post_path = f"/{post.original_language}{post_path}"
            create_user_notification(
                user=attendance.user,
                event_key="event_reminder",
                title="Событие начнется через сутки",
                message=f"{post.title} - {starts_at_local:%d.%m.%Y %H:%M}",
                link_url=post_path,
                payload={
                    "post_id": post.id,
                    "starts_at": post.event_starts_at.isoformat(),
                },
            )
            attendance.reminder_sent_at = timezone.now()
            attendance.save(update_fields=["reminder_sent_at", "updated_at"])
            sent += 1
    return sent
