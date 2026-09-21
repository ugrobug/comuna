from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from max_integration.client import MaxAPIError, MaxClient


class Command(BaseCommand):
    help = "Check the configured MAX bot without sending messages."

    def handle(self, *args, **options):
        try:
            bot = MaxClient().me()
        except MaxAPIError as exc:
            raise CommandError(str(exc)) from None
        expected = getattr(settings, "MAX_BOT_USERNAME", "").lstrip("@")
        if not bot.get("is_bot") or (expected and bot.get("username") != expected):
            raise CommandError("MAX token belongs to a different bot")
        self.stdout.write(self.style.SUCCESS(f"MAX bot @{bot.get('username')} (ID {bot.get('user_id')}) is available"))
