from __future__ import annotations

from django.core.management.base import BaseCommand

from special_projects.public_book import send_due_reminders


class Command(BaseCommand):
    help = "Send due public book Telegram reminders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Maximum number of reminders to send in one run.",
        )

    def handle(self, *args, **options):
        sent = send_due_reminders(limit=int(options.get("limit") or 500))
        self.stdout.write(self.style.SUCCESS(f"public book reminders: sent={sent}"))
