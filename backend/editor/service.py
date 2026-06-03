from __future__ import annotations

import base64
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime as dt_datetime, timedelta, timezone as dt_timezone

from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from django.contrib.auth import get_user_model
from django.db import OperationalError, ProgrammingError
from django.db.models import Avg, Count
from django.http import HttpRequest
from django.utils import timezone
from django.utils.text import slugify

from editor.models import (
    COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE,
    COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_OPTION_ITEMS,
    COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_VALUES,
    COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_HEADER,
    COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_OPTION_ITEMS,
    COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_VALUES,
    COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_OPTION_ITEMS,
    COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_SELECT,
    COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT,
    COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_VALUES,
    POST_TEMPLATE_TYPE_BASIC,
    POST_TEMPLATE_TYPE_CHOICES,
    POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS,
    POST_TEMPLATE_EDITOR_BLOCK_VALUES,
    POST_TEMPLATE_TYPE_MOVIE_REVIEW,
    POST_TEMPLATE_TYPE_MUSIC_RELEASE,
    POST_TEMPLATE_TYPE_POST_VOTE_POLL,
    POST_TEMPLATE_TYPE_TWEET,
    POST_TEMPLATE_TYPE_BUG_REPORT,
    ComunCustomPostTemplate,
    ComunCustomPostTemplateBlock,
    ComunCustomPostTemplateField,
    PostPollVote,
    PostRatingVote,
    PostTemplateConfig,
    default_enabled_template_editor_blocks,
    is_post_template_type_configured,
    normalize_allowed_post_templates,
    normalize_allowed_post_templates_override,
    normalize_post_template_type_code,
    normalize_template_editor_blocks_for_template,
    post_template_type_choices,
    template_editor_block_choices_for_template,
)
from feeds.models import Author, Post, PostFavorite
from rabotaem_backend.media_urls import rewrite_public_media_payload, rewrite_public_media_urls
from users.models import AuthorAdmin

User = get_user_model()

_POST_TEMPLATE_TYPE_OPTIONS = tuple(
    (str(value), str(label)) for value, label in POST_TEMPLATE_TYPE_CHOICES
)
_POST_TEMPLATE_TYPES = {value for value, _label in _POST_TEMPLATE_TYPE_OPTIONS}
_POST_TEMPLATE_MOVIE_KINDS = {"movie", "series"}
_POST_TEMPLATE_MOVIE_GENRES = {
    "action",
    "adventure",
    "animation",
    "biography",
    "comedy",
    "crime",
    "documentary",
    "drama",
    "family",
    "fantasy",
    "history",
    "horror",
    "music",
    "mystery",
    "romance",
    "sci_fi",
    "sport",
    "thriller",
    "war",
    "western",
}
_POST_TEMPLATE_MOVIE_GENRE_ALIASES = {
    "action": "action",
    "боевик": "action",
    "adventure": "adventure",
    "приключения": "adventure",
    "animation": "animation",
    "анимация": "animation",
    "мультфильм": "animation",
    "biography": "biography",
    "биография": "biography",
    "comedy": "comedy",
    "комедия": "comedy",
    "crime": "crime",
    "криминал": "crime",
    "documentary": "documentary",
    "документальный": "documentary",
    "drama": "drama",
    "драма": "drama",
    "family": "family",
    "семейный": "family",
    "fantasy": "fantasy",
    "фэнтези": "fantasy",
    "history": "history",
    "история": "history",
    "horror": "horror",
    "ужасы": "horror",
    "music": "music",
    "музыкальный": "music",
    "mystery": "mystery",
    "детектив": "mystery",
    "romance": "romance",
    "мелодрама": "romance",
    "sci_fi": "sci_fi",
    "sci-fi": "sci_fi",
    "sciencefiction": "sci_fi",
    "fantastic": "sci_fi",
    "фантастика": "sci_fi",
    "sport": "sport",
    "спорт": "sport",
    "thriller": "thriller",
    "триллер": "thriller",
    "war": "war",
    "военный": "war",
    "western": "western",
    "вестерн": "western",
}
_POST_TEMPLATE_MOVIE_WATCH_PROVIDERS = {
    "kinopoisk",
    "okko",
    "ivi",
    "wink",
    "start",
    "premier",
    "more_tv",
    "kion",
    "amediateka",
    "netflix",
    "amazon_prime_video",
    "disney_plus",
    "max",
    "apple_tv_plus",
    "hulu",
    "paramount_plus",
    "peacock",
}
_POST_TEMPLATE_MOVIE_WATCH_PROVIDER_ALIASES = {
    "kinopoisk": "kinopoisk",
    "kinopoisk hd": "kinopoisk",
    "kinopoiskhd": "kinopoisk",
    "кинопоиск": "kinopoisk",
    "кинопоиск hd": "kinopoisk",
    "okko": "okko",
    "ivi": "ivi",
    "иви": "ivi",
    "wink": "wink",
    "start": "start",
    "premier": "premier",
    "more_tv": "more_tv",
    "more tv": "more_tv",
    "moretv": "more_tv",
    "more.tv": "more_tv",
    "kion": "kion",
    "amediateka": "amediateka",
    "амедиатека": "amediateka",
    "netflix": "netflix",
    "amazon_prime_video": "amazon_prime_video",
    "amazonprimevideo": "amazon_prime_video",
    "amazon prime video": "amazon_prime_video",
    "amazon prime": "amazon_prime_video",
    "prime video": "amazon_prime_video",
    "disney_plus": "disney_plus",
    "disney plus": "disney_plus",
    "disneyplus": "disney_plus",
    "disney+": "disney_plus",
    "max": "max",
    "hbomax": "max",
    "hbo max": "max",
    "apple_tv_plus": "apple_tv_plus",
    "apple tv": "apple_tv_plus",
    "appletvplus": "apple_tv_plus",
    "apple tv+": "apple_tv_plus",
    "apple tv plus": "apple_tv_plus",
    "hulu": "hulu",
    "paramount_plus": "paramount_plus",
    "paramount plus": "paramount_plus",
    "paramountplus": "paramount_plus",
    "paramount+": "paramount_plus",
    "peacock": "peacock",
    "peacock tv": "peacock",
    "peacocktv": "peacock",
}
_POST_TEMPLATE_MUSIC_STYLES = {
    "pop",
    "rock",
    "indie",
    "alternative",
    "metal",
    "punk",
    "hip_hop",
    "rap",
    "rnb",
    "electronic",
    "edm",
    "house",
    "techno",
    "trance",
    "drum_and_bass",
    "dubstep",
    "ambient",
    "lo_fi",
    "jazz",
    "blues",
    "soul",
    "funk",
    "reggae",
    "ska",
    "folk",
    "country",
    "classical",
    "soundtrack",
}
_POST_TEMPLATE_MUSIC_STYLE_ALIASES = {
    "pop": "pop",
    "поп": "pop",
    "rock": "rock",
    "рок": "rock",
    "indie": "indie",
    "инди": "indie",
    "alternative": "alternative",
    "альтернатива": "alternative",
    "альтернативный": "alternative",
    "metal": "metal",
    "метал": "metal",
    "металл": "metal",
    "punk": "punk",
    "панк": "punk",
    "hip_hop": "hip_hop",
    "hip-hop": "hip_hop",
    "хипхоп": "hip_hop",
    "хип-хоп": "hip_hop",
    "rap": "rap",
    "рэп": "rap",
    "rnb": "rnb",
    "r&b": "rnb",
    "electronic": "electronic",
    "электроника": "electronic",
    "edm": "edm",
    "house": "house",
    "techno": "techno",
    "trance": "trance",
    "drum_and_bass": "drum_and_bass",
    "drum and bass": "drum_and_bass",
    "dnb": "drum_and_bass",
    "dubstep": "dubstep",
    "ambient": "ambient",
    "эмбиент": "ambient",
    "lo_fi": "lo_fi",
    "lo-fi": "lo_fi",
    "lofi": "lo_fi",
    "jazz": "jazz",
    "джаз": "jazz",
    "blues": "blues",
    "блюз": "blues",
    "soul": "soul",
    "соул": "soul",
    "funk": "funk",
    "фанк": "funk",
    "reggae": "reggae",
    "регги": "reggae",
    "ska": "ska",
    "ска": "ska",
    "folk": "folk",
    "фолк": "folk",
    "country": "country",
    "кантри": "country",
    "classical": "classical",
    "классика": "classical",
    "soundtrack": "soundtrack",
    "саундтрек": "soundtrack",
}
_IMDB_ID_RE = re.compile(r"(tt\d{5,12})", flags=re.IGNORECASE)
_TEMPLATE_POLL_SOURCE_POST_VOTE = "template_post_vote_poll"
_CONTENT_POLL_SOURCE_INLINE = "content_inline_poll"
_TWEET_TEMPLATE_MAX_LENGTH = 280
_TWEET_ALLOWED_EDITOR_BLOCK_TYPES = {"paragraph", "image", "gallery"}
_JUSTWATCH_PROVIDER_CACHE: dict[str, tuple[float, dict[int, str]]] = {}
_BUG_REPORT_STATUSES = {"review", "in_progress", "resolved", "rejected"}
_BUG_REPORT_STATUS_ALIASES = {
    "review": "review",
    "рассмотрение": "review",
    "in_progress": "in_progress",
    "в работе": "in_progress",
    "resolved": "resolved",
    "решена": "resolved",
    "rejected": "rejected",
    "отклонена": "rejected",
}
_BUG_REPORT_PLATFORMS = {"web", "windows", "macos", "linux", "android", "ios"}
_BUG_REPORT_PLATFORM_ALIASES = {
    "web": "web",
    "веб": "web",
    "браузер": "web",
    "windows": "windows",
    "виндовс": "windows",
    "win": "windows",
    "macos": "macos",
    "mac os": "macos",
    "mac": "macos",
    "linux": "linux",
    "линукс": "linux",
    "android": "android",
    "андроид": "android",
    "ios": "ios",
    "айос": "ios",
    "iphone": "ios",
    "ipad": "ios",
}
_BUG_REPORT_BROWSERS = {
    "chrome",
    "safari",
    "firefox",
    "edge",
    "opera",
    "yandex_browser",
    "samsung_internet",
    "arc",
    "other",
}
_BUG_REPORT_BROWSER_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "safari": "safari",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "edge": "edge",
    "microsoft edge": "edge",
    "opera": "opera",
    "yandex browser": "yandex_browser",
    "яндекс браузер": "yandex_browser",
    "yandex_browser": "yandex_browser",
    "samsung internet": "samsung_internet",
    "samsung_internet": "samsung_internet",
    "arc": "arc",
    "other": "other",
    "другое": "other",
}


