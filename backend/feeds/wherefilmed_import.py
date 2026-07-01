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

from feeds.post_paths import build_post_public_path
from communities import service as community_service
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import (
    Author,
    POST_TRANSLATION_LANGUAGE_CHOICES,
    POST_TRANSLATION_STATUS_TRANSLATED,
    Post,
    PostTranslation,
)
from feeds.preview import build_post_preview
from rabotaem_backend.images import save_image_with_variants
from telegram_integration.media import build_public_storage_url, safe_public_url

WHEREFILMED_COMUN_SLUG = "wherefilmed"
WHEREFILMED_CATEGORY_NAME = "локации"
WHEREFILMED_AUTHOR_USERNAME = "wherefilmed"
WHEREFILMED_MESSAGE_ID_BASE = -3_000_000_000_000
WHEREFILMED_IMAGE_MAX_BYTES = 15 * 1024 * 1024
WHEREFILMED_ORIGINAL_LANGUAGE = "ru"
WHEREFILMED_TRANSLATION_LANGUAGES = {
    language
    for language, _label in POST_TRANSLATION_LANGUAGE_CHOICES
    if language != WHEREFILMED_ORIGINAL_LANGUAGE
}

WHEREFILMED_I18N = {
    "en": {
        "post_title": 'Where was "{movie}" filmed?',
        "locations": "Filming locations:",
        "movie": "In the movie",
        "reality": "In reality",
        "scene_prefix": "Scene where",
        "spot_prefix": "The scene was filmed",
    },
    "es": {
        "post_title": 'Dónde se filmó "{movie}"',
        "locations": "Lugares de rodaje:",
        "movie": "En la película",
        "reality": "En la realidad",
        "scene_prefix": "Escena donde",
        "spot_prefix": "La escena se filmó",
    },
    "pt": {
        "post_title": 'Onde foi filmado "{movie}"',
        "locations": "Locais de filmagem:",
        "movie": "No filme",
        "reality": "Na realidade",
        "scene_prefix": "Cena em que",
        "spot_prefix": "A cena foi filmada",
    },
    "de": {
        "post_title": 'Wo wurde "{movie}" gedreht?',
        "locations": "Drehorte:",
        "movie": "Im Film",
        "reality": "In Wirklichkeit",
        "scene_prefix": "Szene, in der",
        "spot_prefix": "Die Szene wurde gedreht",
    },
    "fr": {
        "post_title": 'Où a été tourné "{movie}" ?',
        "locations": "Lieux de tournage :",
        "movie": "Dans le film",
        "reality": "Dans la réalité",
        "scene_prefix": "Scène où",
        "spot_prefix": "La scène a été tournée",
    },
    "tr": {
        "post_title": '"{movie}" nerede çekildi?',
        "locations": "Çekim yerleri:",
        "movie": "Filmde",
        "reality": "Gerçekte",
        "scene_prefix": "Sahnenin geçtiği yer",
        "spot_prefix": "Sahne burada çekildi",
    },
    "id": {
        "post_title": 'Di mana "{movie}" difilmkan?',
        "locations": "Lokasi syuting:",
        "movie": "Dalam film",
        "reality": "Di dunia nyata",
        "scene_prefix": "Adegan ketika",
        "spot_prefix": "Adegan ini difilmkan",
    },
}

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
    return _site_url(build_post_public_path(post.id, post_title))


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


def _operation(payload: dict[str, Any]) -> str:
    operation = str(payload.get("operation") or "upsert").strip().lower()
    if operation not in {"upsert", "translations_only"}:
        raise WhereFilmedImportError("operation must be upsert or translations_only")
    return operation


def _include_media(payload: dict[str, Any], operation: str) -> bool:
    if operation == "translations_only":
        return False
    return bool(payload.get("include_media", True))


def _normalize_translation_language(value: object) -> str:
    return str(value or "").strip().lower()


