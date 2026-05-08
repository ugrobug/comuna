from __future__ import annotations

import json
import os
import secrets

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import F, Max
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, UnidentifiedImageError

from special_projects.models import (
    SpecialProjectGeneratedPhrase,
    SpecialProjectLetterImage,
    SpecialProjectLetterSuggestion,
)
from special_projects.service import (
    LANDNAME_PROJECT_SLUG,
    alphabet_payload,
    map_url_for_coordinates,
    normalize_letter,
    normalize_landname_text,
    parse_coordinates,
    render_landname,
    serialize_letter_image,
    tile_svg,
)
from users.service import _get_user_from_request


def landname_render(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    payload = render_landname(request, request.GET.get("text", ""))
    if request.GET.get("track") == "1" and payload.get("text"):
        generation = SpecialProjectGeneratedPhrase.objects.create(
            project_slug=LANDNAME_PROJECT_SLUG,
            text=payload["text"],
            share_query=payload.get("share_query", payload["text"]),
            generated_by=_get_user_from_request(request),
        )
        payload["generation_id"] = generation.id
    else:
        payload["generation_id"] = None
    return JsonResponse(payload)


def landname_alphabet(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    return JsonResponse(alphabet_payload(request))


@csrf_exempt
def landname_share_event(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    generation = None
    raw_generation_id = payload.get("generation_id")
    if raw_generation_id not in (None, ""):
        try:
            generation_id = int(raw_generation_id)
        except (TypeError, ValueError):
            generation_id = None
        if generation_id is not None:
            generation = SpecialProjectGeneratedPhrase.objects.filter(
                id=generation_id,
                project_slug=LANDNAME_PROJECT_SLUG,
            ).first()

    if generation is None:
        text = normalize_landname_text(str(payload.get("text", "")))
        if not text:
            return JsonResponse({"ok": False, "error": "empty text"}, status=400)
        generation = SpecialProjectGeneratedPhrase.objects.create(
            project_slug=LANDNAME_PROJECT_SLUG,
            text=text,
            share_query=text,
            generated_by=_get_user_from_request(request),
        )

    now = timezone.now()
    SpecialProjectGeneratedPhrase.objects.filter(id=generation.id).update(
        was_shared=True,
        share_clicks=F("share_clicks") + 1,
        shared_at=now,
        updated_at=now,
    )
    generation.refresh_from_db(fields=("was_shared", "share_clicks", "shared_at", "updated_at"))
    return JsonResponse(
        {
            "ok": True,
            "generation": {
                "id": generation.id,
                "text": generation.text,
                "was_shared": generation.was_shared,
                "share_clicks": generation.share_clicks,
                "shared_at": generation.shared_at.isoformat() if generation.shared_at else None,
            },
        }
    )


@csrf_exempt
def landname_suggestions(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if user is None:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    try:
        letter = normalize_letter(str(payload.get("letter", "")))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    map_url = str(payload.get("map_url", "") or "").strip()
    coordinates_text = str(payload.get("coordinates", "") or "").strip()
    location_note = str(payload.get("location_note", "") or "").strip()[:280]

    lat, lng = parse_coordinates(" ".join([coordinates_text, map_url]))
    if not map_url and lat is None:
        return JsonResponse(
            {"ok": False, "error": "Добавьте ссылку на карту или GPS-координаты."},
            status=400,
        )
    if len(map_url) > 700:
        return JsonResponse({"ok": False, "error": "Ссылка слишком длинная."}, status=400)

    suggestion = SpecialProjectLetterSuggestion.objects.create(
        project_slug=LANDNAME_PROJECT_SLUG,
        letter=letter,
        map_url=map_url,
        coordinates_text=coordinates_text,
        latitude=lat,
        longitude=lng,
        location_note=location_note,
        submitted_by=user,
    )
    return JsonResponse(
        {
            "ok": True,
            "suggestion": {
                "id": suggestion.id,
                "letter": suggestion.letter,
                "status": suggestion.status,
                "created_at": suggestion.created_at.isoformat(),
            },
        },
        status=201,
    )


def landname_tile(request: HttpRequest, key: str) -> HttpResponse:
    svg = tile_svg(key)
    if svg is None:
        return JsonResponse({"ok": False, "error": "tile not found"}, status=404)
    return HttpResponse(svg, content_type="image/svg+xml")


def _save_letter_upload(request: HttpRequest, upload) -> str:
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if not content_type.startswith("image/"):
        raise ValueError("Файл должен быть картинкой.")

    max_bytes = getattr(settings, "USER_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
    if upload.size and upload.size > max_bytes:
        raise ValueError("Файл слишком большой.")

    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image.verify()
        upload.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("Не удалось прочитать картинку.")

    base_name = get_valid_filename(os.path.splitext(upload.name or "letter")[0])
    ext = os.path.splitext(upload.name or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    filename = f"special-projects/landname/{base_name}-{secrets.token_hex(8)}{ext}"
    saved_path = default_storage.save(filename, upload)
    relative_url = default_storage.url(saved_path)
    site_base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    return f"{site_base}{relative_url}" if site_base else request.build_absolute_uri(relative_url)


def _require_staff(request: HttpRequest):
    user = _get_user_from_request(request)
    if user is None:
        return None, JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not user.is_staff:
        return None, JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    return user, None


def _serialize_admin_letter(request: HttpRequest, image: SpecialProjectLetterImage) -> dict:
    payload = serialize_letter_image(request, image)
    payload.update(
        {
            "item_type": "letter",
            "status": "active",
            "created_at": image.created_at.isoformat(),
            "updated_at": image.updated_at.isoformat(),
        }
    )
    return payload


def _serialize_admin_suggestion(suggestion: SpecialProjectLetterSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "item_type": "suggestion",
        "status": suggestion.status,
        "letter": suggestion.letter,
        "title": suggestion.location_note or f"Предложение буквы {suggestion.letter}",
        "location_name": suggestion.location_note,
        "image_url": "",
        "map_url": suggestion.map_url,
        "coordinates": suggestion.coordinates_text,
        "latitude": str(suggestion.latitude) if suggestion.latitude is not None else "",
        "longitude": str(suggestion.longitude) if suggestion.longitude is not None else "",
        "submitted_by": {
            "id": suggestion.submitted_by_id,
            "username": getattr(suggestion.submitted_by, "username", ""),
        },
        "created_at": suggestion.created_at.isoformat(),
        "updated_at": suggestion.updated_at.isoformat(),
    }


def _serialize_admin_generation(generation: SpecialProjectGeneratedPhrase) -> dict:
    return {
        "id": generation.id,
        "text": generation.text,
        "share_query": generation.share_query,
        "was_shared": generation.was_shared,
        "share_clicks": generation.share_clicks,
        "shared_at": generation.shared_at.isoformat() if generation.shared_at else None,
        "generated_by": (
            {
                "id": generation.generated_by_id,
                "username": getattr(generation.generated_by, "username", ""),
            }
            if generation.generated_by_id
            else None
        ),
        "created_at": generation.created_at.isoformat(),
        "updated_at": generation.updated_at.isoformat(),
    }


def landname_admin_generations(request: HttpRequest) -> HttpResponse:
    _, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        limit = int(request.GET.get("limit", "200"))
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(limit, 500))

    queryset = SpecialProjectGeneratedPhrase.objects.select_related("generated_by").filter(
        project_slug=LANDNAME_PROJECT_SLUG,
    )
    total = queryset.count()
    shared_total = queryset.filter(was_shared=True).count()
    generations = queryset.order_by("-created_at", "-id")[:limit]
    return JsonResponse(
        {
            "ok": True,
            "total": total,
            "shared_total": shared_total,
            "unshared_total": total - shared_total,
            "limit": limit,
            "generations": [_serialize_admin_generation(generation) for generation in generations],
        }
    )


@csrf_exempt
def landname_admin_letters(request: HttpRequest) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response

    if request.method == "GET":
        images = SpecialProjectLetterImage.objects.filter(
            project_slug=LANDNAME_PROJECT_SLUG,
            is_active=True,
        ).order_by("letter", "sort_order", "id")
        suggestions = (
            SpecialProjectLetterSuggestion.objects.select_related("submitted_by")
            .filter(
                project_slug=LANDNAME_PROJECT_SLUG,
                status=SpecialProjectLetterSuggestion.STATUS_PENDING,
            )
            .order_by("letter", "created_at", "id")
        )
        return JsonResponse(
            {
                "ok": True,
                "letters": [_serialize_admin_letter(request, image) for image in images]
                + [_serialize_admin_suggestion(suggestion) for suggestion in suggestions],
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    if (request.content_type or "").startswith("multipart/form-data"):
        payload = request.POST
    else:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    try:
        letter = normalize_letter(str(payload.get("letter", "")))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    title = str(payload.get("title", "") or "").strip()
    image_url = str(payload.get("image_url", "") or "").strip()
    coordinates_text = str(payload.get("coordinates", "") or "").strip()
    map_url = str(payload.get("map_url", "") or "").strip()
    upload = request.FILES.get("image") or request.FILES.get("file")

    if not title:
        return JsonResponse({"ok": False, "error": "Укажите название."}, status=400)
    if len(title) > 160:
        return JsonResponse({"ok": False, "error": "Название слишком длинное."}, status=400)
    if upload:
        try:
            image_url = _save_letter_upload(request, upload)
        except ValueError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    if not image_url:
        return JsonResponse({"ok": False, "error": "Загрузите картинку."}, status=400)
    if not image_url.startswith(("http://", "https://")) or len(image_url) > 700:
        return JsonResponse({"ok": False, "error": "Некорректная ссылка на картинку."}, status=400)

    lat, lng = parse_coordinates(" ".join([coordinates_text, map_url]))
    if lat is None or lng is None:
        return JsonResponse({"ok": False, "error": "Укажите GPS в формате широта, долгота."}, status=400)

    if map_url and (not map_url.startswith(("http://", "https://")) or len(map_url) > 700):
        return JsonResponse({"ok": False, "error": "Некорректная ссылка на карту."}, status=400)

    max_sort_order = (
        SpecialProjectLetterImage.objects.filter(
            project_slug=LANDNAME_PROJECT_SLUG,
            letter=letter,
        ).aggregate(value=Max("sort_order"))["value"]
        or 0
    )
    image = SpecialProjectLetterImage.objects.create(
        project_slug=LANDNAME_PROJECT_SLUG,
        letter=letter,
        title=title,
        location_name=title,
        image_url=image_url,
        map_url=map_url or map_url_for_coordinates(lat, lng),
        latitude=lat,
        longitude=lng,
        sort_order=max_sort_order + 10,
        created_by=user,
    )
    return JsonResponse({"ok": True, "letter": _serialize_admin_letter(request, image)}, status=201)


@csrf_exempt
def landname_admin_suggestion_approve(request: HttpRequest, suggestion_id: int) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        suggestion = SpecialProjectLetterSuggestion.objects.get(
            id=suggestion_id,
            project_slug=LANDNAME_PROJECT_SLUG,
            status=SpecialProjectLetterSuggestion.STATUS_PENDING,
        )
    except SpecialProjectLetterSuggestion.DoesNotExist:
        return JsonResponse({"ok": False, "error": "suggestion not found"}, status=404)

    if (request.content_type or "").startswith("multipart/form-data"):
        payload = request.POST
    else:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    title = str(payload.get("title", "") or suggestion.location_note or "").strip()
    coordinates_text = str(payload.get("coordinates", "") or suggestion.coordinates_text or "").strip()
    map_url = str(payload.get("map_url", "") or suggestion.map_url or "").strip()
    image_url = str(payload.get("image_url", "") or "").strip()
    upload = request.FILES.get("image") or request.FILES.get("file")

    if not title:
        return JsonResponse({"ok": False, "error": "Укажите название."}, status=400)
    if len(title) > 160:
        return JsonResponse({"ok": False, "error": "Название слишком длинное."}, status=400)
    if upload:
        try:
            image_url = _save_letter_upload(request, upload)
        except ValueError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    if not image_url:
        return JsonResponse({"ok": False, "error": "Загрузите картинку."}, status=400)
    if not image_url.startswith(("http://", "https://")) or len(image_url) > 700:
        return JsonResponse({"ok": False, "error": "Некорректная ссылка на картинку."}, status=400)

    lat, lng = parse_coordinates(" ".join([coordinates_text, map_url]))
    if lat is None and suggestion.latitude is not None and suggestion.longitude is not None:
        lat = suggestion.latitude
        lng = suggestion.longitude
    if lat is None or lng is None:
        return JsonResponse({"ok": False, "error": "Укажите GPS в формате широта, долгота."}, status=400)
    if map_url and (not map_url.startswith(("http://", "https://")) or len(map_url) > 700):
        return JsonResponse({"ok": False, "error": "Некорректная ссылка на карту."}, status=400)

    max_sort_order = (
        SpecialProjectLetterImage.objects.filter(
            project_slug=LANDNAME_PROJECT_SLUG,
            letter=suggestion.letter,
        ).aggregate(value=Max("sort_order"))["value"]
        or 0
    )
    image = SpecialProjectLetterImage.objects.create(
        project_slug=LANDNAME_PROJECT_SLUG,
        letter=suggestion.letter,
        title=title,
        location_name=title,
        image_url=image_url,
        map_url=map_url or map_url_for_coordinates(lat, lng),
        latitude=lat,
        longitude=lng,
        sort_order=max_sort_order + 10,
        created_by=user,
    )
    suggestion.status = SpecialProjectLetterSuggestion.STATUS_APPROVED
    suggestion.reviewed_by = user
    suggestion.reviewed_at = timezone.now()
    suggestion.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
    return JsonResponse({"ok": True, "letter": _serialize_admin_letter(request, image)}, status=201)


@csrf_exempt
def landname_admin_suggestion_detail(request: HttpRequest, suggestion_id: int) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    if request.method != "DELETE":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    updated = SpecialProjectLetterSuggestion.objects.filter(
        id=suggestion_id,
        project_slug=LANDNAME_PROJECT_SLUG,
        status=SpecialProjectLetterSuggestion.STATUS_PENDING,
    ).update(
        status=SpecialProjectLetterSuggestion.STATUS_REJECTED,
        reviewed_by=user,
        reviewed_at=timezone.now(),
    )
    if not updated:
        return JsonResponse({"ok": False, "error": "suggestion not found"}, status=404)
    return JsonResponse({"ok": True, "deleted": True, "id": suggestion_id})


@csrf_exempt
def landname_admin_letter_detail(request: HttpRequest, image_id: int) -> HttpResponse:
    _, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    if request.method != "DELETE":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    deleted, _ = SpecialProjectLetterImage.objects.filter(
        id=image_id,
        project_slug=LANDNAME_PROJECT_SLUG,
    ).delete()
    if not deleted:
        return JsonResponse({"ok": False, "error": "letter not found"}, status=404)
    return JsonResponse({"ok": True, "deleted": True, "id": image_id})
