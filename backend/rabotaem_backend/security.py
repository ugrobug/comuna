from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, JsonResponse


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_host(value: str) -> str:
    parsed = urlparse(value)
    return (parsed.netloc or "").lower()


def _trusted_hosts() -> set[str]:
    hosts: set[str] = set()
    for value in getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
        host = _origin_host(str(value).replace("*.", ""))
        if host:
            hosts.add(host)
    site_base = str(getattr(settings, "SITE_BASE_URL", "") or "").strip()
    if site_base:
        host = _origin_host(site_base)
        if host:
            hosts.add(host)
    return hosts


def _telegram_auth_origin_hosts() -> set[str]:
    hosts: set[str] = set()
    for value in getattr(settings, "TELEGRAM_AUTH_ALLOWED_ORIGINS", []):
        host = _origin_host(str(value))
        if host:
            hosts.add(host)
    return hosts


def _is_telegram_auth_origin(request: HttpRequest, origin: str) -> bool:
    path = request.path_info.rstrip("/")
    if path != "/api/auth/telegram":
        return False
    origin_host = _origin_host(origin)
    return bool(origin_host and origin_host in _telegram_auth_origin_hosts())


def _is_allowed_origin(request: HttpRequest, origin: str) -> bool:
    origin_host = _origin_host(origin)
    if not origin_host:
        return True
    request_host = request.get_host().lower()
    return (
        origin_host == request_host
        or origin_host in _trusted_hosts()
        or _is_telegram_auth_origin(request, origin)
    )


class UnsafeOriginProtectionMiddleware:
    """Protect csrf_exempt JSON endpoints from browser cross-site writes.

    Non-browser clients and Telegram webhooks usually do not send Origin/Referer,
    so absent headers are allowed. Browsers do send them for cross-site unsafe
    requests, which lets us block CSRF even on legacy csrf_exempt views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("Origin") or ""
            referer = request.headers.get("Referer") or ""
            candidate = origin or (referer if request.is_secure() else "")
            if candidate and not _is_allowed_origin(request, candidate):
                return JsonResponse({"ok": False, "error": "forbidden origin"}, status=403)
        return self.get_response(request)
