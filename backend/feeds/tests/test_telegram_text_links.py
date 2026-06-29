from django.test import SimpleTestCase

from feeds.views import _format_telegram_text


class TelegramTextLinksTests(SimpleTestCase):
    def test_url_entity_without_protocol_becomes_https_link(self):
        text = "intheweights.com"
        html = _format_telegram_text(
            text,
            [
                {
                    "type": "url",
                    "offset": 0,
                    "length": len(text),
                }
            ],
        )

        self.assertIn('href="https://intheweights.com"', html)
        self.assertIn('target="_blank"', html)
