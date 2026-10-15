"""Consent transitions and retryable delivery of their result are separate operations."""
from dataclasses import dataclass
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.db import transaction
from django.utils import timezone

from feeds.models import Post

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
