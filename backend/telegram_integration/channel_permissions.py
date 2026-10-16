"""Authorization of a human is independent from the bot's channel membership."""
from telegram_integration.channel_access import TelegramChannelAccessVerifier


class TelegramChannelPermissions:
    def __init__(self, token, *, verifier_factory=TelegramChannelAccessVerifier):
        self.token = token
        self.verifier_factory = verifier_factory

    def can_forward(self, chat_id, actor_id):
        if not self.token or not chat_id or not actor_id:
            return False
        return self.verifier_factory(self.token, lambda: actor_id).is_admin(chat_id)

    @staticmethod
    def owns_selected(session, chat_id):
        author = session.selected_author if session else None
        return bool(author and not author.is_blocked and author.admin_chat_id == chat_id)

    @staticmethod
    def private_actor(callback):
        message = callback.get('message') or {}
        chat = message.get('chat') or {}
        actor_id = (callback.get('from') or {}).get('id')
        return bool(actor_id and actor_id == chat.get('id') and chat.get('type') == 'private')
