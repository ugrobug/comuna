"""Bounded durable photo delivery. No storage/network I/O inside database locks."""
from datetime import timedelta
import hashlib
import json
import logging
import secrets

from django.db import transaction
from django.utils import timezone
from feeds.models import Author, Post
from telegram_integration.channel_posts import TelegramChannelPostWriter, TelegramMediaDownloadError
from telegram_integration.models import TelegramMediaJob

logger = logging.getLogger(__name__)


class TelegramMediaQueue:
    max_pending_per_author = 1000
    max_payload_bytes = 128 * 1024

    @staticmethod
    def content_hash(content):
        return hashlib.sha256(content.encode()).hexdigest()

    def enqueue(self, author, message, prepared):
        # Caller holds the author lock; it serializes enqueue with completion.
        payload = {'message': message, 'prepared': prepared}
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if len(encoded.encode()) > self.max_payload_bytes:
            raise ValueError('Telegram media payload exceeds limit')
        revision = self.content_hash(encoded)
        job = TelegramMediaJob.objects.filter(author=author, message_id=message['message_id']).first()
        if job and job.revision == revision:
            return job, False
        if not job:
            # Bounded index scan rather than COUNT of the whole queue.
            pending = list(TelegramMediaJob.objects.filter(author=author, state='pending')
                           .values_list('pk', flat=True)[:self.max_pending_per_author])
            if len(pending) >= self.max_pending_per_author:
                raise RuntimeError('Telegram media queue capacity reached')
            job = TelegramMediaJob(author=author, message_id=message['message_id'])
        job.media_group_id = message.get('media_group_id') or ''
        job.payload, job.revision = payload, revision
        job.state, job.attempts, job.lease_token, job.last_error = 'pending', 0, '', ''
        job.next_attempt_at = timezone.now()
        job.save()
        return job, True

    @staticmethod
    def bind(job, post):
        if post is None:
            return
        query = TelegramMediaJob.objects.filter(pk=job.pk)
        if job.media_group_id:
            query = TelegramMediaJob.objects.filter(author_id=job.author_id, media_group_id=job.media_group_id)
        query.filter(post__isnull=True).update(post=post)


