import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from max_integration.client import MaxAPIError, MaxClient


@override_settings(MAX_BOT_TOKEN="test-secret", MAX_BOT_USERNAME="se14353168_bot")
class MaxClientTests(SimpleTestCase):
    @patch("max_integration.client.build_opener")
    def test_token_is_sent_only_in_authorization_header(self, open_url):
        open_url.return_value.open.return_value.__enter__.return_value = io.BytesIO(b'{"is_bot":true}')
        MaxClient().me()
        request = open_url.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://platform-api2.max.ru/me")
        self.assertEqual(request.get_header("Authorization"), "test-secret")
        self.assertNotIn("test-secret", request.full_url)
        context = open_url.call_args.args[0]._context
        self.assertTrue(context.check_hostname)

    @patch("max_integration.client.build_opener")
    def test_errors_do_not_expose_token_or_response(self, open_url):
        open_url.return_value.open.side_effect = HTTPError("https://platform-api2.max.ru/me", 401, "test-secret", {}, None)
        with self.assertRaises(MaxAPIError) as caught:
            MaxClient().me()
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn("test-secret", str(caught.exception))

    @patch("max_integration.client.MaxClient.me", return_value={"user_id": 443659383, "username": "se14353168_bot", "is_bot": True})
    def test_check_command_verifies_expected_bot(self, me):
        output = io.StringIO()
        call_command("check_max_bot", stdout=output)
        self.assertIn("se14353168_bot", output.getvalue())
        self.assertNotIn("test-secret", output.getvalue())

    @patch("max_integration.client.MaxClient.me", return_value={"username": "another_bot", "is_bot": True})
    def test_check_command_rejects_other_bot(self, me):
        with self.assertRaises(CommandError):
            call_command("check_max_bot")
