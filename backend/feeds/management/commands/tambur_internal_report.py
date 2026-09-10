from __future__ import annotations

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from product_analytics.internal_metrics import (
    build_internal_product_report,
    write_internal_report,
)
from product_analytics.weekly_report import completed_week


class Command(BaseCommand):
    help = "Собирает метрики из БД текущего backend (для weekly-агента запускать на production)"

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Дата запуска в формате YYYY-MM-DD")
        parser.add_argument("--output", help="Путь для JSON-отчета")
        parser.add_argument(
            "--stdout",
            dest="print_json",
            action="store_true",
            help="Также вывести JSON в stdout",
        )

    def handle(self, *args, **options):
        try:
            as_of = date.fromisoformat(options["date"]) if options.get("date") else None
        except ValueError as exc:
            raise CommandError("--date должен быть в формате YYYY-MM-DD") from exc

        periods = [completed_week(as_of, offset) for offset in range(14)]
        report = build_internal_product_report(periods)
        path = write_internal_report(report, options.get("output"))
        self.stdout.write(self.style.SUCCESS(f"Внутренний отчет сохранен: {path}"))
        if options["print_json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
