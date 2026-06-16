from unittest.mock import patch

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

    @patch("legacy_migration.pt_comun._tag_names_suggest_animation", return_value=False)
    @patch("legacy_migration.pt_comun.wp_categories_suggest_serialy", return_value=True)
    def test_wp_category_serialy_on_root_articles_path(self, _mock_serialy, _mock_anim) -> None:
        d = decide_pt_comun("/articles/buhta-vdov/", wp_post_id=28755)
        self.assertEqual(d.category_slug, CATEGORY_SLUG_SERIALY)
        self.assertEqual(d.reason, "wp_category_serialy")

    @patch("legacy_migration.pt_comun.wp_categories_suggest_serialy", return_value=True)
    @patch("legacy_migration.pt_comun._tag_names_suggest_animation", return_value=True)
    def test_animation_tag_beats_serialy_category(
        self, _mock_anim, _mock_serialy
    ) -> None:
        d = decide_pt_comun("/articles/jujutsu-season-3/", wp_post_id=1)
        self.assertEqual(d.category_slug, CATEGORY_SLUG_ANIMATSIYA)
        self.assertEqual(d.reason, "wp_tag_animation")
