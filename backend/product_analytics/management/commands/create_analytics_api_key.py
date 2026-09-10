from __future__ import annotations

import ipaddress

from django.core.management.base import BaseCommand, CommandError

from communities.models import Comun
from product_analytics.models import (
    AnalyticsApiCredential,
    SCOPE_COMMUNITY_ANALYTICS,
    SCOPE_SITE_ANALYTICS,
)


SCOPE_ALIASES = {
    "site": SCOPE_SITE_ANALYTICS,
    "communities": SCOPE_COMMUNITY_ANALYTICS,
}


class Command(BaseCommand):
    help = "Создает отзываемый read-only ключ для API продуктовой аналитики"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Уникальное имя клиента")
        parser.add_argument(
            "--scope",
            action="append",
            choices=sorted(SCOPE_ALIASES),
            required=True,
            help="Разрешение ключа; можно указать несколько раз",
        )
        parser.add_argument(
            "--community",
            action="append",
            default=[],
            help="Разрешенный slug сообщества; можно указать несколько раз",
        )
        parser.add_argument(
            "--all-communities",
            action="store_true",
            help="Разрешить аналитику всех сообществ",
        )
        parser.add_argument(
            "--allow-ip",
            action="append",
            default=[],
            help="Разрешенный IP или CIDR; можно указать несколько раз",
        )
        parser.add_argument(
            "--expires-in-days",
            type=int,
            default=90,
            help="Срок действия ключа, по умолчанию 90 дней",
        )

    def handle(self, *args, **options):
        name = options["name"].strip()
        if not name:
            raise CommandError("--name не должен быть пустым")
        expires_in_days = options["expires_in_days"]
        if expires_in_days < 1 or expires_in_days > 3650:
            raise CommandError("--expires-in-days должен быть от 1 до 3650")
        if AnalyticsApiCredential.objects.filter(name=name).exists():
            raise CommandError(f"Ключ с именем {name!r} уже существует")

        communities = [str(value).strip() for value in options["community"] if str(value).strip()]
        if options["all_communities"]:
            communities = ["*"]
        scopes = [SCOPE_ALIASES[value] for value in options["scope"]]
        if SCOPE_COMMUNITY_ANALYTICS in scopes and not communities:
            raise CommandError(
                "Для scope communities укажите --community <slug> или --all-communities"
            )
        if communities != ["*"]:
            existing_slugs = set(
                Comun.objects.filter(slug__in=communities).values_list("slug", flat=True)
            )
            missing_slugs = sorted(set(communities) - existing_slugs)
            if missing_slugs:
                raise CommandError(
                    f"Не найдены сообщества: {', '.join(missing_slugs)}"
                )

        allowed_networks = []
        for value in options["allow_ip"]:
            try:
                network = ipaddress.ip_network(str(value).strip(), strict=False)
            except ValueError as exc:
                raise CommandError(f"Некорректный --allow-ip: {value}") from exc
            allowed_networks.append(str(network))

        credential, raw_token = AnalyticsApiCredential.issue(
            name=name,
            scopes=scopes,
            allowed_community_slugs=communities,
            allowed_ip_networks=allowed_networks,
            expires_in_days=expires_in_days,
        )
        self.stdout.write(self.style.SUCCESS(f"Ключ {credential.name!r} создан."))
        self.stdout.write("Сохраните токен сейчас: повторно он показан не будет.")
        self.stdout.write(raw_token)
        self.stdout.write(f"Истекает: {credential.expires_at.isoformat()}")
