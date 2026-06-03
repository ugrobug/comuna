from django.apps import apps
from django.test import SimpleTestCase

from my_feed.models import FeedSourcePost, UserFeedSettings


class MyFeedModelsApiTests(SimpleTestCase):
    def test_my_feed_app_is_installed(self):
        self.assertTrue(apps.is_installed("my_feed"))

    def test_user_feed_settings_remains_available_through_feeds_app_label(self):
        self.assertEqual(UserFeedSettings._meta.app_label, "feeds")
        self.assertIs(apps.get_model("feeds", "UserFeedSettings"), UserFeedSettings)

    def test_feed_source_post_is_available_through_feeds_app_label(self):
        self.assertEqual(FeedSourcePost._meta.app_label, "feeds")
        self.assertIs(apps.get_model("feeds", "FeedSourcePost"), FeedSourcePost)
