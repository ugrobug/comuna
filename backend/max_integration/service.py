import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from communities.service import _comun_is_moderator
from .client import MaxClient
from .models import MaxAccount, MaxChat, MaxVerificationCode


class MaxAccountService:
    @staticmethod
    def issue_code(user):
        code = 'MAX-' + secrets.token_hex(12).upper()
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=user.pk)
            MaxVerificationCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            MaxVerificationCode.objects.create(user=user, digest=hashlib.sha256(code.encode()).hexdigest(), expires_at=timezone.now()+timedelta(minutes=15))
        return code

    @staticmethod
    def redeem_code(code, max_user, dialog_id):
        digest = hashlib.sha256(code.strip().upper().encode()).hexdigest()
        with transaction.atomic():
            record = MaxVerificationCode.objects.select_for_update().select_related('user').filter(digest=digest, used_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True).first()
            if not record:
                raise ValueError('Код не найден, истёк или уже использован. Получите новый код на сайте.')
            get_user_model().objects.select_for_update().get(pk=record.user_id)
            max_id = int(max_user['user_id'])
            if MaxAccount.objects.filter(max_user_id=max_id).exclude(user=record.user).exists():
                raise ValueError('Этот аккаунт MAX уже привязан к другому профилю Тамбура.')
            existing = MaxAccount.objects.filter(user=record.user).first()
            if existing and existing.max_user_id != max_id:
                raise ValueError('К профилю уже привязан другой аккаунт MAX. Сначала отвяжите его на сайте.')
            account, _ = MaxAccount.objects.update_or_create(user=record.user, defaults={
                'max_user_id': max_id, 'dialog_id': dialog_id,
                'name': str(max_user.get('name') or max_user.get('first_name') or '')[:255], 'is_active': True,
            })
            record.used_at = timezone.now()
            record.save(update_fields=['used_at'])
            return account


class MaxChannelService:
    def __init__(self, client=None):
        self.client = client or MaxClient()

    def discover(self, chat_id):
        data = self.client.chat(chat_id)
        if data.get('type') not in ['channel', 'chat']:
            raise ValueError('Нужен канал или групповой чат MAX.')
        chat, _ = MaxChat.objects.update_or_create(chat_id=chat_id, defaults={
            'chat_type': data['type'], 'title': str(data.get('title') or '')[:255],
            'link': str(data.get('link') or '')[:500], 'is_active': data.get('status') == 'active',
        })
        return chat

    def verify_admin(self, account, chat):
        if not chat.is_active or not account.is_active or not account.user.is_active:
            raise ValueError('Подключение MAX неактивно.')
        admins = self.client.admins(chat.chat_id)
        if not any(int(admin.get('user_id', 0)) == account.max_user_id for admin in admins):
            chat.verified_users.remove(account.user)
            raise ValueError('Привязать канал или чат может только его администратор в MAX.')
        membership = self.client.request('GET', f'/chats/{chat.chat_id}/members/me')
        if not membership.get('is_admin'):
            raise ValueError('Добавьте бота администратором канала или чата MAX.')
        chat.verified_users.add(account.user)

    def link(self, account, chat, comun):
        if not comun.is_active or not account.is_active or not account.user.is_active or not _comun_is_moderator(account.user, comun):
            raise ValueError('Нужны права владельца или модератора сообщества Тамбура.')
        self.verify_admin(account, chat)
        with transaction.atomic():
            chat = MaxChat.objects.select_for_update().get(pk=chat.pk)
            if chat.comun_id and chat.comun_id != comun.pk:
                raise ValueError('Канал уже привязан к другому сообществу. Сначала отвяжите его.')
            chat.comun = comun
            chat.save(update_fields=['comun', 'updated_at'])
        return chat
