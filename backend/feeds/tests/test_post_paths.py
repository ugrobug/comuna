from django.test import SimpleTestCase

from feeds.post_paths import build_post_public_path, slugify_title


class PostPathsTests(SimpleTestCase):
    def test_slugify_title_translits_cyrillic(self) -> None:
        self.assertEqual(slugify_title("Целевой материал"), "tselevoj-material")

    def test_slugify_title_keeps_leading_digits_with_cyrillic(self) -> None:
        self.assertEqual(
            slugify_title("10 лучших аниме-фильмов"),
            "10-luchshih-anime-filmov",
        )

    def test_build_post_public_path(self) -> None:
        self.assertEqual(
            build_post_public_path(16649, "10 лучших аниме-фильмов"),
            "/b/post/16649-10-luchshih-anime-filmov",
        )

    def test_build_post_public_path_without_slug(self) -> None:
        self.assertEqual(build_post_public_path(42, ""), "/b/post/42")