def _payload_translation_languages(payload: dict[str, Any]) -> list[str]:
    languages: list[str] = []
    seen: set[str] = set()

    def add_language(raw_language: object) -> None:
        language = _normalize_translation_language(raw_language)
        if language in WHEREFILMED_TRANSLATION_LANGUAGES and language not in seen:
            seen.add(language)
            languages.append(language)

    raw_languages = payload.get("translation_languages")
    if isinstance(raw_languages, list):
        for raw_language in raw_languages:
            add_language(raw_language)

    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    translations = movie.get("translations") if isinstance(movie.get("translations"), dict) else {}
    for language in translations:
        add_language(language)
    for key in ("countries", "genres", "cities", "places"):
        items = movie.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            translations = item.get("translations")
            if isinstance(translations, dict):
                for language in translations:
                    add_language(language)
    for key in ("countries", "genres", "cities", "places"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            translations = item.get("translations")
            if isinstance(translations, dict):
                for language in translations:
                    add_language(language)

    locations = payload.get("locations") if isinstance(payload.get("locations"), list) else []
    for raw_location in locations:
        if not isinstance(raw_location, dict):
            continue
        translations = raw_location.get("translations")
        if not isinstance(translations, dict):
            translations = {}
        for language in translations:
            add_language(language)
        for key in ("countries", "genres", "cities", "places"):
            items = raw_location.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                translations = item.get("translations")
                if isinstance(translations, dict):
                    for language in translations:
                        add_language(language)

    return languages


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


def _stored_gallery_items(raw_items: object) -> list[dict[str, str]]:
    if not isinstance(raw_items, list):
        return []
    result: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = _public_url(item.get("url") or item.get("image_url") or item.get("thumbnail_url"))
        if url:
            result.append(
                {
                    "url": url,
                    "alt": _text(item.get("alt"), 200),
                    "title": _text(item.get("title"), 200),
                }
            )
    return result


def _location_image_payload(image_payload: dict[str, Any], location_id: int) -> dict[str, Any]:
    locations = image_payload.get("locations")
    if not isinstance(locations, list):
        return {}
    for item in locations:
        if not isinstance(item, dict):
            continue
        if _as_int(item.get("id")) == location_id:
            return item
    return {}


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


def _translated_list_titles(items: object, language: str) -> list[str]:
    if not isinstance(items, list):
        return []
    titles: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            translation = _translation_payload(item, language)
            title = _text(translation.get("title") or item.get("title"))
        else:
            title = _text(item)
        key = title.lower()
        if title and key not in seen:
            seen.add(key)
            titles.append(title)
    return titles


def _translation_payload(item: dict[str, Any], language: str) -> dict[str, Any]:
    translations = item.get("translations")
    if not isinstance(translations, dict):
        return {}
    translation = translations.get(language)
    return translation if isinstance(translation, dict) else {}


def _localized_value(item: dict[str, Any], language: str | None, key: str) -> object:
    if not language:
        return item.get(key)
    translation = _translation_payload(item, language)
    return translation.get(key) if key in translation else item.get(key)


def _movie_title_for_language(movie: dict[str, Any], language: str | None = None) -> str:
    if not language:
        return _movie_title(movie)

    title = _text(_localized_value(movie, language, "title"), 180)
    original_title = _text(movie.get("original_title"), 180)
    year = _as_int(movie.get("year"))
    if original_title and original_title.lower() != title.lower():
        title = f"{title} / {original_title}" if title else original_title
    if year:
        title = f"{title} ({year})" if title else str(year)
    return title or _movie_title(movie)


def _labels(language: str | None) -> dict[str, str]:
    if language and language in WHEREFILMED_I18N:
        return WHEREFILMED_I18N[language]
    return {
        "post_title": "Где снимали «{movie}»",
        "locations": "Локации съемок:",
        "movie": "В кино",
        "reality": "В реальности",
        "scene_prefix": "Сцена, где",
        "spot_prefix": "Сцена была снята",
    }


def _movie_genre(movie: dict[str, Any], language: str | None = None) -> str:
    genres = _translated_list_titles(movie.get("genres"), language) if language else _list_titles(movie.get("genres"))
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


def _translated_post_title(movie: dict[str, Any], language: str) -> str:
    title = _movie_title_for_language(movie, language)
    pattern = _labels(language)["post_title"]
    return pattern.format(movie=title)[:255]


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
    include_media: bool = True,
    image_payload: dict[str, Any] | None = None,
    language: str | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    locations = payload.get("locations") if isinstance(payload.get("locations"), list) else []
    labels = _labels(language)
    image_payload = image_payload if isinstance(image_payload, dict) else {}

    blocks: list[dict[str, Any]] = []
    saved_images: list[str] = []

    poster_url = (
        _download_image(str(movie.get("poster_url") or ""), movie_id=movie_id)
        if include_media
        else _public_url(image_payload.get("poster_url"))
    )

    description_html = str(_localized_value(movie, language, "description_html") or "").strip()
    description_text = _text(_localized_value(movie, language, "description_text"))
    description_value = description_html or escape(description_text)
    description_block = _paragraph_block(description_value, "wf-description")
    if description_block:
        blocks.append(description_block)

    if locations:
        header = _header_block(labels["locations"], "wf-locations", level=2)
        if header:
            blocks.append(header)

    source_locations: list[dict[str, Any]] = []
    for index, raw_location in enumerate(locations, start=1):
        if not isinstance(raw_location, dict):
            continue
        location_id = _as_int(raw_location.get("id")) or index
        location_media = _location_image_payload(image_payload, location_id)
        location_title = _text(_localized_value(raw_location, language, "title")) or f"Локация {index}"

        header = _header_block(location_title, f"wf-location-{location_id}", level=3)
        if header:
            blocks.append(header)

        movie_section = _header_block(labels["movie"], f"wf-location-{location_id}-movie", level=4)
        if movie_section:
            blocks.append(movie_section)

        movie_gallery = (
            _gallery_items(raw_location.get("movie_gallery"), movie_id=movie_id)
            if include_media
            else _stored_gallery_items(location_media.get("movie_gallery"))
        )
        saved_images.extend(item["url"] for item in movie_gallery)

        gallery = _gallery_block(movie_gallery, f"wf-location-{location_id}-movie-gallery")
        if gallery:
            blocks.append(gallery)

        scene_html = str(_localized_value(raw_location, language, "scene_description_html") or "").strip()
        if not scene_html:
            scene_html = escape(_text(_localized_value(raw_location, language, "scene_description_text")))
        scene = _paragraph_block(
            _prefixed_paragraph_html(labels["scene_prefix"], scene_html),
            f"wf-location-{location_id}-scene",
        )
        if scene:
            blocks.append(scene)

        reality_section = _header_block(labels["reality"], f"wf-location-{location_id}-reality", level=4)
        if reality_section:
            blocks.append(reality_section)

        reality_gallery = (
            _gallery_items(raw_location.get("reality_gallery"), movie_id=movie_id)
            if include_media
            else _stored_gallery_items(location_media.get("reality_gallery"))
        )
        saved_images.extend(item["url"] for item in reality_gallery)

        reality = _gallery_block(reality_gallery, f"wf-location-{location_id}-reality-gallery")
        if reality:
            blocks.append(reality)

        map_block = _map_block(raw_location, f"wf-location-{location_id}-map")
        if map_block:
            blocks.append(map_block)

        spot_html = str(_localized_value(raw_location, language, "movie_spot_html") or "").strip()
        if not spot_html:
            spot_html = escape(_text(_localized_value(raw_location, language, "movie_spot_text")))
        spot = _paragraph_block(
            _prefixed_paragraph_html(labels["spot_prefix"], spot_html),
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
                "movie_gallery": movie_gallery,
                "reality_gallery": reality_gallery,
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
        template_data["release_date"] = str(year)
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
            "operation": payload.get("operation") or "upsert",
            "original_language": payload.get("original_language") or WHEREFILMED_ORIGINAL_LANGUAGE,
            "translation_languages": _payload_translation_languages(payload),
            "translations": _wherefilmed_translations_snapshot(payload),
            "images": image_payload,
        },
        "gallery_urls": saved_images[:20],
    }


