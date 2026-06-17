from pathlib import Path

from django.test import SimpleTestCase

from legacy_migration.pt_archive_page_redirects import (
    paths_for_section,
    paths_from_csv_archive_pages,
    redirection_plugin_items_to_url,
)


class PtArchivePageRedirectsTests(SimpleTestCase):
    def test_paths_for_section(self) -> None:
        paths = paths_for_section("movies", page_numbers=[2, 10])
        self.assertEqual(paths, ["/articles/movies/page/2/", "/articles/movies/page/10/"])

    def test_csv_extract(self) -> None:
        csv_path = Path(__file__).resolve().parents[1] / "Просмотры-URL-2026-04-01-2026-06-17 (1).csv"
        if not csv_path.is_file():
            self.skipTest("analytics csv not in tree")
        built = paths_from_csv_archive_pages(csv_path, min_views=1)
        self.assertTrue(any("/articles/movies/page/" in p for p in built.movies_paths))

    def test_external_to_url(self) -> None:
        items = redirection_plugin_items_to_url(
            ["/articles/tv-series/page/2/"],
            "https://tambur.pub/comuns/after_the_credits?category=serialy",
        )
        self.assertEqual(items[0]["redirect"]["to"], "https://tambur.pub/comuns/after_the_credits?category=serialy")
