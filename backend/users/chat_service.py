from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from communities import service as community_service
from notifications.models import SiteNotification
from notifications.service import create_user_notification
from users.models import SiteChat, SiteChatMessage, SiteChatParticipantState, SiteChatReport

User = get_user_model()

CHAT_MESSAGE_MAX_LENGTH = 5000
CHAT_LIST_LIMIT_MAX = 100
CHAT_MESSAGES_LIMIT_MAX = 100


def _site_user_display_name(user: User) -> str:
    try:
        display_name = (getattr(user.site_profile, "display_name", "") or "").strip()
    except Exception:
        display_name = ""
    full_name = " ".join(
        part
        for part in (
            (getattr(user, "first_name", "") or "").strip(),
            (getattr(user, "last_name", "") or "").strip(),
        )
        if part
    ).strip()
    return display_name or full_name or (getattr(user, "username", "") or "").strip() or "user"


def _serialize_chat_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": (getattr(user, "username", "") or "").strip(),
        "display_name": _site_user_display_name(user),
        "avatar_url": community_service._site_user_avatar_url(None, user),
        "profile_url": f"/id{user.id}",
    }


def _chat_participants_for(user: User, other_user: User) -> tuple[User, User]:
    if not user or not other_user or user.id == other_user.id:
        raise ValueError("invalid participant")
    if not other_user.is_active:
        raise ValueError("participant not found")
    return (user, other_user) if user.id < other_user.id else (other_user, user)


def _chat_other_user(chat: SiteChat, user: User) -> User:
    if chat.user_one_id == user.id:
        return chat.user_two
    if chat.user_two_id == user.id:
        return chat.user_one
    raise ValueError("chat not found")


def _chat_queryset_for_user(user: User):
    hidden_chat_ids = SiteChatParticipantState.objects.filter(
        user=user,
        hidden_at__isnull=False,
    ).values("chat_id")
    return SiteChat.objects.filter(Q(user_one=user) | Q(user_two=user)).exclude(
        id__in=hidden_chat_ids
    ).select_related(
        "user_one",
        "user_one__site_profile",
        "user_one__telegram_account",
        "user_one__vk_account",
        "user_two",
        "user_two__site_profile",
        "user_two__telegram_account",
        "user_two__vk_account",
        "last_message",
        "last_message__sender",
        "last_message__sender__site_profile",
        "last_message__sender__telegram_account",
        "last_message__sender__vk_account",
    )


def _chat_has_block(chat: SiteChat) -> bool:
    return SiteChatParticipantState.objects.filter(chat=chat, is_blocked=True).exists()


def get_or_create_chat_for_users(user: User, other_user: User) -> tuple[SiteChat, bool]:
    user_one, user_two = _chat_participants_for(user, other_user)
    chat, created = SiteChat.objects.get_or_create(user_one=user_one, user_two=user_two)
    if not created and _chat_has_block(chat):
        raise ValueError("chat is blocked")
    return chat, created


def get_or_create_chat_with_user_id(user: User, participant_id: int) -> tuple[SiteChat, bool]:
    try:
        participant_id = int(participant_id)
    except (TypeError, ValueError):
        raise ValueError("invalid participant") from None
    participant = User.objects.filter(id=participant_id, is_active=True).first()
    if not participant:
        raise ValueError("participant not found")
    return get_or_create_chat_for_users(user, participant)


def _unread_counts_by_chat(user: User, chat_ids: list[int]) -> dict[int, int]:
    if not chat_ids:
        return {}
    return {
        int(item["chat_id"]): int(item["total"])
        for item in (
            SiteChatMessage.objects.filter(
                chat_id__in=chat_ids,
                read_at__isnull=True,
            )
            .exclude(sender=user)
            .values("chat_id")
            .annotate(total=Count("id"))
        )
    }


