import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from max_integration.bot import MaxBot
from max_integration.models import MaxUpdate, MaxNotificationDelivery


class Command(BaseCommand):
    help = 'Process queued MAX webhooks and notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        bot = MaxBot()
        while True:
            worked = self.process_update(bot) | self.process_notification(bot)
            if not options['loop']:
                break
            if not worked:
                time.sleep(1)

    def process_update(self, bot):
        with transaction.atomic():
            event = MaxUpdate.objects.select_for_update(skip_locked=True).filter(processed_at__isnull=True, attempts__lt=18, available_at__lte=timezone.now()).order_by('id').first()
            if not event:
                return False
            event.attempts += 1
            try:
                with transaction.atomic():
                    bot.handle(event.payload)
            except Exception as exc:
                event.last_error = type(exc).__name__
                event.available_at = timezone.now() + timedelta(seconds=min(300, 2 ** event.attempts))
            else:
                event.processed_at = timezone.now()
                event.last_error = ''
            event.save(update_fields=['attempts', 'last_error', 'available_at', 'processed_at'])
        return True

    def process_notification(self, bot):
        with transaction.atomic():
            item = MaxNotificationDelivery.objects.select_for_update(skip_locked=True).select_related('account__user', 'notification').filter(sent_at__isnull=True, attempts__lt=18, available_at__lte=timezone.now()).order_by('id').first()
            if not item:
                return False
            from notifications.service import _notification_preference_key
            if not item.account.is_active or not item.account.user.is_active or _notification_preference_key(item.notification.event_key) not in item.account.notification_events:
                item.delete()
                return True
            item.attempts += 1
            try:
                n = item.notification
                text = '\n\n'.join(v for v in [n.title, n.message] if v)
                buttons = None
                if n.link_url:
                    url = n.link_url if n.link_url.startswith('https://') else 'https://tambur.pub/' + n.link_url.lstrip('/')
                    buttons = [[{'type': 'link', 'text': 'Открыть в Тамбуре', 'url': url}]]
                bot.client.send(item.account.dialog_id, text, buttons)
            except Exception as exc:
                item.last_error = type(exc).__name__
                item.available_at = timezone.now()+timedelta(seconds=min(300, 2 ** item.attempts))
            else:
                item.sent_at = timezone.now()
                item.last_error = ''
            item.save(update_fields=['attempts', 'sent_at', 'available_at', 'last_error'])
        return True
