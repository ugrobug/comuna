from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils.html import strip_tags

from communities.models import Comun
from communities.service import _comun_is_moderator
from telegram_integration.bot import _inline_search_results
from .client import MaxClient, MaxAPIError
from .models import MaxAccount, MaxChat, MaxImportedMessage, MaxSubmission
from .publishing import MaxPostPublisher
from .submissions import MaxSubmissionService
from .service import MaxAccountService, MaxChannelService


def button(text, action):
    return {'type': 'callback', 'text': text, 'payload': action}


class MaxBot:
    def __init__(self, client=None):
        self.client = client or MaxClient()
        self.channels = MaxChannelService(self.client)

    def menu(self, dialog):
        self.client.send(dialog,
            'Привет! Это бот Тамбура в MAX. Сначала создайте сообщество на сайте, '
            'привяжите аккаунт MAX в настройках профиля и добавьте бота администратором существующего канала или группового чата. '
            'Затем выберите канал или чат ниже и привяжите его к сообществу. Сообщества создаются только на сайте.',
            [[{'type': 'link', 'text': 'Создать сообщество на сайте', 'url': 'https://tambur.pub/comuns?create=1'}],
             [{'type': 'link', 'text': 'Привязать аккаунт MAX', 'url': 'https://tambur.pub/settings#max'}],
             [button('Каналы и чаты', 'channels')], [button('Управление оповещениями', 'notifications')]])

    def handle(self, event):
        kind = event['update_type']
        if kind == 'bot_started':
            MaxAccount.objects.filter(max_user_id=event['user']['user_id']).update(dialog_id=event['chat_id'], is_active=True)
            self.menu(event['chat_id'])
        elif kind == 'bot_stopped':
            MaxAccount.objects.filter(max_user_id=event['user']['user_id']).update(is_active=False)
        elif kind == 'bot_added':
            chat = self.channels.discover(event['chat_id'])
            account = MaxAccount.objects.filter(max_user_id=event['user']['user_id'], is_active=True, user__is_active=True).first()
            if account:
                try:
                    self.channels.verify_admin(account, chat)
                except ValueError:
                    return
                self.client.send(account.dialog_id, f'Бот добавлен: «{chat.title}». Привяжите канал или чат к существующему сообществу.', [[button('Каналы и чаты', 'channels')]])
        elif kind == 'bot_removed':
            MaxChat.objects.filter(chat_id=event['chat_id']).update(is_active=False)
        elif kind in ['message_created', 'message_edited']:
            self.message(event['message'], edited=kind == 'message_edited')
        elif kind == 'message_callback':
            self.callback(event)

    def message(self, message, edited=False):
        recipient = message.get('recipient') or {}
        dialog = recipient.get('chat_id')
        body = message.get('body') or {}
        text = str(body.get('text') or '').strip()
        sender = message.get('sender') or {}
        kind = recipient.get('chat_type')
        if kind == 'channel':
            chat = MaxChat.objects.select_related('comun').filter(chat_id=dialog, is_active=True).first()
            if not chat:
                chat = self.channels.discover(dialog)
            post, created = MaxPostPublisher().import_message(chat, message)
            if created and post and post.is_pending:
                for account in MaxAccount.objects.filter(user__in=chat.verified_users.all(), is_active=True, user__is_active=True):
                    if _comun_is_moderator(account.user, chat.comun):
                        self.client.send(account.dialog_id, f'Новый пост из «{chat.title}»:\n{post.title}\n\nОпубликовать?', [[button('Опубликовать', f'approve:{post.pk}'), button('Отклонить', f'reject:{post.pk}')]])
            return
        if edited or sender.get('is_bot'):
            return
        if kind == 'dialog':
            if text.upper().startswith('MAX-'):
                try:
                    account = MaxAccountService.redeem_code(text, sender, dialog)
                except ValueError as exc:
                    self.client.send(dialog, str(exc))
                    return
                # Discover permissions for channels added before account verification.
                for chat in MaxChat.objects.filter(is_active=True):
                    try:
                        self.channels.verify_admin(account, chat)
                    except (ValueError, MaxAPIError):
                        continue
                self.client.send(dialog, 'Аккаунт MAX привязан к профилю Тамбура.', [[button('Каналы и чаты', 'channels')]])
                return
            account = MaxAccount.objects.filter(max_user_id=sender.get('user_id'), is_active=True, user__is_active=True).first()
            linked = message.get('link') or {}
            if linked.get('type') == 'forward' and linked.get('chat_id'):
                chat = self.channels.discover(linked['chat_id'])
                if not account:
                    self.menu(dialog)
                    return
                try:
                    self.channels.verify_admin(account, chat)
                except ValueError as exc:
                    self.client.send(dialog, str(exc))
                    return
                if not chat.comun_id:
                    self.client.send(dialog, 'Канал подтверждён. Сначала привяжите его к сообществу.', [[button('Каналы и чаты', 'channels')]])
                    return
                if chat.chat_type == 'channel':
                    post, created = MaxPostPublisher().import_message(chat, {'body': linked.get('message') or {}})
                    self.client.send(dialog, 'Пост отправлен на согласование.' if post and post.is_pending else 'Пост добавлен на сайт.' if post else 'В сообщении нет доступного текста или вложений.')
                    if post and post.is_pending:
                        self.client.send(dialog, post.title, [[button('Опубликовать', f'approve:{post.pk}'), button('Отклонить', f'reject:{post.pk}')]])
                    return
            self.menu(dialog)
        elif kind == 'chat':
            chat = MaxChat.objects.select_related('comun').filter(chat_id=dialog, is_active=True).first()
            if text.startswith('/link_comun '):
                account = MaxAccount.objects.filter(max_user_id=sender.get('user_id'), is_active=True, user__is_active=True).first()
                comun = Comun.objects.filter(slug=text.split(maxsplit=1)[1], is_active=True).first()
                if not account or not comun:
                    self.client.send(dialog, 'Сначала создайте сообщество на сайте и привяжите аккаунт MAX в настройках профиля.')
                    return
                try:
                    chat = self.channels.discover(dialog)
                    self.channels.link(account, chat, comun)
                    self.client.send(dialog, f'Чат привязан к «{comun.name}». Для поиска используйте /search запрос. Ответьте на сообщение командой /kb или /glossary, чтобы предложить его модераторам.')
                except ValueError as exc:
                    self.client.send(dialog, str(exc))
            elif text.split(' ')[0] in ['/kb', '/glossary']:
                try:
                    item, created = MaxSubmissionService.create(chat, message, text.split(' ')[0][1:])
                except ValueError as exc:
                    self.client.send(dialog, str(exc))
                    return
                self.client.send(dialog, 'Предложение отправлено модераторам.' if created else 'Это предложение уже отправлено.')
                if created:
                    from notifications.service import create_user_notification
                    users = chat.comun.moderators.filter(is_active=True) | get_user_model().objects.filter(pk=chat.comun.creator_id, is_active=True)
                    for user in users.distinct():
                        create_user_notification(user=user, event_key='system', title='Предложение из MAX',
                            message=f'Новое предложение для «{chat.comun.name}».', force_site=True,
                            link_url=f'/comuns/{chat.comun.slug}/settings?tab=max')
                        linked_account = MaxAccount.objects.filter(user=user, is_active=True).first()
                        if linked_account:
                            self.client.send(linked_account.dialog_id, item.source_text[:3000], [[button('Принять', f'submission:{item.pk}:approve'), button('Отклонить', f'submission:{item.pk}:reject')]])
            elif text.startswith('/search'):
                if not chat or not chat.comun_id or not chat.comun.is_active:
                    self.client.send(dialog, 'Сначала привяжите чат к сообществу командой /link_comun slug.')
                    return
                query = text.partition(' ')[2]
                results = _inline_search_results(chat.comun, query)[:5]
                content = '\n\n'.join(strip_tags(r['input_message_content']['message_text']) for r in results)
                self.client.send(dialog, content or 'Ничего не найдено.', [[{'type': 'link', 'text': 'Открыть сообщество', 'url': f'https://tambur.pub/comuns/{chat.comun.slug}'}]])

    def callback(self, event):
        callback = event['callback']
        user_id = callback['user']['user_id']
        action = str(callback.get('payload') or '')
        account = MaxAccount.objects.select_related('user').filter(max_user_id=user_id, is_active=True, user__is_active=True).first()
        if not account:
            self.client.answer(callback['callback_id'], 'Привяжите аккаунт MAX в настройках профиля на сайте.')
            return
        dialog = account.dialog_id
        try:
            self.action(account, action, dialog)
        except (ValueError, MaxChat.DoesNotExist, Comun.DoesNotExist, MaxImportedMessage.DoesNotExist, MaxSubmission.DoesNotExist):
            self.client.answer(callback['callback_id'], 'Действие недоступно. Проверьте привязку и права доступа.')
            return
        self.client.answer(callback['callback_id'], 'Готово')

    def action(self, account, action, dialog):
        if action == 'channels':
            chats = MaxChat.objects.filter(verified_users=account.user, is_active=True).order_by('title')[:25]
            self.client.send(dialog, 'Выберите канал или чат. Если его нет в списке, добавьте бота администратором или перешлите ему пост из канала.', [[button(chat.title or str(chat.chat_id), f'chat:{chat.pk}')] for chat in chats])
        elif action.startswith('chat:'):
            chat = MaxChat.objects.select_related('comun').get(pk=int(action.split(':')[1]), verified_users=account.user, is_active=True)
            self.channels.verify_admin(account, chat)
            rows = []
            if chat.comun_id:
                if not _comun_is_moderator(account.user, chat.comun):
                    raise ValueError()
                rows = [[button('Автопубликация', f'mode:{chat.pk}:auto'), button('Согласование', f'mode:{chat.pk}:review')],
                    [button('Без задержки', f'delay:{chat.pk}:0'), button('1 день', f'delay:{chat.pk}:1')],
                    [button('3 дня', f'delay:{chat.pk}:3'), button('7 дней', f'delay:{chat.pk}:7')]] if chat.chat_type == 'channel' else []
                self.client.send(dialog, f'«{chat.title}» → «{chat.comun.name}»\nРежим: {"автопубликация" if chat.auto_publish else "согласование"}. Задержка: {chat.publish_delay_days} дн.', rows)
            else:
                communities = Comun.objects.filter(Q(creator=account.user)|Q(moderators=account.user), is_active=True).distinct()[:25]
                rows = [[button(c.name, f'link:{chat.pk}:{c.pk}')] for c in communities]
                rows.append([{'type': 'link', 'text': 'Создать сообщество на сайте', 'url': 'https://tambur.pub/comuns?create=1'}])
                self.client.send(dialog, 'Выберите существующее сообщество:', rows)
        elif action.startswith('link:'):
            _, chat_id, comun_id = action.split(':')
            chat = MaxChat.objects.get(pk=int(chat_id), verified_users=account.user, is_active=True)
            comun = Comun.objects.get(pk=int(comun_id), is_active=True)
            self.channels.link(account, chat, comun)
            self.client.send(dialog, f'«{chat.title}» привязан к «{comun.name}».')
        elif action.startswith(('mode:', 'delay:')):
            kind, chat_id, value = action.split(':')
            chat = MaxChat.objects.select_related('comun').get(pk=int(chat_id), verified_users=account.user, is_active=True)
            if not chat.comun_id or not _comun_is_moderator(account.user, chat.comun):
                raise ValueError()
            self.channels.verify_admin(account, chat)
            if kind == 'mode' and value in ['auto', 'review']:
                chat.auto_publish = value == 'auto'
            elif kind == 'delay' and value in ['0', '1', '3', '7']:
                chat.publish_delay_days = int(value)
            else:
                raise ValueError()
            chat.save(update_fields=['auto_publish', 'publish_delay_days', 'updated_at'])
            self.client.send(dialog, 'Настройки публикации сохранены.')
        elif action.startswith(('approve:', 'reject:')):
            kind, post_id = action.split(':')
            imported = MaxImportedMessage.objects.select_related('post', 'chat__comun').get(post_id=int(post_id))
            if not imported.chat.comun_id or not _comun_is_moderator(account.user, imported.chat.comun):
                raise ValueError()
            self.channels.verify_admin(account, imported.chat)
            with transaction.atomic():
                from feeds.models import Post
                post = Post.objects.select_for_update().get(pk=imported.post_id)
                if not post.is_pending:
                    raise ValueError()
                post.is_pending = False
                if kind == 'reject':
                    post.is_blocked = True
                post.save(update_fields=['is_pending', 'is_blocked', 'updated_at'])
            self.client.send(dialog, 'Пост согласован.' if kind == 'approve' else 'Пост отклонён.')
        elif action.startswith('submission:'):
            _, item_id, decision = action.split(':')
            if decision not in ['approve', 'reject']:
                raise ValueError()
            MaxSubmissionService.review(account.user, int(item_id), decision == 'approve')
            self.client.send(dialog, 'Предложение рассмотрено.')
        elif action == 'notifications' or action.startswith('notify:'):
            from notifications.service import get_notification_event_catalog
            definitions = get_notification_event_catalog()
            if action.startswith('notify:'):
                key = action.split(':', 1)[1]
                if key not in {d['key'] for d in definitions}:
                    raise ValueError()
                selected = set(account.notification_events)
                selected.remove(key) if key in selected else selected.add(key)
                account.notification_events = sorted(selected)
                account.save(update_fields=['notification_events'])
            rows = [[button(('✓ ' if d['key'] in account.notification_events else '○ ') + d['title'], f"notify:{d['key']}")] for d in definitions]
            self.client.send(dialog, 'Выберите оповещения Тамбура, которые хотите получать в MAX:', rows)
        else:
            raise ValueError('Неизвестное действие.')
