from __future__ import annotations

from urllib.parse import urlencode

from django.core.management.base import BaseCommand, CommandError

from product_analytics.yandex_metrika import (
    AUTHORIZE_URL,
    MetrikaConfig,
    exchange_authorization_code,
)


class Command(BaseCommand):
    help = "Авторизует read-only доступ к Яндекс Метрике и безопасно сохраняет токены"

    def add_arguments(self, parser):
        parser.add_argument("--code", help="Код подтверждения со страницы Яндекс OAuth")
        parser.add_argument("--secret-file", help="Путь к локальному JSON с OAuth-конфигурацией")

    def handle(self, *args, **options):
        config = MetrikaConfig.load(options.get("secret_file"))
        try:
            config.require_oauth_application()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        code = (options.get("code") or "").strip()
        if not code:
            query = urlencode(
                {
                    "response_type": "code",
                    "client_id": config.client_id,
                    "redirect_uri": config.redirect_uri,
                    "scope": "metrika:read",
                    "force_confirm": "yes",
                }
            )
            self.stdout.write("Откройте ссылку, подтвердите доступ и повторите команду с --code:")
            self.stdout.write(f"{AUTHORIZE_URL}?{query}")
            return

        try:
            updated = exchange_authorization_code(config, code)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Авторизация сохранена в {updated.secret_file}. Сам токен не выводился."
            )
        )
