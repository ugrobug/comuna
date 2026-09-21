from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from communities.models import Comun
from max_integration.client import MaxClient, MaxAPIError
from max_integration.models import MaxChat
from max_integration.service import MaxChannelService


class Command(BaseCommand):
    help = 'Administrative binding of an explicitly specified MAX chat to an existing community.'

    def add_arguments(self, parser):
        parser.add_argument('--chat-id', type=int, required=True)
        parser.add_argument('--community', required=True)
        parser.add_argument('--expected-link', required=True)

    def handle(self, *args, **options):
        comun = Comun.objects.filter(slug=options['community'], is_active=True).first()
        if not comun:
            raise CommandError('Active community not found')
        client = MaxClient()
        try:
            data = client.chat(options['chat_id'])
            if data.get('link') != options['expected_link'] or data.get('status') != 'active':
                raise CommandError('Chat identity or active status does not match')
            if not client.request('GET', f'/chats/{options["chat_id"]}/members/me').get('is_admin'):
                raise CommandError('Bot must be an administrator')
            with transaction.atomic():
                chat = MaxChannelService(client).discover(options['chat_id'])
                chat = MaxChat.objects.select_for_update().get(pk=chat.pk)
                if chat.comun_id and chat.comun_id != comun.pk:
                    raise CommandError('Chat already belongs to another community')
                chat.comun = comun
                chat.save(update_fields=['comun', 'updated_at'])
        except MaxAPIError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f'Linked {chat.chat_type} "{chat.title}" to "{comun.name}"')
