"""Связи Tambur Post ↔ WP из pt_tambur_post_links.csv (без дублей при import_wp_posts)."""

from __future__ import annotations

import csv
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from feeds.models import Post
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.wp_content import legacy_article_source_url

# Относительно корня Django-проекта (backend/ локально, /app в Docker).
DEFAULT_LINKS_CSV = "legacy_migration/pt_tambur_post_links.csv"


def backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_links_path(raw: str) -> Path:
    p = Path((raw or "").strip() or DEFAULT_LINKS_CSV)
    if p.is_absolute():
        return p

    backend = backend_root()
    candidates = [
        backend / p,
        backend.parent / p,
    ]
    if p.parts and p.parts[0] == "backend":
        candidates.insert(0, backend / Path(*p.parts[1:]))

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def parse_links_csv(path: Path) -> list[tuple[int, int]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Пустой CSV: {path}")
        required = {"tambur_post_id", "wp_post_id"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"В {path} нет колонок: {', '.join(sorted(missing))}")
        pairs: list[tuple[int, int]] = []
        for line_no, row in enumerate(reader, start=2):
            if (row.get("enabled") or "1").strip().lower() in ("0", "false", "no"):
                continue
            t_raw = (row.get("tambur_post_id") or "").strip()
            w_raw = (row.get("wp_post_id") or "").strip()
            if not t_raw or not w_raw:
                continue
            if not t_raw.isdigit() or not w_raw.isdigit():
                raise ValueError(f"{path}:{line_no} некорректные id")
            pairs.append((int(t_raw), int(w_raw)))
        return pairs


def apply_title_post_links(
    *,
    path: Path,
    dry_run: bool,
    force_overwrite: bool,
    patch_raw_data: bool = True,
) -> dict[str, int]:
    if not path.is_file():
        return {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "missing_file": 1}

    pairs = parse_links_csv(path)
    if not pairs:
        return {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "missing_file": 0}

    wp_ids = [w for _, w in pairs]
    tambur_ids = [t for t, _ in pairs]

    wp_by_id = {int(wp.id): wp for wp in WpPosts.objects.filter(id__in=wp_ids)}
    post_by_id = {int(p.id): p for p in Post.objects.filter(id__in=tambur_ids)}
    existing = {
        int(m.wp_post_id): m
        for m in LegacyWpPostMap.objects.filter(wp_post_id__in=wp_ids)
    }

    created = updated = skipped = errors = 0
    now = timezone.now()

    for t_id, w_id in pairs:
        wp_post = wp_by_id.get(w_id)
        post = post_by_id.get(t_id)
        if not wp_post:
            errors += 1
            continue
        if not post:
            errors += 1
            continue

        map_row = existing.get(w_id)
        if map_row and map_row.post_id and int(map_row.post_id) != t_id and not force_overwrite:
            skipped += 1
            continue

        slug = (wp_post.post_name or "").strip()
        legacy_url = legacy_article_source_url(slug, wp_post.guid or "")

        if dry_run:
            if map_row and map_row.post_id == t_id:
                skipped += 1
            elif map_row:
                updated += 1
            else:
                created += 1
            continue

        with transaction.atomic():
            LegacyWpPostMap.objects.update_or_create(
                wp_post_id=w_id,
                defaults={
                    "legacy_slug": slug,
                    "legacy_url": legacy_url,
                    "post_id": t_id,
                    "imported_at": now,
                    "notes": "title_match",
                },
            )
            if patch_raw_data:
                raw = post.raw_data if isinstance(post.raw_data, dict) else {}
                merged = {
                    **raw,
                    "legacy_wp_id": w_id,
                    "legacy_slug": slug,
                    "source": raw.get("source") or "wordpress",
                }
                if post.raw_data != merged:
                    post.raw_data = merged
                    post.save(update_fields=["raw_data"])

        if map_row and map_row.post_id == t_id:
            skipped += 1
        elif map_row:
            updated += 1
        else:
            created += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "missing_file": 0,
    }
