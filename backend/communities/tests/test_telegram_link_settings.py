from unittest.mock import patch
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from communities.settings_writer import CommunitySettingsWriter
from feeds.models import Author
from telegram_integration.channel_guidance import TelegramChannelLinkGuidance
from users.models import AuthorAdmin
from users.service import _issue_token


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='',
                   CACHES={'default':{'BACKEND':'django.core.cache.backends.dummy.DummyCache'}})
class TelegramLinkSettingsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='link-owner')
        self.author = Author.objects.create(username='linked-channel', channel_id=-100123)
        self.comun = Comun.objects.create(name='Community', slug='linked-community', creator=self.owner)
        AuthorAdmin.objects.create(user=self.owner, author=self.author, verified_at=timezone.now())
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {_issue_token(self.owner)}'
        self.url = reverse('comun-detail-manage', args=[self.comun.slug])

    def attach_after_read(self):
        Comun.objects.filter(pk=self.comun.pk).update(
            telegram_source_author=self.author, telegram_channel_username=self.author.username)

    def test_stale_object_save_preserves_bot_link(self):
        self.attach_after_read()
        self.comun.product_description = 'Edited'
        CommunitySettingsWriter().save(self.comun, {'product_description':'Edited'})
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_source_author_id, self.author.pk)
        self.assertEqual(self.comun.telegram_channel_username, self.author.username)
        self.assertEqual(self.comun.product_description, 'Edited')

    def test_unrelated_api_patch_preserves_link_created_after_request_read(self):
        original = CommunitySettingsWriter.save
        def save(writer, comun, body):
            self.attach_after_read()
            return original(writer, comun, body)
        with patch.object(CommunitySettingsWriter, 'save', save):
            response = self.client.patch(self.url, data=json.dumps({'product_description':'New'}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['comun']['telegram_source_author_id'], self.author.pk)
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_source_author_id, self.author.pk)

    def test_explicit_link_and_unlink_remain_supported(self):
        response = self.client.patch(self.url, data=json.dumps({
            'telegram_source_author_id': self.author.pk,
            'telegram_channel_username': self.author.username}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_source_author_id, self.author.pk)
        response = self.client.patch(self.url, data=json.dumps({
            'telegram_source_author_id': None, 'telegram_channel_username': ''}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.comun.refresh_from_db()
        self.assertIsNone(self.comun.telegram_source_author_id)

    def test_existing_owner_gets_settings_link_instead_of_new_community_instruction(self):
        with self.assertNumQueries(1):
            message = TelegramChannelLinkGuidance().message(self.author)
        self.assertIn('/comuns/linked-community/settings?tab=telegram', message)
        self.assertIn('сохраните настройки', message)
        self.assertNotIn('/comuns?create=1', message)

    def test_guidance_never_suggests_unverified_or_unrelated_communities(self):
        AuthorAdmin.objects.filter(author=self.author).update(verified_at=None)
        self.assertNotIn('/comuns/linked-community/', TelegramChannelLinkGuidance().message(self.author))
        self.assertIn('/comuns?create=1', TelegramChannelLinkGuidance().message(self.author))
