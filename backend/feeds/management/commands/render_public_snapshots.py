from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from feeds.models import PublicFeedItem
from feeds.post_paths import build_post_public_path
from feeds.seo_indexing import seo_indexable_posts_queryset
from feeds.views import _post_display_title

SNAPSHOT_LANGUAGES = ("ru", "en", "es", "pt", "de", "fr", "tr", "id")


def _snapshot_file_for_path(root: Path, path: str) -> Path:
    normalized_path = "/" + path.strip("/")
    if normalized_path == "/":
        return root / "index.html"
    return root / normalized_path.strip("/") / "index.html"


def _localized_snapshot_path(path: str, language: str) -> str:
    if language == "ru" or path == "/":
        return path
    return f"/{language}{path}"


class Command(BaseCommand):
    help = "Renders anonymous HTML snapshots for hot public pages through the frontend server."

    def add_arguments(self, parser):
        parser.add_argument("--frontend-url", default="")
        parser.add_argument("--site-host", default="")
        parser.add_argument("--output-dir", default="")
        parser.add_argument("--posts", type=int, default=100)
        parser.add_argument("--recent-posts", type=int, default=50)
        parser.add_argument("--timeout", type=int, default=15)
        parser.add_argument("--languages", nargs="+", default=list(SNAPSHOT_LANGUAGES))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        frontend_url = (
            options["frontend_url"]
            or getattr(settings, "SNAPSHOT_FRONTEND_URL", "")
            or "http://frontend:3000"
        ).rstrip("/")
        site_host = (
            options["site_host"]
            or urllib.parse.urlparse(getattr(settings, "SITE_BASE_URL", "")).netloc
            or "tambur.pub"
        )
        output_root = Path(
            options["output_dir"]
            or getattr(settings, "PUBLIC_HTML_SNAPSHOT_ROOT", "")
            or (Path(settings.STATIC_ROOT) / "html-snapshots")
        )
        posts_limit = max(0, int(options["posts"]))
        recent_posts_limit = max(0, int(options["recent_posts"]))
        timeout = max(1, int(options["timeout"]))
        languages = list(
            dict.fromkeys(
                language
                for language in (str(value).strip().lower() for value in options["languages"])
                if language in SNAPSHOT_LANGUAGES
            )
        )
        if not languages:
            raise CommandError("No supported snapshot languages were selected.")
        dry_run = bool(options["dry_run"])

        feed_items = list(
            PublicFeedItem.objects.filter(feed=PublicFeedItem.FEED_HOME)
            .select_related("post")
            .order_by("rank")[:posts_limit]
        )
        recent_posts = list(
            seo_indexable_posts_queryset()
            .select_related("author")
            .order_by("-created_at")[:recent_posts_limit]
        )
        paths = ["/"]
        posts_by_id = {item.post_id: item.post for item in feed_items}
        posts_by_id.update({post.id: post for post in recent_posts})
        for post in posts_by_id.values():
            title = _post_display_title(post)
            paths.append(build_post_public_path(post.id, title))

        unique_paths = list(dict.fromkeys(paths))
        render_tasks = [
            (language, _localized_snapshot_path(path, language))
            for language in languages
            for path in unique_paths
        ]
        self.stdout.write(
            f"Rendering {len(render_tasks)} snapshots in {len(languages)} languages "
            f"from {frontend_url} into {output_root}"
        )
        if dry_run:
            for language, path in render_tasks:
                self.stdout.write(f"{language} {path}")
            return

        temp_root = output_root.with_name(f"{output_root.name}.tmp")
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        rendered: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []
        for language, path in render_tasks:
            url = f"{frontend_url}{path}"
            request = urllib.request.Request(
                url,
                headers={
                    "Host": site_host,
                    "Accept": "text/html",
                    "Accept-Language": language,
                    "User-Agent": "rabotaem-snapshot-renderer/1.0",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    status = int(getattr(response, "status", 200))
                    content_type = response.headers.get("Content-Type", "")
                    response_url = getattr(response, "geturl", lambda: url)()
                    body = response.read()
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                failures.append({"language": language, "path": path, "error": str(exc)})
                continue

            if status != 200 or b"<html" not in body[:2048].lower():
                failures.append(
                    {
                        "language": language,
                        "path": path,
                        "status": status,
                        "content_type": content_type,
                    }
                )
                continue

            effective_path = urllib.parse.urlparse(response_url).path or path
            target = _snapshot_file_for_path(temp_root / language, effective_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            rendered.append(
                {
                    "language": language,
                    "path": effective_path,
                    "requested_path": path,
                    "bytes": len(body),
                }
            )

        manifest = {
            "generated_at": timezone.now().isoformat(),
            "frontend_url": frontend_url,
            "site_host": site_host,
            "languages": languages,
            "rendered": rendered,
            "failures": failures,
        }
        (temp_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        minimum_successes = max(1, int(len(render_tasks) * 0.8))
        if len(rendered) < minimum_successes:
            shutil.rmtree(temp_root)
            raise CommandError(
                f"Rendered only {len(rendered)} of {len(render_tasks)} snapshots; "
                "keeping the previous snapshot set."
            )

        if output_root.exists():
            shutil.rmtree(output_root)
        temp_root.rename(output_root)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rendered {len(rendered)} snapshots; {len(failures)} failures."
            )
        )