def _translated_reference_items(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = container.get(key)
    if not isinstance(items, list):
        return []
    translated_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        translations = item.get("translations")
        if isinstance(translations, dict) and translations:
            translated_items.append(
                {
                    "id": item.get("id"),
                    "slug": item.get("slug"),
                    "title": item.get("title"),
                    "translations": translations,
                }
            )
    return translated_items


def _wherefilmed_translations_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    locations = payload.get("locations") if isinstance(payload.get("locations"), list) else []

    snapshot: dict[str, Any] = {}
    movie_translations = movie.get("translations")
    if isinstance(movie_translations, dict):
        snapshot["movie"] = movie_translations

    reference_payload: dict[str, Any] = {}
    for key in ("countries", "genres", "cities", "places"):
        translated_items = _translated_reference_items(movie, key)
        if translated_items:
            reference_payload[key] = translated_items
    if reference_payload:
        snapshot["references"] = reference_payload

    top_level_reference_payload: dict[str, Any] = {}
    for key in ("countries", "genres", "cities", "places"):
        translated_items = _translated_reference_items(payload, key)
        if translated_items:
            top_level_reference_payload[key] = translated_items
    if top_level_reference_payload:
        snapshot["top_level_references"] = top_level_reference_payload

    location_payload = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        translations = location.get("translations")
        if isinstance(translations, dict) and translations:
            item = {
                "id": location.get("id"),
                "title": location.get("title"),
                "translations": translations,
            }
        else:
            item = {
                "id": location.get("id"),
                "title": location.get("title"),
            }
        location_references: dict[str, Any] = {}
        for key in ("countries", "genres", "cities", "places"):
            translated_items = _translated_reference_items(location, key)
            if translated_items:
                location_references[key] = translated_items
        if location_references:
            item["references"] = location_references
        if item.get("translations") or item.get("references"):
            location_payload.append(item)
    if location_payload:
        snapshot["locations"] = location_payload

    return snapshot


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


def _editor_gallery_images_by_id(post: Post) -> dict[str, list[dict[str, str]]]:
    try:
        payload = json.loads(post.content or "{}")
    except (TypeError, ValueError):
        return {}
    blocks = payload.get("blocks") if isinstance(payload, dict) else []
    if not isinstance(blocks, list):
        return {}
    galleries: dict[str, list[dict[str, str]]] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get("type") or "").strip().lower() != "gallery":
            continue
        block_id = str(block.get("id") or "").strip()
        data = block.get("data")
        images = data.get("images") if isinstance(data, dict) else None
        if block_id and isinstance(images, list):
            galleries[block_id] = _stored_gallery_items(images)
    return galleries


