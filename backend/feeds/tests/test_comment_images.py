from django.test import SimpleTestCase

from feeds.views import _normalize_comment_body_images


class CommentImageMarkdownTests(SimpleTestCase):
    def test_converts_standalone_image_url_to_markdown_image(self):
        body = _normalize_comment_body_images(
            "https://media.tambur.pub/uploads/manual/photo-1024.webp"
        )

        self.assertEqual(body, "![](https://media.tambur.pub/uploads/manual/photo-1024.webp)")

    def test_keeps_regular_text_links_unchanged(self):
        body = _normalize_comment_body_images(
            "Смотри https://media.tambur.pub/uploads/manual/photo-1024.webp"
        )

        self.assertEqual(
            body,
            "Смотри https://media.tambur.pub/uploads/manual/photo-1024.webp",
        )

    def test_keeps_existing_markdown_image_unchanged(self):
        body = _normalize_comment_body_images(
            "Текст\n\n![alt](https://media.tambur.pub/uploads/manual/photo.jpg)"
        )

        self.assertEqual(
            body,
            "Текст\n\n![alt](https://media.tambur.pub/uploads/manual/photo.jpg)",
        )
