from django.test import SimpleTestCase

from legacy_migration.pt_analytics_redirects import (
    _SKIP_PATH_RE,
    slug_tail_from_pt_path,
)


class PtAnalyticsRedirectsTests(SimpleTestCase):
    def test_slug_from_nested_review_path(self) -> None:
        slug = slug_tail_from_pt_path("/articles/movies/reviews/avatar-plamja-i-pepel/")
        self.assertEqual(slug, "avatar-plamja-i-pepel")

    def test_slug_from_tv_news(self) -> None:
        slug = slug_tail_from_pt_path("/news/tv-news/pervyi-vzgljad-na-vlasteliny-vozduha/")
        self.assertEqual(slug, "pervyi-vzgljad-na-vlasteliny-vozduha")

    def test_skip_pagination(self) -> None:
        self.assertTrue(_SKIP_PATH_RE.match("/articles/movies/page/10/"))
