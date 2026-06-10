from django.test import SimpleTestCase

from legacy_migration.pt_comun import (
    CATEGORY_SLUG_ANIMATSIYA,
    CATEGORY_SLUG_FILMY,
    CATEGORY_SLUG_SERIALY,
    PT_COMUN_SLUG,
    decide_pt_comun,
)


class PtComunRulesTests(SimpleTestCase):
    def test_always_after_the_credits_comun(self) -> None:
        d = decide_pt_comun("/articles/movies/reviews/some-slug")
        self.assertEqual(d.comun_slug, PT_COMUN_SLUG)

    def test_movies_reviews_path(self) -> None:
        d = decide_pt_comun("/articles/movies/reviews/some-slug")
        self.assertEqual(d.category_slug, CATEGORY_SLUG_FILMY)
        self.assertEqual(d.wp_subsection, "reviews")
        self.assertEqual(d.reason, "articles_movies")

    def test_tv_series_path(self) -> None:
        d = decide_pt_comun("/articles/tv-series/recaps/foo")
        self.assertEqual(d.category_slug, CATEGORY_SLUG_SERIALY)
        self.assertEqual(d.reason, "articles_tv")

    def test_interview_default_filmy_with_tag(self) -> None:
        d = decide_pt_comun("/articles/interview/director-x")
        self.assertEqual(d.category_slug, CATEGORY_SLUG_FILMY)
        self.assertIn("interview", d.extra_tag_slugs)

    def test_root_articles_slug(self) -> None:
        d = decide_pt_comun("/articles/only-slug-here")
        self.assertEqual(d.category_slug, CATEGORY_SLUG_FILMY)
        self.assertEqual(d.reason, "articles_default")

    def test_podborki(self) -> None:
        d = decide_pt_comun("/podborki/best-2024")
        self.assertEqual(d.category_slug, CATEGORY_SLUG_FILMY)
        self.assertEqual(d.reason, "books_podborki")

    def test_path_anime_segment(self) -> None:
        d = decide_pt_comun("/articles/anime/one-piece")
        self.assertEqual(d.category_slug, CATEGORY_SLUG_ANIMATSIYA)
        self.assertEqual(d.reason, "path_animation")