def _fv():
    from feeds import views as feed_views

    return feed_views


def _decode_editor_payload(raw_content: str) -> dict | None:
    raw = str(raw_content or "").strip()
    if not raw:
        return None

    candidates: list[str] = []
    if raw.startswith("{") and raw.endswith("}"):
        candidates.append(raw)
    elif re.fullmatch(r"[A-Za-z0-9_\-+/=]+", raw):
        for encoded in (raw, raw.replace("-", "+").replace("_", "/")):
            padded = encoded + ("=" * (-len(encoded) % 4))
            try:
                decoded = base64.b64decode(padded, validate=False).decode("utf-8")
            except Exception:
                continue
            if decoded:
                candidates.append(decoded)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("blocks"), list):
            return payload
    return None


def _extract_editor_payload_title(raw_content: str) -> str:
    payload = _decode_editor_payload(raw_content)
    if not payload:
        return ""

    additional = payload.get("additional")
    if isinstance(additional, dict):
        for key in ("metaTitle", "previewDescription"):
            value = _fv()._strip_html(str(additional.get(key) or "")).strip()
            if value:
                title = _fv()._build_title(value)
                if title:
                    return title

    for block in payload.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        block_data = block.get("data")
        if not isinstance(block_data, dict):
            continue
        text_candidates: list[str] = []
        if block_type in {"header", "paragraph", "quote"}:
            text_candidates.append(str(block_data.get("text") or ""))
        elif block_type in {"link", "customlink"}:
            text_candidates.append(str(block_data.get("text") or block_data.get("title") or ""))
        for candidate in text_candidates:
            text = _fv()._strip_html(candidate).strip()
            if not text:
                continue
            title = _fv()._build_title(text)
            if title:
                return title
    return ""


def _tweet_template_text_from_block(raw_block: object) -> str:
    if not isinstance(raw_block, dict):
        return ""
    block_type = str(raw_block.get("type") or "").strip().lower()
    if block_type != "paragraph":
        return ""
    block_data = raw_block.get("data")
    if not isinstance(block_data, dict):
        return ""
    return _fv()._strip_html(str(block_data.get("text") or "")).strip()


def _tweet_template_character_count(raw_content: str) -> int:
    payload = _decode_editor_payload(raw_content)
    if not payload:
        normalized = re.sub(r"\s+", " ", _fv()._strip_html(str(raw_content or ""))).strip()
        return len(normalized)

    normalized_parts = [
        part
        for part in (_tweet_template_text_from_block(block) for block in payload.get("blocks") or [])
        if part
    ]
    return len("\n".join(normalized_parts).strip())


def _validate_template_content_constraints(
    template_payload: dict | None,
    raw_content: str,
) -> str | None:
    if _template_type_from_payload(template_payload) != POST_TEMPLATE_TYPE_TWEET:
        return None

    payload = _decode_editor_payload(raw_content)
    media_blocks_count = 0
    if payload:
        for raw_block in payload.get("blocks") or []:
            if not isinstance(raw_block, dict):
                continue
            block_type = str(raw_block.get("type") or "").strip().lower()
            if not block_type:
                continue
            if block_type not in _TWEET_ALLOWED_EDITOR_BLOCK_TYPES:
                return "Шаблон «Твит» поддерживает только текст и изображения."
            if block_type in {"image", "gallery"}:
                media_blocks_count += 1
    if media_blocks_count > 1:
        return "В шаблоне «Твит» можно использовать только один медиаблок."

    if _tweet_template_character_count(raw_content) > _TWEET_TEMPLATE_MAX_LENGTH:
        return f"Твит не может быть длиннее {_TWEET_TEMPLATE_MAX_LENGTH} символов."
    return None


def _http_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 6.0,
) -> dict | list | None:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "TamburBot/1.0 (+https://tambur.pub)",
    }
    if headers:
        request_headers.update(headers)

    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _http_json_get(
    url: str, *, headers: dict[str, str] | None = None, timeout: float = 6.0
) -> dict | list | None:
    return _http_json_request(url, method="GET", headers=headers, timeout=timeout)


def _http_json_post(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 6.0,
) -> dict | list | None:
    return _http_json_request(
        url, method="POST", payload=payload, headers=headers, timeout=timeout
    )


