from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from max_integration.client import MaxClient, MaxAPIError


class Command(BaseCommand):
    help = 'Register the MAX webhook after deploying its HTTPS endpoint.'

    def handle(self, *args, **options):
        secret = getattr(settings, 'MAX_WEBHOOK_SECRET', '')
        base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
        if not base.startswith('https://') or len(secret) < 24:
            raise CommandError('Set HTTPS SITE_BASE_URL and a random MAX_WEBHOOK_SECRET of at least 24 characters')
        client = MaxClient()
        try:
            bot = client.me()
            if bot.get('username') != settings.MAX_BOT_USERNAME or not bot.get('is_bot'):
                raise CommandError('Token does not match MAX_BOT_USERNAME')
            client.subscribe(base + '/api/max/webhook/', secret)
        except MaxAPIError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS('MAX webhook registered'))
