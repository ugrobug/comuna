from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

from rabotaem_backend.rate_limit import client_ip

logger = logging.getLogger(__name__)

_UNKNOWN_COUNTRY = "--"


def _normalized_ip(request: HttpRequest) -> str:
    # nginx overwrites X-Real-IP with the actual peer address. Prefer it over
    # X-Forwarded-For, which can contain a client-supplied leading value.
    value = str(request.META.get("HTTP_X_REAL_IP") or client_ip(request)).strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def _country_cache_key(ip: str) -> str:
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    return f"auth-country:{digest}"


def _lookup_country(ip: str) -> str:
    if not ip:
        return ""
    try:
        parsed_ip = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    if not parsed_ip.is_global:
        return str(getattr(settings, "AUTH_LOCAL_COUNTRY_CODE", "") or "").strip().upper()[:2]

    cache_key = _country_cache_key(ip)
    cached = cache.get(cache_key)
    if cached is not None:
        return "" if cached == _UNKNOWN_COUNTRY else str(cached)

    url_template = str(
        getattr(settings, "AUTH_COUNTRY_LOOKUP_URL", "https://api.country.is/{ip}") or ""
    ).strip()
    if not url_template:
        return ""
    timeout = float(getattr(settings, "AUTH_COUNTRY_LOOKUP_TIMEOUT_SECONDS", 2.0))
    url = url_template.format(ip=urllib.parse.quote(ip, safe=":"))
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "TamburAuth/1.0"},
    )
    country_code = ""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(4096).decode("utf-8"))
        country_code = str(payload.get("country") or "").strip().upper()
        if len(country_code) != 2 or not country_code.isalpha():
            country_code = ""
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        logger.warning("Auth country lookup failed for %s: %s", ip, exc)

    if country_code:
        cache.set(
            cache_key,
            country_code,
            timeout=int(getattr(settings, "AUTH_COUNTRY_CACHE_SECONDS", 24 * 60 * 60)),
        )
    else:
        cache.set(
            cache_key,
            _UNKNOWN_COUNTRY,
            timeout=int(getattr(settings, "AUTH_COUNTRY_FAILURE_CACHE_SECONDS", 5 * 60)),
        )
    return country_code


def country_code_for_request(request: HttpRequest) -> str:
    return _lookup_country(_normalized_ip(request))


def auth_methods_for_request(request: HttpRequest) -> dict[str, object]:
    country_code = country_code_for_request(request)
    is_russia = country_code == "RU"
    region = "russia" if is_russia else "international" if country_code else "unknown"

    configured = {
        "email": bool(getattr(settings, "ALLOW_PASSWORD_REGISTRATION", False)),
        "vk": bool(str(getattr(settings, "VK_APP_ID", "") or "").strip()),
        "google": bool(str(getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()),
        "apple": bool(str(getattr(settings, "APPLE_OAUTH_CLIENT_ID", "") or "").strip()),
        "telegram": bool(str(getattr(settings, "TELEGRAM_OIDC_CLIENT_ID", "") or "").strip()),
    }
    allowed = {
        "email": True,
        "vk": is_russia,
        "google": region == "international",
        "apple": region == "international",
        "telegram": region == "international",
    }
    methods = {
        name: bool(allowed[name] and (configured[name] or name == "email"))
        for name in allowed
    }
    return {
        "country_code": country_code or None,
        "region": region,
        "methods": methods,
        "allowed_methods": allowed,
        "configured_methods": configured,
    }


__all__ = ["auth_methods_for_request", "country_code_for_request"]
