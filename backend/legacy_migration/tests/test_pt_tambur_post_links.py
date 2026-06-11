from pathlib import Path

from django.test import SimpleTestCase

from legacy_migration import pt_tambur_post_links as links_mod


class ResolveLinksPathTests(SimpleTestCase):
    def test_default_csv_next_to_module(self) -> None:
        path = links_mod.resolve_links_path("")
        expected = Path(links_mod.__file__).resolve().parent / "pt_tambur_post_links.csv"
        self.assertEqual(path, expected)
        self.assertTrue(path.is_file())

    def test_legacy_monorepo_relative_path(self) -> None:
        path = links_mod.resolve_links_path("backend/legacy_migration/pt_tambur_post_links.csv")
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "pt_tambur_post_links.csv")

    def test_short_relative_path(self) -> None:
        path = links_mod.resolve_links_path("legacy_migration/pt_tambur_post_links.csv")
        self.assertTrue(path.is_file())
