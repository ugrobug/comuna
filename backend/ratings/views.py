from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse

from rabotaem_backend.cache import anonymous_cache
from ratings import serializers as ratings_serializers
from ratings import service as ratings_service

_serialize_top_author_item = ratings_serializers.serialize_top_author_item
_serialize_top_comun_item = ratings_serializers.serialize_top_comun_item
_list_top_authors = ratings_service.list_top_authors
_list_top_comuns = ratings_service.list_top_comuns
_normalize_top_authors_period = ratings_service.normalize_top_authors_period
_parse_top_authors_limit = ratings_service.parse_top_authors_limit


def _top_authors_response(request: HttpRequest, *, default_period: str = "month") -> HttpResponse:
    period = _normalize_top_authors_period(request.GET.get("period"), default=default_period)
    limit = _parse_top_authors_limit(request.GET.get("limit"), default=5)
    normalized_period, authors, total_authors = _list_top_authors(period=period, limit=limit)

    return JsonResponse(
        {
            "ok": True,
            "period": normalized_period,
            "authors": [
                _serialize_top_author_item(author, request=request, period=normalized_period)
                for author in authors
            ],
            "total_authors": total_authors,
        }
    )


@anonymous_cache(prefix="top-authors", seconds=120)
def top_authors(request: HttpRequest) -> HttpResponse:
    return _top_authors_response(request)


@anonymous_cache(prefix="top-authors-month", seconds=120)
def top_authors_month(request: HttpRequest) -> HttpResponse:
    return _top_authors_response(request, default_period="month")


@anonymous_cache(prefix="top-comuns", seconds=21_600, cache_authenticated=True)
def top_comuns(request: HttpRequest) -> HttpResponse:
    limit = _parse_top_authors_limit(request.GET.get("limit"), default=5)
    comuns, total_comuns = _list_top_comuns(limit=limit)
    return JsonResponse(
        {
            "ok": True,
            "comuns": [
                _serialize_top_comun_item(comun, request=request)
                for comun in comuns
            ],
            "total_comuns": total_comuns,
        }
    )


def top_comuns_month(request: HttpRequest) -> HttpResponse:
    return top_comuns(request)


__all__ = [
    "top_authors",
    "top_authors_month",
    "top_comuns",
    "top_comuns_month",
]
