from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock
from django.db import connection, connections
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature
from communities.models import Comun
from feeds.models import Author, Post
from feeds import views
from telegram_integration.channel_import import TelegramChannelImport
from telegram_integration.media_queue import TelegramMediaWorker
from telegram_integration.models import TelegramMediaJob


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='')
class ConcurrentMediaTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update_skip_locked')
    def test_two_workers_attach_same_album_without_loss_or_duplicates(self):
        author = Author.objects.create(username='queue-concurrency', auto_publish=False)
        comun = Comun.objects.create(name='Concurrency', slug='queue-concurrency', telegram_source_author=author)
        importer = TelegramChannelImport(token='', content=views, check_access=Mock(),
            refresh_metadata=Mock(), resolve_community=lambda a: comun, send_prompt=Mock())
        for n in (1, 2):
            importer.receive({'chat': {'username': author.username, 'id': -1}, 'message_id': n,
                'media_group_id': 'group', 'caption': 'Caption' if n == 1 else '',
                'photo': [{'file_id': f'photo-{n}', 'width': 100, 'height': 100}]})
        barrier = Barrier(2)

        def deliver(_):
            try:
                worker = TelegramMediaWorker(download=Mock(), content=views, prompt=Mock())
                claimed = worker.claim()
                barrier.wait(timeout=10)
                worker.complete(claimed, f'https://media.test/{claimed.message_id}.webp')
                return claimed.pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(deliver, (1, 2)))
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(Post.objects.get().content.count('<img '), 2)
        self.assertEqual(TelegramMediaJob.objects.filter(state='done').count(), 2)


class MediaMigrationTests(TransactionTestCase):
    def test_new_queue_migrations_apply_and_reverse_on_existing_schema(self):
        with override_settings(MIGRATION_MODULES={}):
            loader = MigrationLoader(connection)
        state = loader.project_state([('feeds', '0183_telegram_approval_delivery')])
        first = loader.get_migration('feeds', '0184_telegram_media_jobs')
        second = loader.get_migration('feeds', '0185_telegram_media_queue_indexes')
        with connection.schema_editor() as editor:
            editor.delete_model(TelegramMediaJob)
        try:
            with connection.schema_editor() as editor:
                after_first = first.apply(state.clone(), editor)
                second.apply(after_first.clone(), editor)
            with connection.cursor() as cursor:
                indexes = connection.introspection.get_constraints(cursor, TelegramMediaJob._meta.db_table)
            for name in ('tg_media_due_idx', 'tg_media_age_idx', 'tg_media_author_pending_idx', 'tg_media_message_unique'):
                self.assertIn(name, indexes)
            with connection.schema_editor() as editor:
                second.unapply(after_first, editor)
                first.unapply(state, editor)
            self.assertNotIn(TelegramMediaJob._meta.db_table, connection.introspection.table_names())
        finally:
            if TelegramMediaJob._meta.db_table not in connection.introspection.table_names():
                with connection.schema_editor() as editor:
                    editor.create_model(TelegramMediaJob)
