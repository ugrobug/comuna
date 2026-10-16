"""Application workflow for import; handlers supply integration adapters explicitly."""
from telegram_integration.channel_identity import TelegramChannelIdentity
from telegram_integration.channel_posts import TelegramChannelPostWriter, TelegramMediaDownloadError
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
        image_url = self.content._extract_photo_url(message, self.token) if self.token else None
        embed_html, embed_label = self.content._extract_telegram_embed(message, chat['username'], self.token)
        poll_html, poll_label = self.content._extract_telegram_poll(message)
        if photo_file_id and not image_url:
            raise TelegramMediaDownloadError('Telegram photo download failed; update must be retried')
        post, created = TelegramChannelPostWriter(self.content).save(
            author=author, message=message, raw_text=raw_text,
            formatted_text=self.content._format_telegram_text(raw_text, self.content._extract_entities(message)),
            explicit_tags=self.content._extract_hashtags(raw_text), photo_file_id=photo_file_id,
            image_url=image_url, embed_html=embed_html, embed_label=embed_label,
            poll_html=poll_html, poll_label=poll_label, force_publish=force_publish,
        )
        if post is None:
            return None
        author = post.author
        if post.is_pending:
            self.prompt.deliver(post, author)
        elif created:
            self.content._maybe_notify_new_author(author, post)
        return post
