"""Скачивание wp-content/uploads и подмена URL в контенте поста."""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse, urlunparse

from django.conf import settings

WP_HOSTS = ("posletitrov.ru", "www.posletitrov.ru")
WP_UPLOADS_MARKER = "/wp-content/uploads/"

_WP_URL_IN_TEXT_RE = re.compile(
    r"https?://(?:www\.)?posletitrov\.ru/*wp-content/uploads/[^\s\"'<>\\)]+",
    re.IGNORECASE,
)

_USER_AGENT = "ComunaLegacyMigration/1.0"


def normalize_wp_media_url(url: str) -> str:
    raw = (url or "").strip().rstrip(")'\",;")
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = "https"
    netloc = (parsed.netloc or "").lower().replace("www.", "")
    if netloc not in ("posletitrov.ru",):
        return raw
    path = re.sub(r"/+", "/", parsed.path or "")
    if WP_UPLOADS_MARKER not in path.lower():
        return raw
    return urlunparse((scheme, "posletitrov.ru", path, "", "", ""))


def _url_for_http_fetch(url: str) -> str:
    normalized = normalize_wp_media_url(url)
    parsed = urlparse(normalized)
    path = quote(parsed.path, safe="/:%")
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
    )


def wp_url_to_storage_path(url: str) -> str | None:
    normalized = normalize_wp_media_url(url)
    if not normalized:
        return None
    path = urlparse(normalized).path
    idx = path.lower().find(WP_UPLOADS_MARKER)
    if idx < 0:
        return None
    rel = path[idx + len(WP_UPLOADS_MARKER) :].lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    return f"legacy-wp/uploads/{rel}"


def public_media_url(storage_path: str, *, backend_base: str) -> str:
    base = (backend_base or "").rstrip("/")
    media = settings.MEDIA_URL.rstrip("/")
    return f"{base}{media}/{storage_path.lstrip('/')}"


def public_media_url_relative(storage_path: str) -> str:
    """Путь для nginx/vite: /media/legacy-wp/..."""
    media = settings.MEDIA_URL.rstrip("/")
    return f"{media}/{storage_path.lstrip('/')}"


def url_rewrite_variants(url: str) -> list[str]:
    """Все варианты URL, которые могли попасть в контент при импорте."""
    variants: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        u = (u or "").strip()
        if u and u not in seen:
            seen.add(u)
            variants.append(u)

    add(url)
    norm = normalize_wp_media_url(url)
    add(norm)
    if norm:
        add(norm.replace("https://", "http://"))
        add(norm.replace("https://posletitrov.ru", "http://posletitrov.ru//"))
    parsed = urlparse(url)
    if parsed.path:
        add(f"http://posletitrov.ru//{parsed.path.lstrip('/')}")
    return variants


def extract_wp_upload_urls_from_text(text: str) -> set[str]:
    found: set[str] = set()
    for m in _WP_URL_IN_TEXT_RE.finditer(text or ""):
        found.add(normalize_wp_media_url(m.group(0)))
    return {u for u in found if u}


def extract_wp_upload_urls_from_editor_payload(payload: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(payload, str):
        return extract_wp_upload_urls_from_text(payload)
    if isinstance(payload, dict):
        for value in payload.values():
            urls.update(extract_wp_upload_urls_from_editor_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            urls.update(extract_wp_upload_urls_from_editor_payload(item))
    return urls


def extract_wp_upload_urls_from_post_content(content: str) -> set[str]:
    raw = content or ""
    urls = extract_wp_upload_urls_from_text(raw)
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            urls.update(extract_wp_upload_urls_from_editor_payload(json.loads(stripped)))
        except json.JSONDecodeError:
            pass
    return urls


def rewrite_urls_in_string(text: str, mapping: dict[str, str]) -> str:
    if not text or not mapping:
        return text
    out = text
    for old, new in sorted(mapping.items(), key=lambda x: -len(x[0])):
        if old and new:
            out = out.replace(old, new)
    return out


def rewrite_post_content(content: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return content
    stripped = (content or "").strip()
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return rewrite_urls_in_string(content, mapping)
        updated = json.loads(rewrite_urls_in_string(json.dumps(payload, ensure_ascii=False), mapping))
        return json.dumps(updated, ensure_ascii=False)
    return rewrite_urls_in_string(content, mapping)


def download_wp_media_file(
    url: str,
    *,
    timeout: float = 60.0,
) -> tuple[Path, str]:
    """
    Скачивает файл в MEDIA_ROOT. Возвращает (absolute_path, storage_path).
  """
    storage_path = wp_url_to_storage_path(url)
    if not storage_path:
        raise ValueError(f"не uploads URL: {url}")

    dest = Path(settings.MEDIA_ROOT) / storage_path
    if dest.is_file() and dest.stat().st_size > 0:
        return dest, storage_path

    dest.parent.mkdir(parents=True, exist_ok=True)
    fetch_url = _url_for_http_fetch(url)
    request = urllib.request.Request(fetch_url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ctx) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise OSError(f"HTTP {exc.code} для {fetch_url}") from exc
    except urllib.error.URLError as exc:
        raise OSError(str(exc)) from exc

    if not data:
        raise OSError(f"пустой ответ: {fetch_url}")

    dest.write_bytes(data)
    return dest, storage_path


def build_url_mapping(
    urls: Iterable[str],
    *,
    backend_base: str,
    relative_urls: bool = False,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for url in urls:
        norm = normalize_wp_media_url(url)
        if not norm:
            continue
        try:
            _, storage_path = download_wp_media_file(norm)
        except OSError:
            raise
        if relative_urls:
            new_url = public_media_url_relative(storage_path)
        else:
            new_url = public_media_url(storage_path, backend_base=backend_base)
        for variant in url_rewrite_variants(url):
            mapping[variant] = new_url
        mapping[norm] = new_url
        mapping[url] = new_url
    return mapping


# Любые уже записанные абсолютные URL медиа → относительные /media/...
_ABSOLUTE_MEDIA_RE = re.compile(
    r"https?://[^/]+/media/(legacy-wp/uploads/[^\s\"'<>\\)]+)",
    re.IGNORECASE,
)


def rewrite_absolute_media_urls_to_relative(content: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return f"/media/{match.group(1)}"

    return _ABSOLUTE_MEDIA_RE.sub(repl, content or "")


def wp_thumbnail_attachment_url(wp_post_id: int) -> str | None:
    from legacy_migration.models import WpPostmeta, WpPosts

    meta = (
        WpPostmeta.objects.filter(post_id=wp_post_id, meta_key="_thumbnail_id")
        .order_by("meta_id")
        .first()
    )
    if not meta or not str(meta.meta_value or "").strip().isdigit():
        return None
    att_id = int(meta.meta_value)
    att = WpPosts.objects.filter(id=att_id, post_type="attachment").first()
    if not att:
        return None
    guid = (att.guid or "").strip()
    return normalize_wp_media_url(guid) if guid else None
