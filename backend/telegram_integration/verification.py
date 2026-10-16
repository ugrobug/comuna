"""Single-use, time-limited verification with atomic local state changes."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from feeds.models import Author
from telegram_integration.models import BotSession
from users.models import AuthorAdmin, AuthorVerificationCode


class TelegramChannelVerification:
    max_channels = 100

    def consume(self, chat_id, code):
        now = timezone.now()
        with transaction.atomic():
            record = AuthorVerificationCode.objects.select_for_update().filter(
                code__iexact=code, used_at__isnull=True, user__is_active=True,
                created_at__gte=now - timedelta(days=1),
            ).first()
            if record is None:
                return None
            authors = list(Author.objects.filter(admin_chat_id=chat_id, is_blocked=False)
                           .order_by('pk')[:self.max_channels + 1])
            if len(authors) > self.max_channels:
                raise ValueError('Too many channels for one verification')
            BotSession.objects.update_or_create(telegram_user_id=chat_id,
                                               defaults={'verified_user_id': record.user_id})
            for author in authors:
                AuthorAdmin.objects.update_or_create(user=record.user, author=author, defaults={
                    'telegram_user_id': chat_id, 'verified_at': now,
                })
            record.used_at = now
            record.save(update_fields=['used_at'])
            return authors
