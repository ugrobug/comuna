import hashlib
from datetime import timedelta
from html import escape
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone
from feeds.language_detection import detect_post_language
from feeds.models import Author, Post
from .models import MaxChat, MaxImportedMessage


def public_url(value):
    value = str(value or '')
    parsed = urlparse(value)
    return value if parsed.scheme == 'https' and parsed.hostname else ''


class MaxPostPublisher:
    def import_message(self, chat, message, *, force=False):
        body = message.get('body') or {}
        mid = str(body.get('mid') or '')
        if not mid or not chat.is_active or not chat.comun_id or not chat.comun.is_active:
            return None, False
        text = str(body.get('text') or '')
        parts = [f'<p>{escape(text).replace(chr(10), "<br>")}</p>'] if text else []
        for attachment in body.get('attachments') or []:
            payload = attachment.get('payload') or {}
            url = public_url(payload.get('url'))
            if not url:
                continue
            if attachment.get('type') == 'image':
                parts.append(f'<img src="{escape(url, quote=True)}" alt="">')
            else:
                label = str(attachment.get('filename') or attachment.get('type') or 'Вложение')
                parts.append(f'<p><a href="{escape(url, quote=True)}" rel="nofollow noopener">{escape(label)}</a></p>')
        source = public_url(message.get('url')) or public_url(chat.link)
        if any(not public_url((a.get('payload') or {}).get('url')) for a in body.get('attachments') or []) and source:
            parts.append(f'<p><a href="{escape(source, quote=True)}" rel="nofollow noopener">Открыть вложения в MAX</a></p>')
        if not parts:
            return None, False
        content = ''.join(parts)
        title = (text.splitlines()[0] if text else 'Публикация из MAX')[:255]
        with transaction.atomic():
            chat = MaxChat.objects.select_for_update(of=('self',)).select_related('comun').get(pk=chat.pk)
            if not chat.comun_id or not chat.is_active or not chat.comun.is_active:
                return None, False
            if not chat.author_id:
                author = Author.objects.create(username=f'max_channel_{chat.chat_id}', title=chat.title,
                    channel_url=public_url(chat.link) or f'https://max.ru/{chat.chat_id}')
                chat.author = author
                chat.save(update_fields=['author', 'updated_at'])
            imported = MaxImportedMessage.objects.select_related('post').filter(chat=chat, message_id=mid).first()
            source_url = public_url(message.get('url')) or public_url(chat.link)
            raw = {'source': 'max', 'comun_slug': chat.comun.slug, 'max_chat_id': str(chat.chat_id), 'max_message_id': mid}
            if imported:
                post = imported.post
                post.title = title
                post.content = content
                post.original_language = detect_post_language(title, content)
                post.source_url = source_url
                post.save(update_fields=['title', 'content', 'original_language', 'source_url', 'updated_at'])
                return post, False
            post = Post.objects.create(author=chat.author, title=title, content=content,
                message_id=int.from_bytes(hashlib.sha256(mid.encode()).digest()[:8], 'big') & ((1 << 63) - 1),
                original_language=detect_post_language(title, content), source_url=source_url,
                channel_url=public_url(chat.link), raw_data=raw, is_pending=not (chat.auto_publish or force),
                publish_at=timezone.now()+timedelta(days=chat.publish_delay_days) if chat.publish_delay_days else None)
            MaxImportedMessage.objects.create(chat=chat, message_id=mid, post=post)
            return post, True
