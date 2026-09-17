"""Companion invitations: validation, responses and an atomic agreement between two people."""
from __future__ import annotations

import math
from functools import partial

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from editor.models import CompanionResponse, CompanionSearch
from feeds.models import Post, PublicFeedItem
from feeds.post_paths import build_post_public_path
from notifications.service import create_user_notification
from users.chat_service import _serialize_chat_user, get_or_create_chat_for_users
from users.models import SiteChat, SiteChatMessage, SiteChatParticipantState


class CompanionError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize_companion_data(raw):
    from editor.service import _normalize_template_datetime

    source = raw if isinstance(raw, dict) else {}
    starts_at, error = _normalize_template_datetime(source.get("starts_at"))
    if error:
        return {}, "Укажите корректные дату и время встречи."
    if starts_at:
        starts_at = parse_datetime(starts_at).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data = {"description": str(source.get("description") or "").strip(),
            "place": str(source.get("place") or "").strip(), "starts_at": starts_at}
    if len(data["description"]) > 1000 or len(data["place"]) > 255:
        return {}, "Описание — до 1000 символов, название места — до 255."
    for key, minimum, maximum in (("lat", -85, 85), ("lng", -180, 180), ("radius_m", 0, 100000)):
        value = source.get(key)
        if value in (None, ""):
            data[key] = None
            continue
        try:
            if isinstance(value, bool):
                raise ValueError()
            value = float(value)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            return {}, "Проверьте координаты и радиус (от 0 до 100 000 м)."
        data[key] = value
    return data, None


def companion_publish_error(template, *, is_draft=False, publish_at=None):
    if not isinstance(template, dict) or template.get("type") != "companion" or is_draft:
        return None
    data = template.get("data") or {}
    if not data.get("description"):
        return "Кратко опишите, куда вы зовёте спутника."
    if data.get("lat") is None or data.get("lng") is None:
        return "Выберите точку на карте."
    starts = parse_datetime(data.get("starts_at") or "")
    now = timezone.now()
    if not starts or starts <= max(now, publish_at or now):
        return "Время встречи должно быть позже публикации и текущего времени."
    return None


def sync_companion_search(post, user):
    template = (post.raw_data or {}).get("template") or {}
    if template.get("type") == "companion":
        CompanionSearch.objects.get_or_create(post=post, defaults={"organizer": user})
    else:
        CompanionSearch.objects.filter(post=post).delete()


class CompanionService:
    def __init__(self, post, search):
        self.post = post
        self.search = search

    @classmethod
    def load(cls, post_id, user=None, *, lock=False):
        posts = Post.objects.select_related("author")
        if lock:
            posts = posts.select_for_update(of=("self",))
        post = posts.filter(id=post_id, is_blocked=False, is_pending=False, author__is_blocked=False).first()
        if not post or (post.publish_at and post.publish_at > timezone.now()):
            raise CompanionError("Объявление не найдено.", 404)
        search = CompanionSearch.objects.filter(post=post).select_related("organizer", "selected_user").first()
        if not search or (post.raw_data or {}).get("template", {}).get("type") != "companion":
            raise CompanionError("Объявление не найдено.", 404)
        if post.companion_matched_at and (not user or user.id not in (search.organizer_id, search.selected_user_id)):
            raise CompanionError("Объявление не найдено.", 404)
        return cls(post, search)

    @property
    def data(self):
        return self.post.raw_data["template"]["data"]

    def ensure_open(self):
        if self.post.companion_matched_at:
            raise CompanionError("Спутник уже выбран.", 409)
        starts_at = parse_datetime(self.data.get("starts_at") or "")
        if not starts_at or starts_at <= timezone.now():
            raise CompanionError("Встреча уже началась. Приём откликов завершён.", 409)

    def serialize(self, user):
        is_owner = bool(user and user.id == self.search.organizer_id)
        mine = self.search.responses.filter(user=user).first() if user else None
        starts = parse_datetime(self.data.get("starts_at") or "")
        return {
            "is_owner": is_owner,
            "closed": bool(self.post.companion_matched_at),
            "expired": not starts or starts <= timezone.now(),
            "has_responded": bool(mine),
            "chat_id": self.search.chat_id if self.post.companion_matched_at else None,
            "responses": [
                {"id": response.id, "user": _serialize_chat_user(response.user),
                 "message": response.message, "created_at": response.created_at.isoformat()}
                for response in self.search.responses.select_related("user").filter(user__is_active=True)
            ] if is_owner else [],
        }

    @classmethod
    @transaction.atomic
    def respond(cls, post_id, user, message="", *, withdraw=False):
        service = cls.load(post_id, user, lock=True)
        service.ensure_open()
        if user.id == service.search.organizer_id:
            raise CompanionError("Нельзя откликнуться на собственное объявление.")
        message = str(message or "").strip()
        if len(message) > 500:
            raise CompanionError("Сообщение к отклику — не более 500 символов.")
        if withdraw:
            service.search.responses.filter(user=user).delete()
        else:
            response, created = CompanionResponse.objects.get_or_create(
                search=service.search, user=user, defaults={"message": message})
            if created:
                transaction.on_commit(partial(create_user_notification,
                    user=service.search.organizer, event_key="companion_response", title="Новый отклик на поиск спутника",
                    message=f"{user.get_full_name() or user.username} хочет присоединиться: {service.post.title}",
                    link_url=build_post_public_path(service.post.id, service.post.title),
                    payload={"post_id": service.post.id, "response_id": response.id}))
        return service.serialize(user)

    @classmethod
    @transaction.atomic
    def approve(cls, post_id, user, response_id):
        service = cls.load(post_id, user, lock=True)
        if service.search.organizer_id != user.id:
            raise CompanionError("Выбрать спутника может только автор объявления.", 403)
        response = service.search.responses.select_related("user").filter(id=response_id, user__is_active=True).first()
        if not response:
            raise CompanionError("Отклик не найден.", 404)
        if service.post.companion_matched_at and service.search.selected_user_id == response.user_id:
            return service.serialize(user)
        service.ensure_open()
        try:
            chat, _created = get_or_create_chat_for_users(user, response.user)
        except ValueError:
            raise CompanionError("Чат с этим пользователем заблокирован. Выберите другого спутника.", 409)
        now = timezone.now()
        event = {**service.data, "post_id": service.post.id, "title": service.post.title,
                 "confirmed_at": now.isoformat(), "kind": "companion_confirmed"}
        message = SiteChatMessage.objects.create(
            chat=chat, sender=user, delivered_at=now, event=event,
            body="Встреча состоится! Спутник выбран, участие подтверждено. Добавьте встречу в календарь, чтобы не забыть.")
        SiteChat.objects.filter(id=chat.id).update(last_message=message, last_message_at=now, updated_at=now)
        SiteChatParticipantState.objects.filter(chat=chat, is_blocked=False).update(hidden_at=None)
        service.search.selected_user = response.user
        service.search.chat = chat
        service.search.save(update_fields=["selected_user", "chat"])
        service.post.companion_matched_at = now
        service.post.save(update_fields=["companion_matched_at", "updated_at"])
        PublicFeedItem.objects.filter(post=service.post).delete()
        from communities.service import sync_comun_map_points_for_post
        sync_comun_map_points_for_post(service.post)
        for participant in (user, response.user):
            transaction.on_commit(partial(create_user_notification,
                user=participant, event_key="chat_message", title="Встреча подтверждена",
                message=service.post.title, link_url=f"/chats/{chat.id}",
                payload={"chat_id": chat.id, "message_id": message.id, "post_id": service.post.id}))
        return service.serialize(user)
