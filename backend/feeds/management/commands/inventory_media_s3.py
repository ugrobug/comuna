from __future__ import annotations

import csv
import json
import mimetypes
import posixpath
import re
import threading
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.utils import timezone


ABSOLUTE_MEDIA_URL_RE = re.compile(
    r"""(?:
        https?://(?:www\.)?tambur\.pub/media/(?P<site>[^"'<>\s]+)
        |https?://media\.tambur\.pub/(?P<media>[^"'<>\s]+)
    )""",
    re.IGNORECASE | re.VERBOSE,
)
LOCAL_MEDIA_PATH_RE = re.compile(
    r"""(?<![A-Za-z0-9:/._-])/media/(?P<path>[^"'<>\s]+)""",
    re.IGNORECASE | re.VERBOSE,
)

REPORT_DIR_NAME = "_migration_reports"


@dataclass(frozen=True)
class LocalMediaFile:
    key: str
    size: int
    mtime: str


@dataclass(frozen=True)
class MediaReference:
    key: str
    source: str


class Command(BaseCommand):
    help = "Inventory local media and optionally copy missing files to the configured S3 storage."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--copy",
            action="store_true",
            help="Upload local files missing from S3. Local files are never deleted.",
        )
        parser.add_argument(
            "--overwrite-mismatched",
            action="store_true",
            help="Replace S3 objects whose size differs from the local file.",
        )
        parser.add_argument(
            "--skip-db-scan",
            action="store_true",
            help="Skip scanning database fields for media references.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit the number of local files processed. Useful for smoke tests.",
        )
        parser.add_argument(
            "--prefix",
            default="",
            help="Only process local files whose key starts with this prefix.",
        )
        parser.add_argument(
            "--report-dir",
            default="",
            help="Directory for CSV/JSON reports. Defaults to MEDIA_ROOT/_migration_reports.",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=500,
            help="Database iterator chunk size.",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help="Concurrent S3 upload workers used with --copy.",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=1000,
            help="Print copy progress every N processed files.",
        )

    def handle(self, *args, **options) -> None:
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        copy_enabled = bool(options["copy"])
        overwrite_mismatched = bool(options["overwrite_mismatched"])
        prefix = self._normalize_prefix(options["prefix"])
        report_dir = self._report_dir(media_root, options["report_dir"])
        report_dir.mkdir(parents=True, exist_ok=True)

        local_storage = self._local_storage()
        s3_storage = self._s3_storage()
        if copy_enabled and s3_storage is None:
            raise CommandError("S3 storage is not configured; cannot copy files.")
        s3_objects = self._list_s3_objects(s3_storage) if s3_storage else None

        started_at = timezone.now()
        self.stdout.write(f"Media root: {media_root}")
        self.stdout.write(f"Report dir: {report_dir}")
        self.stdout.write(f"S3 configured: {'yes' if s3_storage else 'no'}")
        if s3_objects is not None:
            self.stdout.write(f"S3 objects listed: {len(s3_objects)}")

        local_files = self._collect_local_files(
            media_root=media_root,
            report_dir=report_dir,
            prefix=prefix,
            limit=max(0, int(options["limit"] or 0)),
        )
        self.stdout.write(f"Local files found: {len(local_files)}")

        references: list[MediaReference] = []
        if not options["skip_db_scan"]:
            references = self._collect_db_references(chunk_size=max(1, int(options["chunk_size"] or 500)))
            self.stdout.write(f"DB media references found: {len(references)}")

        local_keys = {item.key for item in local_files}
        reference_keys = {item.key for item in references}
        file_rows, status_counts = self._build_file_rows(local_files, s3_objects)
        reference_rows, reference_counts = self._build_reference_rows(
            references,
            local_keys,
            s3_objects,
        )

        copy_counts: Counter[str] = Counter()
        if copy_enabled:
            copy_counts = self._copy_missing_files(
                local_files=local_files,
                file_rows=file_rows,
                local_storage=local_storage,
                s3_storage=s3_storage,
                s3_objects=s3_objects or {},
                overwrite_mismatched=overwrite_mismatched,
                workers=max(1, int(options["workers"] or 1)),
                progress_every=max(0, int(options["progress_every"] or 0)),
            )
            status_counts = Counter(str(row["s3_status"]) for row in file_rows)
            reference_rows, reference_counts = self._build_reference_rows(
                references,
                local_keys,
                s3_objects or {},
            )

        finished_at = timezone.now()
        summary = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "copy_enabled": copy_enabled,
            "overwrite_mismatched": overwrite_mismatched,
            "prefix": prefix,
            "media_root": str(media_root),
            "report_dir": str(report_dir),
            "s3_configured": bool(s3_storage),
            "local_files_count": len(local_files),
            "local_total_bytes": sum(item.size for item in local_files),
            "local_unreferenced_count": len(local_keys - reference_keys) if references else None,
            "db_references_count": len(references),
            "db_reference_unique_keys": len(reference_keys),
            "db_referenced_local_missing": reference_counts.get("local_missing", 0),
            "db_referenced_s3_missing": reference_counts.get("s3_missing", 0),
            "s3_status_counts": dict(status_counts),
            "copy_counts": dict(copy_counts),
        }

        self._write_reports(
            report_dir=report_dir,
            summary=summary,
            file_rows=file_rows,
            reference_rows=reference_rows,
        )
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

    def _collect_db_references(self, *, chunk_size: int) -> list[MediaReference]:
        references: list[MediaReference] = []
        for model in apps.get_models():
            fields = self._media_reference_fields(model)
            if not fields:
                continue

            pk_name = model._meta.pk.attname
            field_names = [field.name for field in fields]
            queryset = model._default_manager.values(pk_name, *field_names).order_by(pk_name)
            model_label = model._meta.label

            for row in queryset.iterator(chunk_size=chunk_size):
                pk = row.get(pk_name)
                for field in fields:
                    value = row.get(field.name)
                    for key in self._extract_keys_from_field(field, value):
                        references.append(
                            MediaReference(
                                key=key,
                                source=f"{model_label}.{field.name}:{pk}",
                            )
                        )
        return references

    def _build_file_rows(
        self,
        local_files: list[LocalMediaFile],
        s3_objects: dict[str, int] | None,
    ) -> tuple[list[dict[str, Any]], Counter[str]]:
        rows: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        for item in local_files:
            status, s3_size, error = self._s3_status(s3_objects, item.key, item.size)
            counts[status] += 1
            rows.append(
                {
                    "key": item.key,
                    "local_size": item.size,
                    "local_mtime": item.mtime,
                    "s3_status": status,
                    "s3_size": s3_size,
                    "error": error,
                    "copy_status": "",
                    "saved_key": "",
                }
            )
        return rows, counts

    def _build_reference_rows(
        self,
        references: list[MediaReference],
        local_keys: set[str],
        s3_objects: dict[str, int] | None,
    ) -> tuple[list[dict[str, Any]], Counter[str]]:
        rows: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()

        for reference in references:
            local_exists = reference.key in local_keys
            if s3_objects is None:
                s3_exists: bool | None = None
            else:
                s3_exists = reference.key in s3_objects

            if not local_exists:
                counts["local_missing"] += 1
            if s3_exists is False:
                counts["s3_missing"] += 1

            rows.append(
                {
                    "key": reference.key,
                    "source": reference.source,
                    "local_exists": local_exists,
                    "s3_exists": s3_exists,
                }
            )

        return rows, counts

    def _copy_missing_files(
        self,
        *,
        local_files: list[LocalMediaFile],
        file_rows: list[dict[str, Any]],
        local_storage: FileSystemStorage,
        s3_storage,
        s3_objects: dict[str, int],
        overwrite_mismatched: bool,
        workers: int,
        progress_every: int,
    ) -> Counter[str]:
        counts: Counter[str] = Counter()
        files_by_key = {item.key: item for item in local_files}
        thread_state = threading.local()

        def worker_storage():
            storage = getattr(thread_state, "s3_storage", None)
            if storage is None:
                storage = s3_storage.__class__()
                thread_state.s3_storage = storage
            return storage

        def upload_one(row: dict[str, Any]) -> dict[str, Any]:
            key = row["key"]
            local_file = files_by_key[key]
            status = row["s3_status"]

            if status == "same_size":
                return {"copy_status": "skipped_exists"}
            if status == "size_mismatch" and not overwrite_mismatched:
                return {"copy_status": "skipped_size_mismatch"}
            if status not in {"missing", "size_mismatch"}:
                return {"copy_status": f"skipped_{status}"}

            try:
                active_s3_storage = worker_storage()
                if status == "size_mismatch" and overwrite_mismatched:
                    active_s3_storage.delete(key)
                with local_storage.open(key, "rb") as source:
                    content = File(source, name=posixpath.basename(key))
                    content_type, _ = mimetypes.guess_type(key)
                    if content_type:
                        content.content_type = content_type
                    save = getattr(active_s3_storage, "_save", active_s3_storage.save)
                    saved_key = save(key, content)
                if saved_key != key:
                    return {
                        "copy_status": "uploaded_renamed",
                        "saved_key": saved_key,
                    }
                return {
                    "copy_status": "uploaded",
                    "saved_key": saved_key,
                    "s3_status": "same_size",
                    "s3_size": local_file.size,
                    "error": "",
                }
            except Exception as exc:  # noqa: BLE001 - keep migration running and report per-file failures.
                return {"copy_status": "error", "error": str(exc)}

        def apply_result(row: dict[str, Any], result: dict[str, Any]) -> None:
            row.update(result)
            copy_status = str(result.get("copy_status") or "unknown")
            counts[copy_status] += 1
            if copy_status == "uploaded":
                s3_objects[row["key"]] = int(row["local_size"])

        rows_iter = iter(file_rows)
        processed = 0
        pending = set()
        future_rows = {}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for _ in range(max(workers * 2, 1)):
                try:
                    row = next(rows_iter)
                except StopIteration:
                    break
                future = executor.submit(upload_one, row)
                pending.add(future)
                future_rows[future] = row

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    row = future_rows.pop(future)
                    apply_result(row, future.result())
                    processed += 1
                    if progress_every and processed % progress_every == 0:
                        self.stdout.write(
                            f"Copy progress: {processed}/{len(file_rows)} processed, "
                            f"uploaded={counts.get('uploaded', 0)}, "
                            f"errors={counts.get('error', 0)}"
                        )

                    try:
                        next_row = next(rows_iter)
                    except StopIteration:
                        continue
                    next_future = executor.submit(upload_one, next_row)
                    pending.add(next_future)
                    future_rows[next_future] = next_row

        return counts

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

    def _write_reports(
        self,
        *,
        report_dir: Path,
        summary: dict[str, Any],
        file_rows: list[dict[str, Any]],
        reference_rows: list[dict[str, Any]],
    ) -> None:
        self._write_csv(
            report_dir / "media_inventory_files.csv",
            fieldnames=[
                "key",
                "local_size",
                "local_mtime",
                "s3_status",
                "s3_size",
                "copy_status",
                "saved_key",
                "error",
            ],
            rows=file_rows,
        )
        self._write_csv(
            report_dir / "media_inventory_refs.csv",
            fieldnames=["key", "source", "local_exists", "s3_exists"],
            rows=reference_rows,
        )
        (report_dir / "media_inventory_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _write_csv(path: Path, *, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _print_summary(self, summary: dict[str, Any]) -> None:
        self.stdout.write("")
        self.stdout.write("Media migration summary")
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    @staticmethod
    def _media_reference_fields(model) -> list[models.Field]:
        media_fields: list[models.Field] = []
        for field in model._meta.concrete_fields:
            if isinstance(field, models.FileField):
                media_fields.append(field)
                continue
            if isinstance(
                field,
                (
                    models.CharField,
                    models.TextField,
                    models.URLField,
                    models.JSONField,
                ),
            ):
                media_fields.append(field)
        return media_fields

    def _extract_keys_from_field(self, field: models.Field, value: Any) -> set[str]:
        if value in (None, ""):
            return set()
        if isinstance(field, models.FileField):
            return {key} if (key := self._normalize_key(str(value))) else set()
        return self._extract_media_keys(value)

    def _extract_media_keys(self, value: Any) -> set[str]:
        keys: set[str] = set()
        if isinstance(value, str):
            for match in ABSOLUTE_MEDIA_URL_RE.finditer(value):
                key = self._normalize_key(match.group("site") or match.group("media"))
                if key:
                    keys.add(key)
            for match in LOCAL_MEDIA_PATH_RE.finditer(value):
                key = self._normalize_key(match.group("path"))
                if key:
                    keys.add(key)
            return keys
        if isinstance(value, dict):
            for nested in value.values():
                keys.update(self._extract_media_keys(nested))
            return keys
        if isinstance(value, (list, tuple)):
            for nested in value:
                keys.update(self._extract_media_keys(nested))
        return keys

    @staticmethod
    def _normalize_key(value: str) -> str:
        raw = str(value or "").strip().rstrip(").,;")
        if not raw:
            return ""
        split = urlsplit(raw)
        path = split.path or raw.split("?", 1)[0].split("#", 1)[0]
        path = unquote(path).lstrip("/")
        if path.startswith("media/"):
            path = path.removeprefix("media/")
        path = posixpath.normpath(path)
        if path in {"", "."} or path.startswith("../") or path == "..":
            return ""
        return path

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
    def _local_storage() -> FileSystemStorage:
        local_storage = getattr(default_storage, "local_storage", None)
        if local_storage is not None:
            return local_storage
        return FileSystemStorage(
            location=settings.MEDIA_ROOT,
            base_url=getattr(settings, "MEDIA_LEGACY_URL", settings.MEDIA_URL),
        )

    @staticmethod
    def _s3_storage():
        return getattr(default_storage, "s3_storage", None)

    @staticmethod
    def _s3_status(s3_objects: dict[str, int] | None, key: str, local_size: int) -> tuple[str, int | str, str]:
        if s3_objects is None:
            return "unavailable", "", ""
        if key not in s3_objects:
            return "missing", "", ""
        s3_size = int(s3_objects[key])
        if s3_size == local_size:
            return "same_size", s3_size, ""
        return "size_mismatch", s3_size, ""

    @staticmethod
    def _is_inside(path: Path, directory: Path) -> bool:
        try:
            path.relative_to(directory)
            return True
        except ValueError:
            return False
