from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand

from feeds.sitemaps import materialize_sitemaps


class Command(BaseCommand):
    help = "Materializes stable XML sitemap shards for direct static serving by nginx."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default="")
        parser.add_argument("--site-base-url", default="")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--max-age-hours", type=float, default=24.0)

    def handle(self, *args, **options):
        manifest = materialize_sitemaps(
            output_dir=options["output_dir"] or None,
            site_base_url=options["site_base_url"] or None,
            force=bool(options["force"]),
            max_age=timedelta(hours=max(0.0, float(options["max_age_hours"]))),
        )
        files = [
            payload
            for group in manifest.get("groups", {}).values()
            for payload in group.get("files", [])
        ]
        urls = sum(int(payload.get("url_count") or 0) for payload in files)
        size = sum(int(payload.get("bytes_uncompressed") or 0) for payload in files)
        self.stdout.write(
            self.style.SUCCESS(
                f"Materialized {len(files)} sitemap files with {urls} URLs "
                f"({size} uncompressed bytes)."
            )
        )
