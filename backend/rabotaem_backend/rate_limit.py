from __future__ import annotations

import hashlib
from typing import Iterable

from django.core.cache import cache
from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str:
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0].strip()
    return forwarded_for or request.META.get("REMOTE_ADDR") or "unknown"


def _client_fingerprint(request: HttpRequest) -> str:
    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:160]
    raw_value = f"{client_ip(request)}:{user_agent}"
    return hashlib.sha256(raw_value.encode("utf-8", "ignore")).hexdigest()[:32]


def _key(scope: str, request: HttpRequest, identifiers: Iterable[object]) -> str:
    normalized_identifiers = ":".join(str(item)[:120] for item in identifiers if item is not None)
    raw_value = f"{scope}:{_client_fingerprint(request)}:{normalized_identifiers}"
    digest = hashlib.sha256(raw_value.encode("utf-8", "ignore")).hexdigest()
    return f"rl:{scope}:{digest}"


def is_rate_limited(
    request: HttpRequest,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    identifiers: Iterable[object] = (),
) -> bool:
    if limit <= 0 or window_seconds <= 0:
        return False
    key = _key(scope, request, identifiers)
    try:
        if cache.add(key, 1, timeout=window_seconds):
            return False
        count = cache.incr(key)
        return count > limit
    except Exception:
        # Availability wins over throttling if the cache backend is unavailable.
        return False
