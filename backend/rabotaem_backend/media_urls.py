from __future__ import annotations

import re
import urllib.parse
from typing import Any

from django.conf import settings
from django.http import HttpRequest

_S3_PUBLIC_MODES = {"s3", "s3-first", "s3_first", "s3_public", "s3-public"}
_URL_CANDIDATE_RE = re.compile(r"https?://[^\s\"'<>\\]+|(?<![:\w/])/[^\s\"'<>\\]+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:)]}"


def public_media_urls_prefer_s3() -> bool:
    mode = str(getattr(settings, "MEDIA_PUBLIC_URL_MODE", "legacy") or "legacy").strip().lower()
    return mode in _S3_PUBLIC_MODES


def _host(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").strip().lower().rstrip(".")


def _site_hosts(request: HttpRequest | None = None) -> set[str]:
    hosts = {
        "tambur.pub",
        "www.tambur.pub",
        "comuna.ru",
        "www.comuna.ru",
        "localhost",
        "127.0.0.1",
    }
    site_host = _host(str(getattr(settings, "SITE_BASE_URL", "") or ""))
    if site_host:
        hosts.add(site_host)
    if request is not None:
        try:
            request_host = _host(request.get_host())
        except Exception:
            request_host = ""
        if request_host:
            hosts.add(request_host)
    return hosts


def _media_prefixes() -> tuple[str, ...]:
    values = [
        str(getattr(settings, "MEDIA_LEGACY_URL", "") or ""),
        str(getattr(settings, "MEDIA_URL", "") or ""),
        "/media/",
    ]
    prefixes: list[str] = []
    for value in values:
        parsed = urllib.parse.urlparse(value)
        path = parsed.path if parsed.scheme or parsed.netloc else value
        if not path:
            continue
        if not path.startswith("/"):
            path = f"/{path}"
        if not path.endswith("/"):
            path = f"{path}/"
        if path not in prefixes:
            prefixes.append(path)
    return tuple(prefixes)


def _path_after_prefix(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix):
        return None
    return urllib.parse.unquote(path[len(prefix) :]).lstrip("/")


def _path_after_media_prefix(path: str) -> str | None:
    for prefix in _media_prefixes():
        result = _path_after_prefix(path, prefix)
        if result:
            return result
    return None


def _s3_public_base_url() -> str:
    explicit_base = str(
        getattr(settings, "MEDIA_S3_PUBLIC_BASE_URL", "")
        or getattr(settings, "MEDIA_PUBLIC_BASE_URL", "")
        or ""
    ).strip()
    if explicit_base:
        base = explicit_base
    else:
        custom_domain = str(getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "") or "").strip().strip("/")
        if not custom_domain:
            return ""
        base = custom_domain if "://" in custom_domain else f"https://{custom_domain}"

    location = str(getattr(settings, "AWS_LOCATION", "") or "").strip("/")
    parsed = urllib.parse.urlparse(base)
    base_path = parsed.path.rstrip("/")
    if location and location not in [part for part in base_path.split("/") if part]:
        base_path = f"{base_path}/{location}" if base_path else f"/{location}"
        base = urllib.parse.urlunparse(parsed._replace(path=base_path))
    return base.rstrip("/")


def _s3_storage_path(parsed: urllib.parse.ParseResult) -> str | None:
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return None

    public_base_host = _host(_s3_public_base_url())
    custom_domain_host = _host(str(getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "") or ""))
    location = str(getattr(settings, "AWS_LOCATION", "") or "").strip("/")
    path = parsed.path or ""

    if hostname in {host for host in (public_base_host, custom_domain_host) if host}:
        if location:
            path_with_location = f"/{location}/"
            if path.startswith(path_with_location):
                return urllib.parse.unquote(path[len(path_with_location) :]).lstrip("/")
        return urllib.parse.unquote(path).lstrip("/")

    endpoint_host = _host(str(getattr(settings, "AWS_S3_ENDPOINT_URL", "") or ""))
    bucket = str(getattr(settings, "AWS_STORAGE_BUCKET_NAME", "") or "").strip()
    if endpoint_host and bucket:
        if hostname == endpoint_host:
            bucket_prefix = f"/{bucket}/"
            if path.startswith(bucket_prefix):
                return urllib.parse.unquote(path[len(bucket_prefix) :]).lstrip("/")
        if hostname == f"{bucket}.{endpoint_host}":
            return urllib.parse.unquote(path).lstrip("/")
    return None