def _serialize_chat_message(message: SiteChatMessage) -> dict:
    sender = message.sender
    return {
        "id": message.id,
        "chat_id": message.chat_id,
        "sender": _serialize_chat_user(sender),
        "sender_id": message.sender_id,
        "body": message.body,
        "read_at": message.read_at.isoformat() if message.read_at else None,
        "created_at": message.created_at.isoformat(),
        "updated_at": message.updated_at.isoformat(),
    }


def serialize_chat(
    chat: SiteChat,
    user: User,
    *,
    last_message: SiteChatMessage | None = None,
    unread_count: int = 0,
) -> dict:
    other_user = _chat_other_user(chat, user)
    return {
        "id": chat.id,
        "participant": _serialize_chat_user(other_user),
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
        "last_message_at": chat.last_message_at.isoformat() if chat.last_message_at else None,
        "last_message": _serialize_chat_message(last_message) if last_message else None,
        "unread_count": int(unread_count or 0),
    }


def list_chats_for_user(user: User, *, limit: int = 50, offset: int = 0) -> tuple[list[SiteChat], dict]:
    limit = min(max(int(limit or 50), 1), CHAT_LIST_LIMIT_MAX)
    offset = max(int(offset or 0), 0)
    queryset = _chat_queryset_for_user(user).order_by("-last_message_at", "-updated_at", "-id")
    total = queryset.count()
    chats = list(queryset[offset : offset + limit])
    chat_ids = [chat.id for chat in chats]
    last_messages = {
        chat.id: chat.last_message
        for chat in chats
        if chat.last_message_id and chat.last_message
    }
    unread_counts = _unread_counts_by_chat(user, chat_ids)
    return chats, {
        "total": total,
        "limit": limit,
        "offset": offset,
        "last_messages": last_messages,
        "unread_counts": unread_counts,
    }


def list_messages_for_chat(
    chat: SiteChat,
    user: User,
    *,
    limit: int = 50,
    before_id: int | None = None,
) -> list[SiteChatMessage]:
    _chat_other_user(chat, user)
    limit = min(max(int(limit or 50), 1), CHAT_MESSAGES_LIMIT_MAX)
    queryset = SiteChatMessage.objects.filter(chat=chat).select_related(
        "sender",
        "sender__site_profile",
        "sender__telegram_account",
        "sender__vk_account",
    )
    if before_id:
        queryset = queryset.filter(id__lt=before_id)
    messages = list(queryset.order_by("-created_at", "-id")[:limit])
    messages.reverse()
    return messages


def mark_chat_read_for_user(chat: SiteChat, user: User) -> int:
    _chat_other_user(chat, user)
    now = timezone.now()
    return SiteChatMessage.objects.filter(
        chat=chat,
        read_at__isnull=True,
    ).exclude(sender=user).update(read_at=now, updated_at=now)


def mark_chat_notifications_read_for_user(chat: SiteChat, user: User) -> int:
    _chat_other_user(chat, user)
    now = timezone.now()
    return SiteNotification.objects.filter(
        user=user,
        is_site=True,
        read_at__isnull=True,
        event_key__in=("new_chat", "chat_message"),
        payload__chat_id=chat.id,
    ).update(read_at=now, updated_at=now)


def get_chat_for_user(user: User, chat_id: int) -> SiteChat | None:
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return None
    return _chat_queryset_for_user(user).filter(id=chat_id).first()


def create_chat_message(chat: SiteChat, sender: User, body: str) -> SiteChatMessage:
    _chat_other_user(chat, sender)
    normalized_body = str(body or "").strip()
    if not normalized_body:
        raise ValueError("message is empty")
    if len(normalized_body) > CHAT_MESSAGE_MAX_LENGTH:
        raise ValueError("message is too long")
    if _chat_has_block(chat):
        raise ValueError("chat is blocked")

    recipient = _chat_other_user(chat, sender)
    sender_name = _site_user_display_name(sender)

    with transaction.atomic():
        had_messages = SiteChatMessage.objects.filter(chat=chat).exists()
        message = SiteChatMessage.objects.create(
            chat=chat,
            sender=sender,
            body=normalized_body,
        )
        SiteChat.objects.filter(id=chat.id).update(
            last_message_id=message.id,
            last_message_at=message.created_at,
            updated_at=message.created_at,
        )

    event_key = "chat_message" if had_messages else "new_chat"
    title = "Новое сообщение в чате" if had_messages else "Новый чат"
    preview = normalized_body.replace("\n", " ")
    if len(preview) > 180:
        preview = f"{preview[:180].rstrip()}..."
    create_user_notification(
        user=recipient,
        event_key=event_key,
        title=title,
        message=f"{sender_name}: {preview}",
        link_url=f"/chats/{chat.id}",
        payload={
            "chat_id": chat.id,
            "message_id": message.id,
            "sender_id": sender.id,
            "sender_name": sender_name,
        },
    )
    return message


