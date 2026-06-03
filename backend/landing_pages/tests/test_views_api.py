from django.test import SimpleTestCase
from django.urls import resolve

from landing_pages import views


class LandingPagesViewsRoutingTests(SimpleTestCase):
    def test_public_routes_resolve_to_landing_pages_app(self):
        self.assertIs(resolve("/api/landing-pages/communities/").func, views.landing_page_detail)
        self.assertIs(resolve("/api/landing-pages/communities/leads/").func, views.landing_page_leads)

    def test_admin_routes_resolve_to_landing_pages_app(self):
        self.assertIs(resolve("/api/landing-pages/admin/pages/").func, views.admin_landing_pages)
        self.assertIs(
            resolve("/api/landing-pages/admin/pages/communities/").func,
            views.admin_landing_page_detail,
        )
        self.assertIs(
            resolve("/api/landing-pages/admin/pages/communities/images/").func,
            views.admin_landing_page_images,
        )
        self.assertIs(
            resolve("/api/landing-pages/admin/images/42/").func,
            views.admin_landing_page_image_detail,
        )
