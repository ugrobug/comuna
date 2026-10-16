"""Consent transitions and retryable delivery of their result are separate operations."""
from dataclasses import dataclass
from datetime import timedelta
import secrets
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.db import transaction
from django.utils import timezone

from feeds.models import Post
from telegram_integration.models import TelegramApprovalDelivery

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModerationResult:
    text: str
    post: Post | None = None
    changed: bool = False


class TelegramPostModeration:
    """One locked post, its current administrator, and an idempotent decision."""

    def decide(self, post_id, *, actor_id, chat_id, approve):
        if not actor_id or actor_id != chat_id:
            return ModerationResult("Нет доступа к согласованию")
        with transaction.atomic():
            post = (Post.objects.select_for_update(of=("self",)).select_related("author")
                    .filter(pk=post_id, author__admin_chat_id=actor_id, message_id__gt=0).first())
            if post is None:
                return ModerationResult("Пост не найден или нет доступа")
            if post.is_blocked or post.author.is_blocked:
                return ModerationResult("Пост отклонён или заблокирован", post)
            if not post.is_pending:
                return ModerationResult(self.published_text(post), post)
            post.is_pending = False
            post.is_blocked = not approve
            post.raw_data = dict(post.raw_data or {})
            post.raw_data["telegram_moderation"] = {
                "state": "approved" if approve else "rejected",
                "actor_id": actor_id,
                "decided_at": timezone.now().isoformat(),
            }
            # Language was detected on import; approval must not delete translations.
            post.save(update_fields=["is_pending", "is_blocked", "raw_data", "updated_at"])
            return ModerationResult(self.published_text(post) if approve else "Пост отклонён", post, True)

    @staticmethod
    def published_text(post):
        if post.publish_at and post.publish_at > timezone.now():
            return "Публикация согласована; ожидает установленного времени"
        return "Пост опубликован"


class TelegramModerationReceiptUnavailable(RuntimeError):
    pass


class TelegramApprovalPrompt:
    """One durable delivery per pending post; bounded retries never block import."""
    max_attempts = 8
    lease_seconds = 30

    def __init__(self, send):
        self.send = send

    def deliver(self, post, author):
        if not post.is_pending or post.is_blocked or not author.admin_chat_id:
            return
        delivery, _ = TelegramApprovalDelivery.objects.get_or_create(
            post=post, defaults={'chat_id': author.admin_chat_id})
        self._attempt(delivery.pk)

    def drain(self, limit=2):
        ids = list(TelegramApprovalDelivery.objects.filter(
            sent_at__isnull=True, failed_at__isnull=True, next_attempt_at__lte=timezone.now(),
        ).order_by('next_attempt_at', 'pk').values_list('pk', flat=True)[:max(1, min(limit, 20))])
        for delivery_id in ids:
            self._attempt(delivery_id)
        return len(ids)

    def _attempt(self, delivery_id):
        now = timezone.now()
        with transaction.atomic():
            delivery = (TelegramApprovalDelivery.objects.select_for_update(of=('self',))
                        .select_related('post__author').get(pk=delivery_id))
            if delivery.sent_at or delivery.failed_at or delivery.next_attempt_at > now:
                return
            post, author = delivery.post, delivery.post.author
            if not post.is_pending or post.is_blocked or author.is_blocked or not author.admin_chat_id:
                delivery.failed_at = now
                delivery.save(update_fields=['failed_at'])
                return
            lease = secrets.token_hex(16)
            delivery.chat_id = author.admin_chat_id
            delivery.attempts += 1
            delivery.lease_token = lease
            delivery.next_attempt_at = now + timedelta(seconds=self.lease_seconds)
            delivery.save(update_fields=['chat_id', 'attempts', 'lease_token', 'next_attempt_at'])
        # No database lock survives into a Telegram request.
        try:
            response = self.send(delivery.chat_id,
                f'Новый пост из канала @{author.username}:\n{post.title}\n\nОпубликуем?',
                {'inline_keyboard': [[
                    {'text': 'Публикуем', 'callback_data': f'approve:{post.pk}'},
                    {'text': 'Этот пропустим', 'callback_data': f'reject:{post.pk}'},
                ]]})
        except (OSError, ValueError):
            response = None
        result = response.get('result') if isinstance(response, dict) and response.get('ok') else None
        sent = isinstance(result, dict) and isinstance(result.get('message_id'), int)
        update = {'lease_token': ''}
        if sent:
            update.update(sent_at=timezone.now(), message_id=result['message_id'])
        elif delivery.attempts >= self.max_attempts:
            update['failed_at'] = timezone.now()
            logger.error('Telegram approval delivery exhausted retries (delivery_id=%s)', delivery.pk)
        else:
            update['next_attempt_at'] = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** (delivery.attempts - 1)))
            logger.warning('Telegram approval delivery scheduled for retry (delivery_id=%s)', delivery.pk)
        TelegramApprovalDelivery.objects.filter(pk=delivery.pk, lease_token=lease).update(**update)


class TelegramModerationReceipt:
    """Edit the same prompt, so retries cannot create duplicate result messages."""

    def __init__(self, token, site_url, *, opener=urllib.request.urlopen):
        self.token = token
        self.site_url = site_url.rstrip("/")
        self.opener = opener

    def deliver(self, result, *, chat_id, message_id):
        if not result.post or not message_id:
            return
        payload = {
            "chat_id": chat_id, "message_id": message_id,
            "text": f"{result.text}.\n{self.site_url}/b/post/{result.post.pk}",
            "reply_markup": json.dumps({"inline_keyboard": []}),
        }
        try:
            with self.opener(
                f"https://api.telegram.org/bot{self.token}/editMessageText",
                data=urllib.parse.urlencode(payload).encode(), timeout=5,
            ) as response:
                body = json.load(response)
        except urllib.error.HTTPError as error:
            try:
                body = json.loads(error.read())
            except (ValueError, OSError):
                raise TelegramModerationReceiptUnavailable("Invalid receipt response") from None
        except (OSError, ValueError):
            raise TelegramModerationReceiptUnavailable("Receipt delivery unavailable") from None
        if isinstance(body, dict):
            description = str(body.get("description") or "").lower()
            if body.get("ok") or "message is not modified" in description:
                return
            if body.get("error_code") in {400, 403} and any(reason in description for reason in (
                "message to edit not found", "message can't be edited", "bot was blocked by the user",
                "chat not found", "user is deactivated",
            )):
                logger.warning("Telegram moderation receipt destination unavailable")
                return
        raise TelegramModerationReceiptUnavailable("Receipt delivery failed")
