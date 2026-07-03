from django.test import SimpleTestCase

from ratings import serializers as ratings_serializers
from ratings import service as ratings_service
from ratings import views as ratings_views


class RatingsRuntimeBridgeTests(SimpleTestCase):
    def test_views_use_ratings_serializer(self):
        self.assertIs(
            ratings_views._serialize_top_author_item,
            ratings_serializers.serialize_top_author_item,
        )

    def test_views_use_ratings_service(self):
        self.assertIs(ratings_views._list_top_authors, ratings_service.list_top_authors)
        self.assertIs(
            ratings_views._normalize_top_authors_period,
            ratings_service.normalize_top_authors_period,
        )
        self.assertIs(
            ratings_views._parse_top_authors_limit,
            ratings_service.parse_top_authors_limit,
        )
