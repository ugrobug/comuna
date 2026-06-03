from __future__ import annotations

import json

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, UnidentifiedImageError

from landing_pages.models import LandingPage, LandingPageImage, LandingPageLead
from landing_pages.service import serialize_image, serialize_page
from users.service import _get_user_from_request


def _require_staff(request: HttpRequest):
    user = _get_user_from_request(request)
    if user is None:
        return None, JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not user.is_staff:
        return None, JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    return user, None


def _json_payload(request: HttpRequest) -> dict:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("invalid json") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    return payload


def _request_payload(request: HttpRequest) -> tuple[dict, object | None]:
    if (request.content_type or "").startswith("multipart/form-data"):
        return request.POST, request.FILES.get("image") or request.FILES.get("file")
    return _json_payload(request), None


def _parse_bool(value, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _parse_positive_int(value, *, default: int = 100) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _validate_image_upload(upload) -> str | None:
    if upload is None:
        return None
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type and not content_type.startswith("image/"):
        return "Файл должен быть картинкой."
    max_bytes = getattr(settings, "USER_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
    if upload.size and upload.size > max_bytes:
        return "Файл слишком большой."
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image.verify()
        upload.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        return "Не удалось прочитать картинку."
    return None


def _assign_page_fields(page: LandingPage, payload: dict, user) -> None:
    if "title" in payload:
        page.title = str(payload.get("title") or "").strip()[:220]
    if "description" in payload:
        page.description = str(payload.get("description") or "").strip()
    if "template_slug" in payload:
        page.template_slug = str(payload.get("template_slug") or "community-platform").strip()[:80]
    if "is_published" in payload:
        page.is_published = _parse_bool(payload.get("is_published"), default=True)
    if "sort_order" in payload:
        page.sort_order = _parse_positive_int(payload.get("sort_order"))
    page.updated_by = user


def landing_page_detail(request: HttpRequest, slug: str) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    page = (
        LandingPage.objects.prefetch_related("images")
        .filter(slug=slug, is_published=True)
        .first()
    )
    if page is None:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)
    return JsonResponse({"ok": True, "page": serialize_page(request, page)})


@csrf_exempt
def landing_page_leads(request: HttpRequest, slug: str) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    page = LandingPage.objects.filter(slug=slug, is_published=True).first()
    if page is None:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)
    try:
        payload = _json_payload(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    contact = str(payload.get("contact") or "").strip()
    if len(contact) < 3:
        return JsonResponse({"ok": False, "error": "Оставьте контакт для связи."}, status=400)
    source = str(payload.get("source") or "").strip()[:80]
    community_url = str(payload.get("community_url") or "").strip()
    if community_url and (not community_url.startswith(("http://", "https://")) or len(community_url) > 700):
        return JsonResponse({"ok": False, "error": "Некорректная ссылка на сообщество."}, status=400)
    note = str(payload.get("note") or "").strip()[:2000]
    lead = LandingPageLead.objects.create(
        page=page,
        source=source,
        contact=contact[:180],
        community_url=community_url,
        note=note,
    )
    return JsonResponse({"ok": True, "lead_id": lead.id}, status=201)


@csrf_exempt
def admin_landing_pages(request: HttpRequest) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response

    if request.method == "GET":
        pages = LandingPage.objects.prefetch_related("images").all()
        return JsonResponse(
            {
                "ok": True,
                "pages": [serialize_page(request, page) for page in pages],
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = _json_payload(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    slug = str(payload.get("slug") or "").strip()
    title = str(payload.get("title") or "").strip()
    if not slug:
        return JsonResponse({"ok": False, "error": "slug is required"}, status=400)
    if not title:
        return JsonResponse({"ok": False, "error": "title is required"}, status=400)

    page = LandingPage(
        slug=slug,
        title=title[:220],
        created_by=user,
        updated_by=user,
    )
    _assign_page_fields(page, payload, user)
    try:
        page.save()
    except IntegrityError:
        return JsonResponse({"ok": False, "error": "landing page already exists"}, status=400)
    return JsonResponse({"ok": True, "page": serialize_page(request, page)}, status=201)


@csrf_exempt
def admin_landing_page_detail(request: HttpRequest, slug: str) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    page = LandingPage.objects.prefetch_related("images").filter(slug=slug).first()
    if page is None:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)

    if request.method == "GET":
        return JsonResponse({"ok": True, "page": serialize_page(request, page)})

    if request.method != "PATCH":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = _json_payload(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    _assign_page_fields(page, payload, user)
    if not page.title:
        return JsonResponse({"ok": False, "error": "title is required"}, status=400)
    page.save()
    page.refresh_from_db()
    return JsonResponse({"ok": True, "page": serialize_page(request, page)})


@csrf_exempt
def admin_landing_page_images(request: HttpRequest, slug: str) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    page = LandingPage.objects.filter(slug=slug).first()
    if page is None:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "images": [serialize_image(request, image) for image in page.images.all()],
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload, upload = _request_payload(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    upload_error = _validate_image_upload(upload)
    if upload_error:
        return JsonResponse({"ok": False, "error": upload_error}, status=400)

    slot = str(payload.get("slot") or "hero").strip()[:80] or "hero"
    title = str(payload.get("title") or "Картинка").strip()[:160] or "Картинка"
    image_url = str(payload.get("image_url") or "").strip()
    if image_url and (not image_url.startswith(("http://", "https://")) or len(image_url) > 700):
        return JsonResponse({"ok": False, "error": "Некорректная ссылка на картинку."}, status=400)

    image = LandingPageImage.objects.create(
        page=page,
        slot=slot,
        title=title,
        alt_text=str(payload.get("alt_text") or "").strip()[:220],
        image=upload if upload else None,
        image_url="" if upload else image_url,
        is_active=_parse_bool(payload.get("is_active"), default=True),
        sort_order=_parse_positive_int(payload.get("sort_order")),
        created_by=user,
    )
    return JsonResponse({"ok": True, "image": serialize_image(request, image)}, status=201)


@csrf_exempt
def admin_landing_page_image_detail(request: HttpRequest, image_id: int) -> HttpResponse:
    user, error_response = _require_staff(request)
    if error_response is not None:
        return error_response
    image = LandingPageImage.objects.select_related("page").filter(id=image_id).first()
    if image is None:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)

    if request.method == "DELETE":
        image.delete()
        return JsonResponse({"ok": True})

    if request.method != "PATCH":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload, upload = _request_payload(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    upload_error = _validate_image_upload(upload)
    if upload_error:
        return JsonResponse({"ok": False, "error": upload_error}, status=400)

    if "slot" in payload:
        image.slot = str(payload.get("slot") or "hero").strip()[:80] or "hero"
    if "title" in payload:
        image.title = str(payload.get("title") or "Картинка").strip()[:160] or "Картинка"
    if "alt_text" in payload:
        image.alt_text = str(payload.get("alt_text") or "").strip()[:220]
    if "image_url" in payload:
        image_url = str(payload.get("image_url") or "").strip()
        if image_url and (not image_url.startswith(("http://", "https://")) or len(image_url) > 700):
            return JsonResponse({"ok": False, "error": "Некорректная ссылка на картинку."}, status=400)
        image.image_url = image_url
        if image_url:
            image.image = None
    if upload:
        image.image = upload
        image.image_url = ""
    if "is_active" in payload:
        image.is_active = _parse_bool(payload.get("is_active"), default=True)
    if "sort_order" in payload:
        image.sort_order = _parse_positive_int(payload.get("sort_order"))
    image.save()
    return JsonResponse({"ok": True, "image": serialize_image(request, image)})
