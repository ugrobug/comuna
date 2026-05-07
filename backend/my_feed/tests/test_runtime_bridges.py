from django.test import SimpleTestCase

from my_feed import serializers as my_feed_serializers
from my_feed import views as my_feed_views


class MyFeedRuntimeBridgeTests(SimpleTestCase):
    def test_my_feed_views_use_my_feed_runtime(self):
        self.assertIs(
            my_feed_views._serialize_feed_post_card,
            my_feed_serializers._serialize_feed_post_card,
        )