def _extract_imdb_id(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    matched = _IMDB_ID_RE.search(raw)
    if not matched:
        return ""
    return matched.group(1).lower()


def _canonical_imdb_url(imdb_id: str) -> str:
    return f"https://www.imdb.com/title/{imdb_id}/"


def _normalize_movie_watch_provider_value(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidates = [raw.lower()]
    normalized_spaces = re.sub(r"[\s._\-]+", " ", raw.lower()).strip()
    if normalized_spaces:
        candidates.extend(
            [
                normalized_spaces,
                normalized_spaces.replace(" ", ""),
                normalized_spaces.replace(" ", "_"),
                normalized_spaces.replace(" ", "."),
            ]
        )
    for candidate in candidates:
        mapped = _POST_TEMPLATE_MOVIE_WATCH_PROVIDER_ALIASES.get(candidate)
        if mapped:
            return mapped
    return raw


def _parse_release_date_hint(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    iso_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw)
    if iso_date:
        return iso_date.group(1)
    year_month = re.search(r"\b(\d{4})-(\d{2})\b", raw)
    if year_month:
        return f"{year_month.group(1)}-{year_month.group(2)}-01"
    year_only = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", raw)
    if year_only:
        return f"{year_only.group(1)}-01-01"
    return ""


def _movie_review_autofill_from_cinemeta(imdb_id: str) -> dict:
    for endpoint_kind in ("movie", "series"):
        payload = _http_json_get(
            f"https://v3-cinemeta.strem.io/meta/{endpoint_kind}/{imdb_id}.json",
            timeout=5.0,
        )
        if not isinstance(payload, dict):
            continue
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            continue
        title = str(meta.get("name") or "").strip()
        if not title:
            continue
        genres_raw = meta.get("genres")
        first_genre = ""
        if isinstance(genres_raw, list):
            for genre_item in genres_raw:
                genre_value = str(genre_item or "").strip()
                if genre_value:
                    first_genre = genre_value
                    break
        if not first_genre:
            first_genre = str(meta.get("genre") or "").strip()
        release_date = _parse_release_date_hint(
            meta.get("releaseInfo") or meta.get("released") or meta.get("year")
        )
        raw_kind = str(meta.get("type") or endpoint_kind).strip().lower()
        content_kind = "series" if raw_kind in {"series", "show", "tv"} else "movie"
        return {
            "title": title,
            "poster_url": str(meta.get("poster") or "").strip(),
            "genre": first_genre,
            "content_kind": content_kind,
            "release_date": release_date,
        }
    return {}


def _movie_review_autofill_from_wikidata(imdb_id: str) -> dict:
    query = f"""
SELECT ?itemLabel ?originalTitle ?genreLabel ?publicationDate ?instanceOfLabel ?poster WHERE {{
  ?item wdt:P345 "{imdb_id}".
  OPTIONAL {{ ?item wdt:P1476 ?originalTitle. }}
  OPTIONAL {{ ?item wdt:P136 ?genre. }}
  OPTIONAL {{ ?item wdt:P577 ?publicationDate. }}
  OPTIONAL {{ ?item wdt:P31 ?instanceOf. }}
  OPTIONAL {{ ?item wdt:P18 ?poster. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en". }}
}}
LIMIT 25
""".strip()
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
        {"format": "json", "query": query}
    )
    payload = _http_json_get(
        url,
        headers={"Accept": "application/sparql-results+json"},
        timeout=8.0,
    )
    if not isinstance(payload, dict):
        return {}
    rows = (
        payload.get("results", {}).get("bindings", [])
        if isinstance(payload.get("results"), dict)
        else []
    )
    if not isinstance(rows, list) or not rows:
        return {}

    title = ""
    original_title = ""
    genre = ""
    release_date = ""
    content_kind = ""
    poster_url = ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not title:
            title = str(row.get("itemLabel", {}).get("value") or "").strip()
        if not original_title:
            original_title = str(row.get("originalTitle", {}).get("value") or "").strip()
        if not genre:
            genre = str(row.get("genreLabel", {}).get("value") or "").strip()
        if not release_date:
            release_date = _parse_release_date_hint(
                row.get("publicationDate", {}).get("value")
            )
        if not content_kind:
            raw_instance = str(row.get("instanceOfLabel", {}).get("value") or "").lower()
            if any(token in raw_instance for token in ("сериал", "series", "television")):
                content_kind = "series"
            elif any(token in raw_instance for token in ("фильм", "film", "movie")):
                content_kind = "movie"
        if not poster_url:
            poster_value = str(row.get("poster", {}).get("value") or "").strip()
            if poster_value.startswith("http://") or poster_value.startswith("https://"):
                poster_url = poster_value
            elif poster_value:
                poster_url = (
                    "https://commons.wikimedia.org/wiki/Special:FilePath/"
                    + urllib.parse.quote(poster_value)
                )

    return {
        "title": title,
        "original_title": original_title,
        "genre": genre,
        "release_date": release_date,
        "content_kind": content_kind,
        "poster_url": poster_url,
    }


def _justwatch_provider_names_by_id(locale: str) -> dict[int, str]:
    now_ts = time.time()
    cached = _JUSTWATCH_PROVIDER_CACHE.get(locale)
    if cached and (now_ts - cached[0]) < 60 * 60 * 24:
        return cached[1]

    payload = _http_json_get(
        f"https://apis.justwatch.com/content/providers/locale/{locale}",
        timeout=6.0,
    )
    providers_raw: list[object]
    if isinstance(payload, list):
        providers_raw = payload
    elif isinstance(payload, dict):
        providers_raw = payload.get("items") or payload.get("providers") or []
    else:
        providers_raw = []

    provider_map: dict[int, str] = {}
    for provider in providers_raw:
        if not isinstance(provider, dict):
            continue
        provider_id = provider.get("id")
        if not isinstance(provider_id, int):
            continue
        provider_name = str(
            provider.get("clear_name")
            or provider.get("short_name")
            or provider.get("technical_name")
            or ""
        ).strip()
        if not provider_name:
            continue
        provider_map[provider_id] = provider_name

    _JUSTWATCH_PROVIDER_CACHE[locale] = (now_ts, provider_map)
    return provider_map


def _movie_review_autofill_from_justwatch(
    imdb_id: str,
    *,
    title: str = "",
    original_title: str = "",
    content_kind: str = "",
) -> dict:
    queries: list[str] = []
    for raw_query in (title, original_title, imdb_id):
        query = str(raw_query or "").strip()
        if query and query not in queries:
            queries.append(query)

    if not queries:
        return {}

    collected: list[str] = []
    seen: set[str] = set()
    for locale in ("ru_RU", "en_US"):
        provider_names_by_id = _justwatch_provider_names_by_id(locale)
        for query in queries:
            search_payload = _http_json_post(
                f"https://apis.justwatch.com/content/titles/{locale}/popular",
                {
                    "query": query,
                    "page_size": 8,
                    "page": 1,
                    "content_types": ["movie", "show"],
                },
                timeout=7.0,
            )
            if not isinstance(search_payload, dict):
                continue
            items = search_payload.get("items")
            if not isinstance(items, list):
                continue

            for item in items[:6]:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("id")
                if not isinstance(item_id, int):
                    continue
                object_type = str(item.get("object_type") or "").strip().lower()
                inferred_kind = "series" if object_type in {"show", "series"} else "movie"
                if content_kind in _POST_TEMPLATE_MOVIE_KINDS and inferred_kind != content_kind:
                    continue

                details_payload = _http_json_get(
                    f"https://apis.justwatch.com/content/titles/{object_type or 'movie'}/{item_id}/locale/{locale}",
                    timeout=7.0,
                )
                if not isinstance(details_payload, dict):
                    continue
                offers = details_payload.get("offers")
                if not isinstance(offers, list):
                    continue
                for offer in offers:
                    if not isinstance(offer, dict):
                        continue
                    provider_id_raw = offer.get("provider_id")
                    provider_name_from_map = (
                        provider_names_by_id.get(provider_id_raw)
                        if isinstance(provider_id_raw, int)
                        else None
                    )
                    candidates = [
                        offer.get("package_short_name"),
                        offer.get("package_clear_name"),
                        offer.get("retailer"),
                        provider_name_from_map,
                    ]
                    for candidate in candidates:
                        mapped = _normalize_movie_watch_provider_value(candidate)
                        if mapped not in _POST_TEMPLATE_MOVIE_WATCH_PROVIDERS:
                            continue
                        if mapped in seen:
                            continue
                        seen.add(mapped)
                        collected.append(mapped)
                if len(collected) >= 10:
                    return {"watch_where": collected[:10]}
    if not collected:
        return {}
    return {"watch_where": collected[:10]}


def movie_review_autofill_template_from_imdb(imdb_input: object) -> tuple[dict | None, str | None, list[str], list[str], str]:
    imdb_id = _extract_imdb_id(imdb_input)
    if not imdb_id:
        return None, "invalid imdb url", [], [], ""

    autofill_data: dict[str, object] = {"imdb_url": _canonical_imdb_url(imdb_id)}
    sources: list[str] = []
    warnings: list[str] = []

    cinemeta_data = _movie_review_autofill_from_cinemeta(imdb_id)
    if cinemeta_data:
        sources.append("cinemeta")
        for key, value in cinemeta_data.items():
            if isinstance(value, str) and value.strip():
                autofill_data[key] = value.strip()

    wikidata_data = _movie_review_autofill_from_wikidata(imdb_id)
    if wikidata_data:
        sources.append("wikidata")
        for key in ("title", "original_title", "genre", "release_date", "content_kind", "poster_url"):
            value = wikidata_data.get(key)
            if isinstance(value, str) and value.strip() and not autofill_data.get(key):
                autofill_data[key] = value.strip()

    justwatch_data = _movie_review_autofill_from_justwatch(
        imdb_id,
        title=str(autofill_data.get("title") or ""),
        original_title=str(autofill_data.get("original_title") or ""),
        content_kind=str(autofill_data.get("content_kind") or ""),
    )
    if justwatch_data:
        sources.append("justwatch")
        watch_where = justwatch_data.get("watch_where")
        if isinstance(watch_where, list) and watch_where:
            autofill_data["watch_where"] = watch_where
    else:
        warnings.append("Не удалось определить площадки для просмотра")

    normalized_data, template_error = _normalize_movie_review_template_data(autofill_data)
    if template_error:
        return None, template_error, sources, warnings, imdb_id
    if not normalized_data:
        return None, "could not fetch movie data", sources, warnings, imdb_id
    return normalized_data, None, sources, warnings, imdb_id


def _normalize_template_text(value: object, max_length: int) -> tuple[str, str | None]:
    text = str(value or "").strip()
    if len(text) > max_length:
        return "", "template field is too long"
    return text, None


def _normalize_template_http_url(value: object) -> tuple[str, str | None]:
    url = str(value or "").strip()
    if not url:
        return "", None
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "", "invalid template url"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", "invalid template url"
    return url, None


def _normalize_movie_review_genre(value: object) -> tuple[str, str | None]:
    genre, genre_error = _normalize_template_text(value, 80)
    if genre_error:
        return "", "genre is too long"
    if not genre:
        return "", None
    normalized = _POST_TEMPLATE_MOVIE_GENRE_ALIASES.get(genre.lower(), genre)
    if normalized in _POST_TEMPLATE_MOVIE_GENRES:
        return normalized, None
    return normalized, None


def _normalize_movie_review_watch_where(value: object) -> tuple[list[str], str | None]:
    if value in (None, "", []):
        return [], None

    raw_items: list[object]
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    elif isinstance(value, str):
        raw_items = [item for item in re.split(r"[;,]", value)]
    else:
        return [], "invalid watch platform value"

    normalized_items: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item, item_error = _normalize_template_text(raw_item, 120)
        if item_error:
            return [], "watch platform value is too long"
        if not item:
            continue
        normalized = _normalize_movie_watch_provider_value(item)
        value_to_store = normalized
        dedupe_key = value_to_store.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_items.append(value_to_store)

    if len(normalized_items) > 24:
        return [], "too many watch platforms"
    return normalized_items, None


def _normalize_movie_review_author_rating(value: object) -> tuple[str, str | None]:
    raw = str(value or "").strip().replace(",", ".")
    if not raw:
        return "", None
    try:
        numeric = float(raw)
    except (TypeError, ValueError):
        return "", "invalid author rating"
    if numeric < 0 or numeric > 10:
        return "", "invalid author rating"
    normalized = round(numeric, 1)
    if float(normalized).is_integer():
        return str(int(normalized)), None
    return f"{normalized:.1f}".rstrip("0").rstrip("."), None


def _normalize_movie_review_template_data(raw_data: object) -> tuple[dict | None, str | None]:
    if raw_data in (None, "", {}):
        return None, None
    if not isinstance(raw_data, dict):
        return None, "invalid movie review template data"

    imdb_url, url_error = _normalize_template_http_url(raw_data.get("imdb_url"))
    if url_error:
        return None, "invalid imdb url"
    poster_url, poster_error = _normalize_template_http_url(raw_data.get("poster_url"))
    if poster_error:
        return None, "invalid poster url"
    genre, genre_error = _normalize_movie_review_genre(raw_data.get("genre"))
    if genre_error:
        return None, genre_error
    title, title_error = _normalize_template_text(raw_data.get("title"), 255)
    if title_error:
        return None, "movie title is too long"
    original_title, original_title_error = _normalize_template_text(
        raw_data.get("original_title"), 255
    )
    if original_title_error:
        return None, "original title is too long"
    watch_where, watch_where_error = _normalize_movie_review_watch_where(
        raw_data.get("watch_where")
    )
    if watch_where_error:
        return None, watch_where_error
    author_rating, author_rating_error = _normalize_movie_review_author_rating(
        raw_data.get("author_rating")
    )
    if author_rating_error:
        return None, author_rating_error

    raw_kind = str(
        raw_data.get("content_kind")
        or raw_data.get("kind")
        or raw_data.get("content_type")
        or ""
    ).strip().lower()
    if raw_kind in {"film", "movie", "фильм"}:
        content_kind = "movie"
    elif raw_kind in {"series", "serial", "tv", "сериал"}:
        content_kind = "series"
    else:
        content_kind = ""
    if raw_kind and content_kind not in _POST_TEMPLATE_MOVIE_KINDS:
        return None, "invalid movie review type"

    release_date_raw = str(raw_data.get("release_date") or "").strip()
    release_date = ""
    if release_date_raw:
        try:
            release_date = dt_datetime.strptime(release_date_raw, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None, "invalid release date"

    normalized_data = {
        "imdb_url": imdb_url,
        "poster_url": poster_url,
        "genre": genre,
        "content_kind": content_kind,
        "title": title,
        "original_title": original_title,
        "release_date": release_date,
        "watch_where": watch_where,
        "author_rating": author_rating,
    }
    cleaned_data: dict[str, object] = {}
    for key, value in normalized_data.items():
        if isinstance(value, str) and value.strip():
            cleaned_data[key] = value
            continue
        if isinstance(value, list) and value:
            cleaned_data[key] = value
    if not cleaned_data:
        return None, None
    return cleaned_data, None


def _normalize_music_release_style(value: object) -> tuple[str, str | None]:
    style, style_error = _normalize_template_text(value, 120)
    if style_error:
        return "", "music style is too long"
    if not style:
        return "", None
    normalized = _POST_TEMPLATE_MUSIC_STYLE_ALIASES.get(style.lower(), style)
    if normalized in _POST_TEMPLATE_MUSIC_STYLES:
        return normalized, None
    return normalized, None


def _normalize_music_release_template_data(raw_data: object) -> tuple[dict | None, str | None]:
    if raw_data in (None, "", {}):
        return None, None
    if not isinstance(raw_data, dict):
        return None, "invalid music release template data"

    cover_image_url, cover_error = _normalize_template_http_url(
        raw_data.get("cover_image_url") or raw_data.get("cover_url")
    )
    if cover_error:
        return None, "invalid cover image url"

    album_url, album_url_error = _normalize_template_http_url(
        raw_data.get("album_url")
        or raw_data.get("release_url")
        or raw_data.get("link")
        or raw_data.get("album_link")
    )
    if album_url_error:
        return None, "invalid album url"

    artist_name, artist_name_error = _normalize_template_text(
        raw_data.get("artist_name")
        or raw_data.get("group_name")
        or raw_data.get("band_name"),
        255,
    )
    if artist_name_error:
        return None, "artist name is too long"

    release_title, release_title_error = _normalize_template_text(
        raw_data.get("release_title")
        or raw_data.get("album_title")
        or raw_data.get("title"),
        255,
    )
    if release_title_error:
        return None, "release title is too long"

    country, country_error = _normalize_template_text(raw_data.get("country"), 120)
    if country_error:
        return None, "country is too long"

    city, city_error = _normalize_template_text(raw_data.get("city"), 120)
    if city_error:
        return None, "city is too long"

    style, style_error = _normalize_music_release_style(
        raw_data.get("style") or raw_data.get("music_style") or raw_data.get("genre")
    )
    if style_error:
        return None, style_error

    release_date_raw = str(raw_data.get("release_date") or "").strip()
    release_date = ""
    if release_date_raw:
        try:
            release_date = dt_datetime.strptime(release_date_raw, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None, "invalid release date"

    normalized_data = {
        "cover_image_url": cover_image_url,
        "release_date": release_date,
        "album_url": album_url,
        "artist_name": artist_name,
        "release_title": release_title,
        "country": country,
        "city": city,
        "style": style,
    }
    cleaned_data: dict[str, object] = {}
    for key, value in normalized_data.items():
        if isinstance(value, str) and value.strip():
            cleaned_data[key] = value
            continue
        if isinstance(value, list) and value:
            cleaned_data[key] = value
    if not cleaned_data:
        return None, None
    return cleaned_data, None


def _normalize_bug_report_status(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "review"
    return _BUG_REPORT_STATUS_ALIASES.get(raw, "review")


def _normalize_bug_report_multi_value(
    value: object,
    *,
    aliases: dict[str, str],
    allowed_values: set[str],
) -> list[str]:
    if isinstance(value, str):
        source = re.split(r"[\n,;]+", value)
    elif isinstance(value, (list, tuple, set)):
        source = list(value)
    else:
        source = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in source:
        raw = str(item or "").strip()
        if not raw:
            continue
        normalized_value = aliases.get(raw.lower(), raw.lower())
        if normalized_value not in allowed_values or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized.append(normalized_value)
    return normalized


def _normalize_bug_report_template_data(raw_data: object) -> tuple[dict, str | None]:
    source = raw_data if isinstance(raw_data, dict) else {}
    return {
        "status": _normalize_bug_report_status(source.get("status")),
        "platforms": _normalize_bug_report_multi_value(
            source.get("platforms") or source.get("platform"),
            aliases=_BUG_REPORT_PLATFORM_ALIASES,
            allowed_values=_BUG_REPORT_PLATFORMS,
        ),
        "browsers": _normalize_bug_report_multi_value(
            source.get("browsers") or source.get("browser"),
            aliases=_BUG_REPORT_BROWSER_ALIASES,
            allowed_values=_BUG_REPORT_BROWSERS,
        ),
        "error_code": str(source.get("error_code") or source.get("error") or "").strip()[:4000],
        "screenshot_url": str(
            source.get("screenshot_url") or source.get("photo_url") or source.get("image_url") or ""
        ).strip()[:2000],
    }, None


def _normalize_template_datetime(value: object) -> tuple[str, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return "", None
    normalized_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = dt_datetime.fromisoformat(normalized_raw)
    except ValueError:
        return "", "invalid datetime"
    if timezone.is_naive(parsed):
        try:
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        except Exception:
            return "", "invalid datetime"
    return parsed.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z"), None


def _normalize_template_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    raw = str(value or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _normalize_post_vote_poll_template_items(
    raw_items: object,
    *,
    resolve_posts: bool = False,
) -> tuple[list[dict], str | None]:
    if not isinstance(raw_items, list):
        return [], "invalid voting posts list"

    ordered_post_ids: list[int] = []
    seen_post_ids: set[int] = set()
    raw_items_by_post_id: dict[int, dict] = {}
    for raw_item in raw_items:
        candidate_id: int | None = None
        raw_item_dict = raw_item if isinstance(raw_item, dict) else None
        if isinstance(raw_item_dict, dict):
            candidate_id = _fv()._parse_post_reference_to_id(
                raw_item_dict.get("post_id")
                or raw_item_dict.get("id")
                or raw_item_dict.get("post")
                or raw_item_dict.get("url")
                or raw_item_dict.get("path")
                or raw_item_dict.get("ref")
            )
        if candidate_id is None:
            candidate_id = _fv()._parse_post_reference_to_id(raw_item)
        if candidate_id is None:
            continue
        if candidate_id in seen_post_ids:
            continue
        seen_post_ids.add(candidate_id)
        ordered_post_ids.append(candidate_id)
        raw_items_by_post_id[candidate_id] = raw_item_dict or {}

    if len(ordered_post_ids) < 2:
        return [], "at least two posts are required for voting"
    if len(ordered_post_ids) > 10:
        return [], "too many posts in voting"

    if resolve_posts:
        now = timezone.now()
        posts = (
            Post.objects.filter(
                id__in=ordered_post_ids,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(_fv()._publish_ready_filter(now))
            .select_related("author")
        )
        posts_by_id = {post.id: post for post in posts}
        missing_ids = [post_id for post_id in ordered_post_ids if post_id not in posts_by_id]
        if missing_ids:
            return [], "some voting posts were not found"

        normalized_items: list[dict] = []
        for post_id in ordered_post_ids:
            post = posts_by_id[post_id]
            post_title = _fv()._post_display_title(post)
            post_slug = _fv()._slugify_title(post_title)
            post_path = f"/b/post/{post.id}-{post_slug}" if post_slug else f"/b/post/{post.id}"
            normalized_items.append(
                {
                    "post_id": post.id,
                    "title": post_title,
                    "path": post_path,
                    "author_username": post.author.username,
                }
            )
        return normalized_items, None

    normalized_items = []
    for post_id in ordered_post_ids:
        raw_item = raw_items_by_post_id.get(post_id, {})
        title, title_error = _normalize_template_text(raw_item.get("title"), 255)
        if title_error:
            return [], "voting post title is too long"
        if title:
            decoded_title = _extract_editor_payload_title(title)
            if decoded_title:
                title = decoded_title
            elif len(title) >= 48 and re.fullmatch(r"[A-Za-z0-9_\-+/=]+", title):
                title = f"Пост #{post_id}"
        if not title:
            title = f"Пост #{post_id}"
        path = str(raw_item.get("path") or "").strip()
        if path and not path.startswith("/"):
            path = ""
        author_username, author_error = _normalize_template_text(
            raw_item.get("author_username"), 150
        )
        if author_error:
            return [], "voting post author username is too long"
        normalized_item: dict[str, object] = {
            "post_id": post_id,
            "title": title,
        }
        if path:
            normalized_item["path"] = path
        if author_username:
            normalized_item["author_username"] = author_username
        normalized_items.append(normalized_item)
    return normalized_items, None


def _normalize_post_vote_poll_template_data(
    raw_data: object,
    *,
    resolve_posts: bool = False,
) -> tuple[dict | None, str | None]:
    if raw_data in (None, "", {}):
        return None, "invalid post vote poll template data"
    if not isinstance(raw_data, dict):
        return None, "invalid post vote poll template data"

    question, question_error = _normalize_template_text(raw_data.get("question"), 255)
    if question_error:
        return None, "poll question is too long"

    ends_at, ends_at_error = _normalize_template_datetime(
        raw_data.get("ends_at")
        or raw_data.get("deadline_at")
        or raw_data.get("expires_at")
        or raw_data.get("close_at")
    )
    if ends_at_error:
        return None, "invalid voting deadline"
    if not ends_at:
        return None, "voting deadline is required"

    allows_multiple_answers = _normalize_template_bool(
        raw_data.get("allows_multiple_answers")
        or raw_data.get("allow_multiple_answers")
        or raw_data.get("multiple")
    )

    items_input = raw_data.get("items")
    if items_input is None:
        items_input = raw_data.get("posts")
    if items_input is None:
        items_input = raw_data.get("post_refs")
    normalized_items, items_error = _normalize_post_vote_poll_template_items(
        items_input, resolve_posts=resolve_posts
    )
    if items_error:
        return None, items_error

    normalized_data: dict[str, object] = {
        "items": normalized_items,
        "ends_at": ends_at,
        "allows_multiple_answers": allows_multiple_answers,
    }
    if question:
        normalized_data["question"] = question
    return normalized_data, None


def _build_post_vote_poll_raw_poll(template_data: object) -> dict | None:
    if not isinstance(template_data, dict):
        return None
    items = template_data.get("items")
    if not isinstance(items, list):
        return None
    option_items: list[dict] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        post_id = _fv()._parse_post_reference_to_id(raw_item.get("post_id"))
        if post_id is None:
            continue
        option_text = str(raw_item.get("title") or "").strip() or f"Пост #{post_id}"
        option_payload: dict[str, object] = {
            "text": option_text,
            "voter_count": 0,
            "post_id": post_id,
        }
        path = str(raw_item.get("path") or "").strip()
        if path.startswith("/"):
            option_payload["post_path"] = path
        option_items.append(option_payload)
    if len(option_items) < 2:
        return None

    question = str(template_data.get("question") or "").strip() or "Голосование за посты"
    allows_multiple_answers = _normalize_template_bool(
        template_data.get("allows_multiple_answers")
    )
    raw_poll: dict[str, object] = {
        "question": question,
        "options": option_items,
        "is_anonymous": False,
        "allows_multiple_answers": allows_multiple_answers,
        "is_closed": False,
        "total_voter_count": 0,
    }
    close_at = str(template_data.get("ends_at") or "").strip()
    if close_at:
        raw_poll["close_at"] = close_at
    return raw_poll


def _extract_inline_poll_from_content(raw_content: str) -> dict | None:
    payload = _decode_editor_payload(raw_content)
    if not payload:
        return None

    for block in payload.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        if block_type != "poll":
            continue
        block_data = block.get("data")
        if not isinstance(block_data, dict):
            continue

        question = str(block_data.get("question") or "").strip()
        raw_options = block_data.get("options")
        if not question or not isinstance(raw_options, list):
            return None

        option_items: list[dict[str, object]] = []
        for raw_option in raw_options[:10]:
            text = str(raw_option or "").strip()
            if not text:
                continue
            option_items.append({"text": text, "voter_count": 0})
        if len(option_items) < 2:
            return None

        uid = str(block_data.get("uid") or "").strip()
        raw_poll: dict[str, object] = {
            "question": question,
            "options": option_items,
            "is_anonymous": False,
            "allows_multiple_answers": bool(block_data.get("allows_multiple_answers")),
            "is_closed": False,
            "total_voter_count": 0,
        }
        if uid:
            raw_poll["id"] = uid
        return raw_poll

    return None


def _content_contains_inline_poll(raw_content: str) -> bool:
    return _extract_inline_poll_from_content(raw_content) is not None


def _sync_template_derived_raw_data(
    raw_data: dict, template_payload: dict | None, content: str | None = None
) -> None:
    template_type = str(template_payload.get("type") or "").strip().lower() if template_payload else ""
    if template_type == POST_TEMPLATE_TYPE_POST_VOTE_POLL:
        poll_payload = _build_post_vote_poll_raw_poll(template_payload.get("data"))
        if poll_payload:
            raw_data["poll"] = poll_payload
            raw_data["poll_source"] = _TEMPLATE_POLL_SOURCE_POST_VOTE
            raw_data.pop("poll_html", None)
        return

    inline_poll_payload = _extract_inline_poll_from_content(content or "")
    if inline_poll_payload:
        raw_data["poll"] = inline_poll_payload
        raw_data["poll_source"] = _CONTENT_POLL_SOURCE_INLINE
        raw_data.pop("poll_html", None)
        return

    if str(raw_data.get("poll_source") or "") in {
        _TEMPLATE_POLL_SOURCE_POST_VOTE,
        _CONTENT_POLL_SOURCE_INLINE,
    }:
        raw_data.pop("poll", None)
        raw_data.pop("poll_source", None)
        raw_data.pop("poll_html", None)


def _serialize_post_template_type_options() -> list[dict]:
    descriptions_by_type: dict[str, str] = {
        POST_TEMPLATE_TYPE_TWEET: "До 280 символов и один медиаблок с изображениями.",
        POST_TEMPLATE_TYPE_BUG_REPORT: "Платформа, браузер, код ошибки и скриншот.",
    }
    try:
        for template_type, description in PostTemplateConfig.objects.filter(
            is_active=True
        ).values_list("template_type", "description"):
            code = normalize_post_template_type_code(template_type)
            normalized_description = re.sub(r"\s+", " ", str(description or "").strip())[:500]
            if code and normalized_description:
                descriptions_by_type[code] = normalized_description
    except (OperationalError, ProgrammingError):
        pass

    options: list[dict] = []
    for value, label in post_template_type_choices():
        option = {"value": value, "label": label}
        description = descriptions_by_type.get(normalize_post_template_type_code(value), "")
        if description:
            option["description"] = description
        options.append(option)
    return options


def _serialize_template_editor_block_options_by_template() -> dict[str, list[dict]]:
    payload: dict[str, list[dict]] = {}
    for template_type, _template_label in post_template_type_choices():
        payload[template_type] = [
            {"value": value, "label": label}
            for value, label in template_editor_block_choices_for_template(template_type)
        ]
    return payload


def _serialize_comun_custom_template_editor_options() -> dict[str, list[dict]]:
    return {
        "block_options": list(POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS),
        "block_placement_options": list(COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_OPTION_ITEMS),
        "field_type_options": list(COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_OPTION_ITEMS),
        "field_placement_options": list(COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_OPTION_ITEMS),
    }


def _normalize_comun_custom_template_name(raw_value: object) -> str:
    return re.sub(r"\s+", " ", str(raw_value or "").strip())[:120]


def _generate_comun_custom_template_slug(
    comun: Comun,
    name: str,
    *,
    exclude_template_id: int | None = None,
) -> str:
    normalized_name = str(name or "").strip()
    base_slug = slugify(normalized_name)[:160]
    if not base_slug:
        base_slug = _fv()._slugify_title(normalized_name)[:160]
    if not base_slug:
        base_slug = f"template-{secrets.token_hex(4)}"
    slug = base_slug
    suffix = 2
    queryset = ComunCustomPostTemplate.objects.filter(comun=comun)
    if exclude_template_id:
        queryset = queryset.exclude(id=exclude_template_id)
    while queryset.filter(slug=slug).exists():
        suffix_literal = f"-{suffix}"
        max_base_length = max(160 - len(suffix_literal), 1)
        slug = f"{base_slug[:max_base_length]}{suffix_literal}"
        suffix += 1
    return slug


def _normalize_comun_custom_template_field_label(raw_value: object) -> str:
    return re.sub(r"\s+", " ", str(raw_value or "").strip())[:120]


def _generate_comun_custom_template_field_key(
    label: str,
    *,
    existing_keys: set[str],
    fallback_index: int,
) -> str:
    base_key = slugify(label)[:160]
    if not base_key:
        base_key = _fv()._slugify_title(label)[:160]
    if not base_key:
        base_key = f"field-{fallback_index}"
    key = base_key
    suffix = 2
    while key in existing_keys:
        suffix_literal = f"-{suffix}"
        max_base_length = max(160 - len(suffix_literal), 1)
        key = f"{base_key[:max_base_length]}{suffix_literal}"
        suffix += 1
    existing_keys.add(key)
    return key


def _normalize_comun_custom_template_field_options(raw_value: object) -> list[str]:
    if isinstance(raw_value, str):
        source = re.split(r"[\n,;]+", raw_value)
    elif isinstance(raw_value, (list, tuple, set)):
        source = list(raw_value)
    else:
        source = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in source:
        value = re.sub(r"\s+", " ", str(item or "").strip())[:120]
        if not value:
            continue
        value_key = value.casefold()
        if value_key in seen:
            continue
        seen.add(value_key)
        normalized.append(value)
    return normalized[:50]


def _normalize_comun_custom_template_blocks(raw_value: object) -> list[dict]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict] = []
    seen_block_types: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, dict):
            continue
        block_type = str(item.get("block_type") or item.get("type") or "").strip().lower()
        if not block_type or block_type not in POST_TEMPLATE_EDITOR_BLOCK_VALUES:
            continue
        if block_type in seen_block_types:
            continue
        placement = str(item.get("placement") or "").strip().lower()
        if placement not in COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_VALUES:
            placement = COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE
        seen_block_types.add(block_type)
        normalized.append(
            {
                "block_type": block_type,
                "placement": placement,
                "is_required": bool(item.get("is_required")),
                "sort_order": index,
            }
        )
    return normalized


def _normalize_comun_custom_template_fields(
    raw_value: object,
) -> tuple[list[dict], str | None]:
    if not isinstance(raw_value, list):
        return [], None
    normalized: list[dict] = []
    seen_keys: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, dict):
            continue
        label = _normalize_comun_custom_template_field_label(item.get("label") or item.get("name"))
        if not label:
            continue
        field_type = str(item.get("field_type") or item.get("type") or "").strip().lower()
        if field_type not in COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_VALUES:
            field_type = COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT
        placement = str(item.get("placement") or "").strip().lower()
        if placement not in COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_VALUES:
            placement = COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_HEADER
        options = _normalize_comun_custom_template_field_options(item.get("options"))
        raw_settings = item.get("settings") if isinstance(item.get("settings"), dict) else {}
        settings: dict[str, object] = {}
        if field_type == COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT:
            max_length_raw = raw_settings.get("max_length", item.get("max_length"))
            max_length = int(max_length_raw) if str(max_length_raw or "").isdigit() else 0
            if max_length > 0:
                settings["max_length"] = min(max_length, 10000)
        elif field_type == COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHECKBOX:
            settings["default_checked"] = bool(
                raw_settings.get("default_checked", item.get("default_checked"))
            )
        if field_type == COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_SELECT and not options:
            return [], f"field '{label}' must have select options"
        key = _generate_comun_custom_template_field_key(
            label,
            existing_keys=seen_keys,
            fallback_index=index + 1,
        )
        normalized.append(
            {
                "key": key,
                "label": label,
                "field_type": field_type,
                "placement": placement,
                "is_required": bool(item.get("is_required")),
                "options": options if field_type == COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_SELECT else [],
                "settings": settings,
                "sort_order": index,
            }
        )
    return normalized, None


def _normalize_comun_custom_templates(
    comun: Comun,
    raw_value: object,
) -> tuple[list[dict], str | None]:
    if raw_value in (None, ""):
        return [], None
    if not isinstance(raw_value, list):
        return [], "custom_templates must be a list"

    normalized: list[dict] = []
    seen_template_ids: set[int] = set()
    for index, item in enumerate(raw_value[:50]):
        if not isinstance(item, dict):
            continue
        template_id_raw = item.get("id")
        template_id = int(template_id_raw) if str(template_id_raw or "").isdigit() else None
        if template_id and template_id in seen_template_ids:
            continue
        name = _normalize_comun_custom_template_name(item.get("name") or item.get("title"))
        if not name:
            return [], "template name is required"
        blocks = _normalize_comun_custom_template_blocks(item.get("blocks"))
        fields, field_error = _normalize_comun_custom_template_fields(item.get("fields"))
        if field_error:
            return [], field_error
        normalized.append(
            {
                "id": template_id,
                "name": name,
                "sort_order": index,
                "blocks": blocks,
                "fields": fields,
            }
        )
        if template_id:
            seen_template_ids.add(template_id)
    return normalized, None


def _serialize_comun_custom_post_template(template: ComunCustomPostTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "slug": template.slug,
        "sort_order": template.sort_order,
        "blocks": [
            {
                "id": block.id,
                "block_type": block.block_type,
                "placement": block.placement,
                "is_required": bool(block.is_required),
                "sort_order": block.sort_order,
            }
            for block in template.block_rules.all().order_by("sort_order", "id")
        ],
        "fields": [
            {
                "id": field.id,
                "key": field.key,
                "label": field.label,
                "field_type": field.field_type,
                "placement": field.placement,
                "is_required": bool(field.is_required),
                "options": list(field.options or []),
                "settings": dict(field.settings or {}),
                "sort_order": field.sort_order,
            }
            for field in template.fields.all().order_by("sort_order", "id")
        ],
    }


def _serialize_comun_custom_post_templates(comun: Comun) -> list[dict]:
    templates = (
        ComunCustomPostTemplate.objects.filter(comun=comun)
        .select_related("post_template_config")
        .prefetch_related("block_rules", "fields")
        .order_by("sort_order", "name", "id")
    )
    return [
        _serialize_comun_custom_post_template(template)
        for template in templates
        if getattr(getattr(template, "post_template_config", None), "is_active", True)
    ]


def _custom_post_template_config_type(template: ComunCustomPostTemplate) -> str:
    return f"custom_{int(template.id)}"


def _enabled_editor_blocks_for_custom_template(blocks: list[dict]) -> list[str]:
    enabled_blocks = [
        str(block.get("block_type") or "").strip().lower()
        for block in blocks
        if str(block.get("placement") or "").strip().lower()
        == COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE
    ]
    return normalize_template_editor_blocks_for_template("custom_template", enabled_blocks)


def _sync_post_template_config_for_custom_template(
    template: ComunCustomPostTemplate,
    blocks: list[dict],
) -> str:
    template_type = _custom_post_template_config_type(template)
    config = PostTemplateConfig.objects.filter(custom_template=template).first()
    if not config:
        config = PostTemplateConfig.objects.filter(template_type=template_type).first()
    if not config:
        config = PostTemplateConfig(custom_template=template)
    config.template_type = template_type
    config.label = template.name
    config.custom_template = template
    config.enabled_editor_blocks = _enabled_editor_blocks_for_custom_template(blocks)
    config.is_active = True
    config.save()
    return template_type


def _sync_comun_custom_post_templates(
    comun: Comun,
    raw_value: object,
) -> str | None:
    normalized_templates, template_error = _normalize_comun_custom_templates(comun, raw_value)
    if template_error:
        return template_error

    existing_templates = {
        item.id: item
        for item in ComunCustomPostTemplate.objects.filter(comun=comun)
    }
    kept_template_ids: list[int] = []
    kept_template_types: list[str] = []

    for index, item in enumerate(normalized_templates):
        template_id = item.get("id")
        template = existing_templates.get(template_id) if isinstance(template_id, int) else None
        if template:
            template.name = str(item["name"])
            template.sort_order = index
            template.save(update_fields=["name", "sort_order", "updated_at"])
        else:
            template = ComunCustomPostTemplate.objects.create(
                comun=comun,
                name=str(item["name"]),
                slug=_generate_comun_custom_template_slug(comun, str(item["name"])),
                sort_order=index,
            )
        kept_template_ids.append(template.id)

        template.block_rules.all().delete()
        ComunCustomPostTemplateBlock.objects.bulk_create(
            [
                ComunCustomPostTemplateBlock(template=template, **block)
                for block in item["blocks"]
            ]
        )

        template.fields.all().delete()
        ComunCustomPostTemplateField.objects.bulk_create(
            [
                ComunCustomPostTemplateField(template=template, **field)
                for field in item["fields"]
            ]
        )
        kept_template_types.append(
            _sync_post_template_config_for_custom_template(template, item["blocks"])
        )

    ComunCustomPostTemplate.objects.filter(comun=comun).exclude(id__in=kept_template_ids).delete()
    if kept_template_types:
        allowed_templates = normalize_allowed_post_templates(comun.allowed_post_templates)
        changed = False
        for template_type in kept_template_types:
            if template_type in allowed_templates:
                continue
            allowed_templates.append(template_type)
            changed = True
        if changed:
            comun.allowed_post_templates = allowed_templates
            comun.save(update_fields=["allowed_post_templates", "updated_at"])
    return None


def _template_editor_blocks_by_template() -> dict[str, list[str]]:
    payload: dict[str, list[str]] = {
        template_type: default_enabled_template_editor_blocks(template_type)
        for template_type, _template_label in post_template_type_choices()
    }
    for item in PostTemplateConfig.objects.filter(is_active=True).values(
        "template_type", "enabled_editor_blocks"
    ):
        template_type = normalize_post_template_type_code(item.get("template_type"))
        if not template_type:
            continue
        payload[template_type] = normalize_template_editor_blocks_for_template(
            template_type, item.get("enabled_editor_blocks")
        )
    return payload


def _allowed_templates_for_comun(comun: Comun | None) -> list[str]:
    if not comun:
        return normalize_allowed_post_templates(None)
    return normalize_allowed_post_templates(comun.allowed_post_templates)


def _allowed_template_overrides_for_comun_category(category: ComunCategory | None) -> list[str]:
    if not category:
        return []
    return normalize_allowed_post_templates_override(category.allowed_post_templates)


def _allowed_templates_for_comun_category(
    comun: Comun | None,
    category: ComunCategory | None,
) -> list[str]:
    category_overrides = _allowed_template_overrides_for_comun_category(category)
    if category_overrides:
        return category_overrides
    return _allowed_templates_for_comun(comun)


def _requested_template_type(template_payload: dict | None) -> str:
    if not template_payload:
        return POST_TEMPLATE_TYPE_BASIC
    template_type = normalize_post_template_type_code(template_payload.get("type"))
    if template_type and is_post_template_type_configured(template_type):
        return template_type
    return POST_TEMPLATE_TYPE_BASIC


def _template_not_allowed_error(
    requested_template_type: str,
    allowed_template_types: list[str],
    *,
    scope: str,
) -> str | None:
    allowed = normalize_allowed_post_templates(allowed_template_types)
    if requested_template_type in allowed:
        return None
    return f"template '{requested_template_type}' is not allowed for this {scope}"


def _normalize_post_template_payload(
    raw_template: object,
    *,
    resolve_post_refs: bool = False,
) -> tuple[dict | None, str | None]:
    if raw_template in (None, "", {}):
        return None, None
    if not isinstance(raw_template, dict):
        return None, "invalid template payload"

    template_type = normalize_post_template_type_code(raw_template.get("type"))
    if not template_type:
        return None, None
    if template_type == POST_TEMPLATE_TYPE_BASIC:
        return None, None
    if not is_post_template_type_configured(template_type):
        return None, "unsupported template type"
    if template_type == POST_TEMPLATE_TYPE_MOVIE_REVIEW:
        template_data_input = raw_template.get("data")
        if template_data_input is None:
            template_data_input = {
                key: raw_template.get(key)
                for key in (
                    "imdb_url",
                    "poster_url",
                    "genre",
                    "content_kind",
                    "author_rating",
                    "title",
                    "original_title",
                    "release_date",
                    "watch_where",
                )
                if raw_template.get(key) is not None
            }
        normalized_data, template_error = _normalize_movie_review_template_data(
            template_data_input
        )
        if template_error:
            return None, template_error
        if not normalized_data:
            return None, None
        return {
            "type": POST_TEMPLATE_TYPE_MOVIE_REVIEW,
            "version": 1,
            "data": normalized_data,
        }, None

    if template_type == POST_TEMPLATE_TYPE_POST_VOTE_POLL:
        template_data_input = raw_template.get("data")
        if template_data_input is None:
            template_data_input = {
                key: raw_template.get(key)
                for key in (
                    "question",
                    "items",
                    "posts",
                    "post_refs",
                    "ends_at",
                    "allows_multiple_answers",
                    "allow_multiple_answers",
                    "multiple",
                )
                if raw_template.get(key) is not None
            }
        normalized_data, template_error = _normalize_post_vote_poll_template_data(
            template_data_input,
            resolve_posts=resolve_post_refs,
        )
        if template_error:
            return None, template_error
        if not normalized_data:
            return None, None
        return {
            "type": POST_TEMPLATE_TYPE_POST_VOTE_POLL,
            "version": 1,
            "data": normalized_data,
        }, None

    if template_type == POST_TEMPLATE_TYPE_MUSIC_RELEASE:
        template_data_input = raw_template.get("data")
        if template_data_input is None:
            template_data_input = {
                key: raw_template.get(key)
                for key in (
                    "cover_image_url",
                    "cover_url",
                    "release_date",
                    "album_url",
                    "release_url",
                    "link",
                    "album_link",
                    "artist_name",
                    "group_name",
                    "band_name",
                    "release_title",
                    "album_title",
                    "title",
                    "country",
                    "city",
                    "style",
                    "music_style",
                    "genre",
                )
                if raw_template.get(key) is not None
            }
        normalized_data, template_error = _normalize_music_release_template_data(
            template_data_input
        )
        if template_error:
            return None, template_error
        if not normalized_data:
            return None, None
        return {
            "type": POST_TEMPLATE_TYPE_MUSIC_RELEASE,
            "version": 1,
            "data": normalized_data,
        }, None

    if template_type == POST_TEMPLATE_TYPE_BUG_REPORT:
        template_data_input = raw_template.get("data")
        if template_data_input is None:
            template_data_input = {
                key: raw_template.get(key)
                for key in (
                    "status",
                    "platforms",
                    "platform",
                    "browsers",
                    "browser",
                    "error_code",
                    "error",
                    "screenshot_url",
                    "photo_url",
                    "image_url",
                )
                if raw_template.get(key) is not None
            }
        normalized_data, template_error = _normalize_bug_report_template_data(template_data_input)
        if template_error:
            return None, template_error
        return {
            "type": POST_TEMPLATE_TYPE_BUG_REPORT,
            "version": 1,
            "data": normalized_data,
        }, None

    return {
        "type": template_type,
        "version": 1,
        "data": {},
    }, None


def _serialize_post_template(post: Post) -> dict | None:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    normalized_template, _template_error = _normalize_post_template_payload(raw_data.get("template"))
    return rewrite_public_media_payload(normalized_template)


def _content_with_live_poll(post: Post, user: User | None = None) -> tuple[str, dict | None]:
    content = post.content or ""
    content = _fv()._replace_legacy_audio_embed(post, content)
    live_poll = _fv()._live_poll_for_post(post, user)
    if not live_poll:
        return rewrite_public_media_urls(content), None

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    template_payload = _serialize_post_template(post)
    template_type = (
        str(template_payload.get("type") or "").strip().lower() if isinstance(template_payload, dict) else ""
    )
    if template_type == POST_TEMPLATE_TYPE_POST_VOTE_POLL:
        return rewrite_public_media_urls(content), live_poll["poll"]

    if _content_contains_inline_poll(content):
        return rewrite_public_media_urls(content), live_poll["poll"]

    poll_html = live_poll["html"]
    stored_poll_html = raw_data.get("poll_html")
    if isinstance(stored_poll_html, str) and stored_poll_html and stored_poll_html in content:
        return rewrite_public_media_urls(content.replace(stored_poll_html, poll_html, 1)), live_poll["poll"]
    if not content:
        return rewrite_public_media_urls(poll_html), live_poll["poll"]
    if '<div class="post-poll"' not in content and poll_html not in content:
        return rewrite_public_media_urls(f"{content}<br><br>{poll_html}"), live_poll["poll"]
    return rewrite_public_media_urls(content), live_poll["poll"]


def _template_type_from_payload(template_payload: dict | None) -> str:
    if not isinstance(template_payload, dict):
        return POST_TEMPLATE_TYPE_BASIC
    template_type = normalize_post_template_type_code(template_payload.get("type"))
    if template_type and is_post_template_type_configured(template_type):
        return template_type
    return POST_TEMPLATE_TYPE_BASIC


def _normalize_editor_block_identifier(
    value: object,
    *,
    fallback_prefix: str,
    fallback_index: int,
) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = f"{fallback_prefix}-{fallback_index + 1}"
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-_")
    if not normalized:
        normalized = f"{fallback_prefix}-{fallback_index + 1}"
    return normalized[:64]


def _extract_inline_post_rating_blocks(raw_content: str) -> list[str]:
    payload = _decode_editor_payload(raw_content)
    if not payload:
        return []

    block_ids: list[str] = []
    seen: set[str] = set()
    for index, raw_block in enumerate(payload.get("blocks") or []):
        if not isinstance(raw_block, dict):
            continue
        block_type = str(raw_block.get("type") or "").strip().lower()
        if block_type not in {"post_rating", "postrating"}:
            continue
        block_data = raw_block.get("data")
        data_block_id = block_data.get("block_id") if isinstance(block_data, dict) else ""
        block_id = _normalize_editor_block_identifier(
            raw_block.get("id") or data_block_id,
            fallback_prefix="post-rating",
            fallback_index=index,
        )
        if block_id in seen:
            continue
        seen.add(block_id)
        block_ids.append(block_id)
    return block_ids


def _serialize_post_rating_block(
    post: Post,
    user: User | None,
    block_id: str,
    *,
    include_legacy_votes: bool = False,
) -> dict:
    current_votes = PostRatingVote.objects.filter(post=post, block_id=block_id)
    current_aggregate = current_votes.aggregate(
        average_value=Avg("value"),
        votes_count=Count("id"),
    )

    votes_count = max(int(current_aggregate.get("votes_count") or 0), 0)
    average_raw = current_aggregate.get("average_value")
    weighted_sum = float(average_raw) * votes_count if average_raw is not None else 0.0

    user_vote = None
    if user:
        user_vote = current_votes.filter(user=user).values_list("value", flat=True).first()
        if user_vote is not None:
            user_vote = int(user_vote)

    if include_legacy_votes:
        legacy_votes = PostRatingVote.objects.filter(post=post, block_id="")
        legacy_aggregate = legacy_votes.aggregate(
            average_value=Avg("value"),
            votes_count=Count("id"),
        )
        legacy_votes_count = max(int(legacy_aggregate.get("votes_count") or 0), 0)
        legacy_average_raw = legacy_aggregate.get("average_value")
        if legacy_average_raw is not None and legacy_votes_count > 0:
            weighted_sum += float(legacy_average_raw) * legacy_votes_count
            votes_count += legacy_votes_count
        if user and user_vote is None:
            legacy_user_vote = legacy_votes.filter(user=user).values_list("value", flat=True).first()
            if legacy_user_vote is not None:
                user_vote = int(legacy_user_vote)

    average_value = round(weighted_sum / votes_count, 1) if votes_count > 0 else None
    return {
        "block_id": block_id,
        "scale_min": 1,
        "scale_max": 10,
        "average_value": average_value,
        "votes_count": votes_count,
        "user_vote": user_vote,
    }


def _serialize_post_ratings(post: Post, user: User | None = None) -> dict[str, dict]:
    block_ids = _extract_inline_post_rating_blocks(post.content or "")
    if not block_ids:
        return {}

    include_legacy_votes = len(block_ids) == 1
    return {
        block_id: _serialize_post_rating_block(
            post,
            user,
            block_id,
            include_legacy_votes=include_legacy_votes and index == 0,
        )
        for index, block_id in enumerate(block_ids)
    }


def _serialize_post_rating(
    post: Post,
    user: User | None = None,
    *,
    template_payload: dict | None = None,
) -> dict | None:
    del template_payload
    ratings = _serialize_post_ratings(post, user)
    if not ratings:
        return None
    first_key = next(iter(ratings.keys()), "")
    return ratings.get(first_key)


def _serialize_enabled_template_editor_blocks(
    template_payload: dict | None = None,
) -> list[str]:
    template_type = _template_type_from_payload(template_payload)
    config = (
        PostTemplateConfig.objects.filter(template_type=template_type, is_active=True)
        .values("enabled_editor_blocks")
        .first()
    )
    if not config:
        return default_enabled_template_editor_blocks(template_type)
    return normalize_template_editor_blocks_for_template(
        template_type, config.get("enabled_editor_blocks")
    )


def _serialize_post_for_user(request: HttpRequest, post: Post, user: User | None = None) -> dict:
    author_channel_url, author_title = _fv()._author_display_fields(
        request, post.author, post.channel_url
    )
    content, poll_payload = _content_with_live_poll(post, user)
    template_payload = _serialize_post_template(post)
    is_favorite = PostFavorite.objects.filter(post=post, user=user).exists() if user else False
    is_draft = _is_post_draft(post)
    payload = {
        "id": post.id,
        "title": _fv()._post_display_title(post),
        "template": template_payload,
        "enabled_template_editor_blocks": _serialize_enabled_template_editor_blocks(template_payload),
        "content": content,
        "poll": poll_payload,
        "post_ratings": _serialize_post_ratings(post, user),
        "post_rating": _serialize_post_rating(post, user, template_payload=template_payload),
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "is_pending": post.is_pending,
        "is_draft": is_draft,
        "publish_at": post.publish_at.isoformat() if post.publish_at else None,
        "comments_count": post.comments_count,
        "likes_count": post.rating,
        "views_count": _fv()._post_total_views(post),
        "tags": _fv()._serialize_tags(post.tags.all()),
        "is_favorite": is_favorite,
        "can_manage": _user_can_manage_site_post(user, post),
        "author": {
            "username": post.author.username,
            "title": author_title,
            "channel_url": author_channel_url,
            "avatar_url": _fv()._author_avatar_for_display(request, post.author),
            **_fv()._author_admin_fields_for_user(user, post.author),
        },
    }
    if is_draft and _user_can_manage_site_post(user, post):
        payload["draft_share_token"] = _post_draft_share_token(post)
    return payload


def _get_or_create_personal_author(user: User) -> tuple[Author | None, str | None]:
    username = (getattr(user, "username", "") or "").strip()
    if not username:
        return None, "invalid username"
    existing = Author.objects.filter(username__iexact=username).first()
    if existing:
        if existing.channel_url or existing.channel_id:
            return (
                None,
                "Этот ник уже занят Telegram-каналом. Подключите канал через бота или смените логин.",
            )
        return existing, None
    author = Author.objects.create(username=username, title=username)
    return author, None


def _is_post_draft(post: Post) -> bool:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    return bool(raw_data.get("draft"))


def _post_draft_share_token(post: Post) -> str:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    return str(raw_data.get("draft_share_token") or "").strip()


def _set_post_draft_state(raw_data: dict | None, is_draft: bool) -> dict:
    next_raw = dict(raw_data or {})
    if is_draft:
        next_raw["draft"] = True
        next_raw["draft_share_token"] = str(
            next_raw.get("draft_share_token") or secrets.token_urlsafe(24)
        )
        next_raw["draft_saved_at"] = timezone.now().isoformat()
    else:
        next_raw.pop("draft", None)
        next_raw.pop("draft_share_token", None)
        next_raw.pop("draft_saved_at", None)
    return next_raw


def _get_personal_author_for_user(user: User) -> Author | None:
    return Author.objects.filter(
        username__iexact=(user.username or "").strip(),
        channel_url="",
        channel_id__isnull=True,
    ).first()


def _resolve_site_post_author_context(user: User):
    author_links = (
        AuthorAdmin.objects.filter(user=user, verified_at__isnull=False)
        .select_related("author")
        .order_by("author__username")
    )
    author_ids = [link.author_id for link in author_links]
    personal_author = _get_personal_author_for_user(user)
    if personal_author and personal_author.id not in author_ids:
        author_ids.append(personal_author.id)
    return author_links, author_ids, personal_author


def _resolve_manual_post_author(
    user: User,
    *,
    author_links,
    author_ids: list[int],
    author_source: str,
    author_username: str,
    allow_default: bool = False,
) -> tuple[Author | None, str | None]:
    personal_author, personal_author_error = _get_or_create_personal_author(user)
    if personal_author_error:
        return None, personal_author_error
    if personal_author:
        return personal_author, None
    return None, "author required"


def _user_can_manage_site_post(user: User | None, post: Post) -> bool:
    if not user:
        return False
    if AuthorAdmin.objects.filter(
        user=user, author=post.author, verified_at__isnull=False
    ).exists():
        return True
    personal_author = _get_personal_author_for_user(user)
    return bool(personal_author and personal_author.id == post.author_id)


def _serialize_post_template(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._serialize_post_template(*args, **kwargs)


def _content_with_live_poll(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._content_with_live_poll(*args, **kwargs)


def _serialize_post_rating_block(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._serialize_post_rating_block(*args, **kwargs)


def _serialize_post_ratings(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._serialize_post_ratings(*args, **kwargs)


def _serialize_post_rating(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._serialize_post_rating(*args, **kwargs)


def _serialize_enabled_template_editor_blocks(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._serialize_enabled_template_editor_blocks(*args, **kwargs)


def _serialize_post_for_user(*args, **kwargs):
    from editor import serializers as editor_serializers

    return editor_serializers._serialize_post_for_user(*args, **kwargs)


__all__ = [
    "_allowed_template_overrides_for_comun_category",
    "_allowed_templates_for_comun",
    "_allowed_templates_for_comun_category",
    "_build_post_vote_poll_raw_poll",
    "_canonical_imdb_url",
    "_content_with_live_poll",
    "_decode_editor_payload",
    "_extract_editor_payload_title",
    "_extract_imdb_id",
    "_extract_inline_post_rating_blocks",
    "_get_or_create_personal_author",
    "_get_personal_author_for_user",
    "_is_post_draft",
    "movie_review_autofill_template_from_imdb",
    "_normalize_editor_block_identifier",
    "_normalize_movie_review_template_data",
    "_normalize_comun_custom_templates",
    "_normalize_music_release_template_data",
    "_normalize_post_template_payload",
    "_normalize_post_vote_poll_template_data",
    "_normalize_template_bool",
    "_normalize_template_datetime",
    "_normalize_template_http_url",
    "_normalize_template_text",
    "_post_draft_share_token",
    "_requested_template_type",
    "_resolve_manual_post_author",
    "_resolve_site_post_author_context",
    "_serialize_enabled_template_editor_blocks",
    "_serialize_comun_custom_post_templates",
    "_serialize_comun_custom_template_editor_options",
    "_serialize_post_for_user",
    "_serialize_post_rating",
    "_serialize_post_rating_block",
    "_serialize_post_ratings",
    "_serialize_post_template",
    "_serialize_post_template_type_options",
    "_serialize_template_editor_block_options_by_template",
    "_set_post_draft_state",
    "_sync_comun_custom_post_templates",
    "_sync_template_derived_raw_data",
    "_template_editor_blocks_by_template",
    "_template_not_allowed_error",
    "_template_type_from_payload",
    "_validate_template_content_constraints",
    "_user_can_manage_site_post",
]
