from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from feeds.language_detection import (
    SUPPORTED_POST_LANGUAGES,
    detect_post_language,
    post_language_text,
)
from feeds.models import Post


class Command(BaseCommand):
    help = "Detect and persist original languages for existing published posts."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--post-id", type=int, action="append", default=[])
        parser.add_argument("--current-language", choices=sorted(SUPPORTED_POST_LANGUAGES))
        parser.add_argument("--show-changed", action="store_true")
        parser.add_argument("--batch-size", type=int, default=250)
        parser.add_argument("--sleep-ms", type=int, default=0)

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit = max(int(options["limit"] or 0), 0)
        post_ids = [post_id for post_id in options["post_id"] if post_id > 0]
        current_language = str(options.get("current_language") or "").strip()
        show_changed = bool(options["show_changed"])
        batch_size = min(max(int(options["batch_size"] or 250), 1), 2000)
        sleep_seconds = min(max(int(options["sleep_ms"] or 0), 0), 10_000) / 1000

        queryset = Post.objects.filter(is_blocked=False, is_pending=False).order_by("id")
        if post_ids:
            queryset = queryset.filter(id__in=post_ids)
        if current_language:
            queryset = queryset.filter(original_language=current_language)
        if limit:
            queryset = queryset[:limit]

        scanned = 0
        changed = 0
        counts: dict[str, int] = {}
        for post in queryset.iterator(chunk_size=batch_size):
            scanned += 1
            language = detect_post_language(
                post.title,
                post.content,
                fallback=post.original_language,
            )
            counts[language] = counts.get(language, 0) + 1
            if language == post.original_language:
                if sleep_seconds and scanned % batch_size == 0:
                    time.sleep(sleep_seconds)
                continue
            changed += 1
            if show_changed:
                text_preview = post_language_text(post.title, post.content)[:240]
                self.stdout.write(
                    f"post={post.id} {post.original_language}->{language} "
                    f"title={post.title[:120]!r} text={text_preview!r}"
                )
            if dry_run:
                if sleep_seconds and scanned % batch_size == 0:
                    time.sleep(sleep_seconds)
                continue
            post.original_language = language
            post.translations.filter(language=language).delete()
            post.save(update_fields=["original_language", "updated_at"])
            if sleep_seconds and scanned % batch_size == 0:
                time.sleep(sleep_seconds)

        prefix = "DRY_RUN " if dry_run else ""
        language_counts = ",".join(
            f"{language}:{count}" for language, count in sorted(counts.items())
        )
        self.stdout.write(
            f"{prefix}scanned={scanned} changed={changed} languages={language_counts}"
        )
