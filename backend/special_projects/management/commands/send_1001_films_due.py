from __future__ import annotations

from django.core.management.base import BaseCommand

from special_projects.film_journey import send_due_deliveries


class Command(BaseCommand):
    help = "Send due 365 films project notifications and reminders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore next_delivery_at when selecting active subscriptions.",
        )

    def handle(self, *args, **options):
        result = send_due_deliveries(force=bool(options.get("force")))
        self.stdout.write(
            self.style.SUCCESS(
                "365 films: "
                f"delivered={result.delivered}, "
                f"reminders={result.reminders}, "
                f"paused={result.paused}, "
                f"completed={result.completed}"
            )
        )
