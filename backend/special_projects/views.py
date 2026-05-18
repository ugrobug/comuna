from __future__ import annotations

import json
import os
import secrets
from io import BytesIO

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Avg, Count, F, Max, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from special_projects import film_journey
from special_projects.models import (
    FilmJourneyEntry,
    FilmJourneyFilm,
    FilmJourneySubscription,
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


def _preview_font(size: int, bold: bool = True):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/{filename}",
        f"/usr/local/share/fonts/{filename}",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def landname_preview_image(request: HttpRequest) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    text = normalize_landname_text(request.GET.get("text", "")) or "КОМУНА"
    image = Image.new("RGB", (1200, 630), "#f8fafc")
    draw = ImageDraw.Draw(image)

    # Restrained Comuna-like card: quiet background, orange accent, strong phrase signal.
    draw.rounded_rectangle((72, 62, 1128, 568), radius=28, fill="#ffffff", outline="#e2e8f0", width=2)
    draw.rectangle((72, 62, 1128, 178), fill="#fff7ed")
    draw.rounded_rectangle((96, 92, 228, 132), radius=20, fill="#ea580c")
    draw.text((162, 111), "T", anchor="mm", font=_preview_font(26), fill="#ffffff")
    draw.text((252, 102), "Имя на карте", font=_preview_font(34), fill="#0f172a")
    draw.text(
        (252, 142),
        "Спутниковая фраза Tambur",
        font=_preview_font(24, bold=False),
        fill="#64748b",
    )

    font_size = 122
    font = _preview_font(font_size)
    max_width = 960
    while font_size > 52 and draw.textbbox((0, 0), text, font=font)[2] > max_width:
        font_size -= 6
        font = _preview_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = 600 - text_width / 2
    y = 320 - text_height / 2
    draw.text((x + 4, y + 5), text, font=font, fill="#fed7aa")
    draw.text((x, y), text, font=font, fill="#0f172a")

    subtitle = "Введите слово на русском, а мы соберём его из спутниковых снимков"
    subtitle_font = _preview_font(28, bold=False)
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    draw.text((600 - (subtitle_bbox[2] - subtitle_bbox[0]) / 2, 466), subtitle, font=subtitle_font, fill="#475569")

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    return response


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


def film_journey_status(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    return JsonResponse(film_journey.project_status_for_user(_get_user_from_request(request)))


@csrf_exempt
def film_journey_start(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if user is None:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if film_journey.active_films_count() <= 0:
        return JsonResponse({"ok": False, "error": "Список фильмов пока пуст."}, status=400)
    subscription = film_journey.start_subscription(user)
    return JsonResponse(
        {
            "ok": True,
            "subscription": film_journey.serialize_subscription(subscription),
        },
        status=201,
    )


@csrf_exempt
def film_journey_resume(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if user is None:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    subscription = FilmJourneySubscription.objects.filter(
        project_slug=film_journey.PROJECT_SLUG,
        user=user,
    ).first()
    if subscription is None:
        return JsonResponse({"ok": False, "error": "subscription not found"}, status=404)
    film_journey.resume_subscription(subscription)
    subscription.refresh_from_db()
    return JsonResponse(
        {
            "ok": True,
            "subscription": film_journey.serialize_subscription(subscription),
        }
    )


@csrf_exempt
def film_journey_entry_detail(request: HttpRequest, access_token: str) -> HttpResponse:
    user = _get_user_from_request(request)
    if user is None:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    entry = film_journey.entry_for_token_and_user(access_token, user)
    if entry is None:
        return JsonResponse({"ok": False, "error": "film not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "entry": film_journey.serialize_entry(entry, include_film=True),
                "subscription": film_journey.serialize_subscription(entry.subscription),
            }
        )
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Поставьте оценку от 1 до 10."}, status=400)
    comment = str(payload.get("comment") or "")
    try:
        entry = film_journey.submit_entry_review(entry, rating=rating, comment=comment)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    entry.refresh_from_db()
    return JsonResponse(
        {
            "ok": True,
            "entry": film_journey.serialize_entry(entry, include_film=True),
            "subscription": film_journey.serialize_subscription(entry.subscription),
        }
    )


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


def _parse_bool(value, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _parse_positive_int(value, *, default=None, maximum=None):
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _parse_imdb_rating(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > 10:
        return None
    return round(parsed, 1)


def _film_admin_payload(film: FilmJourneyFilm) -> dict:
    avg_rating = getattr(film, "avg_user_rating", None)
    return {
        "id": film.id,
        "title": film.title,
        "original_title": film.original_title,
        "year": film.year,
        "category": film.category,
        "description": film.description,
        "imdb_url": film.imdb_url,
        "imdb_rating": str(film.imdb_rating) if film.imdb_rating is not None else "",
        "poster_url": film.poster_url,
        "runtime_minutes": film.runtime_minutes,
        "director": film.director,
        "country": film.country,
        "genres": film.genres,
        "sort_order": film.sort_order,
        "is_active": film.is_active,
        "created_at": film.created_at.isoformat(),
        "updated_at": film.updated_at.isoformat(),
        "analytics": {
            "delivered_count": getattr(film, "delivered_count", 0) or 0,
            "completed_count": getattr(film, "completed_count", 0) or 0,
            "waiting_review_count": getattr(film, "waiting_review_count", 0) or 0,
            "avg_user_rating": round(float(avg_rating), 1) if avg_rating is not None else None,
        },
    }


def _film_admin_queryset():
    return (
        FilmJourneyFilm.objects.filter(project_slug=film_journey.PROJECT_SLUG)
        .annotate(
            delivered_count=Count("journey_entries", distinct=True),
            completed_count=Count(
                "journey_entries",
                filter=Q(journey_entries__completed_at__isnull=False),
                distinct=True,
            ),
            waiting_review_count=Count(
                "journey_entries",
                filter=Q(journey_entries__completed_at__isnull=True),
                distinct=True,
            ),
            avg_user_rating=Avg("journey_entries__rating"),
        )
        .order_by("sort_order", "id")
    )


def _film_journey_admin_analytics() -> dict:
    subscriptions = FilmJourneySubscription.objects.filter(
        project_slug=film_journey.PROJECT_SLUG,
    )
    subscription_totals = {
        "total": subscriptions.count(),
        "active": subscriptions.filter(status=FilmJourneySubscription.STATUS_ACTIVE).count(),
        "paused": subscriptions.filter(status=FilmJourneySubscription.STATUS_PAUSED).count(),
        "completed": subscriptions.filter(status=FilmJourneySubscription.STATUS_COMPLETED).count(),
    }

    entries = FilmJourneyEntry.objects.filter(
        subscription__project_slug=film_journey.PROJECT_SLUG,
    )
    entry_totals = {
        "delivered": entries.count(),
        "completed": entries.filter(completed_at__isnull=False).count(),
        "waiting_review": entries.filter(completed_at__isnull=True).count(),
        "commented": entries.exclude(comment="").count(),
    }

    stages = {
        "active_no_film": 0,
        "active_review_required": 0,
        "active_waiting_next": 0,
        "paused": subscription_totals["paused"],
        "completed": subscription_totals["completed"],
    }
    latest_entries = (
        FilmJourneyEntry.objects.filter(subscription__project_slug=film_journey.PROJECT_SLUG)
        .select_related("subscription")
        .order_by("subscription_id", "-position", "-id")
    )
    latest_by_subscription: dict[int, FilmJourneyEntry] = {}
    for entry in latest_entries:
        latest_by_subscription.setdefault(entry.subscription_id, entry)

    active_subscriptions = subscriptions.filter(status=FilmJourneySubscription.STATUS_ACTIVE)
    for subscription in active_subscriptions.only("id", "status"):
        latest = latest_by_subscription.get(subscription.id)
        if latest is None:
            stages["active_no_film"] += 1
        elif latest.completed_at is None:
            stages["active_review_required"] += 1
        else:
            stages["active_waiting_next"] += 1

    return {
        "public_total": film_journey.PUBLIC_TOTAL_COUNT,
        "loaded_films": FilmJourneyFilm.objects.filter(project_slug=film_journey.PROJECT_SLUG).count(),
        "active_films": FilmJourneyFilm.objects.filter(
            project_slug=film_journey.PROJECT_SLUG,
            is_active=True,
        ).count(),
        "subscriptions": subscription_totals,
        "entries": entry_totals,
        "stages": stages,
    }


def _film_payload_from_request(payload: dict, *, existing: FilmJourneyFilm | None = None) -> dict:
    title = str(payload.get("title", existing.title if existing else "") or "").strip()
    if not title:
        raise ValueError("Укажите название фильма.")
    if len(title) > 220:
        raise ValueError("Название слишком длинное.")

    sort_order = _parse_positive_int(
        payload.get("sort_order", existing.sort_order if existing else None),
        default=None,
    )
    if sort_order is None:
        sort_order = (
            FilmJourneyFilm.objects.filter(project_slug=film_journey.PROJECT_SLUG).aggregate(value=Max("sort_order"))[
                "value"
            ]
            or 0
        ) + 10

    data = {
        "project_slug": film_journey.PROJECT_SLUG,
        "title": title,
        "original_title": str(payload.get("original_title", existing.original_title if existing else "") or "").strip()[:220],
        "year": _parse_positive_int(payload.get("year", existing.year if existing else None), default=None, maximum=3000),
        "category": str(payload.get("category", existing.category if existing else "") or "").strip()[:120],
        "description": str(payload.get("description", existing.description if existing else "") or "").strip(),
        "imdb_url": str(payload.get("imdb_url", existing.imdb_url if existing else "") or "").strip()[:700],
        "imdb_rating": _parse_imdb_rating(payload.get("imdb_rating", existing.imdb_rating if existing else None)),
        "poster_url": str(payload.get("poster_url", existing.poster_url if existing else "") or "").strip()[:700],
        "runtime_minutes": _parse_positive_int(
            payload.get("runtime_minutes", existing.runtime_minutes if existing else None),
            default=None,
            maximum=2000,
        ),
        "director": str(payload.get("director", existing.director if existing else "") or "").strip()[:220],
        "country": str(payload.get("country", existing.country if existing else "") or "").strip()[:160],
        "genres": str(payload.get("genres", existing.genres if existing else "") or "").strip()[:240],
        "sort_order": sort_order,
        "is_active": _parse_bool(payload.get("is_active", existing.is_active if existing else True), default=True),
    }
    for url_field in ("imdb_url", "poster_url"):
        if data[url_field] and not data[url_field].startswith(("http://", "https://")):
            raise ValueError("Ссылки должны начинаться с http:// или https://.")
    return data


@csrf_exempt
def film_journey_admin_films(request: HttpRequest) -> HttpResponse:
    _, error_response = _require_staff(request)
    if error_response is not None:
        return error_response

    if request.method == "GET":
        films = [_film_admin_payload(film) for film in _film_admin_queryset()]
        return JsonResponse(
            {
                "ok": True,
                "analytics": _film_journey_admin_analytics(),
                "films": films,
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    try:
        data = _film_payload_from_request(payload)
        film = FilmJourneyFilm.objects.create(**data)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        return JsonResponse({"ok": False, "error": "Не удалось сохранить фильм."}, status=400)

    return JsonResponse({"ok": True, "film": _film_admin_payload(film)}, status=201)


@csrf_exempt
def film_journey_admin_film_detail(request: HttpRequest, film_id: int) -> HttpResponse:
    _, error_response = _require_staff(request)
    if error_response is not None:
        return error_response

    film = FilmJourneyFilm.objects.filter(
        id=film_id,
        project_slug=film_journey.PROJECT_SLUG,
    ).first()
    if film is None:
        return JsonResponse({"ok": False, "error": "film not found"}, status=404)

    if request.method == "PATCH":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
        try:
            data = _film_payload_from_request(payload, existing=film)
            for key, value in data.items():
                setattr(film, key, value)
            film.save()
        except ValueError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        except Exception:
            return JsonResponse({"ok": False, "error": "Не удалось сохранить фильм."}, status=400)
        return JsonResponse({"ok": True, "film": _film_admin_payload(film)})

    if request.method == "DELETE":
        film.is_active = False
        film.save(update_fields=("is_active", "updated_at"))
        return JsonResponse({"ok": True, "deleted": True, "id": film.id})

    return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)


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
