"""Bind each settings button to its channel and recheck the current owner on writes."""
from dataclasses import dataclass

from django.utils import timezone

from feeds.models import Author


class ChannelSettingUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class ChannelSettingAction:
    command: str
    author: Author | None


class TelegramChannelSettings:
    actions = {'settings', 'mode', 'delay', 'comments_notify'}
    fields = {'auto_publish', 'publish_delay_days', 'notify_comments', 'invite_url'}

    def resolve(self, data, *, chat_id, session):
        parts = data.split(':')
        if parts[0] not in self.actions:
            return None
        if len(parts) == 3:
            try:
                author_id = int(parts[2])
            except ValueError:
                raise ChannelSettingUnavailable('Некорректный канал') from None
            author = Author.objects.filter(pk=author_id, admin_chat_id=chat_id, is_blocked=False).first()
            if not author:
                raise ChannelSettingUnavailable('Нет доступа к этому каналу')
            return ChannelSettingAction(':'.join(parts[:2]), author)
        if len(parts) == 2 and parts[0] in {'mode', 'delay'} and not (session and session.selected_author_id):
            return ChannelSettingAction(data, None)  # Initial setup, before choosing a channel.
        raise ChannelSettingUnavailable('Кнопка устарела. Выберите канал заново через меню')

    def change(self, author_id, chat_id, field, value):
        if field not in self.fields:
            raise ValueError('Unsupported channel setting')
        # One conditional UPDATE: a concurrently changed owner cannot be bypassed.
        if not Author.objects.filter(pk=author_id, admin_chat_id=chat_id, is_blocked=False).update(
            **{field: value, 'updated_at': timezone.now()}
        ):
            raise ChannelSettingUnavailable('Нет доступа к этому каналу')
