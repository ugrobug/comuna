from django.apps import apps
from django.test import SimpleTestCase

from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunPostCategoryAssignment,
    ComunVote,
)
from feeds.models import (
    Comun as FeedsComun,
    ComunCategory as FeedsComunCategory,
    ComunGlossaryTerm as FeedsComunGlossaryTerm,
    ComunPostCategoryAssignment as FeedsComunPostCategoryAssignment,
    ComunVote as FeedsComunVote,
)


class CommunitiesModelsApiTests(SimpleTestCase):
    def test_communities_app_is_installed(self):
        self.assertTrue(apps.is_installed("communities"))

    def test_communities_models_keep_existing_feeds_app_label(self):
        self.assertEqual(Comun._meta.app_label, "feeds")
        self.assertEqual(ComunCategory._meta.app_label, "feeds")
        self.assertEqual(ComunGlossaryTerm._meta.app_label, "feeds")
        self.assertEqual(ComunPostCategoryAssignment._meta.app_label, "feeds")
        self.assertEqual(ComunVote._meta.app_label, "feeds")

    def test_communities_models_reexport_existing_feeds_models(self):
        self.assertIs(Comun, FeedsComun)
        self.assertIs(ComunCategory, FeedsComunCategory)
        self.assertIs(ComunGlossaryTerm, FeedsComunGlossaryTerm)
        self.assertIs(ComunPostCategoryAssignment, FeedsComunPostCategoryAssignment)
        self.assertIs(ComunVote, FeedsComunVote)

    def test_roadmap_is_disabled_by_default(self):
        field = Comun._meta.get_field("roadmap_enabled")

        self.assertFalse(field.default)
