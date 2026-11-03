"""Application workflow for import; handlers supply integration adapters explicitly."""
from telegram_integration.channel_identity import TelegramChannelIdentity
from django.db import transaction
from feeds.models import Author, Post
from telegram_integration.channel_posts import TelegramChannelPostWriter
from telegram_integration.media_queue import TelegramMediaQueue
from telegram_integration.models import TelegramMediaJob
from telegram_integration.moderation import TelegramApprovalPrompt


class TelegramChannelImport:
    def __init__(self, *, token, content, check_access, refresh_metadata, resolve_community, send_prompt):
        self.token = token
        self.content = content
        self.check_access = check_access
        self.refresh_metadata = refresh_metadata
        self.resolve_community = resolve_community
        self.prompt = TelegramApprovalPrompt(send_prompt)

    def receive(self, message, *, force_publish=False):
        chat = message.get('chat') or {}
        if not chat.get('username') or message.get('message_id') is None:
            return None
        if self.content._is_telegram_service_message(message):
            return None
        author = TelegramChannelIdentity().resolve(chat)
        if author is None or author.is_blocked:
            return None
        if self.token and chat.get('id') and not self.check_access(chat['id'], self.token):
            return None
        if self.token and chat.get('id'):
            self.refresh_metadata(author, chat['id'], self.token)
        comun = self.resolve_community(author)
        if not comun or not comun.is_active:
            return None
        raw_text = self.content._extract_plain_text(message)
        photo_file_id = self.content._extract_photo_file_id(message)
        embed_html, embed_label = self.content._extract_telegram_embed(message, chat['username'], self.token)
        poll_html, poll_label = self.content._extract_telegram_poll(message)
        prepared = dict(raw_text=raw_text,
            formatted_text=self.content._format_telegram_text(raw_text, self.content._extract_entities(message)),
            explicit_tags=self.content._extract_hashtags(raw_text), photo_file_id=photo_file_id,
            embed_html=embed_html, embed_label=embed_label, poll_html=poll_html,
            poll_label=poll_label, force_publish=force_publish)
        post, created = self.save_receipt(author, message, prepared)
        if post is None:
            return None
        author = post.author
        if post.is_pending:
            self.prompt.deliver(post, author)
        elif created:
            self.content._maybe_notify_new_author(author, post)
        return post

    def save_receipt(self, author, message, prepared):
        with transaction.atomic():
            author = Author.objects.select_for_update().get(pk=author.pk)
            if author.is_blocked:
                return None, False
            job = None
            if prepared['photo_file_id']:
                job, changed = TelegramMediaQueue().enqueue(author, message, prepared)
                if not changed:
                    return (Post.objects.filter(pk=job.post_id).first() if job.post_id else None), False
                if not prepared['raw_text'].strip():
                    # Store photo-only messages without exposing an empty publication.
                    existing = Post.objects.filter(author=author)
                    existing = (existing.filter(media_group_id=job.media_group_id).first() if job.media_group_id
                                else existing.filter(message_id=job.message_id).first())
                    TelegramMediaQueue.bind(job, existing)
                    return existing, False
            if not prepared['photo_file_id'] and message.get('edit_date'):
                TelegramMediaJob.objects.filter(author=author, message_id=message['message_id']).update(
                    state='cancelled', payload={}, lease_token='', last_error='PhotoRemoved')
            # A pending photo must not be marked as successfully attached in album metadata.
            immediate = {**prepared, 'photo_file_id': None} if job else prepared
            post, created = TelegramChannelPostWriter(self.content).save(
                author=author, message=message, image_url=None, **immediate)
            if job:
                TelegramMediaQueue.bind(job, post)
        return post, created
