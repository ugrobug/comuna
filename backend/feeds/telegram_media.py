from __future__ import annotations

import json
import os
import re
import secrets
import urllib.parse
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


def download_telegram_file_by_url(url: str) -> str | None:
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = response.read()
    except URLError:
        return None
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if not ext or len(ext) > 8:
        ext = ".jpg"
    filename = f"posts/telegram/{secrets.token_hex(12)}{ext}"
    saved_path = default_storage.save(filename, ContentFile(data))
    return build_public_media_url(saved_path)


def download_telegram_file_by_id(file_id: str, token: str) -> str | None:
    if not file_id or not token:
        return None
    file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
    if not file_info or not file_info.get("ok") or not file_info.get("result"):
        return None
    file_path = file_info["result"].get("file_path")
    if not file_path:
        return None
    return download_telegram_file_by_path(file_path, token)


def _fetch_telegram_json(method: str, token: str, payload: dict) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError):
        return None
