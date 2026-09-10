from __future__ import annotations

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from product_analytics.remote_internal_metrics import load_remote_internal_metrics_config
from product_analytics.weekly_report import build_weekly_report, write_report
from product_analytics.yandex_metrika import MetrikaConfig, YandexMetrikaClient


class Command(BaseCommand):
    help = "Собирает недельный продуктовый отчет Тамбура из Яндекс Метрики"

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Дата запуска в формате YYYY-MM-DD")
        parser.add_argument("--output", help="Путь для JSON-отчета")
        parser.add_argument("--secret-file", help="Путь к локальному JSON с OAuth-конфигурацией")
        parser.add_argument(
            "--stdout",
            dest="print_json",
            action="store_true",
            help="Также вывести JSON в stdout",
        )
        parser.add_argument("--no-git", action="store_true", help="Не добавлять список Git-коммитов")
        parser.add_argument(
            "--no-internal",
            action="store_true",
            help="Не получать продуктовые метрики с production backend по SSH",
        )
        parser.add_argument(
            "--prod-ssh-target",
            help="Production SSH target в формате user@host (по умолчанию TAMBUR_PROD_SSH_TARGET)",
        )
        parser.add_argument(
            "--prod-ssh-identity-file",
            help="Приватный SSH-ключ (по умолчанию TAMBUR_PROD_SSH_IDENTITY_FILE)",
        )
        parser.add_argument(
            "--analytics-api-url",
            help="Base URL read-only Analytics API (по умолчанию TAMBUR_ANALYTICS_API_BASE_URL)",
        )
        parser.add_argument(
            "--analytics-api-token-file",
            help="Файл с API-токеном (по умолчанию TAMBUR_ANALYTICS_API_TOKEN_FILE)",
        )

    def handle(self, *args, **options):
        try:
            as_of = date.fromisoformat(options["date"]) if options.get("date") else None
        except ValueError as exc:
            raise CommandError("--date должен быть в формате YYYY-MM-DD") from exc

        try:
            config = MetrikaConfig.load(options.get("secret_file"))
            internal_config = None
            if not options["no_internal"] and any(
                options.get(value)
                for value in (
                    "analytics_api_url",
                    "analytics_api_token_file",
                    "prod_ssh_target",
                    "prod_ssh_identity_file",
                )
            ):
                internal_config = load_remote_internal_metrics_config(
                    api_base_url=options.get("analytics_api_url"),
                    api_token_file=options.get("analytics_api_token_file"),
                    ssh_target=options.get("prod_ssh_target"),
                    ssh_identity_file=options.get("prod_ssh_identity_file"),
                )
            report = build_weekly_report(
                YandexMetrikaClient(config),
                as_of=as_of,
                include_git=not options["no_git"],
                include_internal=not options["no_internal"],
                internal_config=internal_config,
            )
            path = write_report(report, options.get("output"))
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Отчет сохранен: {path}"))
        if options["print_json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