def _image_payload_from_post(post: Post) -> dict[str, Any]:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    wherefilmed_data = raw_data.get("wherefilmed")
    if not isinstance(wherefilmed_data, dict):
        return {}
    images = wherefilmed_data.get("images")
    if not isinstance(images, dict):
        images = {}

    payload = dict(images)
    galleries = _editor_gallery_images_by_id(post)
    locations = payload.get("locations")
    if not isinstance(locations, list):
        locations = []
    next_locations: list[dict[str, Any]] = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        location_id = _as_int(item.get("id"))
        next_item = dict(item)
        if location_id:
            movie_key = f"wf-location-{location_id}-movie-gallery"
            reality_key = f"wf-location-{location_id}-reality-gallery"
            next_item["movie_gallery"] = _stored_gallery_items(
                next_item.get("movie_gallery") or galleries.get(movie_key)
            )
            next_item["reality_gallery"] = _stored_gallery_items(
                next_item.get("reality_gallery") or galleries.get(reality_key)
            )
        next_locations.append(next_item)
    payload["locations"] = next_locations
    return payload


def _find_wherefilmed_post(author: Author, *, site: str, movie_id: int) -> Post | None:
    existing = (
        Post.objects.filter(
            raw_data__wherefilmed__source_site=site,
            raw_data__wherefilmed__movie_id=movie_id,
        )
        .order_by("id")
        .first()
    )
    if existing:
        return existing
    return Post.objects.filter(
        author=author,
        message_id=_wherefilmed_message_id(movie_id),
    ).first()


def _merge_wherefilmed_metadata(
    post: Post,
    payload: dict[str, Any],
    *,
    movie_id: int,
    image_payload: dict[str, Any] | None = None,
) -> None:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    wherefilmed_data = raw_data.get("wherefilmed")
    if not isinstance(wherefilmed_data, dict):
        wherefilmed_data = {}
        raw_data["wherefilmed"] = wherefilmed_data
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    wherefilmed_data.update(
        {
            "source_site": "wherefilmed",
            "movie_id": movie_id,
            "slug": source.get("slug") or wherefilmed_data.get("slug"),
            "url": source.get("url") or wherefilmed_data.get("url"),
            "payload_version": payload.get("payload_version"),
            "operation": payload.get("operation") or wherefilmed_data.get("operation") or "upsert",
            "original_language": payload.get("original_language") or WHEREFILMED_ORIGINAL_LANGUAGE,
            "translation_languages": _payload_translation_languages(payload),
            "translations": _wherefilmed_translations_snapshot(payload),
        }
    )
    if image_payload:
        wherefilmed_data["images"] = image_payload
    post.raw_data = raw_data
    post.save(update_fields=["raw_data", "updated_at"])


