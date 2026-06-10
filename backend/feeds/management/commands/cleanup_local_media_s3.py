from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


REPORT_DIR_NAME = "_migration_reports"
READ_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class LocalMediaFile:
    key: str
    path: Path
    size: int
    mtime: str


class Command(BaseCommand):
    help = "Delete local MEDIA_ROOT files only when the same key exists in configured S3 storage."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete eligible local files. Without this flag the command is a dry-run.",
        )
        parser.add_argument(
            "--verify-content",
            action="store_true",
            help="Compare local and S3 SHA256 hashes before deleting each same-size file.",
        )
        parser.add_argument(
            "--prefix",
            default="",
            help="Only process local files whose key starts with this prefix.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit the number of local files processed. Useful for smoke tests.",
        )
        parser.add_argument(
            "--report-dir",
            default="",
            help="Directory for CSV/JSON reports. Defaults to MEDIA_ROOT/_migration_reports.",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=1000,
            help="Print progress every N processed files.",
        )

    def handle(self, *args, **options) -> None:
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        s3_storage = self._s3_storage()
        if s3_storage is None:
            raise CommandError("S3 storage is not configured; refusing to delete local media.")

        delete_enabled = bool(options["delete"])
        verify_content = bool(options["verify_content"])
        prefix = self._normalize_prefix(options["prefix"])
        limit = max(0, int(options["limit"] or 0))
        progress_every = max(0, int(options["progress_every"] or 0))
        report_dir = self._report_dir(media_root, options["report_dir"])
        report_dir.mkdir(parents=True, exist_ok=True)

        started_at = timezone.now()
        self.stdout.write(f"Media root: {media_root}")
        self.stdout.write(f"Report dir: {report_dir}")
        self.stdout.write(f"Mode: {'delete' if delete_enabled else 'dry-run'}")
        self.stdout.write(f"Content verification: {'yes' if verify_content else 'no'}")

        s3_objects = self._list_s3_objects(s3_storage)
        self.stdout.write(f"S3 objects listed: {len(s3_objects)}")

        local_files = self._collect_local_files(
            media_root=media_root,
            report_dir=report_dir,
            prefix=prefix,
            limit=limit,
        )
        self.stdout.write(f"Local files found: {len(local_files)}")

        rows: list[dict] = []
        counts: Counter[str] = Counter()
        bytes_by_status: Counter[str] = Counter()
        deleted_bytes = 0

        for index, item in enumerate(local_files, start=1):
            status, s3_size, error = self._s3_status(s3_objects, item.key, item.size)
            verified = False

            if status == "same_size" and verify_content:
                verified, error = self._same_content(item.path, s3_storage, item.key)
                if not verified:
                    status = "content_mismatch"
            elif status == "same_size":
                verified = True

            deleted = False
            if delete_enabled and status == "same_size" and verified:
                try:
                    item.path.unlink()
                    deleted = True
                    deleted_bytes += item.size
                except Exception as exc:  # noqa: BLE001 - report per-file deletion failures.
                    status = "delete_error"
                    error = str(exc)

            counts[status] += 1
            bytes_by_status[status] += item.size
            rows.append(
                {
                    "key": item.key,
                    "local_size": item.size,
                    "local_mtime": item.mtime,
                    "s3_status": status,
                    "s3_size": s3_size,
                    "content_verified": verified,
                    "deleted": deleted,
                    "error": error,
                }
            )

            if progress_every and index % progress_every == 0:
                self.stdout.write(
                    f"Progress: {index}/{len(local_files)} processed, "
                    f"same_size={counts.get('same_size', 0)}, "
                    f"deleted={sum(1 for row in rows if row['deleted'])}, "
                    f"errors={counts.get('delete_error', 0) + counts.get('content_mismatch', 0)}"
                )

        finished_at = timezone.now()
        summary = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "delete_enabled": delete_enabled,
            "verify_content": verify_content,
            "prefix": prefix,
            "media_root": str(media_root),
            "report_dir": str(report_dir),
            "s3_objects_count": len(s3_objects),
            "local_files_count": len(local_files),
            "local_total_bytes": sum(item.size for item in local_files),
            "deleted_count": sum(1 for row in rows if row["deleted"]),
            "deleted_bytes": deleted_bytes,
            "status_counts": dict(counts),
            "status_bytes": dict(bytes_by_status),
        }

        self._write_reports(report_dir=report_dir, summary=summary, rows=rows)
        self._print_summary(summary)

    def _collect_local_files(
        self,
        *,
        media_root: Path,
        report_dir: Path,
        prefix: str,
        limit: int,
    ) -> list[LocalMediaFile]:
        files: list[LocalMediaFile] = []
        report_dir_resolved = report_dir.resolve()

        for path in sorted(media_root.rglob("*")):
            if not path.is_file():
                continue
            if self._is_inside(path.resolve(), report_dir_resolved):
                continue
            if REPORT_DIR_NAME in path.relative_to(media_root).parts:
                continue
            key = path.relative_to(media_root).as_posix()
            if prefix and not key.startswith(prefix):
                continue
            stat = path.stat()
            files.append(
                LocalMediaFile(
                    key=key,
                    path=path,
                    size=stat.st_size,
                    mtime=datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.get_current_timezone(),
                    ).isoformat(),
                )
            )
            if limit and len(files) >= limit:
                break
        return files

    def _list_s3_objects(self, s3_storage) -> dict[str, int]:
        objects: dict[str, int] = {}
        location = str(getattr(s3_storage, "location", "") or "").strip("/")
        prefix = f"{location}/" if location else ""

        try:
            iterator = s3_storage.bucket.objects.filter(Prefix=prefix)
            for item in iterator:
                key = str(item.key)
                if prefix and key.startswith(prefix):
                    key = key[len(prefix):]
                if key:
                    objects[key] = int(item.size)
        except Exception as exc:  # noqa: BLE001 - surface storage-specific failure.
            raise CommandError(f"Could not list S3 objects: {exc}") from exc

        return objects

    def _same_content(self, local_path: Path, s3_storage, key: str) -> tuple[bool, str]:
        try:
            local_hash = hashlib.sha256()
            with local_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(READ_CHUNK_SIZE), b""):
                    local_hash.update(chunk)

            s3_hash = hashlib.sha256()
            with s3_storage.open(key, "rb") as handle:
                for chunk in iter(lambda: handle.read(READ_CHUNK_SIZE), b""):
                    s3_hash.update(chunk)

            return local_hash.hexdigest() == s3_hash.hexdigest(), ""
        except Exception as exc:  # noqa: BLE001 - keep cleanup running and report per-file failures.
            return False, str(exc)

    @staticmethod
    def _s3_status(s3_objects: dict[str, int], key: str, local_size: int) -> tuple[str, int | str, str]:
        if key not in s3_objects:
            return "missing", "", ""
        s3_size = int(s3_objects[key])
        if s3_size == local_size:
            return "same_size", s3_size, ""
        return "size_mismatch", s3_size, ""

    def _write_reports(self, *, report_dir: Path, summary: dict, rows: list[dict]) -> None:
        self._write_csv(
            report_dir / "local_media_s3_cleanup.csv",
            fieldnames=[
                "key",
                "local_size",
                "local_mtime",
                "s3_status",
                "s3_size",
                "content_verified",
                "deleted",
                "error",
            ],
            rows=rows,
        )
        (report_dir / "local_media_s3_cleanup_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _write_csv(path: Path, *, fieldnames: list[str], rows: list[dict]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _print_summary(self, summary: dict) -> None:
        self.stdout.write("")
        self.stdout.write("Local media cleanup summary")
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    @staticmethod
    def _normalize_prefix(value: str) -> str:
        prefix = str(value or "").strip().lstrip("/")
        if not prefix:
            return ""
        return prefix.removeprefix("media/")

    @staticmethod
    def _report_dir(media_root: Path, value: str) -> Path:
        if value:
            return Path(value)
        return media_root / REPORT_DIR_NAME

    @staticmethod
    def _s3_storage():
        return getattr(default_storage, "s3_storage", None)

    @staticmethod
    def _is_inside(path: Path, directory: Path) -> bool:
        try:
            path.relative_to(directory)
            return True
        except ValueError:
            return False
