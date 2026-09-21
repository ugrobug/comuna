import json
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

from django.conf import settings


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class MaxAPIError(Exception):
    def __init__(self, status=None):
        self.status = status
        super().__init__(f"MAX API request failed (status={status or 'connection'})")


class MaxClient:
    """MAX transport; the additional CA is trusted only by this client."""

    base_url = "https://platform-api2.max.ru"

    def __init__(self, token=None):
        self.token = token if token is not None else getattr(settings, "MAX_BOT_TOKEN", "")
        self.context = ssl.create_default_context()
        self.context.load_verify_locations(Path(__file__).parent / "certs" / "russian_trusted_root_ca.crt")

    def request(self, method, path, *, query=None, data=None):
        if not self.token:
            raise MaxAPIError("not_configured")
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query)
        request = Request(url, method=method, headers={
            "Authorization": self.token, "Content-Type": "application/json",
        }, data=json.dumps(data, ensure_ascii=False).encode() if data is not None else None)
        try:
            with build_opener(HTTPSHandler(context=self.context), NoRedirect()).open(request, timeout=20) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise MaxAPIError(exc.code) from None
        except (URLError, TimeoutError, ValueError):
            raise MaxAPIError() from None
        if result.get("success") is False:
            raise MaxAPIError("rejected")
        return result

    def me(self):
        return self.request("GET", "/me")

    def chat(self, chat_id):
        return self.request("GET", f"/chats/{int(chat_id)}")

    def admins(self, chat_id):
        return self.request("GET", f"/chats/{int(chat_id)}/members/admins").get("members", [])

    def send(self, chat_id, text, buttons=None):
        body = {"text": text[:4000]}
        if buttons:
            body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
        return self.request("POST", "/messages", query={"chat_id": int(chat_id)}, data=body)

    def answer(self, callback_id, text):
        return self.request("POST", "/answers", query={"callback_id": callback_id}, data={"notification": text[:200]})

    def subscribe(self, url, secret):
        return self.request("POST", "/subscriptions", data={
            "url": url, "secret": secret,
            "update_types": ["bot_started", "bot_stopped", "bot_added", "bot_removed", "message_created", "message_edited", "message_callback"],
        })
