from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from pathlib import Path
from importlib import import_module
from django.core.files.base import ContentFile
from django.db import connection, connections
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase, override_settings
from media_storage.models import MediaTransfer
from media_storage.spool import LocalMediaSpool, MediaReserveFull


class ReserveConcurrencyTests(TransactionTestCase):
    def test_simultaneous_writers_respect_remaining_space(self):
        with TemporaryDirectory() as directory:
            def available():
                used = sum(p.stat().st_size for p in Path(directory).glob('_spool/*/*.jpg'))
                return 105 - used

            def save(number):
                try:
                    spool = LocalMediaSpool(directory, free_bytes=available, reserve_bytes=100)
                    try:
                        spool.save(f'{number}.jpg', ContentFile(b'abc'))
                        return True
                    except MediaReserveFull:
                        return False
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(save, (1, 2)))
            self.assertEqual(sum(results), 1)
            self.assertEqual(MediaTransfer.objects.count(), 1)

    def test_initial_migration_applies_and_reverses(self):
        migration = import_module('media_storage.migrations.0001_initial').Migration('0001_initial', 'media_storage')
        state = ProjectState()
        with connection.schema_editor() as editor:
            editor.delete_model(MediaTransfer)
        try:
            with connection.schema_editor() as editor:
                migration.apply(state.clone(), editor)
            with connection.cursor() as cursor:
                indexes = connection.introspection.get_constraints(cursor, MediaTransfer._meta.db_table)
            self.assertIn('media_transfer_due_idx', indexes)
            with connection.schema_editor() as editor:
                migration.unapply(state, editor)
            self.assertNotIn(MediaTransfer._meta.db_table, connection.introspection.table_names())
        finally:
            if MediaTransfer._meta.db_table not in connection.introspection.table_names():
                with connection.schema_editor() as editor:
                    editor.create_model(MediaTransfer)