class TelegramMediaWorker:
    lease_seconds = 600
    max_attempts = 100

    def __init__(self, *, download, content, prompt, progress=None):
        self.download, self.content, self.prompt = download, content, prompt
        self.progress = progress or (lambda: None)

    def drain(self, limit=10):
        processed = failed = 0
        error_name = ''
        for _ in range(max(1, min(int(limit), 20))):
            self.progress()
            job = self.claim()
            if job is None:
                break
            try:
                url = self.download(job.payload['message'])
                if not url:
                    raise TelegramMediaDownloadError('Photo download unavailable')
                post = self.complete(job, url)
            except Exception as error:
                error_name = type(error).__name__
                self.retry(job, error)
                failed += 1
                # An unavailable storage must not cause a burst of retries.
                break
            processed += 1
            # Approval delivery already has its own durable retry mechanism.
            if post is not None and post.is_pending:
                self.prompt.deliver(post, post.author)
            elif post is not None:
                self.content._maybe_notify_new_author(post.author, post)
        return {'processed': processed, 'failed': failed, 'error': error_name}

    def claim(self):
        with transaction.atomic():
            job = (TelegramMediaJob.objects.select_for_update(skip_locked=True)
                   .filter(state='pending', next_attempt_at__lte=timezone.now())
                   .order_by('next_attempt_at', 'pk').first())
            if job is None:
                return None
            job.lease_token = secrets.token_hex(16)
            job.attempts += 1
            job.next_attempt_at = timezone.now() + timedelta(seconds=self.lease_seconds)
            job.save(update_fields=['lease_token', 'attempts', 'next_attempt_at', 'updated_at'])
            return job

    def complete(self, claimed, image_url):
        with transaction.atomic():
            # Same lock order as receipt: author -> job -> post.
            author = Author.objects.select_for_update().filter(pk=claimed.author_id).first()
            if author is None:
                return None
            job = TelegramMediaJob.objects.select_for_update().filter(
                pk=claimed.pk, state='pending', lease_token=claimed.lease_token,
                revision=claimed.revision).first()
            if job is None:
                return None  # Deleted or superseded while downloading.
            from communities.models import Comun
            if author.is_blocked or not Comun.objects.filter(telegram_source_author=author, is_active=True).exists():
                self.finish(job, 'cancelled', 'ChannelUnavailable')
                return None
            message, prepared = job.payload['message'], job.payload['prepared']
            post = Post.objects.select_for_update().filter(pk=job.post_id).first() if job.post_id else None
            if post is None:
                candidates = Post.objects.select_for_update().filter(author=author)
                post = (candidates.filter(media_group_id=job.media_group_id).first() if job.media_group_id
                        else candidates.filter(message_id=job.message_id).first())
            if post is not None:
                raw = dict(post.raw_data or {})
                base_text = raw.get('formatted_text')
                if base_text is None:
                    text = self.content._extract_plain_text(raw)
                    base_text = self.content._format_telegram_text(text, self.content._extract_entities(raw))
                expected = raw.get('telegram_managed_content_sha256') or TelegramMediaQueue.content_hash(
                    self.content._build_content_with_images(base_text, raw.get('gallery_urls', []),
                        raw.get('embed_html', ''), raw.get('poll_html', '')))
                if post.is_blocked or expected != TelegramMediaQueue.content_hash(post.content):
                    self.finish(job, 'cancelled', 'PostChangedOrBlocked')
                    return None
                raw['formatted_text'] = base_text
                if message.get('edit_date') and not prepared['raw_text'].strip():
                    owner = raw.get('gallery_caption_message_id', post.message_id)
                    if not job.media_group_id or owner == job.message_id:
                        raw['formatted_text'] = ''
                # Attach to current text, never overwrite website/Telegram edits with an old caption.
                raw = TelegramChannelPostWriter.merge_image(raw, image_url=image_url,
                    photo_file_id=prepared['photo_file_id'], media_group_id=job.media_group_id,
                    message_id=job.message_id)
                post.content = self.content._build_content_with_images(raw.get('formatted_text', ''),
                    raw.get('gallery_urls', []), raw.get('embed_html', ''), raw.get('poll_html', ''))
                raw['telegram_managed_content_sha256'] = TelegramMediaQueue.content_hash(post.content)
                post.raw_data = raw
                post.save(update_fields=['content', 'raw_data', 'updated_at'])
            else:
                post, _ = TelegramChannelPostWriter(self.content).save(
                    author=author, message=message, image_url=image_url, **prepared)
            TelegramMediaQueue.bind(job, post)
            if post and post.is_pending and author.admin_chat_id:
                from telegram_integration.models import TelegramApprovalDelivery
                TelegramApprovalDelivery.objects.get_or_create(post=post, defaults={'chat_id': author.admin_chat_id})
            self.finish(job, 'done')
            return post

    @staticmethod
    def finish(job, state, error=''):
        job.state, job.last_error, job.lease_token = state, error, ''
        job.payload = {}  # Completed receipts retain deduplication keys, not user content.
        job.save(update_fields=['state', 'last_error', 'lease_token', 'payload', 'updated_at'])

    def retry(self, job, error):
        terminal = job.attempts >= self.max_attempts
        TelegramMediaJob.objects.filter(pk=job.pk, lease_token=job.lease_token).update(
            state='failed' if terminal else 'pending', lease_token='',
            last_error=type(error).__name__[:100], updated_at=timezone.now(),
            next_attempt_at=timezone.now() + timedelta(seconds=min(3600, 60 * 2 ** min(job.attempts - 1, 6))))
        logger.warning('Telegram media retry (job=%s, error=%s, terminal=%s)', job.pk, type(error).__name__, terminal)
