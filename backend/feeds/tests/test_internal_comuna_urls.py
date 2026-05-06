from django.test import SimpleTestCase

from feeds.views import _is_internal_comuna_url


class InternalComunaUrlTests(SimpleTestCase):
    def test_accepts_only_exact_internal_hosts(self) -> None:
        self.assertTrue(_is_internal_comuna_url("https://comuna.ru/test"))
        self.assertTrue(_is_internal_comuna_url("https://www.comuna.ru/test"))
        self.assertTrue(_is_internal_comuna_url("https://tambur.pub/x"))
        self.assertTrue(_is_internal_comuna_url("https://www.tambur.pub/y"))
        self.assertTrue(_is_internal_comuna_url("localhost"))
        self.assertTrue(_is_internal_comuna_url("127.0.0.1"))

    def test_rejects_subdomains_of_comuna(self) -> None:
        self.assertFalse(_is_internal_comuna_url("https://admin.comuna.ru"))
        self.assertFalse(_is_internal_comuna_url("https://foo.bar.comuna.ru"))
        self.assertFalse(_is_internal_comuna_url("https://staging.tambur.pub"))
