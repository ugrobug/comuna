from django.core.management.base import BaseCommand

from telegram_integration.bot import _send_bot_message_with_keyboard
from telegram_integration.moderation import TelegramApprovalPrompt


class Command(BaseCommand):
    help = 'Deliver a bounded due batch of Telegram approval prompts (also drained by polling).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=2)

    def handle(self, *args, **options):
        count = TelegramApprovalPrompt(_send_bot_message_with_keyboard).drain(limit=options['limit'])
        self.stdout.write(f'Processed {count} due deliveries')
