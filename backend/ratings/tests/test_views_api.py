from django.test import SimpleTestCase
from django.urls import resolve

from ratings.views import top_authors, top_authors_month, top_comuns, top_comuns_month


class RatingsViewsApiTests(SimpleTestCase):
    def test_rating_urls_resolve_to_ratings_app_views(self):
        self.assertIs(resolve("/api/authors/top/").func, top_authors)
        self.assertIs(resolve("/api/authors/top-month/").func, top_authors_month)
        self.assertIs(resolve("/api/comuns/top/").func, top_comuns)
        self.assertIs(resolve("/api/comuns/top-month/").func, top_comuns_month)
