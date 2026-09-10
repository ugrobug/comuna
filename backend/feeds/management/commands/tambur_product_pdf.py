from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from product_analytics.pdf_report import build_pdf, load_json


class Command(BaseCommand):
    help = "Создаёт PDF по JSON-отчёту продуктовой аналитики Тамбура"

    def add_arguments(self, parser):
        parser.add_argument("--report", required=True, help="Путь к JSON-отчёту Метрики")
        parser.add_argument("--analysis", required=True, help="Путь к JSON с выводами и гипотезами")
        parser.add_argument("--output", help="Итоговый путь PDF")

    def handle(self, *args, **options):
        report_path = Path(options["report"])
        analysis_path = Path(options["analysis"])
        try:
            output = build_pdf(
                load_json(report_path),
                load_json(analysis_path),
                options.get("output"),
            )
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            raise CommandError(f"Не удалось создать PDF: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"PDF сохранён: {output}"))
