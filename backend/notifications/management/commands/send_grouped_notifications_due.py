from __future__ import annotations

from django.core.management.base import BaseCommand

from notifications.service import send_due_grouped_notifications


class Command(BaseCommand):
    help = "Send due grouped site notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Maximum number of grouped notifications to deliver in one run.",
        )

    def handle(self, *args, **options):
        sent = send_due_grouped_notifications(limit=int(options.get("limit") or 500))
        self.stdout.write(self.style.SUCCESS(f"grouped notifications: sent={sent}"))
