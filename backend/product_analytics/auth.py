from __future__ import annotations

import ipaddress
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from product_analytics.models import AnalyticsApiAccessLog, AnalyticsApiCredential
from rabotaem_backend.rate_limit import client_ip


@dataclass(frozen=True)
class AnalyticsApiPrincipal:
    credential: AnalyticsApiCredential
    ip_address: str | None


def _error_response(error: str, *, status: int) -> JsonResponse:
    response = JsonResponse({"ok": False, "error": error}, status=status)
    response["Cache-Control"] = "no-store"
    if status == 401:
        response["WWW-Authenticate"] = 'Bearer realm="Tambur analytics API"'
    return response


def _raw_bearer_token(request: HttpRequest) -> str:
    authorization = str(request.headers.get("Authorization") or "").strip()
    if not authorization.startswith("Bearer "):
        return ""
    return authorization[7:].strip()


def _token_prefix(raw_token: str) -> str:
    marker = "tambur_analytics_"
    if not raw_token.startswith(marker) or "." not in raw_token:
        return ""
    return raw_token[len(marker) :].split(".", 1)[0]


def _ip_is_allowed(credential: AnalyticsApiCredential, address: str | None) -> bool:
    networks = credential.allowed_ip_networks or []
    if not networks:
        return True
    if not address:
        return False
    try:
        parsed_address = ipaddress.ip_address(address)
    except ValueError:
        return False
    for value in networks:
        try:
            if parsed_address in ipaddress.ip_network(str(value), strict=False):
                return True
        except ValueError:
            continue
    return False


def _credential_is_rate_limited(credential_id: int, limit: int) -> bool:
    if limit <= 0:
        return False
    if AnalyticsApiAccessLog.objects.filter(
        credential_id=credential_id,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).count() >= limit:
        return True
    key = f"rl:analytics-api:credential:{credential_id}"
    try:
        if cache.add(key, 1, timeout=60):
            return False
        return cache.incr(key) > limit
    except Exception:
        return False


def authenticate_analytics_request(
    request: HttpRequest,
    *,
    required_scope: str,
) -> tuple[AnalyticsApiPrincipal | None, JsonResponse | None]:
    if bool(getattr(settings, "ANALYTICS_API_REQUIRE_HTTPS", True)) and not request.is_secure():
        return None, _error_response("HTTPS required", status=403)
    raw_token = _raw_bearer_token(request)
    key_prefix = _token_prefix(raw_token)
    if not key_prefix:
        return None, _error_response("unauthorized", status=401)

    credential = AnalyticsApiCredential.objects.filter(key_prefix=key_prefix).first()
    if (
        credential is None
        or not secrets.compare_digest(
            credential.token_hash,
            AnalyticsApiCredential.hash_token(raw_token),
        )
        or not credential.is_active()
    ):
        return None, _error_response("unauthorized", status=401)
    if not credential.has_scope(required_scope):
        return None, _error_response("forbidden", status=403)

    # Nginx overwrites X-Real-IP from its trusted upstream chain. X-Forwarded-For
    # can contain client-supplied entries, so it is only a fallback for local tests.
    address = str(request.META.get("HTTP_X_REAL_IP") or client_ip(request)).strip()
    if not _ip_is_allowed(credential, address):
        return None, _error_response("forbidden", status=403)

    limit = int(getattr(settings, "ANALYTICS_API_RATE_LIMIT_PER_MINUTE", 60))
    if _credential_is_rate_limited(credential.id, limit):
        response = _error_response("rate limit exceeded", status=429)
        response["Retry-After"] = "60"
        return None, response

    AnalyticsApiCredential.objects.filter(pk=credential.pk).update(
        last_used_at=timezone.now(),
        last_used_ip=address if address != "unknown" else None,
    )
    return AnalyticsApiPrincipal(
        credential=credential,
        ip_address=address if address != "unknown" else None,
    ), None


def record_analytics_access(
    principal: AnalyticsApiPrincipal,
    *,
    endpoint: str,
    community_slug: str = "",
) -> None:
    AnalyticsApiAccessLog.objects.create(
        credential=principal.credential,
        endpoint=endpoint,
        community_slug=community_slug,
        ip_address=principal.ip_address,
    )


def secure_json_response(payload: dict, *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization"
    response["X-Content-Type-Options"] = "nosniff"
    return response
