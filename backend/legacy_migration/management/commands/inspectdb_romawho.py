from __future__ import annotations

from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent.parent / "models.py"


class Command(BaseCommand):
    help = "inspectdb romawho → legacy_migration/models.py"

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--output",
            default=str(DEFAULT_OUTPUT),
            help=f"Путь к файлу (по умолчанию: {DEFAULT_OUTPUT})",
        )
        parser.add_argument("table", nargs="*", help="Только указанные таблицы")

    def handle(self, *args, **options):
        out_path = Path(options["output"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        buffer = StringIO()
        call_command(
            "inspectdb",
            *options["table"],
            database="romawho",
            stdout=buffer,
        )
        header = (
            "# Сгенерировано: python manage.py inspectdb_romawho\n"
            "# Не править вручную — перегенерировать командой.\n\n"
        )
        out_path.write_text(header + buffer.getvalue(), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Записано: {out_path}"))
