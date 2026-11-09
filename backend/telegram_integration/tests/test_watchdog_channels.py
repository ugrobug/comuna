from unittest.mock import Mock, patch
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from telegram_integration.management.commands.watch_telegram_bot import Command
from telegram_integration.tests.test_runtime import MemoryStore
from telegram_integration.watchdog import TelegramWatchdog


class WatchdogChannelTests(SimpleTestCase):
    def test_max_only_does_not_construct_email_sender(self):
        with patch('telegram_integration.management.commands.watch_telegram_bot.EmailAlertSender') as email:
            senders = Command().build_senders({'TELEGRAM_ALERT_EMAIL': '  ', 'TELEGRAM_ALERT_MAX_CHAT_ID': '123'})
        self.assertEqual(set(senders), {'max'})
        self.assertEqual(senders['max'].chat_id, 123)
        email.assert_not_called()

    def test_email_only_and_both_channels_remain_supported(self):
        self.assertEqual(set(Command().build_senders({'TELEGRAM_ALERT_EMAIL': 'test@example.test'})), {'email'})
        self.assertEqual(set(Command().build_senders({'TELEGRAM_ALERT_EMAIL': 'test@example.test',
            'TELEGRAM_ALERT_MAX_CHAT_ID': '123'})), {'email', 'max'})

    def test_missing_channels_or_invalid_chat_fails_clearly(self):
        for environment in ({}, {'TELEGRAM_ALERT_MAX_CHAT_ID': 'invalid'}):
            with self.assertRaises(CommandError):
                Command().build_senders(environment)

    def test_old_email_delivery_state_does_not_enable_email_on_outage_or_recovery(self):
        status, state = MemoryStore(), MemoryStore()
        state.value = {'channels': {'email': {'problem': 'previous outage', 'sent_at': 1}}}
        old_email = dict(state.value['channels']['email'])
        status.value = {'heartbeat_at': 1000, 'api_ok_at': 1, 'started_at': 1}
        max_sender = Mock()
        watchdog = TelegramWatchdog(status, state, {'max': max_sender}, clock=lambda: 1000)
        watchdog.check()
        self.assertEqual(max_sender.call_count, 1)
        status.value = {'heartbeat_at': 1000, 'api_ok_at': 1000, 'cycle_ok_at': 1000}
        watchdog.check()
        self.assertEqual(max_sender.call_count, 2)
        self.assertIn('снова', max_sender.call_args.args[0])
        self.assertEqual(state.value['channels']['email'], old_email)
