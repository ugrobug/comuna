from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import call, patch
from urllib.error import URLError

from django.test import SimpleTestCase

from telegram_integration import media


class _Response:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.data


class TelegramMediaRetryTests(SimpleTestCase):
    @patch("telegram_integration.media.time.sleep")
    @patch("telegram_integration.media.build_public_storage_url", return_value="https://media.test/photo.webp")
    @patch("telegram_integration.media.save_image_with_variants")
    @patch("telegram_integration.media.urllib.request.urlopen")
    def test_file_download_retries_after_temporary_network_error(
        self,
        urlopen,
        save_image,
        build_public_url,
        sleep,
    ) -> None:
        urlopen.side_effect = [URLError("temporary"), _Response(b"image-data")]
        save_image.return_value = SimpleNamespace(default_url="posts/telegram/photo.webp")

        result = media.download_telegram_file_by_path("photos/file.jpg", "secret-token")

        self.assertEqual(result, "https://media.test/photo.webp")
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleep.call_count, 1)
        save_image.assert_called_once()
        build_public_url.assert_called_once_with("posts/telegram/photo.webp")

    @patch("telegram_integration.media.time.sleep")
    @patch("telegram_integration.media.urllib.request.urlopen")
    def test_get_file_retries_after_invalid_json(self, urlopen, sleep) -> None:
        payload = {"ok": True, "result": {"file_path": "photos/file.jpg"}}
        urlopen.side_effect = [
            _Response(b"not-json"),
            _Response(json.dumps(payload).encode("utf-8")),
        ]

        result = media._fetch_telegram_json("getFile", "secret-token", {"file_id": "photo-id"})

        self.assertEqual(result, payload)
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(
            urlopen.call_args_list,
            [
                call(
                    "https://api.telegram.org/botsecret-token/getFile",
                    data=b"file_id=photo-id",
                    timeout=media._TELEGRAM_REQUEST_TIMEOUT_SECONDS,
                ),
                call(
                    "https://api.telegram.org/botsecret-token/getFile",
                    data=b"file_id=photo-id",
                    timeout=media._TELEGRAM_REQUEST_TIMEOUT_SECONDS,
                ),
            ],
        )
