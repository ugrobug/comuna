from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from communities import service as community_service
from notifications.models import SiteNotification
from notifications.service import create_user_notification
from users.models import SiteChat, SiteChatMessage

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
    return SiteChat.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related(
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


def get_or_create_chat_for_users(user: User, other_user: User) -> tuple[SiteChat, bool]:
    user_one, user_two = _chat_participants_for(user, other_user)
    return SiteChat.objects.get_or_create(user_one=user_one, user_two=user_two)


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
    "serialize_chat",
    "serialize_chat_messages",
]