def _has_language_payload(payload: dict[str, Any], language: str) -> bool:
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    if _translation_payload(movie, language):
        return True
    for key in ("countries", "genres", "cities", "places"):
        items = movie.get(key)
        if not isinstance(items, list):
            continue
        if any(isinstance(item, dict) and _translation_payload(item, language) for item in items):
            return True
    for key in ("countries", "genres", "cities", "places"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        if any(isinstance(item, dict) and _translation_payload(item, language) for item in items):
            return True
    locations = payload.get("locations") if isinstance(payload.get("locations"), list) else []
    for location in locations:
        if not isinstance(location, dict):
            continue
        if _translation_payload(location, language):
            return True
        for key in ("countries", "genres", "cities", "places"):
            items = location.get(key)
            if not isinstance(items, list):
                continue
            if any(isinstance(item, dict) and _translation_payload(item, language) for item in items):
                return True
    return False


def _save_wherefilmed_translations(
    post: Post,
    payload: dict[str, Any],
    *,
    movie_id: int,
    image_payload: dict[str, Any],
) -> None:
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    for language in _payload_translation_languages(payload):
        if not _has_language_payload(payload, language):
            continue
        content, _saved_images, _translated_image_payload = _build_content(
            payload,
            movie_id=movie_id,
            include_media=False,
            image_payload=image_payload,
            language=language,
        )
        preview = build_post_preview(content, post.raw_data)
        PostTranslation.objects.update_or_create(
            post=post,
            language=language,
            defaults={
                "title": _translated_post_title(movie, language),
                "content": content,
                "preview_content": preview["preview_content"],
                "status": POST_TRANSLATION_STATUS_TRANSLATED,
                "model": "wherefilmed-v2",
                "error_message": "",
                "raw_response": {
                    "source": payload.get("source"),
                    "payload_version": payload.get("payload_version"),
                    "operation": payload.get("operation") or "upsert",
                    "language": language,
                    "translation_payload": _wherefilmed_translations_snapshot(payload),
                },
            },
        )


def _import_payload(payload: dict[str, Any]) -> tuple[Post, bool]:
    payload_version = payload.get("payload_version")
    if payload_version not in {1, 2}:
        raise WhereFilmedImportError("unsupported payload_version")

    operation = _operation(payload) if payload_version == 2 else "upsert"
    include_media = _include_media(payload, operation)
    site, movie_id = _source_key(payload)
    author = _wherefilmed_author()
    message_id = _wherefilmed_message_id(movie_id)

    existing = _find_wherefilmed_post(author, site=site, movie_id=movie_id)
    if operation == "translations_only" and not existing:
        raise WhereFilmedImportError("source movie is not imported yet", 404)

    comun, category = _target_comun_and_category()
    if existing:
        image_payload = _image_payload_from_post(existing)
        if operation == "upsert":
            movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
            content, saved_images, image_payload = _build_content(
                payload,
                movie_id=movie_id,
                include_media=include_media and not bool(image_payload.get("poster_url")),
                image_payload=image_payload,
            )
            raw_data = _raw_data(
                payload,
                movie_id=movie_id,
                saved_images=saved_images,
                image_payload=image_payload,
            )
            source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
            source_url = _public_url(source.get("url"))
            existing.title = _post_title(movie)
            existing.content = content
            existing.source_url = source_url[:255]
            existing.channel_url = author.channel_url
            existing.raw_data = raw_data
            existing.is_pending = False
            existing.is_blocked = False
            existing.publish_at = None
            existing.save(
                update_fields=[
                    "title",
                    "content",
                    "source_url",
                    "channel_url",
                    "raw_data",
                    "is_pending",
                    "is_blocked",
                    "publish_at",
                    "updated_at",
                ]
            )
        else:
            _merge_wherefilmed_metadata(
                existing,
                payload,
                movie_id=movie_id,
                image_payload=image_payload,
            )
        _sync_existing_template_poster(existing)
        _save_wherefilmed_translations(
            existing,
            payload,
            movie_id=movie_id,
            image_payload=_image_payload_from_post(existing),
        )
        ComunPostCategoryAssignment.objects.update_or_create(
            comun=comun,
            post=existing,
            defaults={"category": category, "assigned_by": None},
        )
        return existing, False

    if operation == "translations_only":
        raise WhereFilmedImportError("source movie is not imported yet", 404)
    if not include_media:
        raise WhereFilmedImportError("include_media must be true for a new upsert")

    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
    content, saved_images, image_payload = _build_content(
        payload,
        movie_id=movie_id,
        include_media=True,
    )
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
    _save_wherefilmed_translations(post, payload, movie_id=movie_id, image_payload=image_payload)
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
