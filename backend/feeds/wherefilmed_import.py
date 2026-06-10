from __future__ import annotations

import hmac
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Any

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from communities import service as community_service
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Author, Post
from rabotaem_backend.images import save_image_with_variants
from telegram_integration.media import build_public_storage_url, safe_public_url

WHEREFILMED_COMUN_SLUG = "wherefilmed"
WHEREFILMED_CATEGORY_NAME = "локации"
WHEREFILMED_AUTHOR_USERNAME = "wherefilmed"
WHEREFILMED_MESSAGE_ID_BASE = -3_000_000_000_000
WHEREFILMED_IMAGE_MAX_BYTES = 15 * 1024 * 1024

logger = logging.getLogger(__name__)


class WhereFilmedImportError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _site_url(path: str) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    clean_path = f"/{str(path or '').lstrip('/')}"
    return f"{base_url}{clean_path}" if base_url else clean_path


def _post_public_url(post: Post) -> str:
    post_title = str(post.title or "").strip() or f"post-{post.id}"
    post_slug = community_service._slugify_title(post_title)
    return _site_url(f"/b/post/{post.id}-{post_slug}" if post_slug else f"/b/post/{post.id}")


def _auth_token() -> str:
    return (
        str(getattr(settings, "WHEREFILMED_IMPORT_TOKEN", "") or "").strip()
        or str(getattr(settings, "TAMBUR_EXPORT_TOKEN", "") or "").strip()
    )


def _check_auth(request: HttpRequest) -> None:
    expected = _auth_token()
    if not expected:
        raise WhereFilmedImportError("wherefilmed import token is not configured", 503)

    authorization = str(request.headers.get("Authorization") or "").strip()
    prefix = "Bearer "
    supplied = authorization[len(prefix) :].strip() if authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise WhereFilmedImportError("unauthorized", 401)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _source_key(payload: dict[str, Any]) -> tuple[str, int]:
    source = payload.get("source")
    if not isinstance(source, dict):
        raise WhereFilmedImportError("source is required")

    site = re.sub(r"\s+", "", str(source.get("site") or "").strip().lower())
    movie_id = _as_int(source.get("movie_id"))
    if site != "wherefilmed" or not movie_id:
        raise WhereFilmedImportError("source.site and source.movie_id are invalid")
    return site, movie_id


def _wherefilmed_message_id(movie_id: int) -> int:
    return WHEREFILMED_MESSAGE_ID_BASE - int(movie_id)


def _wherefilmed_author() -> Author:
    author, _created = Author.objects.get_or_create(
        username=WHEREFILMED_AUTHOR_USERNAME,
        defaults={
            "title": "WhereFilmed",
            "channel_url": "https://wherefilmed.org",
            "invite_url": "https://wherefilmed.org",
            "description": "Материалы WhereFilmed о местах съемок фильмов и сериалов.",
            "auto_publish": True,
        },
    )
    updates: list[str] = []
    if author.title != "WhereFilmed":
        author.title = "WhereFilmed"
        updates.append("title")
    if not author.channel_url:
        author.channel_url = "https://wherefilmed.org"
        updates.append("channel_url")
    if not author.invite_url:
        author.invite_url = "https://wherefilmed.org"
        updates.append("invite_url")
    if updates:
        author.save(update_fields=[*updates, "updated_at"])
    return author


def _target_comun_and_category() -> tuple[Comun, ComunCategory]:
    comun = Comun.objects.filter(slug=WHEREFILMED_COMUN_SLUG, is_active=True).first()
    if not comun:
        raise WhereFilmedImportError("wherefilmed community is not configured", 500)

    category, _created = community_service._ensure_comun_category_by_name(
        comun,
        WHEREFILMED_CATEGORY_NAME,
    )
    if not category:
        raise WhereFilmedImportError("wherefilmed category is not configured", 500)
    return comun, category