def media_storage_path_from_url(
    value: object,
    *,
    request: HttpRequest | None = None,
    allow_storage_key: bool = False,
) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value or raw_value.startswith(("data:", "blob:", "#")):
        return None
    if raw_value.startswith("//"):
        raw_value = f"https:{raw_value}"

    parsed = urllib.parse.urlparse(raw_value)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None

    if parsed.scheme or parsed.netloc:
        s3_path = _s3_storage_path(parsed)
        if s3_path:
            return s3_path
        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        if hostname in _site_hosts(request):
            return _path_after_media_prefix(parsed.path or "")
        return None

    path = parsed.path or raw_value
    media_path = _path_after_media_prefix(path)
    if media_path:
        return media_path
    if allow_storage_key and path and not path.startswith("/") and "://" not in path:
        return urllib.parse.unquote(path).lstrip("/")
    return None


def _quote_storage_path(path: str) -> str:
    return "/".join(
        urllib.parse.quote(part, safe="!$&'()*+,;=:@-._~%")
        for part in str(path or "").strip().lstrip("/").split("/")
        if part
    )


def site_absolute_url(value: object, *, request: HttpRequest | None = None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    if raw_value.startswith("//"):
        return f"https:{raw_value}"
    if raw_value.startswith(("http://", "https://")):
        return raw_value
    site_base = str(getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    path = raw_value if raw_value.startswith("/") else f"/{raw_value}"
    if site_base:
        return f"{site_base}{path}"
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            return raw_value
    return raw_value


def public_media_url(value: object, *, request: HttpRequest | None = None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    storage_path = media_storage_path_from_url(
        raw_value,
        request=request,
        allow_storage_key=True,
    )
    if not storage_path:
        return raw_value if raw_value.startswith(("http://", "https://")) else site_absolute_url(raw_value, request=request)

    parsed = urllib.parse.urlparse(raw_value if not raw_value.startswith("//") else f"https:{raw_value}")
    if not public_media_urls_prefer_s3() and (parsed.scheme or parsed.netloc) and _s3_storage_path(parsed):
        return raw_value

    if public_media_urls_prefer_s3():
        base_url = _s3_public_base_url()
        if base_url:
            return f"{base_url}/{_quote_storage_path(storage_path)}"

    media_url = str(getattr(settings, "MEDIA_LEGACY_URL", "") or getattr(settings, "MEDIA_URL", "/media/") or "/media/")
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"
    return site_absolute_url(f"{media_url}{_quote_storage_path(storage_path)}", request=request)


def public_url(value: object, *, request: HttpRequest | None = None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    if media_storage_path_from_url(raw_value, request=request):
        return public_media_url(raw_value, request=request)
    return site_absolute_url(raw_value, request=request) if raw_value.startswith("/") else raw_value


def rewrite_public_media_urls(value: object, *, request: HttpRequest | None = None) -> str:
    text = str(value or "")
    if not text or not public_media_urls_prefer_s3():
        return text

    def replace(match: re.Match[str]) -> str:
        matched = match.group(0)
        candidate = matched
        suffix = ""
        while candidate and candidate[-1] in _TRAILING_PUNCTUATION:
            suffix = candidate[-1] + suffix
            candidate = candidate[:-1]
        if not media_storage_path_from_url(candidate, request=request):
            return matched
        return f"{public_media_url(candidate, request=request)}{suffix}"

    return _URL_CANDIDATE_RE.sub(replace, text)


def rewrite_public_media_payload(value: Any, *, request: HttpRequest | None = None) -> Any:
    if isinstance(value, str):
        return rewrite_public_media_urls(value, request=request)
    if isinstance(value, list):
        return [rewrite_public_media_payload(item, request=request) for item in value]
    if isinstance(value, tuple):
        return tuple(rewrite_public_media_payload(item, request=request) for item in value)
    if isinstance(value, dict):
        return {
            key: rewrite_public_media_payload(item, request=request)
            for key, item in value.items()
        }
    return value
