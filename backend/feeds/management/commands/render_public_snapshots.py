from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from feeds.models import PublicFeedItem
from feeds.views import _post_display_title


def _slugify_title(value: str) -> str:
    import re

    normalized = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ\s-]+", "", value or "").strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized[:100]


def _snapshot_file_for_path(root: Path, path: str) -> Path:
    normalized_path = "/" + path.strip("/")
    if normalized_path == "/":
        return root / "index.html"
    return root / normalized_path.strip("/") / "index.html"


class Command(BaseCommand):
    help = "Renders anonymous HTML snapshots for hot public pages through the frontend server."

    def add_arguments(self, parser):
        parser.add_argument("--frontend-url", default="")
        parser.add_argument("--site-host", default="")
        parser.add_argument("--output-dir", default="")
        parser.add_argument("--posts", type=int, default=100)
        parser.add_argument("--timeout", type=int, default=15)
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
        timeout = max(1, int(options["timeout"]))
        dry_run = bool(options["dry_run"])

        feed_items = list(
            PublicFeedItem.objects.filter(feed=PublicFeedItem.FEED_HOME)
            .select_related("post")
            .order_by("rank")[:posts_limit]
        )
        paths = ["/"]
        for item in feed_items:
            title = _post_display_title(item.post)
            slug = _slugify_title(title)
            paths.append(f"/b/post/{item.post_id}-{slug}" if slug else f"/b/post/{item.post_id}")

        unique_paths = list(dict.fromkeys(paths))
        self.stdout.write(
            f"Rendering {len(unique_paths)} snapshots from {frontend_url} into {output_root}"
        )
        if dry_run:
            for path in unique_paths:
                self.stdout.write(path)
            return

        temp_root = output_root.with_name(f"{output_root.name}.tmp")
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        rendered: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []
        for path in unique_paths:
            url = f"{frontend_url}{path}"
            request = urllib.request.Request(
                url,
                headers={
                    "Host": site_host,
                    "Accept": "text/html",
                    "User-Agent": "rabotaem-snapshot-renderer/1.0",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    status = int(getattr(response, "status", 200))
                    content_type = response.headers.get("Content-Type", "")
                    body = response.read()
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                failures.append({"path": path, "error": str(exc)})
                continue

            if status != 200 or b"<html" not in body[:2048].lower():
                failures.append({"path": path, "status": status, "content_type": content_type})
                continue

            target = _snapshot_file_for_path(temp_root, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            rendered.append({"path": path, "bytes": len(body)})

        manifest = {
            "generated_at": timezone.now().isoformat(),
            "frontend_url": frontend_url,
            "site_host": site_host,
            "rendered": rendered,
            "failures": failures,
        }
        (temp_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if output_root.exists():
            shutil.rmtree(output_root)
        temp_root.rename(output_root)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rendered {len(rendered)} snapshots; {len(failures)} failures."
            )
        )
