import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from telegram_integration.login_payload import TelegramLoginRedirect
from telegram_integration.models import TelegramAccount
from users.models import SiteUserProfile


@override_settings(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_USE_POLLING=False)
class LoginBoundaryTests(TestCase):
    def test_unsigned_phone_and_oidc_identity_cannot_merge_other_account(self):
        victim = get_user_model().objects.create_user(username='other-owner')
        SiteUserProfile.objects.update_or_create(user=victim, defaults={'phone': '+79990001122'})
        TelegramAccount.objects.create(user=victim, telegram_id=456, oidc_sub='other-sub')
        fields = {'id': 123, 'first_name': 'Reader', 'auth_date': int(timezone.now().timestamp())}
        signature = hmac.new(hashlib.sha256(b'test-token').digest(),
            '\n'.join(f'{key}={fields[key]}' for key in sorted(fields)).encode(), hashlib.sha256).hexdigest()
        response = self.client.post(reverse('auth-telegram'), data=json.dumps({**fields,
            'hash': signature, 'phone': '+79990001122', 'oidc_sub': 'other-sub',
            'telegram_id_source': 'sub'}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(get_user_model().objects.filter(pk=victim.pk).exists())
        self.assertEqual(TelegramAccount.objects.get(telegram_id=456).user_id, victim.pk)
        self.assertNotEqual(TelegramAccount.objects.get(telegram_id=123).user_id, victim.pk)


class RedirectTests(SimpleTestCase):
    def test_redirect_is_local_and_cannot_end_script_element(self):
        for target in ['javascript:alert(1)', 'https://elsewhere.test', '//elsewhere.test', '/%5celsewhere.test']:
            self.assertEqual(TelegramLoginRedirect(target).target, '/')
        page = TelegramLoginRedirect('/search?q=</script><script>alert(1)</script>').html()
        self.assertEqual(page.count('</script>'), 1)
        self.assertIn('\\u003c', page)
        self.assertEqual(TelegramLoginRedirect('/settings?tab=about').target, '/settings?tab=about')