def _latest_reportable_message(chat: SiteChat, reported_user: User) -> SiteChatMessage | None:
    return (
        SiteChatMessage.objects.filter(chat=chat, sender=reported_user)
        .select_related(
            "sender",
            "sender__site_profile",
            "sender__telegram_account",
            "sender__vk_account",
        )
        .order_by("-created_at", "-id")
        .first()
    )


def report_and_block_chat(chat: SiteChat, user: User) -> SiteChatReport:
    reported_user = _chat_other_user(chat, user)
    reported_message = _latest_reportable_message(chat, reported_user)
    message_snapshot = (reported_message.body if reported_message else "").strip()
    now = timezone.now()

    with transaction.atomic():
        state, _created = SiteChatParticipantState.objects.select_for_update().get_or_create(
            chat=chat,
            user=user,
            defaults={
                "is_blocked": True,
                "hidden_at": now,
                "blocked_at": now,
            },
        )
        state.is_blocked = True
        state.hidden_at = state.hidden_at or now
        state.blocked_at = state.blocked_at or now
        state.save(update_fields=["is_blocked", "hidden_at", "blocked_at", "updated_at"])
        mark_chat_read_for_user(chat, user)
        mark_chat_notifications_read_for_user(chat, user)
        report = SiteChatReport.objects.create(
            chat=chat,
            reporter=user,
            reported_user=reported_user,
            message=reported_message,
            message_body_snapshot=message_snapshot,
        )

    return report


def serialize_chat_report(report: SiteChatReport) -> dict:
    message = report.message
    body = (report.message_body_snapshot or (message.body if message else "") or "").strip()
    return {
        "id": report.id,
        "chat_id": report.chat_id,
        "status": report.status,
        "status_label": report.get_status_display(),
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
        "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
        "reporter": _serialize_chat_user(report.reporter),
        "reported_user": _serialize_chat_user(report.reported_user),
        "reviewed_by": _serialize_chat_user(report.reviewed_by) if report.reviewed_by else None,
        "message": {
            "id": message.id if message else None,
            "sender_id": message.sender_id if message else report.reported_user_id,
            "body": body,
            "created_at": message.created_at.isoformat() if message else None,
        },
    }


def set_chat_report_status(report: SiteChatReport, moderator: User, status: str) -> SiteChatReport:
    valid_statuses = {choice[0] for choice in SiteChatReport.STATUS_CHOICES}
    if status not in valid_statuses:
        raise ValueError("invalid status")

    report.status = status
    if status == SiteChatReport.STATUS_OPEN:
        report.reviewed_at = None
        report.reviewed_by = None
    else:
        report.reviewed_at = timezone.now()
        report.reviewed_by = moderator
    report.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"])
    return report


def serialize_chat_messages(messages: list[SiteChatMessage]) -> list[dict]:
    return [_serialize_chat_message(message) for message in messages]


__all__ = [
    "create_chat_message",
    "get_chat_for_user",
    "get_or_create_chat_with_user_id",
    "list_chats_for_user",
    "list_messages_for_chat",
    "mark_chat_notifications_read_for_user",
    "mark_chat_read_for_user",
    "report_and_block_chat",
    "serialize_chat",
    "serialize_chat_report",
    "serialize_chat_messages",
    "set_chat_report_status",
]
