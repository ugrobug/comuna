from __future__ import annotations

import io
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from feeds.models import Author, Post


LONG_CONTENT = f"<p>{'Полезный текст публикации ' * 12}</p>"


class FakeSnapshotResponse:
    def __init__(self, body: bytes):
        self.status = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body


@override_settings(SITE_BASE_URL="https://tambur.pub")
class RenderPublicSnapshotsTests(TestCase):
    def setUp(self) -> None:
        self.author = Author.objects.create(username="snapshot-author")

    def test_dry_run_includes_recent_indexable_posts(self) -> None:
        post = Post.objects.create(
            author=self.author,
            message_id=1,
            title="Новый полезный материал",
            content=LONG_CONTENT,
        )
        Post.objects.create(
            author=self.author,
            message_id=2,
            title="Короткий материал",
            content="Слишком коротко",
        )
        stdout = io.StringIO()

        call_command(
            "render_public_snapshots",
            posts=0,
            recent_posts=10,
            dry_run=True,
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn(f"/b/post/{post.id}-novyy-poleznyy-material", output)
        self.assertNotIn("korotkiy-material", output)

    def test_failed_render_keeps_previous_snapshot_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "html-snapshots"
            output_dir.mkdir()
            marker = output_dir / "existing.html"
            marker.write_text("existing", encoding="utf-8")

            with patch(
                "feeds.management.commands.render_public_snapshots.urllib.request.urlopen",
                side_effect=urllib.error.URLError("frontend unavailable"),
            ):
                with self.assertRaises(CommandError):
                    call_command(
                        "render_public_snapshots",
                        posts=0,
                        recent_posts=0,
                        output_dir=str(output_dir),
                    )

            self.assertEqual(marker.read_text(encoding="utf-8"), "existing")

    def test_renders_separate_snapshot_tree_for_each_language(self) -> None:
        requested_languages: list[str] = []

        def render(request, timeout):
            del timeout
            language = request.get_header("Accept-language")
            requested_languages.append(language)
            return FakeSnapshotResponse(f'<html lang="{language}"></html>'.encode())

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "html-snapshots"
            with patch(
                "feeds.management.commands.render_public_snapshots.urllib.request.urlopen",
                side_effect=render,
            ):
                call_command(
                    "render_public_snapshots",
                    posts=0,
                    recent_posts=0,
                    languages=["ru", "en"],
                    output_dir=str(output_dir),
                )

            self.assertEqual(requested_languages, ["ru", "en"])
            self.assertIn('lang="ru"', (output_dir / "ru" / "index.html").read_text())
            self.assertIn('lang="en"', (output_dir / "en" / "index.html").read_text())
