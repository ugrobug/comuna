from __future__ import annotations

import io
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from PIL import Image, UnidentifiedImageError

from rabotaem_backend.images import save_image_with_variants
from rabotaem_backend.media_urls import media_storage_path_from_url, public_url
from telegram_integration.media import is_private_telegram_file_url
from users.models import SiteUserProfile

logger = logging.getLogger(__name__)

AVATAR_VARIANT_WIDTHS = (32, 48, 64, 96, 128, 192, 256, 320, 512)
_DEFAULT_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS = 8
_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def is_cached_media_avatar_url(value: object) -> bool:
    return bool(media_storage_path_from_url(value, allow_storage_key=False))


def public_cached_avatar_url(value: object) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value or not is_cached_media_avatar_url(raw_value):
        return None
    return public_url(raw_value) or None


def _normalize_external_avatar_url(value: object) -> str:
    url = str(value or "").strip()
    if not url or is_private_telegram_file_url(url):
        return ""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def _avatar_ext(url: str, content_type: str) -> str:
    normalized_content_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_content_type in _CONTENT_TYPE_EXTENSIONS:
        return _CONTENT_TYPE_EXTENSIONS[normalized_content_type]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return ext if ext in _IMAGE_EXTENSIONS else ".jpg"


def _download_external_avatar(url: str) -> tuple[bytes, str] | None:
    max_bytes = int(getattr(settings, "EXTERNAL_AVATAR_MAX_BYTES", _DEFAULT_MAX_AVATAR_BYTES))
    timeout = int(
        getattr(settings, "EXTERNAL_AVATAR_DOWNLOAD_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS)
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "User-Agent": "TamburAvatarCache/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            normalized_content_type = content_type.split(";", 1)[0].strip().lower()
            if normalized_content_type and not normalized_content_type.startswith("image/"):
                return None
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                return None
            data = response.read(max_bytes + 1)
    except (OSError, ValueError, urllib.error.URLError):
        return None

    if len(data) > max_bytes:
        return None
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    return data, _avatar_ext(url, content_type)


def cache_external_avatar_for_user(
    user,
    avatar_url: object,
    *,
    source: str,
    force: bool = False,
) -> str | None:
    if not getattr(user, "id", None):
        return None

    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    existing_avatar_url = str(profile.avatar_url or "").strip()
    if existing_avatar_url and is_cached_media_avatar_url(existing_avatar_url) and not force:
        return public_url(existing_avatar_url) or existing_avatar_url

    cached_source_url = public_cached_avatar_url(avatar_url)
    if cached_source_url:
        profile.avatar_url = cached_source_url
        profile.save(update_fields=["avatar_url", "updated_at"])
        return cached_source_url

    external_url = _normalize_external_avatar_url(avatar_url)
    if not external_url:
        return None

    downloaded = _download_external_avatar(external_url)
    if not downloaded:
        return None

    data, ext = downloaded
    safe_source = "".join(char for char in str(source or "external").lower() if char.isalnum() or char in "-_")
    safe_source = safe_source or "external"
    original_path = f"avatars/users/{user.id}/{safe_source}-{secrets.token_hex(12)}{ext}"
    try:
        image_set = save_image_with_variants(
            data=data,
            original_path=original_path,
            variant_widths=AVATAR_VARIANT_WIDTHS,
            keep_original=False,
        )
    except Exception:
        logger.warning("Failed to save cached avatar for user_id=%s", user.id, exc_info=True)
        return None

    cached_url = public_url(image_set.default_url) or image_set.default_url
    if not cached_url or len(cached_url) > 500:
        return None

    profile.avatar_url = cached_url
    profile.save(update_fields=["avatar_url", "updated_at"])
    return cached_url


__all__ = [
    "AVATAR_VARIANT_WIDTHS",
    "cache_external_avatar_for_user",
    "is_cached_media_avatar_url",
    "public_cached_avatar_url",
]
