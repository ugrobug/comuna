"""Keep unsigned widget fields out of account identity and account merging."""
import json
from urllib.parse import unquote


class TelegramLoginPayload:
    identity_fields = {'id', 'first_name', 'last_name', 'username', 'photo_url', 'auth_date'}
    context_fields = {'auth_intent', 'intent', 'mode', 'privacy_accepted',
                      'registration_source', 'registration_path'}

    @classmethod
    def signed_widget(cls, payload):
        return {key: value for key, value in payload.items()
                if key in cls.identity_fields or key in cls.context_fields}


class TelegramLoginRedirect:
    def __init__(self, next_url):
        target = str(next_url or '/')
        decoded = unquote(target)
        self.target = target if (decoded.startswith('/') and not decoded.startswith('//')
            and '\\' not in decoded and not any(ord(char) < 32 for char in decoded)) else '/'

    def html(self):
        literal = json.dumps(self.target).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        return ('<!doctype html><html><head><meta charset="utf-8">'
                '<title>Telegram login</title></head><body><script>'
                f'window.location.replace({literal});</script></body></html>')