def _public_url(value: object) -> str:
    raw = safe_public_url(str(value or "").strip())
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = f"https:{raw}"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def _download_image(url: str, *, movie_id: int) -> str:
    source_url = _public_url(url)
    if not source_url:
        return ""

    max_bytes = int(getattr(settings, "WHEREFILMED_IMPORT_IMAGE_MAX_BYTES", WHEREFILMED_IMAGE_MAX_BYTES))
    request = urllib.request.Request(
        source_url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "User-Agent": "TamburWhereFilmedImporter/1.0 (+https://tambur.pub)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(max_bytes + 1)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise WhereFilmedImportError(f"failed to download image: {source_url}", 502) from exc

    if len(data) > max_bytes:
        raise WhereFilmedImportError(f"image is too large: {source_url}", 413)
    if not data:
        raise WhereFilmedImportError(f"image is empty: {source_url}", 502)

    parsed = urllib.parse.urlparse(source_url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if not ext or len(ext) > 8:
        ext = ".jpg"
    filename = f"posts/wherefilmed/{movie_id}/{secrets.token_hex(10)}{ext}"
    try:
        image_set = save_image_with_variants(
            data=data,
            original_path=filename,
            keep_original=False,
        )
    except Exception as exc:
        raise WhereFilmedImportError(f"failed to store image: {source_url}", 502) from exc
    return build_public_storage_url(image_set.default_url)


def _gallery_items(raw_items: object, *, movie_id: int) -> list[dict[str, str]]:
    if not isinstance(raw_items, list):
        return []

    result: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        source_url = item.get("image_url") or item.get("url") or item.get("thumbnail_url")
        local_url = _download_image(str(source_url or ""), movie_id=movie_id)
        if local_url:
            result.append({"url": local_url, "alt": "", "title": ""})
    return result


def _text(value: object, max_length: int | None = None) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip())
    return normalized[:max_length] if max_length else normalized


def _list_titles(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    titles: list[str] = []
    seen: set[str] = set()
    for item in items:
        title = _text(item.get("title") if isinstance(item, dict) else item)
        key = title.lower()
        if title and key not in seen:
            seen.add(key)
            titles.append(title)
    return titles


def _movie_genre(movie: dict[str, Any]) -> str:
    genres = _list_titles(movie.get("genres"))
    return genres[0][:80] if genres else ""


def _movie_content_kind(movie: dict[str, Any]) -> str:
    raw_kind = re.sub(r"\s+", "", str(movie.get("type") or "").strip().lower())
    if raw_kind in {"series", "serial", "tv", "show", "сериал"}:
        return "series"
    return "movie"


def _movie_title(movie: dict[str, Any]) -> str:
    title = _text(movie.get("title"), 180)
    original_title = _text(movie.get("original_title"), 180)
    year = _as_int(movie.get("year"))
    if original_title and original_title.lower() != title.lower():
        title = f"{title} / {original_title}" if title else original_title
    if year:
        title = f"{title} ({year})" if title else str(year)
    return title or "WhereFilmed"


def _post_title(movie: dict[str, Any]) -> str:
    return f"Где снимали «{_movie_title(movie)}»"[:255]


def _editor_paragraph_html(value: str) -> str:
    html = str(value or "").strip()
    if not html:
        return ""
    html = re.sub(r"</p>\s*<p\b[^>]*>", "<br><br>", html, flags=re.IGNORECASE)
    html = re.sub(r"^\s*<p\b[^>]*>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>\s*$", "", html, flags=re.IGNORECASE)
    return html.strip()


def _paragraph_block(text: str, block_id: str) -> dict[str, Any] | None:
    value = _editor_paragraph_html(text)
    if not value:
        return None
    return {"id": block_id, "type": "paragraph", "data": {"text": value}}


def _header_block(text: str, block_id: str, level: int = 2) -> dict[str, Any] | None:
    value = _text(text)
    if not value:
        return None
    return {"id": block_id, "type": "header", "data": {"text": escape(value), "level": level}}


def _gallery_block(images: list[dict[str, str]], block_id: str) -> dict[str, Any] | None:
    if not images:
        return None
    return {"id": block_id, "type": "gallery", "data": {"images": images}}


def _map_block(location: dict[str, Any], block_id: str) -> dict[str, Any] | None:
    gps = str(location.get("gps_coordinate") or "").strip()
    matches = re.findall(r"[-+]?\d{1,3}(?:[.,]\d+)?", gps)
    for index in range(0, max(len(matches) - 1, 0)):
        try:
            lat = Decimal(matches[index].replace(",", "."))
            lng = Decimal(matches[index + 1].replace(",", "."))
        except InvalidOperation:
            continue
        if Decimal("-90") <= lat <= Decimal("90") and Decimal("-180") <= lng <= Decimal("180"):
            return {
                "id": block_id,
                "type": "map",
                "data": {
                    "lat": float(lat.quantize(Decimal("0.000001"))),
                    "lng": float(lng.quantize(Decimal("0.000001"))),
                    "zoom": 16,
                },
            }
    return None


def _prefixed_paragraph_html(prefix: str, value: str) -> str:
    html = _editor_paragraph_html(value)
    if not html:
        return ""
    return f"<b>{escape(prefix)}</b> {html}"


def _build_content(
    payload: dict[str, Any],
    *,
    movie_id: int,
) -> tuple[str, list[str], dict[str, Any]]:
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    locations = payload.get("locations") if isinstance(payload.get("locations"), list) else []

    blocks: list[dict[str, Any]] = []
    saved_images: list[str] = []

    poster_url = _download_image(str(movie.get("poster_url") or ""), movie_id=movie_id)

    description_html = str(movie.get("description_html") or "").strip()
    description_text = _text(movie.get("description_text"))
    description_value = description_html or escape(description_text)
    description_block = _paragraph_block(description_value, "wf-description")
    if description_block:
        blocks.append(description_block)

    if locations:
        header = _header_block("Локации съемок:", "wf-locations", level=2)
        if header:
            blocks.append(header)

    source_locations: list[dict[str, Any]] = []
    for index, raw_location in enumerate(locations, start=1):
        if not isinstance(raw_location, dict):
            continue
        location_id = _as_int(raw_location.get("id")) or index
        location_title = _text(raw_location.get("title")) or f"Локация {index}"

        header = _header_block(location_title, f"wf-location-{location_id}", level=3)
        if header:
            blocks.append(header)

        movie_section = _header_block("В кино", f"wf-location-{location_id}-movie", level=4)
        if movie_section:
            blocks.append(movie_section)

        movie_gallery = _gallery_items(raw_location.get("movie_gallery"), movie_id=movie_id)
        saved_images.extend(item["url"] for item in movie_gallery)

        gallery = _gallery_block(movie_gallery, f"wf-location-{location_id}-movie-gallery")
        if gallery:
            blocks.append(gallery)

        scene_html = str(raw_location.get("scene_description_html") or "").strip()
        if not scene_html:
            scene_html = escape(_text(raw_location.get("scene_description_text")))
        scene = _paragraph_block(
            _prefixed_paragraph_html("Сцена, где", scene_html),
            f"wf-location-{location_id}-scene",
        )
        if scene:
            blocks.append(scene)

        reality_section = _header_block("В реальности", f"wf-location-{location_id}-reality", level=4)
        if reality_section:
            blocks.append(reality_section)

        reality_gallery = _gallery_items(raw_location.get("reality_gallery"), movie_id=movie_id)
        saved_images.extend(item["url"] for item in reality_gallery)

        reality = _gallery_block(reality_gallery, f"wf-location-{location_id}-reality-gallery")
        if reality:
            blocks.append(reality)

        map_block = _map_block(raw_location, f"wf-location-{location_id}-map")
        if map_block:
            blocks.append(map_block)

        spot_html = str(raw_location.get("movie_spot_html") or "").strip()
        if not spot_html:
            spot_html = escape(_text(raw_location.get("movie_spot_text")))
        spot = _paragraph_block(
            _prefixed_paragraph_html("Сцена была снята", spot_html),
            f"wf-location-{location_id}-spot",
        )
        if spot:
            blocks.append(spot)

        source_locations.append(
            {
                "id": raw_location.get("id"),
                "title": location_title,
                "movie_gallery_count": len(movie_gallery),
                "reality_gallery_count": len(reality_gallery),
                "gps_coordinate": raw_location.get("gps_coordinate"),
            }
        )

    content = json.dumps({"time": 0, "blocks": blocks, "version": "2.31.0"}, ensure_ascii=False)
    image_payload = {"poster_url": poster_url, "saved_image_urls": saved_images, "locations": source_locations}
    return content, saved_images, image_payload


def _raw_data(
    payload: dict[str, Any],
    *,
    movie_id: int,
    saved_images: list[str],
    image_payload: dict[str, Any],
) -> dict[str, Any]:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    template_data: dict[str, object] = {}
    title = _text(movie.get("title"), 255)
    original_title = _text(movie.get("original_title"), 255)
    genre = _movie_genre(movie)
    year = _as_int(movie.get("year"))
    if title:
        template_data["title"] = title
    if original_title:
        template_data["original_title"] = original_title
    if genre:
        template_data["genre"] = genre
    if year:
        template_data["release_date"] = f"{year}-01-01"
    poster_url = _public_url(image_payload.get("poster_url"))
    if poster_url:
        template_data["poster_url"] = poster_url
    template_data["content_kind"] = _movie_content_kind(movie)
    return {
        "source": "manual_comun",
        "comun_slug": WHEREFILMED_COMUN_SLUG,
        "comun_category_name": WHEREFILMED_CATEGORY_NAME,
        "template": {
            "type": "movie_review",
            "version": 1,
            "data": template_data,
        },
        "wherefilmed": {
            "source_site": "wherefilmed",
            "movie_id": movie_id,
            "slug": source.get("slug"),
            "url": source.get("url"),
            "payload_version": payload.get("payload_version"),
            "images": image_payload,
        },
        "gallery_urls": saved_images[:20],
    }


def _sync_existing_template_poster(post: Post) -> None:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    wherefilmed_data = raw_data.get("wherefilmed")
    if not isinstance(wherefilmed_data, dict):
        return
    images = wherefilmed_data.get("images")
    if not isinstance(images, dict):
        return
    poster_url = _public_url(images.get("poster_url"))
    if not poster_url:
        return

    template = raw_data.get("template")
    if not isinstance(template, dict) or str(template.get("type") or "").strip() != "movie_review":
        return
    template_data = template.get("data")
    if not isinstance(template_data, dict):
        template_data = {}
        template["data"] = template_data
    if template_data.get("poster_url") == poster_url:
        return

    template_data["poster_url"] = poster_url
    post.raw_data = raw_data
    post.save(update_fields=["raw_data", "updated_at"])


def _import_payload(payload: dict[str, Any]) -> tuple[Post, bool]:
    if payload.get("payload_version") != 1:
        raise WhereFilmedImportError("unsupported payload_version")

    _site, movie_id = _source_key(payload)
    author = _wherefilmed_author()
    message_id = _wherefilmed_message_id(movie_id)

    existing = Post.objects.filter(author=author, message_id=message_id).first()
    comun, category = _target_comun_and_category()
    if existing:
        _sync_existing_template_poster(existing)
        ComunPostCategoryAssignment.objects.update_or_create(
            comun=comun,
            post=existing,
            defaults={"category": category, "assigned_by": None},
        )
        return existing, False

    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    content, saved_images, image_payload = _build_content(payload, movie_id=movie_id)
    raw_data = _raw_data(payload, movie_id=movie_id, saved_images=saved_images, image_payload=image_payload)
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    source_url = _public_url(source.get("url"))

    try:
        with transaction.atomic():
            post, created = Post.objects.get_or_create(
                author=author,
                message_id=message_id,
                defaults={
                    "title": _post_title(movie),
                    "content": content,
                    "source_url": source_url[:255],
                    "channel_url": author.channel_url,
                    "raw_data": raw_data,
                    "is_pending": False,
                    "is_blocked": False,
                    "publish_at": None,
                },
            )
            ComunPostCategoryAssignment.objects.update_or_create(
                comun=comun,
                post=post,
                defaults={"category": category, "assigned_by": None},
            )
    except IntegrityError:
        post = Post.objects.get(author=author, message_id=message_id)
        created = False

    if created and post.rating:
        community_service._apply_comun_rating_delta_for_post(
            post,
            value_delta=post.rating,
            event_type="post_vote",
        )
    return post, created


@csrf_exempt
def wherefilmed_import(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        _check_auth(request)
        payload = json.loads(request.body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise WhereFilmedImportError("invalid json payload")
        post, created = _import_payload(payload)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    except RequestDataTooBig:
        return JsonResponse({"ok": False, "error": "payload is too large"}, status=413)
    except WhereFilmedImportError as exc:
        if exc.status >= 500:
            logger.warning("wherefilmed import failed: %s", exc, exc_info=True)
        return JsonResponse({"ok": False, "error": str(exc)}, status=exc.status)
    except Exception as exc:
        logger.exception("wherefilmed import failed with an unexpected error")
        return JsonResponse({"ok": False, "error": f"internal import error: {type(exc).__name__}"}, status=500)

    status = 201 if created else 200
    return JsonResponse({"id": str(post.id), "url": _post_public_url(post)}, status=status)


__all__ = [
    "wherefilmed_import",
]
