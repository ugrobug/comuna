from django.core.management.base import BaseCommand

from notifications.event_reminders import send_event_reminders_due


class Command(BaseCommand):
    help = "Send reminders for upcoming post events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        sent = send_event_reminders_due(limit=int(options.get("limit") or 500))
        self.stdout.write(self.style.SUCCESS(f"event reminders: sent={sent}"))
