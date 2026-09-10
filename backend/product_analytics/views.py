from __future__ import annotations

from datetime import date, timedelta

from django.http import HttpRequest, HttpResponse

from communities.analytics import build_community_analytics
from communities.models import Comun
from moderator.analytics import analytics_period, build_moderator_analytics
from product_analytics.auth import (
    authenticate_analytics_request,
    record_analytics_access,
    secure_json_response,
)
from product_analytics.internal_metrics import build_internal_product_report
from product_analytics.models import SCOPE_COMMUNITY_ANALYTICS, SCOPE_SITE_ANALYTICS
from product_analytics.weekly_report import completed_week


def _method_not_allowed() -> HttpResponse:
    response = secure_json_response({"ok": False, "error": "method not allowed"}, status=405)
    response["Allow"] = "GET"
    return response


def agent_site_analytics(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return _method_not_allowed()
    principal, error = authenticate_analytics_request(
        request,
        required_scope=SCOPE_SITE_ANALYTICS,
    )
    if error is not None:
        return error
    try:
        starts_at, ends_at = analytics_period(request)
    except ValueError as exc:
        return secure_json_response({"ok": False, "error": str(exc)}, status=400)
    if ends_at - starts_at > timedelta(days=366):
        return secure_json_response(
            {"ok": False, "error": "period must not exceed 366 days"},
            status=400,
        )

    payload = build_moderator_analytics(request, starts_at=starts_at, ends_at=ends_at)
    record_analytics_access(principal, endpoint="site")
    return secure_json_response(payload)


def agent_product_analytics(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return _method_not_allowed()
    principal, error = authenticate_analytics_request(
        request,
        required_scope=SCOPE_SITE_ANALYTICS,
    )
    if error is not None:
        return error
    try:
        as_of = date.fromisoformat(request.GET["date"]) if request.GET.get("date") else None
    except ValueError:
        return secure_json_response(
            {"ok": False, "error": "date must use YYYY-MM-DD"},
            status=400,
        )

    periods = [completed_week(as_of, offset) for offset in range(5)]
    payload = build_internal_product_report(periods)
    payload["ok"] = True
    record_analytics_access(principal, endpoint="product")
    return secure_json_response(payload)


def agent_community_analytics_list(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return _method_not_allowed()
    principal, error = authenticate_analytics_request(
        request,
        required_scope=SCOPE_COMMUNITY_ANALYTICS,
    )
    if error is not None:
        return error

    allowed_slugs = set(principal.credential.allowed_community_slugs or [])
    communities = Comun.objects.filter(is_active=True).order_by("name", "id")
    if "*" not in allowed_slugs:
        communities = communities.filter(slug__in=allowed_slugs)
    payload = {
        "ok": True,
        "communities": [
            {
                "id": comun.id,
                "slug": comun.slug,
                "name": comun.name,
                "subscribers_count": int(comun.subscribers_count or 0),
                "analytics_url": f"/api/agent/v1/analytics/communities/{comun.slug}/",
            }
            for comun in communities
        ],
    }
    record_analytics_access(principal, endpoint="communities")
    return secure_json_response(payload)


def agent_community_analytics(request: HttpRequest, slug: str) -> HttpResponse:
    if request.method != "GET":
        return _method_not_allowed()
    principal, error = authenticate_analytics_request(
        request,
        required_scope=SCOPE_COMMUNITY_ANALYTICS,
    )
    if error is not None:
        return error
    if not principal.credential.allows_community(slug):
        return secure_json_response({"ok": False, "error": "not found"}, status=404)

    comun = Comun.objects.filter(slug=slug).first()
    if comun is None:
        return secure_json_response({"ok": False, "error": "not found"}, status=404)
    payload = build_community_analytics(comun)
    record_analytics_access(principal, endpoint="community", community_slug=comun.slug)
    return secure_json_response(payload)
