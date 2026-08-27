from __future__ import annotations

import gzip
import tempfile
from datetime import timedelta
from pathlib import Path
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from communities.models import Comun
from feeds.models import (
    Author,
    ComunTranslation,
    Post,
    PostComment,
    PostTranslation,
    StaticPageContent,
    StaticPageTranslation,
    Tag,
)
from feeds.sitemaps import SITEMAP_SHARD_SIZE, _range_bounds, materialize_sitemaps
from feeds.seo_indexing import seo_indexable_posts_queryset
from landing_pages.models import LandingPage


SITE_BASE_URL = "https://tambur.pub"
LONG_CONTENT = f"<p>{'Полезный текст публикации ' * 24}</p>"
User = get_user_model()


@override_settings(SITE_BASE_URL=SITE_BASE_URL)
class MaterializedSitemapTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

        self.author = Author.objects.create(username="public-author")
        self.blocked_author = Author.objects.create(username="blocked-author", is_blocked=True)
        self.post = Post.objects.create(
            id=5001,
            author=self.author,
            message_id=1,
            title="Русский заголовок",
            content=LONG_CONTENT,
            raw_data={"source": "manual_comun", "comun_slug": "community"},
        )
        PostTranslation.objects.create(
            post=self.post,
            language="en",
            title="English title",
            content="<p>Text</p>",
            status="translated",
        )
        self.english_post = Post.objects.create(
            id=5006,
            author=self.author,
            message_id=6,
            title="Original English guide",
            content=LONG_CONTENT,
            original_language="en",
            raw_data={"source": "manual_comun", "comun_slug": "community"},
        )
        PostTranslation.objects.create(
            post=self.english_post,
            language="ru",
            title="Русский перевод руководства",
            content="<p>Русский перевод</p>",
            status="translated",
        )
        Post.objects.create(
            id=5002,
            author=self.author,
            message_id=2,
            title="Заблокированный пост",
            is_blocked=True,
        )
        Post.objects.create(
            id=5003,
            author=self.author,
            message_id=3,
            title="Будущий пост",
            publish_at=timezone.now() + timedelta(days=1),
        )
        Post.objects.create(
            id=5004,
            author=self.author,
            message_id=4,
            title="Пост спецпроекта",
            raw_data={"special_project": {"slug": "book"}},
        )
        Post.objects.create(
            id=5005,
            author=self.blocked_author,
            message_id=5,
            title="Пост заблокированного автора",
        )

        self.tag = Tag.objects.create(name="Кино и ТВ")
        self.post.tags.add(self.tag)

        self.comun = Comun.objects.create(
            name="Сообщество",
            slug="community",
            glossary_enabled=True,
            roadmap_enabled=True,
            knowledge_base_enabled=True,
            community_map_enabled=True,
        )
        ComunTranslation.objects.create(
            comun=self.comun,
            language="en",
            name="Community",
            status="translated",
        )

        self.about_page = StaticPageContent.objects.create(
            slug="about",
            title="О проекте",
        )
        StaticPageTranslation.objects.create(
            page=self.about_page,
            language="en",
            title="About",
            status="translated",
        )
        LandingPage.objects.create(
            slug="community-platform",
            title="Платформа для сообществ",
            is_published=True,
        )
        LandingPage.objects.create(
            slug="hidden-landing",
            title="Скрытая посадочная",
            is_published=False,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _materialize(self, **kwargs) -> dict:
        return materialize_sitemaps(
            output_dir=self.output_dir,
            site_base_url=SITE_BASE_URL,
            **kwargs,
        )

    def _read(self, filename: str) -> str:
        return (self.output_dir / filename).read_text(encoding="utf-8")

    def test_range_bounds_are_stable_and_capped_at_5000_ids(self) -> None:
        self.assertEqual(SITEMAP_SHARD_SIZE, 5000)
        self.assertEqual(_range_bounds(1), (1, 5000))
        self.assertEqual(_range_bounds(5000), (1, 5000))
        self.assertEqual(_range_bounds(5001), (5001, 10000))

    def test_materializes_localized_shards_index_and_gzip_files(self) -> None:
        manifest = self._materialize()

        russian_filename = "sitemap-posts-ru-000005001-000010000.xml"
        english_filename = "sitemap-posts-en-000005001-000010000.xml"
        russian = self._read(russian_filename)
        english = self._read(english_filename)
        index = self._read("sitemap.xml")

        self.assertIn(f"{SITE_BASE_URL}/{russian_filename}", index)
        self.assertIn(f"{SITE_BASE_URL}/{english_filename}", index)
        self.assertNotIn(".xml.gz</loc>", index)

        russian_url = f"{SITE_BASE_URL}/b/post/5001-russkiy-zagolovok"
        english_url = f"{SITE_BASE_URL}/en/b/post/5001-english-title"
        english_original_url = f"{SITE_BASE_URL}/en/b/post/5006-original-english-guide"
        russian_translation_url = (
            f"{SITE_BASE_URL}/b/post/5006-russkiy-perevod-rukovodstva"
        )
        self.assertIn(f"<loc>{russian_url}</loc>", russian)
        self.assertIn(f'hreflang="en" href="{english_url}"', russian)
        self.assertIn(f'hreflang="x-default" href="{russian_url}"', russian)
        self.assertIn(f"<loc>{english_url}</loc>", english)
        self.assertIn(f'hreflang="ru" href="{russian_url}"', english)
        self.assertNotIn(f"<loc>{russian_url}</loc>", english)
        self.assertIn(f"<loc>{english_original_url}</loc>", english)
        self.assertIn(
            f'hreflang="x-default" href="{english_original_url}"',
            english,
        )
        self.assertIn(f"<loc>{russian_translation_url}</loc>", russian)
        self.assertIn(
            f'hreflang="en" href="{english_original_url}"',
            russian,
        )

        all_xml = "".join(
            path.read_text(encoding="utf-8")
            for path in self.output_dir.glob("sitemap*.xml")
        )
        self.assertNotIn("zablokirovannyj-post", all_xml)
        self.assertNotIn("budushchij-post", all_xml)
        self.assertNotIn("post-spetsproekta", all_xml)
        self.assertNotIn("post-zablokirovannogo-avtora", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/comuns/community", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/en/comuns/community", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/comuns/community/glossary", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/comuns/community/roadmap", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/comuns/community/knowledge-base", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/comuns/community/map", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/en/about", all_xml)
        self.assertIn(f"{SITE_BASE_URL}/l/community-platform", all_xml)
        self.assertNotIn(f"{SITE_BASE_URL}/l/hidden-landing", all_xml)
        self.assertNotIn(f"{SITE_BASE_URL}/tags/", all_xml)
        self.assertFalse(list(self.output_dir.glob("sitemap-tags-*.xml")))

        for path in self.output_dir.glob("sitemap*.xml"):
            ElementTree.fromstring(path.read_bytes())
        for group in manifest["groups"].values():
            for payload in group["files"]:
                self.assertLessEqual(payload["url_count"], SITEMAP_SHARD_SIZE)
                self.assertLess(payload["bytes_uncompressed"], 50 * 1024 * 1024)

        compressed = (self.output_dir / f"{russian_filename}.gz").read_bytes()
        self.assertEqual(gzip.decompress(compressed).decode("utf-8"), russian)
        self.assertEqual((self.output_dir / russian_filename).stat().st_mode & 0o777, 0o644)

    def test_only_changed_shard_gets_new_content_and_unchanged_force_keeps_lastmod(self) -> None:
        first = self._materialize()
        group_key = "posts:5001:10000"
        first_files = {
            item["filename"]: item for item in first["groups"][group_key]["files"]
        }
        russian_path = self.output_dir / "sitemap-posts-ru-000005001-000010000.xml"
        russian_path.chmod(0o600)

        second = self._materialize(force=True)
        second_files = {
            item["filename"]: item for item in second["groups"][group_key]["files"]
        }
        self.assertEqual(first_files, second_files)
        self.assertEqual(russian_path.stat().st_mode & 0o777, 0o644)

        translation = self.post.translations.get(language="en")
        translation.title = "Updated English title"
        translation.save(update_fields=["title", "updated_at"])
        third = self._materialize()
        third_files = {
            item["filename"]: item for item in third["groups"][group_key]["files"]
        }

        self.assertNotEqual(
            second_files["sitemap-posts-en-000005001-000010000.xml"]["checksum"],
            third_files["sitemap-posts-en-000005001-000010000.xml"]["checksum"],
        )
        self.assertIn(
            "/en/b/post/5001-updated-english-title",
            self._read("sitemap-posts-en-000005001-000010000.xml"),
        )

    def test_django_fallback_serves_only_materialized_sitemap_files(self) -> None:
        self._materialize()
        with override_settings(SITEMAP_OUTPUT_DIR=str(self.output_dir)):
            response = self.client.get("/sitemap.xml")
            child = self.client.get("/sitemap-static.xml")
            missing = self.client.get("/sitemap-does-not-exist.xml")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(child.status_code, 200)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(response["Cache-Control"], "public, max-age=300")

    def test_detail_apis_expose_the_same_indexing_decision(self) -> None:
        short_post = Post.objects.create(
            id=5090,
            author=self.author,
            message_id=90,
            title="Короткая запись для API",
            content="<p>Мало текста</p>",
        )
        sparse_comun = Comun.objects.create(
            name="Малое сообщество для API",
            slug="sparse-api-community",
        )
        Post.objects.create(
            id=5091,
            author=self.author,
            message_id=91,
            title="Единственный пост малого сообщества для API",
            content=LONG_CONTENT,
            raw_data={"source": "manual_comun", "comun_slug": sparse_comun.slug},
        )

        long_post_response = self.client.get(f"/api/posts/{self.post.id}/")
        short_post_response = self.client.get(f"/api/posts/{short_post.id}/")
        comun_response = self.client.get(f"/api/comuns/{self.comun.slug}/")
        sparse_comun_response = self.client.get(
            f"/api/comuns/{sparse_comun.slug}/"
        )

        self.assertTrue(long_post_response.json()["post"]["seo_indexable"])
        self.assertFalse(short_post_response.json()["post"]["seo_indexable"])
        self.assertTrue(comun_response.json()["comun"]["seo_indexable"])
        self.assertFalse(
            sparse_comun_response.json()["comun"]["seo_indexable"]
        )

    def test_applies_dynamic_post_and_comun_indexing_rules(self) -> None:
        short_post = Post.objects.create(
            id=5010,
            author=self.author,
            message_id=10,
            title="Короткая запись",
            content="<p>Мало текста</p>",
        )
        discussed_post = Post.objects.create(
            id=5011,
            author=self.author,
            message_id=11,
            title="Короткая запись с обсуждением",
            content="<p>Мало текста</p>",
        )
        commenter = User.objects.create_user(username="seo-commenter")
        PostComment.objects.create(
            post=discussed_post,
            user=commenter,
            body="Подробный содержательный комментарий " * 8,
        )
        self.assertTrue(
            seo_indexable_posts_queryset().filter(id=discussed_post.id).exists()
        )

        sparse_comun = Comun.objects.create(
            name="Малое сообщество",
            slug="sparse-community",
            roadmap_enabled=True,
        )
        Post.objects.create(
            id=5012,
            author=self.author,
            message_id=12,
            title="Единственный пост малого сообщества",
            content=LONG_CONTENT,
            raw_data={"source": "manual_comun", "comun_slug": sparse_comun.slug},
        )

        blocked_comun = Comun.objects.create(
            name="Заблокированное сообщество",
            slug="blocked-community",
            is_active=False,
        )
        blocked_comun_post = Post.objects.create(
            id=5013,
            author=self.author,
            message_id=13,
            title="Пост заблокированного сообщества",
            content=LONG_CONTENT,
            raw_data={"source": "manual_comun", "comun_slug": blocked_comun.slug},
        )

        self._materialize()
        all_xml = "".join(
            path.read_text(encoding="utf-8")
            for path in self.output_dir.glob("sitemap*.xml")
        )
        self.assertNotIn(f"/b/post/{short_post.id}-", all_xml)
        self.assertIn(f"/b/post/{discussed_post.id}-", all_xml)
        self.assertNotIn("/comuns/sparse-community", all_xml)
        self.assertNotIn(f"/b/post/{blocked_comun_post.id}-", all_xml)
        self.assertNotIn("/comuns/blocked-community", all_xml)

        Post.objects.create(
            id=5014,
            author=self.author,
            message_id=14,
            title="Второй пост малого сообщества",
            content=LONG_CONTENT,
            raw_data={"source": "manual_comun", "comun_slug": sparse_comun.slug},
        )
        self._materialize()
        refreshed_xml = "".join(
            path.read_text(encoding="utf-8")
            for path in self.output_dir.glob("sitemap*.xml")
        )
        self.assertIn("/comuns/sparse-community", refreshed_xml)
        self.assertIn("/comuns/sparse-community/roadmap", refreshed_xml)

    def test_short_post_translation_is_noindex_and_excluded_from_hreflang_and_sitemap(self) -> None:
        short_translated_post = Post.objects.create(
            id=5095,
            author=self.author,
            message_id=95,
            title="Оригинальный короткий пост",
            content=f"<p>{'Содержательный текст ' * 18} #неучитываемыйтег</p>",
        )
        PostTranslation.objects.create(
            post=short_translated_post,
            language="en",
            title="Short translated post",
            content="<p>Translated text</p>",
            status="translated",
        )

        self.assertGreaterEqual(short_translated_post.seo_text_length, 200)
        self.assertLess(short_translated_post.translation_text_length, 500)

        self._materialize()
        all_xml = "".join(
            path.read_text(encoding="utf-8")
            for path in self.output_dir.glob("sitemap*.xml")
        )
        original_url = f"{SITE_BASE_URL}/b/post/{short_translated_post.id}-"
        translated_url = f"{SITE_BASE_URL}/en/b/post/{short_translated_post.id}-"
        self.assertIn(original_url, all_xml)
        self.assertNotIn(translated_url, all_xml)

        original_response = self.client.get(f"/api/posts/{short_translated_post.id}/?lang=ru")
        translated_response = self.client.get(f"/api/posts/{short_translated_post.id}/?lang=en")
        self.assertTrue(original_response.json()["post"]["seo_indexable"])
        self.assertFalse(translated_response.json()["post"]["seo_indexable"])
        self.assertEqual(
            [
                version["language"]
                for version in translated_response.json()["post"]["language_versions"]
            ],
            ["ru"],
        )
