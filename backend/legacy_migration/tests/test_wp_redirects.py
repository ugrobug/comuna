from django.test import SimpleTestCase

from legacy_migration.wp_redirects import normalize_legacy_path, path_variants


class WpRedirectsPathTests(SimpleTestCase):
    def test_normalize_full_url(self) -> None:
        self.assertEqual(
            normalize_legacy_path(
                "https://posletitrov.ru/articles/movies/reviews/slug/?utm=1"
            ),
            "/articles/movies/reviews/slug",
        )

    def test_path_variants(self) -> None:
        self.assertEqual(
            path_variants("/articles/foo/"),
            ["/articles/foo", "/articles/foo/"],
        )
