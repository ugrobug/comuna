from __future__ import annotations

import json

from functools import wraps
from hashlib import sha256
from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers


def _cache_prefix_version_key(prefix: str) -> str:
    return f"public-api:{prefix}:version"


def bump_public_cache_prefix(prefix: str) -> None:
    version_key = _cache_prefix_version_key(prefix)
    try:
        cache.incr(version_key)
    except ValueError:
        cache.set(version_key, 2, timeout=None)


def has_auth_context(request: HttpRequest) -> bool:
    auth_cookie_name = str(
        getattr(settings, "SITE_AUTH_COOKIE_NAME", "comuna_site_token")
        or "comuna_site_token"
    )
    return bool(
        request.META.get("HTTP_AUTHORIZATION")
        or request.COOKIES.get(auth_cookie_name)
        or request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    )


def public_cache_control(response: HttpResponse, *, seconds: int | None = None) -> HttpResponse:
    max_age = int(seconds if seconds is not None else getattr(settings, "PUBLIC_API_CACHE_SECONDS", 60))
    stale = int(getattr(settings, "PUBLIC_API_STALE_SECONDS", 300))
    response["Cache-Control"] = f"public, max-age={max_age}, stale-while-revalidate={stale}"
    return response


def contains_dynamic_invitation(response: HttpResponse) -> bool:
    if getattr(response, "streaming", False) or "application/json" not in response.get("Content-Type", ""):
        return False
    if b'companion' not in response.content:
        return False

    def contains(value):
        if isinstance(value, dict):
            return value.get("type") == "companion" or value.get("kind") == "companion_confirmed" or any(contains(item) for item in value.values())
        return isinstance(value, list) and any(contains(item) for item in value)

    try:
        return contains(json.loads(response.content))
    except (ValueError, UnicodeDecodeError):
        return False


class DynamicPostPrivacyMiddleware:
    """Keep invitations out of intermediary caches, including embedded welcome posts."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if contains_dynamic_invitation(response):
            response["Cache-Control"] = "private, no-store"
        return response


def anonymous_cache(
    *,
    prefix: str,
    seconds: int | None = None,
    cache_authenticated: bool = False,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    timeout = int(seconds if seconds is not None else getattr(settings, "PUBLIC_API_CACHE_SECONDS", 60))

    def decorator(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if request.method not in {"GET", "HEAD"} or (
                has_auth_context(request) and not cache_authenticated
            ):
                response = view_func(request, *args, **kwargs)
                patch_vary_headers(response, ["Cookie", "Authorization"])
                return response

            # Invitation detail/actions must never outlive a match in any cache layer.
            post_id = kwargs.get("post_id")
            if post_id:
                from feeds.models import Post
                if Post.objects.filter(id=post_id, raw_data__template__type="companion").exists():
                    response = view_func(request, *args, **kwargs)
                    response["Cache-Control"] = "private, no-store"
                    return response

            version = cache.get(_cache_prefix_version_key(prefix)) or 1
            key_digest = sha256(request.get_full_path().encode("utf-8")).hexdigest()
            cache_key = f"public-api:{prefix}:v{version}:{key_digest}"
            cached = cache.get(cache_key)
            if cached is not None:
                response = HttpResponse(
                    cached["content"],
                    status=cached["status"],
                    content_type=cached["content_type"],
                )
                for name, value in cached["headers"].items():
                    response[name] = value
                response["X-Cache"] = "HIT"
                return response

            response = view_func(request, *args, **kwargs)
            if not cache_authenticated:
                patch_vary_headers(response, ["Cookie", "Authorization"])
            if contains_dynamic_invitation(response):
                response["Cache-Control"] = "private, no-store"
                return response
            if response.status_code == 200 and "no-store" not in response.get("Cache-Control", ""):
                public_cache_control(response, seconds=timeout)
                cache.set(
                    cache_key,
                    {
                        "content": bytes(response.content),
                        "status": response.status_code,
                        "content_type": response.get("Content-Type", "application/json"),
                        "headers": {
                            name: value
                            for name, value in response.items()
                            if name.lower() not in {"set-cookie", "x-cache"}
                        },
                    },
                    timeout=timeout,
                )
                response["X-Cache"] = "MISS"
            return response

        return wrapped

    return decorator
