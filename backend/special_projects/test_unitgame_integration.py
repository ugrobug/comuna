"""Integration checks for the unmodified suphub application."""

from pathlib import Path
from urllib.parse import urljoin

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["testserver"])
class UnitGameIntegrationTests(SimpleTestCase):
    # SimpleTestCase rejects database access, including accidental session reads.
    def test_menu_links_use_tambur_mount_without_database_access(self):
        response = self.client.get("/s/unitgame/")
        self.assertContains(response, 'href="/s/unitgame/play/"')
        self.assertContains(response, 'href="/s/unitgame/onboarding/"')
        self.assertEqual(reverse("unitgame_app:menu"), "/s/unitgame/")

    def test_play_and_tutorial_keep_their_original_modes(self):
        for name, tutorial in (("play", False), ("onboarding", True)):
            with self.subTest(name=name):
                response = self.client.get(reverse(f"unitgame_app:{name}"))
                self.assertContains(response, 'id="introStart"')
                self.assertContains(response, 'id="stack"')
                self.assertEqual(b"tour-mask" in response.content, tutorial)

    def test_site_cookies_do_not_make_game_pages_personal_or_query_database(self):
        for name in ("menu", "play", "onboarding"):
            with self.subTest(name=name):
                url = reverse(f"unitgame_app:{name}")
                self.client.cookies.clear()
                guest = self.client.get(url)
                self.client.cookies["sessionid"] = "unused-game-session"
                self.client.cookies["comuna_site_token"] = "unused-game-token"
                signed_in = self.client.get(url)
                self.assertEqual(signed_in.status_code, 200)
                self.assertEqual(signed_in.content, guest.content)

    def test_original_module_path_and_assets_are_supported(self):
        root = Path(__file__).resolve().parents[2]
        nginx = (root / "deploy/nginx.conf").read_text()
        for name in ("play", "onboarding"):
            module_url = urljoin(reverse(f"unitgame_app:{name}"), "../../static/unitgame_app/main.js")
            self.assertEqual(module_url, "/s/static/unitgame_app/main.js")
        self.assertIn("location ^~ /s/static/unitgame_app/", nginx)
        self.assertIn("alias /var/www/static/unitgame_app/;", nginx)
        for asset in ("style.css", "main.js", "cards.js", "events.js", "constants.js"):
            self.assertIsNotNone(finders.find(f"unitgame_app/{asset}"))

    def test_unknown_game_page_does_not_fall_back_to_another_page(self):
        self.assertEqual(self.client.get("/s/unitgame/missing/").status_code, 404)
