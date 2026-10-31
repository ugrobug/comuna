from tempfile import TemporaryDirectory
from unittest.mock import Mock

from django.test import SimpleTestCase

from telegram_integration.health import JsonStatusFile, PollingHealth, PollingStatus
from telegram_integration.runtime import TelegramPollingRuntime
from telegram_integration.watchdog import TelegramWatchdog


class MemoryStore:
    def __init__(self):
        self.value = {}

    def read(self):
        return self.value.copy()

    def write(self, value):
        self.value = value.copy()


class RuntimeTests(SimpleTestCase):
    def setUp(self):
        self.now = 1000
        self.clock = lambda: self.now
        self.store = MemoryStore()
        self.status = PollingStatus(self.store, self.clock)
        self.fetch = Mock(return_value={'ok': True, 'result': []})
        self.processor = Mock(offset=None)
        self.approvals = Mock()
        self.runtime = TelegramPollingRuntime('secret', self.fetch, self.processor, self.approvals, self.status, self.clock)

    def test_startup_timeout_retries_without_dropping_updates(self):
        self.fetch.side_effect = [TimeoutError(), {'ok': True}, {'ok': True, 'result': []}]
        self.assertEqual(self.runtime.step(), 2)
        self.assertEqual(self.runtime.step(), 0)
        self.assertEqual([c.args[0] for c in self.fetch.call_args_list], ['deleteWebhook', 'deleteWebhook', 'getUpdates'])
        self.assertEqual(self.fetch.call_args_list[0].args[2], {'drop_pending_updates': False})

    def test_network_failure_is_unhealthy_after_two_minutes_and_recovers(self):
        self.fetch.return_value = None
        for _ in range(9):
            self.assertLessEqual(self.runtime.step(), 30)
        self.now += 121
        self.runtime.step()
        self.assertIn('API', PollingHealth().problem(self.store.read(), self.now))
        self.fetch.return_value = {'ok': True, 'result': []}
        self.assertEqual(self.runtime.step(), 0)
        self.assertIsNone(PollingHealth().problem(self.store.read(), self.now))

    def test_failed_update_keeps_offset_and_alerts_despite_successful_api(self):
        self.processor.offset = 42
        self.processor.process.side_effect = ValueError()
        self.runtime.step()
        self.now += 121
        self.runtime.step()
        self.assertEqual(self.fetch.call_args.args[2]['offset'], 42)
        self.assertIn('очередь', PollingHealth().problem(self.store.read(), self.now))
        self.processor.process.side_effect = None
        self.runtime.step()
        self.assertIsNone(PollingHealth().problem(self.store.read(), self.now))

    def test_queue_exception_does_not_stop_new_updates(self):
        self.approvals.drain.side_effect = RuntimeError()
        self.runtime.step()
        self.runtime.step()
        self.assertEqual(self.processor.process.call_count, 2)
        self.now += 121
        self.runtime.step()
        self.assertIn('согласований', PollingHealth().problem(self.store.read(), self.now))

    def test_processing_progress_keeps_long_batch_healthy_but_stall_does_not(self):
        self.status.update(phase='processing')
        self.now += 121
        self.status.progress()
        self.assertIsNone(PollingHealth().problem(self.store.read(), self.now))
        self.now += 121
        self.assertIsNotNone(PollingHealth().problem(self.store.read(), self.now))


class WatchdogTests(SimpleTestCase):
    def setUp(self):
        self.now = 1000
        self.clock = lambda: self.now
        self.status, self.state = MemoryStore(), MemoryStore()
        self.senders = {'email': Mock(), 'max': Mock()}
        self.watchdog = TelegramWatchdog(self.status, self.state, self.senders, self.clock)

    def fail(self):
        self.now += 121
        self.watchdog.check()

    def recover(self):
        self.status.write({'started_at': self.now, 'heartbeat_at': self.now, 'api_ok_at': self.now, 'cycle_ok_at': self.now})
        self.watchdog.check()

    def test_missing_worker_alerts_both_channels_then_recovery_once(self):
        self.watchdog.check()
        self.assertFalse(self.senders['email'].called)
        self.fail()
        self.watchdog.check()
        self.assertEqual(self.senders['email'].call_count, 1)
        self.assertEqual(self.senders['max'].call_count, 1)
        self.recover()
        self.watchdog.check()
        self.assertEqual(self.senders['email'].call_count, 2)
        self.assertIn('снова', self.senders['email'].call_args.args[0])

    def test_one_broken_destination_does_not_block_other_and_retries(self):
        self.senders['email'].side_effect = TimeoutError()
        self.fail()
        self.assertEqual(self.senders['max'].call_count, 1)
        self.watchdog.check()
        self.assertEqual(self.senders['email'].call_count, 1)
        self.senders['email'].side_effect = None
        self.now += 61
        self.watchdog.check()
        self.assertEqual(self.senders['email'].call_count, 2)
        self.assertEqual(self.senders['max'].call_count, 1)

    def test_restart_does_not_duplicate_delivered_alert(self):
        self.fail()
        restarted = TelegramWatchdog(self.status, self.state, self.senders, self.clock)
        restarted.check()
        self.assertEqual(self.senders['max'].call_count, 1)
        self.now += 3601
        restarted.check()
        self.assertEqual(self.senders['max'].call_count, 2)

    def test_restart_without_successful_poll_does_not_report_recovery(self):
        self.fail()
        self.status.write({'started_at': self.now, 'heartbeat_at': self.now})
        self.watchdog.check()
        self.assertEqual(self.senders['max'].call_count, 1)
        self.recover()
        self.assertEqual(self.senders['max'].call_count, 2)

    def test_atomic_file_roundtrip_and_corrupt_state(self):
        with TemporaryDirectory() as directory:
            store = JsonStatusFile(directory + '/status.json')
            self.assertEqual(store.read(), {})
            store.write({'phase': 'idle'})
            self.assertEqual(store.read(), {'phase': 'idle'})
            store.path.write_text('broken')
            self.assertEqual(store.read(), {})
