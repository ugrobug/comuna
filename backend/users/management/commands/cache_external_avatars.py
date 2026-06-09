from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from users.avatar_media import cache_external_avatar_for_user, is_cached_media_avatar_url

User = get_user_model()


class Command(BaseCommand):
    help = "Copy Telegram/VK profile avatars to local media storage/S3 and store them in SiteUserProfile."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--source",
            choices=("all", "telegram", "vk"),
            default="all",
        )

    def handle(self, *args, **options):
        limit = max(int(options["limit"] or 0), 0)
        force = bool(options["force"])
        dry_run = bool(options["dry_run"])
        source_filter = str(options["source"] or "all")

        queryset = User.objects.select_related(
            "site_profile",
            "telegram_account",
            "vk_account",
        ).order_by("id")
        if source_filter == "telegram":
            queryset = queryset.filter(telegram_account__avatar_url__gt="")
        elif source_filter == "vk":
            queryset = queryset.filter(vk_account__avatar_url__gt="")
        else:
            queryset = queryset.filter(
                Q(telegram_account__avatar_url__gt="") | Q(vk_account__avatar_url__gt="")
            ).distinct()

        checked = 0
        cached = 0
        skipped = 0
        failed = 0

        for user in queryset:
            if limit and checked >= limit:
                break
            checked += 1
            profile_avatar_url = str(getattr(getattr(user, "site_profile", None), "avatar_url", "") or "")
            if profile_avatar_url and is_cached_media_avatar_url(profile_avatar_url) and not force:
                skipped += 1
                continue

            candidates: list[tuple[str, str]] = []
            telegram_avatar_url = str(
                getattr(getattr(user, "telegram_account", None), "avatar_url", "") or ""
            ).strip()
            vk_avatar_url = str(getattr(getattr(user, "vk_account", None), "avatar_url", "") or "").strip()
            if source_filter in {"all", "telegram"} and telegram_avatar_url:
                candidates.append(("telegram", telegram_avatar_url))
            if source_filter in {"all", "vk"} and vk_avatar_url:
                candidates.append(("vk", vk_avatar_url))
            if not candidates:
                skipped += 1
                continue

            if dry_run:
                cached += 1
                self.stdout.write(f"would cache user_id={user.id} source={candidates[0][0]}")
                continue

            result = None
            for source, avatar_url in candidates:
                result = cache_external_avatar_for_user(
                    user,
                    avatar_url,
                    source=source,
                    force=force,
                )
                if result:
                    cached += 1
                    self.stdout.write(f"cached user_id={user.id} source={source}")
                    break
            if not result:
                failed += 1
                self.stdout.write(f"failed user_id={user.id}")

        self.stdout.write(
            self.style.SUCCESS(
                f"checked={checked} cached={cached} skipped={skipped} failed={failed}"
            )
        )
