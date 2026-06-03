from django.apps import apps
from django.test import SimpleTestCase

from landing_pages.models import LandingPage, LandingPageImage, LandingPageLead


class LandingPagesModelsApiTests(SimpleTestCase):
    def test_landing_pages_app_is_installed(self):
        self.assertTrue(apps.is_installed("landing_pages"))

    def test_core_models_use_landing_pages_app_label(self):
        self.assertEqual(LandingPage._meta.app_label, "landing_pages")
        self.assertEqual(LandingPageImage._meta.app_label, "landing_pages")
        self.assertEqual(LandingPageLead._meta.app_label, "landing_pages")

    def test_initial_page_seed_slug_is_supported_by_model(self):
        field = LandingPage._meta.get_field("template_slug")

        self.assertEqual(field.default, "community-platform")
