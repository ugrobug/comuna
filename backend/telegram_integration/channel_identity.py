"""Resolve a Telegram source by its immutable chat ID, never transfer ownership by name."""
import logging

from django.db import transaction

from feeds.models import Author

logger = logging.getLogger(__name__)


class TelegramChannelIdentity:
    def resolve(self, chat):
        username = str(chat.get('username') or '').strip()
        chat_id = chat.get('id')
        if not username:
            return None  # Only public channels are supported by the website contract.
        if chat_id:
            matches = list(Author.objects.filter(channel_id=chat_id).order_by('pk')[:2])
            if len(matches) > 1:
                # Legacy sources can share a chat ID. Preserve an exact established
                # route, otherwise use only a single linked community, never "first".
                exact = list(Author.objects.filter(channel_id=chat_id, username__iexact=username)[:2])
                if len(exact) == 1:
                    return exact[0]
                linked = list(Author.objects.filter(channel_id=chat_id, telegram_source_comun__isnull=False)[:2])
                if len(linked) == 1:
                    return linked[0]
                logger.error('Ambiguous Telegram channel identity; import refused')
                return None
            if matches:
                # Keep the website author's URL stable when Telegram is renamed.
                return matches[0]
        with transaction.atomic():
            author = Author.objects.select_for_update().filter(username__iexact=username).first()
            if author:
                if chat_id and author.channel_id not in (None, chat_id):
                    logger.error('Telegram username belongs to a different stored chat; import refused')
                    return None
                if chat_id and not author.channel_id:
                    author.channel_id = chat_id
                    author.save(update_fields=['channel_id', 'updated_at'])
                return author
            author, _ = Author.objects.get_or_create(username=username, defaults={
                'channel_id': chat_id, 'title': chat.get('title', ''),
                'channel_url': f'https://t.me/{username}',
            })
            if chat_id and author.channel_id != chat_id:
                return None
            return author
