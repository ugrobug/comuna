from html import escape

from django.db import transaction
from django.utils.text import slugify

from communities.models import ComunGlossaryTerm, ComunKnowledgeBaseItem
from communities.service import _comun_is_moderator
from feeds.models import Author, Post
from telegram_integration.bot import _glossary_candidate_from_text
from .models import MaxSubmission


class MaxSubmissionService:
    @staticmethod
    def create(chat, message, request_type):
        if not chat or not chat.is_active or not chat.comun_id or not chat.comun.is_active:
            raise ValueError('Сначала привяжите чат к сообществу командой /link_comun slug.')
        enabled = chat.comun.knowledge_base_enabled if request_type == 'kb' else chat.comun.glossary_enabled
        if not enabled:
            raise ValueError('Этот раздел пока выключен в сообществе.')
        linked = message.get('link') or {}
        body = linked.get('message') or {}
        text = str(body.get('text') or '').strip()
        if linked.get('type') != 'reply' or not body.get('mid') or not text:
            raise ValueError('Ответьте этой командой на текстовое сообщение, которое хотите предложить.')
        return MaxSubmission.objects.get_or_create(chat=chat, comun=chat.comun, message_id=body['mid'], request_type=request_type,
            defaults={'source_text': text[:20000]})

    @staticmethod
    @transaction.atomic
    def review(user, submission_id, approve):
        item = MaxSubmission.objects.select_for_update().select_related('comun', 'chat').get(pk=submission_id)
        if not item.comun.is_active or not _comun_is_moderator(user, item.comun):
            raise ValueError('Нужны права модератора сообщества.')
        if item.status != 'pending':
            raise ValueError('Заявка уже рассмотрена.')
        if approve:
            if item.request_type == 'glossary':
                if not item.comun.glossary_enabled:
                    raise ValueError('Глоссарий выключен.')
                term, definition = _glossary_candidate_from_text(item.source_text)
                if ComunGlossaryTerm.objects.filter(comun=item.comun, term=term).exists():
                    raise ValueError('Этот термин уже есть в глоссарии.')
                ComunGlossaryTerm.objects.create(comun=item.comun, term=term, definition=definition,
                    slug=f'{slugify(term)[:145] or "max-term"}-{item.pk}')
            else:
                if not item.comun.knowledge_base_enabled:
                    raise ValueError('База знаний выключена.')
                author, _ = Author.objects.get_or_create(username=f'max_group_{item.chat.chat_id}', defaults={
                    'title': item.chat.title, 'channel_url': item.chat.link or f'https://max.ru/{item.chat.chat_id}'})
                title = item.source_text.splitlines()[0][:255]
                post = Post.objects.create(author=author, title=title, message_id=item.pk,
                    content=f'<p>{escape(item.source_text).replace(chr(10), "<br>")}</p>',
                    raw_data={'source': 'max', 'comun_slug': item.comun.slug}, source_url=item.chat.link)
                ComunKnowledgeBaseItem.objects.create(comun=item.comun, post=post, title=title, created_by=user)
        item.status = 'approved' if approve else 'rejected'
        item.reviewed_by = user
        item.save(update_fields=['status', 'reviewed_by'])
        return item
