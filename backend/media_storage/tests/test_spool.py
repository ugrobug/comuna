from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from datetime import timedelta
import io

from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings, RequestFactory
from django.utils import timezone
from django.http import Http404
from django.db import connection
from django.test.utils import CaptureQueriesContext
from PIL import Image

from media_storage.models import MediaTransfer
from media_storage.spool import LocalMediaSpool, S3Availability, MediaReserveFull
from media_storage.transfer import MediaTransferWorker, S3TransferDestination
from media_storage.views import MediaSpoolView
from media_storage.middleware import MediaReserveErrorsMiddleware
from rabotaem_backend.storage import S3MediaStorage
from rabotaem_backend.media_urls import public_media_url, rewrite_public_media_urls


@override_settings(SITE_BASE_URL='https://tambur.pub', MEDIA_PUBLIC_URL_MODE='s3', MEDIA_S3_PUBLIC_BASE_URL='https://media.test')
class MediaSpoolTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.spool = LocalMediaSpool(reserve_bytes=100, free_bytes=lambda: 10000, max_file_bytes=1000)
        self.storage = S3MediaStorage()
        self.storage.spool = self.spool
        self.storage.availability = S3Availability(self.spool)
        self.remote = Mock()
        self.remote.exists.return_value = False
        self.storage.s3_storage = self.remote

    def failed_remote(self):
        self.remote.save.side_effect = EndpointConnectionError(endpoint_url='https://s3.invalid')

    def worker(self, destination=None):
        return MediaTransferWorker(spool=self.spool, destination=destination or Mock(), availability=self.storage.availability)

    def test_successful_s3_save_does_not_queue(self):
        self.remote.save.return_value = 'normal.jpg'
        self.assertEqual(self.storage.save('normal.jpg', ContentFile(b'abc')), 'normal.jpg')
        self.assertFalse(MediaTransfer.objects.exists())

    def test_endpoint_failure_stores_local_bytes_and_job(self):
        self.failed_remote()
        key = self.storage.save('posts/photo.jpg', ContentFile(b'abc'))
        self.assertTrue(key.startswith('_spool/'))
        self.assertEqual(self.spool.local.open(key).read(), b'abc')
        self.assertEqual(MediaTransfer.objects.get().key, key)
        self.assertEqual(self.storage.url(key), f'https://tambur.pub/media/{key}')
        self.assertEqual(public_media_url(self.storage.url(key)), self.storage.url(key))
        self.assertEqual(rewrite_public_media_urls(f'<img src="{self.storage.url(key)}">'), f'<img src="{self.storage.url(key)}">')

    def test_exists_network_failure_also_falls_back(self):
        self.remote.exists.side_effect = EndpointConnectionError(endpoint_url='https://s3.invalid')
        key = self.storage.save('test.jpg', ContentFile(b'abc'))
        self.assertTrue(self.spool.local.exists(key))

    def test_shared_circuit_avoids_repeated_network_waits(self):
        self.failed_remote()
        self.storage.save('one.jpg', ContentFile(b'abc'))
        another = S3MediaStorage()
        another.spool = self.spool
        another.s3_storage = Mock(side_effect=AssertionError('network'))
        key = another.save('two.jpg', ContentFile(b'abc'))
        self.assertTrue(self.spool.local.exists(key))
        another.s3_storage.save.assert_not_called()
        self.assertEqual(self.remote.save.call_count, 1)

    def test_permission_error_is_not_silently_hidden(self):
        self.remote.save.side_effect = ClientError({'Error': {'Code': 'AccessDenied'}, 'ResponseMetadata': {'HTTPStatusCode': 403}}, 'PutObject')
        with self.assertRaises(ClientError):
            self.storage.save('photo.jpg', ContentFile(b'abc'))
        self.assertFalse(MediaTransfer.objects.exists())

    def test_disk_reserve_and_file_limit_stop_writes(self):
        for spool in (LocalMediaSpool(reserve_bytes=100, free_bytes=lambda: 102),
                      LocalMediaSpool(max_file_bytes=2)):
            with self.assertRaises(MediaReserveFull):
                spool.save('photo.jpg', ContentFile(b'abc'))
        self.assertFalse(MediaTransfer.objects.exists())
        response = MediaReserveErrorsMiddleware(lambda r: None).process_exception(RequestFactory().post('/'), MediaReserveFull('Повторите загрузку позже'))
        self.assertEqual(response.status_code, 503)

    def test_failed_job_creation_removes_new_local_copy(self):
        with patch('media_storage.models.MediaTransfer.objects.create', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.spool.save('photo.jpg', ContentFile(b'abc'))
        self.assertFalse(list(self.spool.directory.glob('*/*.jpg')))

    def test_transfer_verifies_before_removing_local_copy_and_redirects(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        worker = self.worker()
        with self.captureOnCommitCallbacks(execute=True):
            result = worker.drain()
        self.assertEqual(result['processed'], 1)
        self.assertFalse(self.spool.local.exists(key))
        self.assertEqual(MediaTransfer.objects.get().state, 'uploaded')
        with patch('media_storage.views.default_storage', self.storage):
            self.remote.url.return_value = 'https://media.test/' + key
            response = MediaSpoolView.as_view()(RequestFactory().get('/'), key=key.removeprefix('_spool/'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://media.test/' + key)

    def test_failed_verification_keeps_local_image_available(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        destination = Mock()
        destination.put_and_verify.side_effect = ValueError('mismatch')
        with self.captureOnCommitCallbacks(execute=True):
            self.worker(destination).drain()
        self.assertTrue(self.spool.local.exists(key))
        self.assertEqual(MediaTransfer.objects.get().state, 'pending')
        response = MediaSpoolView.as_view()(RequestFactory().get('/'), key=key.removeprefix('_spool/'))
        self.assertEqual(b''.join(response.streaming_content), b'abc')
        response.file_to_stream.close()

    def test_inflight_delete_cannot_resurrect_object(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        worker = self.worker()
        claimed = worker.claim()
        self.spool.delete(key)
        self.assertFalse(worker.complete(claimed))
        self.assertFalse(self.spool.local.exists(key))
        row = MediaTransfer.objects.get()
        self.assertEqual(row.state, 'deleting')
        self.assertGreater(row.next_attempt_at, timezone.now())
        MediaTransfer.objects.update(next_attempt_at=timezone.now())
        with self.captureOnCommitCallbacks(execute=True):
            worker.drain()
        self.assertEqual(MediaTransfer.objects.get().state, 'deleted')
        with self.assertRaises(Http404):
            MediaSpoolView.as_view()(RequestFactory().get('/'), key=key.removeprefix('_spool/'))

    def test_old_lease_cannot_mark_uploaded_or_remove_file(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        worker = self.worker()
        first = worker.claim()
        MediaTransfer.objects.update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        second = worker.claim()
        self.assertFalse(worker.complete(first))
        self.assertTrue(self.spool.local.exists(key))
        self.assertNotEqual(first.lease_token, second.lease_token)

    def test_cleanup_recovers_after_crash(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        MediaTransfer.objects.update(state='uploaded')
        self.worker().drain()
        self.assertFalse(self.spool.local.exists(key))
        self.assertIsNotNone(MediaTransfer.objects.get().local_deleted_at)

    def test_private_spool_files_and_traversal_are_not_served(self):
        for key in ('.s3-availability.json', '../private', 'a'*32+'/..'):
            with self.assertRaises(Http404):
                MediaSpoolView.as_view()(RequestFactory().get('/'), key=key)

    def test_queue_cost_is_constant_as_receipts_grow(self):
        counts = []
        for n in range(10):
            with CaptureQueriesContext(connection) as queries:
                self.spool.save(f'{n}.jpg', ContentFile(b'abc'))
            counts.append(len(queries))
        self.assertEqual(set(counts), {1})

    def test_image_variants_stay_in_reserve_namespace(self):
        from rabotaem_backend.images import save_image_with_variants
        self.failed_remote()
        self.spool.max_file_bytes = 100000
        self.spool.free_bytes = lambda: 1000000
        source = io.BytesIO()
        Image.new('RGB', (700, 400)).save(source, format='JPEG')
        with patch('rabotaem_backend.images.default_storage', self.storage):
            result = save_image_with_variants(data=source.getvalue(), original_path='posts/photo.jpg', variant_widths=(320,640))
        self.assertEqual(MediaTransfer.objects.count(), 3)
        self.assertTrue(all(v.path.startswith('_spool/') for v in result.variants))
        self.assertEqual(self.remote.save.call_count, 1)

    def test_remote_checksum_and_length_are_checked(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        row = MediaTransfer.objects.get()
        storage = Mock(location='', bucket_name='bucket', object_parameters={}, default_acl='public-read')
        adapter = S3TransferDestination(storage)
        adapter.client.head_object.return_value = {'ContentLength': 99, 'Metadata': {'sha256': row.sha256}}
        with self.spool.local.open(key) as source:
            with self.assertRaises(ValueError):
                adapter.put_and_verify(row, source)
        self.assertIn('ContentMD5', adapter.client.put_object.call_args.kwargs)

    def test_rollback_orphan_is_reclaimed_after_grace_but_pending_file_is_kept(self):
        import os
        from django.db import transaction
        from media_storage.reconcile import MediaReserveReconciler
        pending = self.spool.save('pending.jpg', ContentFile(b'abc'))
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                orphan = self.spool.save('orphan.jpg', ContentFile(b'abc'))
                raise RuntimeError('application transaction rollback')
        self.assertTrue(self.spool.local.exists(orphan))
        for key in (pending, orphan):
            os.utime(self.spool.local.path(key), (1, 1))
        self.assertEqual(MediaReserveReconciler(self.spool).run(), 1)
        self.assertTrue(self.spool.local.exists(pending))
        self.assertFalse(self.spool.local.exists(orphan))

    def test_new_orphan_is_not_removed_and_url_quotes_filename(self):
        from media_storage.reconcile import MediaReserveReconciler
        key = self.spool.save('with space.jpg', ContentFile(b'abc'))
        MediaTransfer.objects.filter(key=key).delete()
        self.assertEqual(MediaReserveReconciler(self.spool).run(), 0)
        self.assertTrue(self.spool.local.exists(key))
        self.assertIn('with%20space.jpg', self.storage.url(key))

    def test_disabling_new_fallback_keeps_existing_reserve_urls(self):
        key = self.spool.save('photo.jpg', ContentFile(b'abc'))
        self.failed_remote()
        with override_settings(MEDIA_SPOOL_ENABLED=False):
            with self.assertRaises(EndpointConnectionError):
                self.storage.save('new.jpg', ContentFile(b'abc'))
            self.assertIn('/media/_spool/', self.storage.url(key))

    def test_authenticated_website_upload_is_visible_during_s3_outage(self):
        from django.contrib.auth import get_user_model
        from django.core.files.uploadedfile import SimpleUploadedFile
        from users.service import _issue_token
        from urllib.parse import urlsplit
        user = get_user_model().objects.create_user(username='reserve-upload-user')
        token = _issue_token(user)
        source = io.BytesIO()
        Image.new('RGB', (50, 30)).save(source, format='PNG')
        self.failed_remote()
        self.spool.max_file_bytes = 10000
        self.spool.free_bytes = lambda: 100000
        with patch('rabotaem_backend.images.default_storage', self.storage):
            response = self.client.post('/api/auth/uploads/',
                {'image': SimpleUploadedFile('photo.png', source.getvalue(), content_type='image/png')},
                HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('/media/_spool/', payload['url'])
        image = self.client.get(urlsplit(payload['url']).path)
        self.assertEqual(image.status_code, 200)
        with Image.open(io.BytesIO(b''.join(image.streaming_content))) as opened:
            self.assertEqual(opened.size, (50, 30))

    def test_unauthenticated_upload_does_not_create_spool_job(self):
        response = self.client.post('/api/auth/uploads/')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(MediaTransfer.objects.exists())

    def test_circuit_metadata_error_does_not_break_healthy_primary(self):
        self.storage.availability = Mock()
        self.storage.availability.allow_request.side_effect = OSError('read-only circuit state')
        self.storage.availability.recovered.side_effect = OSError('read-only circuit state')
        self.remote.save.return_value = 'photo.jpg'
        self.assertEqual(self.storage.save('photo.jpg', ContentFile(b'abc')), 'photo.jpg')
        self.assertFalse(MediaTransfer.objects.exists())
