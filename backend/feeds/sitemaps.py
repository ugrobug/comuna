from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q, QuerySet
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.http import http_date

from communities.models import Comun
from feeds.models import (
    Author,
    ComunTranslation,
    POST_TRANSLATION_STATUS_TRANSLATED,
    Post,
    PostTranslation,
    StaticPageContent,
    StaticPageTranslation,
    Tag,
)
from feeds.post_paths import build_post_public_path
from landing_pages.models import LandingPage


SITEMAP_MATERIALIZER_VERSION = 2
SITEMAP_SHARD_SIZE = 5_000
ORIGINAL_LANGUAGE = "ru"
TRANSLATED_LANGUAGES = ("en", "es", "pt", "de", "fr", "tr", "id")
PUBLIC_LANGUAGES = (ORIGINAL_LANGUAGE, *TRANSLATED_LANGUAGES)
SITEMAP_FILE_RE = re.compile(r"sitemap(?:-[a-z0-9-]+)?\.xml(?:\.gz)?\Z")

STATIC_RUSSIAN_PATHS = (
    "/",
    "/about",
    "/advertisement",
    "/apps",
    "/authors",
    "/comuns",
    "/privacy",
    "/rules",
    "/s/365-films",
    "/s/book",
    "/s/landname",
)
LOCALIZED_STATIC_SLUGS = {"about", "advertisement", "apps", "authors", "rules"}


@dataclass(frozen=True)
class SitemapAlternate:
    hreflang: str
    href: str


@dataclass(frozen=True)
class SitemapEntry:
    loc: str
    lastmod: str | None = None
    alternates: tuple[SitemapAlternate, ...] = ()


@dataclass(frozen=True)
class SitemapFile:
    filename: str
    lastmod: str
    url_count: int
    bytes_uncompressed: int
    checksum: str


