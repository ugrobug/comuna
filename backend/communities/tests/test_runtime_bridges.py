from django.test import SimpleTestCase

from communities import serializers as community_serializers
from communities import service as community_service
from communities import views as community_views
from feeds import views as feeds_views


class CommunityRuntimeBridgeTests(SimpleTestCase):
    def test_communities_views_uses_extracted_service_and_serializers(self):
        self.assertIs(community_views._serialize_comun, community_serializers._serialize_comun)
        self.assertIs(
            community_views._serialize_comun_profile_card,
            community_serializers._serialize_comun_profile_card,
        )
        self.assertIs(
            community_views._serialize_comun_sidebar,
            community_serializers._serialize_comun_sidebar,
        )
        self.assertIs(community_views._serialize_comun_activity, community_serializers._serialize_comun_activity)
        self.assertIs(community_views._comun_source_filter, community_service._comun_source_filter)
        self.assertIs(community_views._author_telegram_source_comun, community_service._author_telegram_source_comun)

    def test_feeds_views_is_only_a_compatibility_bridge_for_communities(self):
        self.assertIs(feeds_views.comun_posts, community_views.comun_posts)
        self.assertIs(feeds_views.comun_detail_manage, community_views.comun_detail_manage)
        self.assertIs(feeds_views.comun_vote, community_views.comun_vote)
        self.assertIs(feeds_views._serialize_comun, community_serializers._serialize_comun)
        self.assertIs(feeds_views._serialize_comun_profile_card, community_serializers._serialize_comun_profile_card)
        self.assertIs(feeds_views._serialize_comun_activity, community_serializers._serialize_comun_activity)
        self.assertIs(feeds_views._comun_source_filter, community_service._comun_source_filter)
        self.assertIs(feeds_views._author_telegram_source_comun, community_service._author_telegram_source_comun)
