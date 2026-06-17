import json

from django.test import TestCase

from feeds.models import Author, Post
from legacy_migration.models import LegacyWpPostMap, LegacyWpUserMap
from legacy_migration.wp_content_rewrites import rewrite_post_content_string


class WpContentRewritesTests(TestCase):
    def setUp(self) -> None:
        self.author = Author.objects.create(username="pt-writer", title="Writer")
        self.target = Post.objects.create(
            author=self.author,
            message_id=9001,
            title="Целевой материал",
            content=json.dumps(
                {
                    "blocks": [],
                    "additional": {
                        "previewDescription": "Кратко о цели",
                        "previewImage": "https://cdn.example/cover.jpg",
                    },
                },
                ensure_ascii=False,
            ),
        )
        LegacyWpPostMap.objects.create(
            wp_post_id=42,
            legacy_slug="target-slug",
            post=self.target,
        )
        self.wp_author = Author.objects.create(username="legacy-login", title="Legacy")
        LegacyWpUserMap.objects.create(wp_user_id=7, wp_login="legacy-login", author=self.wp_author)

    def test_single_article_link_becomes_post_link_block(self) -> None:
        content = json.dumps(
            {
                "blocks": [
                    {
                        "id": "abc",
                        "type": "paragraph",
                        "data": {
                            "text": (
                                '<p><a href="https://posletitrov.ru/articles/foo/target-slug/">'
                                "Читать</a></p>"
                            ),
                        },
                    }
                ]
            },
            ensure_ascii=False,
        )
        new_content, stats = rewrite_post_content_string(content)
        self.assertEqual(stats.post_links, 1)
        payload = json.loads(new_content)
        block = payload["blocks"][0]
        self.assertEqual(block["type"], "post_link")
        self.assertEqual(block["data"]["post_id"], self.target.id)
        self.assertEqual(block["data"]["snapshot"]["path"], f"/b/post/{self.target.id}-tselevoj-material")
        self.assertEqual(block["data"]["snapshot"]["preview_text"], "Кратко о цели")

    def test_author_link_becomes_author_block(self) -> None:
        content = json.dumps(
            {
                "blocks": [
                    {
                        "id": "x",
                        "type": "paragraph",
                        "data": {
                            "text": (
                                '<p><a href="https://www.posletitrov.ru/author/legacy-login/">'
                                "Иван Иванов</a></p>"
                            ),
                        },
                    }
                ]
            },
            ensure_ascii=False,
        )
        new_content, stats = rewrite_post_content_string(content)
        self.assertEqual(stats.authors, 1)
        block = json.loads(new_content)["blocks"][0]
        self.assertEqual(block["type"], "author")
        self.assertEqual(block["data"]["username"], "legacy-login")
        self.assertEqual(block["data"]["snapshot"]["path"], "/legacy-login")
        self.assertEqual(block["data"]["caption"], "Иван Иванов")

    def test_inline_href_replaced_when_multiple_links(self) -> None:
        content = json.dumps(
            {
                "blocks": [
                    {
                        "id": "p1",
                        "type": "paragraph",
                        "data": {
                            "text": (
                                '<p>Текст <a href="https://posletitrov.ru/articles/x/target-slug/">one</a> '
                                'и <a href="https://posletitrov.ru/articles/y/other/">two</a></p>'
                            ),
                        },
                    }
                ]
            },
            ensure_ascii=False,
        )
        new_content, stats = rewrite_post_content_string(content)
        self.assertEqual(stats.post_links, 0)
        self.assertEqual(stats.url_replacements, 1)
        text = json.loads(new_content)["blocks"][0]["data"]["text"]
        self.assertIn(f'href="/b/post/{self.target.id}-tselevoj-material"', text)
        self.assertIn("posletitrov.ru/articles/y/other", text)