def _base_url(value: str | None = None) -> str:
    base = str(value or getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if not base:
        raise ValueError("SITE_BASE_URL is required to materialize sitemaps")
    return base


def _output_root(value: str | os.PathLike[str] | None = None) -> Path:
    configured = value or getattr(settings, "SITEMAP_OUTPUT_DIR", "")
    if not configured:
        raise ValueError("SITEMAP_OUTPUT_DIR is required to materialize sitemaps")
    return Path(configured)


def _utc_timestamp(value: datetime | None) -> str | None:
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _now_timestamp() -> str:
    return _utc_timestamp(timezone.now()) or ""


def _xml_attr(value: str) -> str:
    return xml_escape(str(value), {'"': "&quot;"})


def _urlset(entries: Iterable[SitemapEntry]) -> str:
    entry_list = list(entries)
    has_alternates = any(entry.alternates for entry in entry_list)
    namespaces = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    if has_alternates:
        namespaces += ' xmlns:xhtml="http://www.w3.org/1999/xhtml"'
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', f"<urlset {namespaces}>"]
    for item in entry_list:
        parts.append(f"<url><loc>{xml_escape(item.loc)}</loc>")
        if item.lastmod:
            parts.append(f"<lastmod>{xml_escape(item.lastmod)}</lastmod>")
        for alternate in item.alternates:
            parts.append(
                '<xhtml:link rel="alternate" '
                f'hreflang="{_xml_attr(alternate.hreflang)}" '
                f'href="{_xml_attr(alternate.href)}" />'
            )
        parts.append("</url>")
    parts.append("</urlset>")
    return "".join(parts)


def _sitemap_index(files: Iterable[SitemapFile], base_url: str) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in sorted(files, key=lambda value: value.filename):
        parts.append(
            f"<sitemap><loc>{xml_escape(f'{base_url}/{item.filename}')}</loc>"
            f"<lastmod>{xml_escape(item.lastmod)}</lastmod></sitemap>"
        )
    parts.append("</sitemapindex>")
    return "".join(parts)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_xml_file(
    root: Path,
    filename: str,
    body: str,
    generated_at: str,
    previous: SitemapFile | None = None,
) -> SitemapFile:
    payload = body.encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()
    source_path = root / filename
    compressed_path = root / f"{filename}.gz"
    if previous and previous.checksum == checksum and source_path.is_file() and compressed_path.is_file():
        try:
            source_is_current = hashlib.sha256(source_path.read_bytes()).hexdigest() == checksum
            compressed_is_current = gzip.decompress(compressed_path.read_bytes()) == payload
        except (OSError, EOFError):
            source_is_current = False
            compressed_is_current = False
        if source_is_current and compressed_is_current:
            source_path.chmod(0o644)
            compressed_path.chmod(0o644)
            return previous
    _atomic_write(source_path, payload)
    _atomic_write(compressed_path, gzip.compress(payload, compresslevel=6, mtime=0))
    return SitemapFile(
        filename=filename,
        lastmod=generated_at,
        url_count=body.count("<url>"),
        bytes_uncompressed=len(payload),
        checksum=checksum,
    )


def _json_value(value):
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, dt_timezone.utc)
        return value.astimezone(dt_timezone.utc).isoformat(timespec="microseconds")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _fingerprint(payload: dict) -> str:
    normalized = json.dumps(_json_value(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_manifest(root: Path) -> dict:
    path = root / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_files(group: dict) -> list[SitemapFile]:
    files = []
    for payload in group.get("files") or []:
        try:
            files.append(SitemapFile(**payload))
        except (TypeError, ValueError):
            return []
    return files


def _files_exist(root: Path, files: Iterable[SitemapFile]) -> bool:
    file_list = list(files)
    return bool(file_list) and all(
        (root / item.filename).is_file() and (root / f"{item.filename}.gz").is_file()
        for item in file_list
    )


def _group_is_stale(group: dict, max_age: timedelta) -> bool:
    generated_at = group.get("generated_at")
    if not generated_at:
        return True
    try:
        value = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    return value <= timezone.now() - max_age


def _range_bounds(item_id: int) -> tuple[int, int]:
    start = ((max(1, int(item_id)) - 1) // SITEMAP_SHARD_SIZE) * SITEMAP_SHARD_SIZE + 1
    return start, start + SITEMAP_SHARD_SIZE - 1


def _ranges_for_queryset(queryset: QuerySet) -> list[tuple[int, int]]:
    max_id = queryset.aggregate(value=Max("id")).get("value") or 0
    return [
        (start, start + SITEMAP_SHARD_SIZE - 1)
        for start in range(1, int(max_id) + 1, SITEMAP_SHARD_SIZE)
    ]


def _public_posts(now=None) -> QuerySet:
    current_time = now or timezone.now()
    return (
        Post.objects.filter(
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=current_time))
        .filter(
            Q(raw_data__special_project__slug__isnull=True)
            | ~Q(raw_data__special_project__slug="book")
        )
    )


def _post_group_fingerprint(queryset: QuerySet) -> tuple[str, int]:
    stats = queryset.aggregate(
        count=Count("id"),
        max_updated=Max("updated_at"),
        max_author_updated=Max("author__updated_at"),
    )
    translations = PostTranslation.objects.filter(
        post_id__in=queryset.values("id"),
        status=POST_TRANSLATION_STATUS_TRANSLATED,
        language__in=PUBLIC_LANGUAGES,
    ).aggregate(count=Count("id"), max_updated=Max("updated_at"))
    payload = {
        "kind": "posts",
        "version": SITEMAP_MATERIALIZER_VERSION,
        "posts": stats,
        "translations": translations,
    }
    return _fingerprint(payload), int(stats.get("count") or 0)


def _post_fallback_titles(post_ids: list[int]) -> dict[int, str]:
    if not post_ids:
        return {}
    from feeds.views import _post_display_title

    posts = Post.objects.filter(id__in=post_ids).only("id", "title", "content", "raw_data")
    return {post.id: _post_display_title(post) for post in posts}


def _build_post_files(queryset: QuerySet, start: int, end: int, base_url: str) -> dict[str, str]:
    translations = PostTranslation.objects.filter(
        status=POST_TRANSLATION_STATUS_TRANSLATED,
        language__in=PUBLIC_LANGUAGES,
    ).only("post_id", "language", "title", "updated_at", "status")
    posts = list(
        queryset.filter(id__gte=start, id__lte=end)
        .only("id", "title", "original_language", "created_at", "updated_at")
        .prefetch_related(Prefetch("translations", queryset=translations, to_attr="_sitemap_translations"))
        .order_by("id")
    )
    fallback_titles = _post_fallback_titles([post.id for post in posts if not (post.title or "").strip()])
    entries_by_language: dict[str, list[SitemapEntry]] = {language: [] for language in PUBLIC_LANGUAGES}

    for post in posts:
        original_title = (post.title or "").strip() or fallback_titles.get(post.id) or "Пост"
        original_language = (
            post.original_language
            if post.original_language in PUBLIC_LANGUAGES
            else ORIGINAL_LANGUAGE
        )
        original_path = build_post_public_path(post.id, original_title)
        if original_language != ORIGINAL_LANGUAGE:
            original_path = f"/{original_language}{original_path}"
        versions: dict[str, tuple[str, str | None]] = {
            original_language: (
                original_path,
                _utc_timestamp(post.updated_at or post.created_at),
            )
        }
        for translation in getattr(post, "_sitemap_translations", []):
            if translation.language == original_language:
                continue
            title = (translation.title or "").strip() or original_title
            path = build_post_public_path(post.id, title)
            if translation.language != ORIGINAL_LANGUAGE:
                path = f"/{translation.language}{path}"
            versions[translation.language] = (path, _utc_timestamp(translation.updated_at))

        alternates = tuple(
            SitemapAlternate(language, f"{base_url}{versions[language][0]}")
            for language in PUBLIC_LANGUAGES
            if language in versions
        ) + (
            SitemapAlternate("x-default", f"{base_url}{versions[original_language][0]}"),
        )
        for language, (path, lastmod) in versions.items():
            entries_by_language[language].append(
                SitemapEntry(loc=f"{base_url}{path}", lastmod=lastmod, alternates=alternates)
            )

    return {
        f"sitemap-posts-{language}-{start:09d}-{end:09d}.xml": _urlset(entries)
        for language, entries in entries_by_language.items()
        if entries
    }


def _public_authors() -> QuerySet:
    return Author.objects.filter(is_blocked=False)


def _author_group_fingerprint(queryset: QuerySet) -> tuple[str, int]:
    stats = queryset.aggregate(count=Count("id"), max_updated=Max("updated_at"))
    return _fingerprint({"kind": "authors", "version": SITEMAP_MATERIALIZER_VERSION, **stats}), int(
        stats.get("count") or 0
    )


def _build_author_files(queryset: QuerySet, start: int, end: int, base_url: str) -> dict[str, str]:
    entries = [
        SitemapEntry(
            loc=f"{base_url}/{quote(author.username, safe='')}",
            lastmod=_utc_timestamp(author.updated_at or author.created_at),
        )
        for author in queryset.filter(id__gte=start, id__lte=end).only(
            "id", "username", "created_at", "updated_at"
        ).order_by("id")
    ]
    return {f"sitemap-authors-{start:09d}-{end:09d}.xml": _urlset(entries)} if entries else {}


def _public_landing_pages() -> QuerySet:
    return LandingPage.objects.filter(is_published=True)


def _landing_page_group_fingerprint(queryset: QuerySet) -> tuple[str, int]:
    stats = queryset.aggregate(count=Count("id"), max_updated=Max("updated_at"))
    return _fingerprint(
        {"kind": "landing-pages", "version": SITEMAP_MATERIALIZER_VERSION, **stats}
    ), int(stats.get("count") or 0)


def _build_landing_page_files(
    queryset: QuerySet,
    start: int,
    end: int,
    base_url: str,
) -> dict[str, str]:
    entries = [
        SitemapEntry(
            loc=f"{base_url}/l/{quote(page.slug, safe='')}",
            lastmod=_utc_timestamp(page.updated_at or page.created_at),
        )
        for page in queryset.filter(id__gte=start, id__lte=end).only(
            "id", "slug", "created_at", "updated_at"
        ).order_by("id")
    ]
    filename = f"sitemap-landing-pages-{start:09d}-{end:09d}.xml"
    return {filename: _urlset(entries)} if entries else {}


def _public_comuns() -> QuerySet:
    return Comun.objects.filter(is_active=True)


def _comun_group_fingerprint(queryset: QuerySet) -> tuple[str, int]:
    stats = queryset.aggregate(count=Count("id"), max_updated=Max("updated_at"))
    translations = ComunTranslation.objects.filter(
        comun_id__in=queryset.values("id"),
        status=POST_TRANSLATION_STATUS_TRANSLATED,
        language__in=TRANSLATED_LANGUAGES,
    ).aggregate(count=Count("id"), max_updated=Max("updated_at"))
    return _fingerprint(
        {
            "kind": "comuns",
            "version": SITEMAP_MATERIALIZER_VERSION,
            "comuns": stats,
            "translations": translations,
        }
    ), int(stats.get("count") or 0)


def _build_comun_files(queryset: QuerySet, start: int, end: int, base_url: str) -> dict[str, str]:
    translations = ComunTranslation.objects.filter(
        status=POST_TRANSLATION_STATUS_TRANSLATED,
        language__in=TRANSLATED_LANGUAGES,
    ).only("comun_id", "language", "updated_at", "status")
    comuns = list(
        queryset.filter(id__gte=start, id__lte=end)
        .only("id", "slug", "created_at", "updated_at")
        .prefetch_related(Prefetch("translations", queryset=translations, to_attr="_sitemap_translations"))
        .order_by("id")
    )
    entries_by_language: dict[str, list[SitemapEntry]] = {language: [] for language in PUBLIC_LANGUAGES}
    for comun in comuns:
        versions: dict[str, tuple[str, str | None]] = {
            ORIGINAL_LANGUAGE: (f"/comuns/{quote(comun.slug, safe='')}", _utc_timestamp(comun.updated_at))
        }
        for translation in getattr(comun, "_sitemap_translations", []):
            versions[translation.language] = (
                f"/{translation.language}/comuns/{quote(comun.slug, safe='')}",
                _utc_timestamp(translation.updated_at),
            )
        alternates = tuple(
            SitemapAlternate(language, f"{base_url}{versions[language][0]}")
            for language in PUBLIC_LANGUAGES
            if language in versions
        ) + (
            SitemapAlternate("x-default", f"{base_url}{versions[ORIGINAL_LANGUAGE][0]}"),
        )
        for language, (path, lastmod) in versions.items():
            entries_by_language[language].append(
                SitemapEntry(loc=f"{base_url}{path}", lastmod=lastmod, alternates=alternates)
            )
    return {
        f"sitemap-comuns-{language}-{start:09d}-{end:09d}.xml": _urlset(entries)
        for language, entries in entries_by_language.items()
        if entries
    }


def _public_tags(now=None) -> QuerySet:
    public_post = _public_posts(now).filter(tags=OuterRef("pk"))
    return Tag.objects.filter(is_active=True).annotate(
        has_public_post=Exists(public_post)
    ).filter(has_public_post=True)


def _tag_group_fingerprint(queryset: QuerySet) -> tuple[str, int]:
    stats = queryset.aggregate(
        count=Count("id"),
        max_updated=Max("updated_at"),
    )
    return _fingerprint({"kind": "tags", "version": SITEMAP_MATERIALIZER_VERSION, **stats}), int(
        stats.get("count") or 0
    )


def _build_tag_files(queryset: QuerySet, start: int, end: int, base_url: str) -> dict[str, str]:
    entries = [
        SitemapEntry(loc=f"{base_url}/tags/{quote(tag.name, safe='')}")
        for tag in queryset.filter(id__gte=start, id__lte=end).only("id", "name").order_by("id")
    ]
    return {f"sitemap-tags-{start:09d}-{end:09d}.xml": _urlset(entries)} if entries else {}


def _static_fingerprint() -> tuple[str, int]:
    pages = StaticPageContent.objects.aggregate(count=Count("id"), max_updated=Max("updated_at"))
    translations = StaticPageTranslation.objects.filter(
        status=POST_TRANSLATION_STATUS_TRANSLATED,
        language__in=TRANSLATED_LANGUAGES,
    ).aggregate(count=Count("id"), max_updated=Max("updated_at"))
    payload = {
        "kind": "static",
        "version": SITEMAP_MATERIALIZER_VERSION,
        "paths": STATIC_RUSSIAN_PATHS,
        "pages": pages,
        "translations": translations,
    }
    return _fingerprint(payload), len(STATIC_RUSSIAN_PATHS) + int(translations.get("count") or 0)


def _build_static_files(base_url: str) -> dict[str, str]:
    pages = {
        page.slug: page
        for page in StaticPageContent.objects.prefetch_related(
            Prefetch(
                "translations",
                queryset=StaticPageTranslation.objects.filter(
                    status=POST_TRANSLATION_STATUS_TRANSLATED,
                    language__in=TRANSLATED_LANGUAGES,
                ).only("page_id", "language", "updated_at", "status"),
                to_attr="_sitemap_translations",
            )
        ).only("id", "slug", "created_at", "updated_at")
    }
    entries_by_language: dict[str, list[SitemapEntry]] = {language: [] for language in PUBLIC_LANGUAGES}
    for path in STATIC_RUSSIAN_PATHS:
        slug = path.strip("/")
        page = pages.get(slug)
        versions: dict[str, tuple[str, str | None]] = {
            ORIGINAL_LANGUAGE: (path, _utc_timestamp(page.updated_at) if page else None)
        }
        if page and slug in LOCALIZED_STATIC_SLUGS:
            for translation in getattr(page, "_sitemap_translations", []):
                versions[translation.language] = (
                    f"/{translation.language}/{slug}",
                    _utc_timestamp(translation.updated_at),
                )
        alternates = tuple(
            SitemapAlternate(language, f"{base_url}{versions[language][0]}")
            for language in PUBLIC_LANGUAGES
            if language in versions
        ) + (SitemapAlternate("x-default", f"{base_url}{path}"),)
        for language, (version_path, lastmod) in versions.items():
            entries_by_language[language].append(
                SitemapEntry(f"{base_url}{version_path}", lastmod=lastmod, alternates=alternates)
            )
    files = {"sitemap-static.xml": _urlset(entries_by_language[ORIGINAL_LANGUAGE])}
    files.update(
        {
            f"sitemap-static-{language}.xml": _urlset(entries)
            for language, entries in entries_by_language.items()
            if language != ORIGINAL_LANGUAGE and entries
        }
    )
    return files


def _materialize_group(
    *,
    root: Path,
    previous: dict,
    fingerprint: str,
    force: bool,
    max_age: timedelta,
    build: Callable[[], dict[str, str]],
) -> dict:
    previous_files = _manifest_files(previous)
    should_build = (
        force
        or previous.get("fingerprint") != fingerprint
        or not _files_exist(root, previous_files)
        or _group_is_stale(previous, max_age)
    )
    if not should_build:
        return previous

    generated_at = _now_timestamp()
    previous_by_filename = {item.filename: item for item in previous_files}
    files = [
        _write_xml_file(
            root,
            filename,
            body,
            generated_at,
            previous=previous_by_filename.get(filename),
        )
        for filename, body in sorted(build().items())
    ]
    return {
        "fingerprint": fingerprint,
        "generated_at": generated_at,
        "files": [asdict(item) for item in files],
    }


def _remove_orphans(root: Path, expected: set[str]) -> None:
    for path in root.glob("sitemap*.xml*"):
        if path.name not in expected and path.is_file():
            path.unlink()


def materialize_sitemaps(
    *,
    output_dir: str | os.PathLike[str] | None = None,
    site_base_url: str | None = None,
    force: bool = False,
    max_age: timedelta = timedelta(hours=24),
) -> dict:
    root = _output_root(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    base_url = _base_url(site_base_url)

    with (root / ".materialize.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        previous_manifest = _load_manifest(root)
        manifest_changed = (
            previous_manifest.get("version") != SITEMAP_MATERIALIZER_VERSION
            or previous_manifest.get("base_url") != base_url
            or previous_manifest.get("shard_size") != SITEMAP_SHARD_SIZE
        )
        force = force or manifest_changed
        previous_groups = previous_manifest.get("groups") or {}
        groups: dict[str, dict] = {}

        static_fingerprint, _ = _static_fingerprint()
        groups["static"] = _materialize_group(
            root=root,
            previous=previous_groups.get("static") or {},
            fingerprint=static_fingerprint,
            force=force,
            max_age=max_age,
            build=lambda: _build_static_files(base_url),
        )

        specifications = (
            ("posts", _public_posts(), _post_group_fingerprint, _build_post_files),
            ("authors", _public_authors(), _author_group_fingerprint, _build_author_files),
            (
                "landing-pages",
                _public_landing_pages(),
                _landing_page_group_fingerprint,
                _build_landing_page_files,
            ),
            ("comuns", _public_comuns(), _comun_group_fingerprint, _build_comun_files),
            ("tags", _public_tags(), _tag_group_fingerprint, _build_tag_files),
        )
        for kind, base_queryset, signature_builder, file_builder in specifications:
            for start, end in _ranges_for_queryset(base_queryset):
                queryset = base_queryset.filter(id__gte=start, id__lte=end)
                fingerprint, count = signature_builder(queryset)
                if count <= 0:
                    continue
                key = f"{kind}:{start}:{end}"
                groups[key] = _materialize_group(
                    root=root,
                    previous=previous_groups.get(key) or {},
                    fingerprint=fingerprint,
                    force=force,
                    max_age=max_age,
                    build=lambda qs=base_queryset, lo=start, hi=end, builder=file_builder: builder(
                        qs, lo, hi, base_url
                    ),
                )

        all_files = [item for group in groups.values() for item in _manifest_files(group)]
        index_generated_at = _now_timestamp()
        index_body = _sitemap_index(all_files, base_url)
        previous_index = None
        try:
            previous_index = SitemapFile(**(previous_manifest.get("index") or {}))
        except (TypeError, ValueError):
            pass
        index_file = _write_xml_file(
            root,
            "sitemap.xml",
            index_body,
            index_generated_at,
            previous=previous_index,
        )

        expected = {"sitemap.xml", "sitemap.xml.gz"}
        for item in all_files:
            expected.add(item.filename)
            expected.add(f"{item.filename}.gz")
        _remove_orphans(root, expected)

        manifest = {
            "version": SITEMAP_MATERIALIZER_VERSION,
            "base_url": base_url,
            "shard_size": SITEMAP_SHARD_SIZE,
            "generated_at": index_generated_at,
            "index": asdict(index_file),
            "groups": groups,
        }
        _atomic_write(
            root / "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )
        return manifest


def materialized_sitemap_file(request: HttpRequest, filename: str = "sitemap.xml") -> HttpResponse:
    if not SITEMAP_FILE_RE.fullmatch(filename):
        raise Http404
    path = _output_root() / filename
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open("rb"), content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=300"
    response["Last-Modified"] = http_date(path.stat().st_mtime)
    if filename.endswith(".gz"):
        response["Content-Encoding"] = "gzip"
    return response
