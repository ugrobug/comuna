from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from legacy_migration.legacy_posts import articles_q
from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.wp_content_rewrites import rewrite_post_content_string


class Command(BaseCommand):
    help = "Переписать ссылки ПТ в Post.content: post_link, author, href /articles/ → /b/post/"

    def add_arguments(self, parser):
        parser.add_argument("--wp-ids", type=str, default="", help="WP post ID через запятую")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument(
            "--no-post-link",
            action="store_true",
            help="Не превращать одиночные ссылки на статьи в блок post_link",
        )
        parser.add_argument(
            "--no-author",
            action="store_true",
            help="Не превращать /author/… в блок author",
        )
        parser.add_argument(
            "--urls-only",
            action="store_true",
            help="Только заменить href, без post_link/author",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)
        offset: int = max(int(options["offset"] or 0), 0)
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")

        convert_post_link = not options["no_post_link"] and not options["urls_only"]
        convert_author = not options["no_author"] and not options["urls_only"]
        replace_urls = True

        qs = WpPosts.objects.filter(articles_q()).order_by("-post_date")
        if wp_ids:
            qs = qs.filter(id__in=wp_ids)
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]

        updated = 0
        skipped = 0
        total_links = 0
        total_authors = 0
        total_urls = 0

        for wp_post in qs:
            wp_id = int(wp_post.id)
            map_row = LegacyWpPostMap.objects.filter(wp_post_id=wp_id).select_related("post").first()
            if not map_row or not map_row.post_id:
                skipped += 1
                continue

            post = map_row.post
            new_content, stats = rewrite_post_content_string(
                post.content or "",
                convert_post_link=convert_post_link,
                convert_author=convert_author,
                replace_urls=replace_urls,
            )
            changed = new_content != (post.content or "")
            if not changed:
                continue

            total_links += stats.post_links
            total_authors += stats.authors
            total_urls += stats.url_replacements

            if dry_run:
                self.stdout.write(
                    f"[dry-run] wp:{wp_id} post:{post.id} "
                    f"links={stats.post_links} authors={stats.authors} urls={stats.url_replacements}"
                )
                updated += 1
                continue

            with transaction.atomic():
                post.content = new_content
                post.save(update_fields=["content", "updated_at"])
            updated += 1
            self.stdout.write(
                f"wp:{wp_id} post:{post.id} "
                f"links={stats.post_links} authors={stats.authors} urls={stats.url_replacements}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Контент: обновлено {updated}, пропущено {skipped}; "
                f"блоков post_link={total_links}, author={total_authors}, href={total_urls}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run"))
