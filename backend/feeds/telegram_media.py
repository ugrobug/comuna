from __future__ import annotations

import os
import re
import secrets
import urllib.request
from urllib.error import URLError

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

_TELEGRAM_FILE_RE = re.compile(r"https?://api\.telegram\.org/file/bot[^/]+/(.+)")


def build_public_media_url(path: str) -> str:
    base = settings.SITE_BASE_URL.rstrip("/")
    media_url = settings.MEDIA_URL
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"
    return f"{base}{media_url}{path.lstrip('/')}"


def extract_telegram_file_path(url: str) -> str | None:
    match = _TELEGRAM_FILE_RE.match(url)
    if not match:
        return None
    return match.group(1)


def download_telegram_file_by_path(file_path: str, token: str) -> str | None:
    if not file_path or not token:
        return None
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = response.read()
    except URLError:
        return None
    ext = os.path.splitext(file_path)[1].lower()
    if not ext or len(ext) > 8:
        ext = ".jpg"
    filename = f"posts/telegram/{secrets.token_hex(12)}{ext}"
    saved_path = default_storage.save(filename, ContentFile(data))
    return build_public_media_url(saved_path)
