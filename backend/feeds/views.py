from __future__ import annotations

import json
import os
import re
import secrets
from django.core.files.base import ContentFile
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import timedelta
from html import escape
from xml.sax.saxutils import escape as xml_escape
from django.db import transaction
from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, get_user_model

from .models import (
    Author,
    AuthorAdmin,
    AuthorVerificationCode,
    BotSession,
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    Rubric,
)
from .telegram_media import download_telegram_file_by_path

User = get_user_model()

_BOT_ID: int | None = None
_TOKEN_SIGNER = TimestampSigner(salt="comuna-auth")
_TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def _issue_token(user: User) -> str:
    return _TOKEN_SIGNER.sign(str(user.id))


def _get_user_from_token(token: str) -> User | None:
    try:
        unsigned = _TOKEN_SIGNER.unsign(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return User.objects.get(id=int(unsigned))
    except (User.DoesNotExist, ValueError, TypeError):
        return None


def _get_user_from_request(request: HttpRequest) -> User | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    elif auth.lower().startswith("token "):
        token = auth.split(" ", 1)[1].strip()
    else:
        token = ""
    if not token:
        return None
    return _get_user_from_token(token)


def _serialize_user(user: User) -> dict:
    author_links = (
        AuthorAdmin.objects.select_related("author")
        .filter(user=user, verified_at__isnull=False)
        .order_by("author__username")
    )
    authors = [
        {
            "username": link.author.username,
            "title": link.author.title,
            "channel_url": link.author.invite_url or link.author.channel_url,
        }
        for link in author_links
    ]
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_author": bool(authors),
        "authors": authors,
    }


def _generate_verification_code() -> str:
    token = secrets.token_urlsafe(6).replace("_", "").replace("-", "").upper()
    return f"COMUNA-{token}"


def _maybe_notify_new_author(author: Author, post: Post) -> None:
    if author.first_post_notified:
        return
    if post.is_pending or post.is_blocked:
        return
    already_published = (
        Post.objects.filter(author=author, is_pending=False, is_blocked=False)
        .exclude(id=post.id)
        .exists()
    )
    if already_published:
        author.first_post_notified = True
        author.save(update_fields=["first_post_notified", "updated_at"])
        return

    admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID
    if not admin_chat:
        return

    site_base = settings.SITE_BASE_URL.rstrip("/")
    author_url = f"{site_base}/{author.username}"
    post_url = f"{site_base}/b/post/{post.id}"
    rubric = author.rubric.name if author.rubric else "—"
    _send_bot_message(
        int(admin_chat),
        "Новый автор опубликовал первый пост.\n"
        f"Канал: @{author.username}\n"
        f"Рубрика: {rubric}\n"
        f"Автор: {author_url}\n"
        f"Пост: {post_url}",
    )
    author.first_post_notified = True
    author.save(update_fields=["first_post_notified", "updated_at"])


def _media_url(request: HttpRequest, field) -> str | None:
    if not field:
        return None
    site_base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if site_base:
        try:
            return f"{site_base}{field.url}"
        except Exception:
            pass
    try:
        return request.build_absolute_uri(field.url)
    except Exception:
        return None


def _author_avatar_url(request: HttpRequest, author: Author) -> str | None:
    return _media_url(request, author.avatar_image) or author.avatar_url


def _format_lastmod(value) -> str | None:
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.utc)
    return value.astimezone(timezone.utc).date().isoformat()


def _build_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().splitlines()[0].strip()
    for separator in (".", "!", "?"):
        idx = first_line.find(separator)
        if idx > 0:
            return first_line[:idx].strip()
    if len(first_line) <= 120:
        return first_line
    return first_line[:117].strip() + "..."


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


def _slugify_title(text: str) -> str:
    if not text:
        return ""
    translit_map = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ъ": "",
        "ь": "",
    }
    lowered = text.lower()
    translit = "".join(translit_map.get(ch, ch) for ch in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    return slug


def _extract_plain_text(message: dict) -> str:
    return (message.get("text") or message.get("caption") or "").strip()


def _extract_entities(message: dict) -> list[dict]:
    if message.get("text"):
        return message.get("entities") or []
    if message.get("caption"):
        return message.get("caption_entities") or []
    return []


def _utf16_offset_to_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    units = 0
    for index, ch in enumerate(text):
        codepoint = ord(ch)
        units += 2 if codepoint > 0xFFFF else 1
        if units > offset:
            return index + 1
        if units == offset:
            return index + 1
    return len(text)


def _entity_tags(entity: dict, segment: str) -> tuple[str, str] | None:
    entity_type = entity.get("type")
    if entity_type == "bold":
        return "<b>", "</b>"
    if entity_type == "italic":
        return "<i>", "</i>"
    if entity_type == "underline":
        return "<u>", "</u>"
    if entity_type == "strikethrough":
        return "<s>", "</s>"
    if entity_type == "spoiler":
        return '<span class="tg-spoiler">', "</span>"
    if entity_type == "code":
        return "<code>", "</code>"
    if entity_type == "pre":
        language = entity.get("language")
        class_attr = f' class="language-{escape(language)}"' if language else ""
        return f"<pre><code{class_attr}>", "</code></pre>"
    if entity_type == "blockquote":
        return "<blockquote>", "</blockquote>"
    if entity_type == "text_link":
        url = entity.get("url") or ""
        return f'<a href="{escape(url)}" target="_blank" rel="noopener">', "</a>"
    if entity_type == "url":
        href = segment.strip()
        return f'<a href="{escape(href)}" target="_blank" rel="noopener">', "</a>"
    if entity_type == "mention":
        username = segment.lstrip("@")
        return f'<a href="https://t.me/{escape(username)}" target="_blank" rel="noopener">', "</a>"
    return None


def _format_telegram_text(text: str, entities: list[dict]) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n")
    if not entities:
        return escape(normalized).replace("\n", "<br>")

    start_tags: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    end_tags: dict[int, list[tuple[int, str]]] = defaultdict(list)

    for entity in entities:
        offset = entity.get("offset")
        length = entity.get("length")
        if offset is None or length is None:
            continue
        start = _utf16_offset_to_index(normalized, offset)
        end = _utf16_offset_to_index(normalized, offset + length)
        if start >= end:
            continue
        segment = normalized[start:end]
        tags = _entity_tags(entity, segment)
        if not tags:
            continue
        open_tag, close_tag = tags
        start_tags[start].append((end, open_tag, close_tag))
        end_tags[end].append((start, close_tag))

    for index in start_tags:
        start_tags[index].sort(key=lambda item: item[0], reverse=True)
    for index in end_tags:
        end_tags[index].sort(key=lambda item: item[0], reverse=True)

    out: list[str] = []
    text_len = len(normalized)
    for index, ch in enumerate(normalized):
        if index in start_tags:
            for _, open_tag, _ in start_tags[index]:
                out.append(open_tag)
        out.append(escape(ch))
        if index + 1 in end_tags:
            for _, close_tag in end_tags[index + 1]:
                out.append(close_tag)

    return "".join(out).replace("\n", "<br>")


def _extract_photo_file_id(message: dict) -> str | None:
    photos = message.get("photo") or []
    if not photos:
        return None
    largest = max(
        photos,
        key=lambda item: (item.get("file_size", 0), item.get("width", 0) * item.get("height", 0)),
    )
    return largest.get("file_id")


def _extract_photo_url(message: dict, token: str) -> str | None:
    file_id = _extract_photo_file_id(message)
    if not file_id:
        return None
    file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
    if not file_info or not file_info.get("ok") or not file_info.get("result"):
        return None
    file_path = file_info["result"].get("file_path")
    if not file_path:
        return None
    return download_telegram_file_by_path(file_path, token)


def _build_content_with_images(
    text_html: str,
    image_urls: list[str],
    embed_html: str = "",
) -> str:
    parts: list[str] = []
    if image_urls:
        if len(image_urls) == 1:
            media_html = f'<img src="{image_urls[0]}" alt="" />'
        else:
            gallery_imgs = "".join(f'<img src="{url}" alt="" />' for url in image_urls)
            media_html = f'<div class="post-gallery">{gallery_imgs}</div>'
        parts.append(media_html)
    if embed_html:
        parts.append(embed_html)
    if text_html:
        parts.append(text_html)
    return "<br><br>".join([part for part in parts if part])


def _build_telegram_embed_html(username: str, message_id: int, height: int) -> str:
    src = f"https://t.me/{username}/{message_id}?embed=1&single=1"
    return (
        '<div class="post-embed">'
        f'<iframe class="telegram-embed" src="{src}" '
        f'width="100%" height="{height}" frameborder="0" '
        'allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" '
        'allowfullscreen loading="lazy" referrerpolicy="no-referrer"></iframe>'
        "</div>"
    )


def _extract_telegram_embed(message: dict, username: str) -> tuple[str, str]:
    message_id = message.get("message_id")
    if not message_id or not username:
        return "", ""

    document = message.get("document") or {}
    mime_type = (document.get("mime_type") or "").lower()
    has_video = any(
        message.get(key) for key in ("video", "video_note", "animation")
    ) or mime_type.startswith("video/")
    has_audio = any(message.get(key) for key in ("audio", "voice")) or mime_type.startswith(
        "audio/"
    )

    if has_video:
        return _build_telegram_embed_html(username, message_id, 420), "Видео"
    if has_audio:
        return _build_telegram_embed_html(username, message_id, 200), "Аудио"
    return "", ""


def _fetch_telegram_json(method: str, token: str, payload: dict) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        timeout = 30 if method == "getUpdates" else 5
        with urllib.request.urlopen(url, data=data, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _get_bot_id(token: str) -> int | None:
    global _BOT_ID
    if _BOT_ID:
        return _BOT_ID
    response = _fetch_telegram_json("getMe", token, {})
    if response and response.get("ok") and response.get("result"):
        bot_id = response["result"].get("id")
        if isinstance(bot_id, int):
            _BOT_ID = bot_id
            return bot_id
    return None


def _is_bot_admin(chat_id: int, token: str) -> bool:
    bot_id = _get_bot_id(token)
    if not bot_id:
        return False
    response = _fetch_telegram_json(
        "getChatMember", token, {"chat_id": chat_id, "user_id": bot_id}
    )
    if not response or not response.get("ok") or not response.get("result"):
        return False
    status = response["result"].get("status")
    return status in {"administrator", "creator"}


def _send_bot_message(chat_id: int, text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    _fetch_telegram_json("sendMessage", token, {"chat_id": chat_id, "text": text})


def _send_bot_message_with_keyboard(chat_id: int, text: str, keyboard: dict) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    payload = {"chat_id": chat_id, "text": text, "reply_markup": json.dumps(keyboard)}
    _fetch_telegram_json("sendMessage", token, payload)


def _answer_callback_query(callback_query_id: str, text: str = "") -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    _fetch_telegram_json("answerCallbackQuery", token, payload)


def _refresh_author_from_telegram(author: Author, chat_ref, token: str) -> None:
    chat = _fetch_telegram_json("getChat", token, {"chat_id": chat_ref})
    if not chat or not chat.get("ok") or not chat.get("result"):
        return

    result = chat["result"]
    if result.get("type") != "channel":
        return

    channel_id = result.get("id")
    if channel_id:
        author.channel_id = channel_id

    if result.get("title"):
        author.title = result["title"]
    if result.get("description"):
        author.description = result["description"]
    if result.get("username"):
        author.channel_url = f"https://t.me/{result['username']}"

    photo = result.get("photo")
    if photo and photo.get("big_file_id"):
        file_id = photo["big_file_id"]
        file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
        if file_info and file_info.get("ok") and file_info.get("result"):
            file_path = file_info["result"].get("file_path")
            if file_path:
                author.avatar_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                if file_id != author.avatar_file_id:
                    try:
                        with urllib.request.urlopen(author.avatar_url, timeout=10) as response:
                            data = response.read()
                        filename = os.path.basename(file_path) or f"{author.username}.jpg"
                        author.avatar_image.save(filename, ContentFile(data), save=False)
                        author.avatar_file_id = file_id
                    except Exception:
                        pass

    if channel_id:
        count = _fetch_telegram_json("getChatMemberCount", token, {"chat_id": channel_id})
        if count and count.get("ok") and isinstance(count.get("result"), int):
            author.subscribers_count = count["result"]

    author.save(
        update_fields=[
            "title",
            "description",
            "channel_id",
            "channel_url",
            "avatar_url",
            "avatar_image",
            "avatar_file_id",
            "subscribers_count",
            "updated_at",
        ]
    )


def _build_rubric_keyboard() -> list[list[dict]]:
    rubrics = list(Rubric.objects.filter(is_active=True).order_by("sort_order", "name"))
    keyboard: list[list[dict]] = []
    row: list[dict] = []
    for rubric in rubrics:
        row.append({"text": rubric.name, "callback_data": f"rubric:{rubric.id}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard


def _send_setup_options(chat_id: int) -> None:
    BotSession.objects.update_or_create(
        telegram_user_id=chat_id, defaults={"instructions_sent": False}
    )
    _send_bot_message_with_keyboard(
        chat_id,
        "Будем публиковать все новые посты на сайте или ты хочешь каждый новый пост "
        "согласовывать в этом боте (удобно, если много постов картинок, видео, "
        "голосований, не подходящих для внешнего ресурса)",
        {
            "inline_keyboard": [
                [{"text": "Автопубликация", "callback_data": "mode:auto"}],
                [{"text": "Согласование", "callback_data": "mode:approval"}],
            ]
        },
    )
    rubric_keyboard = _build_rubric_keyboard()
    if rubric_keyboard:
        _send_bot_message_with_keyboard(
            chat_id,
            "Выберите тематику канала",
            {"inline_keyboard": rubric_keyboard},
        )


def _send_setup_instructions(chat_id: int, auto_publish: bool) -> None:
    publish_line = (
        "Новые посты будут публиковаться автоматически."
        if auto_publish
        else "Новые посты будут отправляться на согласование в боте."
    )
    _send_bot_message(
        chat_id,
        "Отлично! Теперь:\n"
        "1) Добавьте бота в админы канала.\n"
        "2) Дайте права: «Читать сообщения» и «Публиковать сообщения».\n"
        "3) По желанию добавьте ссылку приглашения на канал.\n"
        "4) Для старых постов — пересылайте их сюда, и они появятся на сайте.\n"
        f"{publish_line}",
    )


def _maybe_send_setup_instructions(chat_id: int) -> None:
    session = BotSession.objects.filter(telegram_user_id=chat_id).first()
    if not session or session.instructions_sent:
        return
    if session.mode_selected and session.rubric:
        _send_setup_instructions(chat_id, session.auto_publish)
        session.instructions_sent = True
        session.save(update_fields=["instructions_sent", "updated_at"])


def _handle_channel_post(message: dict, force_publish: bool = False) -> None:
    chat = message.get("chat", {})
    username = chat.get("username")
    if not username:
        return

    author, _ = Author.objects.get_or_create(
        username=username,
        defaults={
            "title": chat.get("title", ""),
            "channel_url": f"https://t.me/{username}",
            "channel_id": chat.get("id"),
        },
    )

    if author.is_blocked:
        return

    message_id = message.get("message_id")
    if message_id is None:
        return
    media_group_id = message.get("media_group_id") or ""

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = chat.get("id")
    if token and chat_id:
        if not _is_bot_admin(chat_id, token):
            return
        _refresh_author_from_telegram(author, chat_id, token)

    if not author.rubric:
        if author.admin_chat_id and token:
            _send_bot_message(
                author.admin_chat_id,
                "Перед первой публикацией необходимо выбрать тематику канала.",
            )
        return

    raw_text = _extract_plain_text(message)
    formatted_text = _format_telegram_text(raw_text, _extract_entities(message))
    photo_file_id = _extract_photo_file_id(message)
    image_url = _extract_photo_url(message, token) if token else None
    gallery_urls = [image_url] if image_url else []
    embed_html, embed_label = _extract_telegram_embed(message, username)
    if media_group_id:
        with transaction.atomic():
            Author.objects.select_for_update().filter(pk=author.pk)
            existing_group_post = (
                Post.objects.select_for_update()
                .filter(author=author, media_group_id=media_group_id)
                .first()
            )
            if not existing_group_post:
                existing_by_message = (
                    Post.objects.select_for_update()
                    .filter(author=author, message_id=message_id)
                    .first()
                )
                if existing_by_message and not existing_by_message.media_group_id:
                    existing_group_post = existing_by_message
                    existing_group_post.media_group_id = media_group_id

            if existing_group_post:
                raw_data = existing_group_post.raw_data or {}
                existing_urls = list(raw_data.get("gallery_urls") or [])
                if image_url and image_url not in existing_urls:
                    existing_urls.append(image_url)
                raw_data["gallery_urls"] = existing_urls
                if photo_file_id:
                    existing_file_ids = list(raw_data.get("gallery_file_ids") or [])
                    if photo_file_id not in existing_file_ids:
                        existing_file_ids.append(photo_file_id)
                    raw_data["gallery_file_ids"] = existing_file_ids
                raw_data["media_group_id"] = media_group_id
                if not raw_data.get("formatted_text") and formatted_text:
                    raw_data["formatted_text"] = formatted_text
                if embed_html and not raw_data.get("embed_html"):
                    raw_data["embed_html"] = embed_html
                base_text = raw_data.get("formatted_text") or formatted_text
                content = _build_content_with_images(
                    base_text,
                    existing_urls,
                    raw_data.get("embed_html") or embed_html,
                )
                existing_group_post.content = content
                existing_group_post.raw_data = raw_data
                existing_group_post.channel_url = f"https://t.me/{username}"
                existing_group_post.source_url = (
                    f"{existing_group_post.channel_url}/{existing_group_post.message_id}"
                )
                existing_group_post.save(
                    update_fields=[
                        "content",
                        "raw_data",
                        "channel_url",
                        "source_url",
                        "media_group_id",
                        "updated_at",
                    ]
                )
                return

    content = _build_content_with_images(formatted_text, gallery_urls, embed_html)
    title = _build_title(raw_text)
    if not title and image_url:
        title = "Фото"
    if not title and embed_label:
        title = embed_label
    channel_url = f"https://t.me/{username}"
    source_url = f"{channel_url}/{message_id}"

    requires_approval = (not author.auto_publish and author.admin_chat_id) and not force_publish

    raw_data = dict(message)
    if photo_file_id:
        raw_data["photo_file_id"] = photo_file_id
    if media_group_id:
        raw_data["media_group_id"] = media_group_id
    if media_group_id and gallery_urls:
        raw_data["gallery_urls"] = gallery_urls
        raw_data["formatted_text"] = formatted_text
    if media_group_id and photo_file_id:
        raw_data["gallery_file_ids"] = [photo_file_id]
    if embed_html:
        raw_data["embed_html"] = embed_html
    post, created = Post.objects.get_or_create(
        author=author,
        message_id=message_id,
        defaults={
            "title": title,
            "content": content,
            "source_url": source_url,
            "channel_url": channel_url,
            "raw_data": raw_data,
            "is_pending": requires_approval,
            "rubric": author.rubric,
            "media_group_id": media_group_id,
        },
    )

    if not created:
        post.title = title
        post.content = content
        post.source_url = source_url
        post.channel_url = channel_url
        post.raw_data = raw_data
        if media_group_id and not post.media_group_id:
            post.media_group_id = media_group_id
        post.save(
            update_fields=[
                "title",
                "content",
                "source_url",
                "channel_url",
                "raw_data",
                "media_group_id",
                "updated_at",
            ]
        )
    elif requires_approval:
        _send_bot_message_with_keyboard(
            author.admin_chat_id,
            f"Новый пост из канала @{author.username}:\n{title}\n\nОпубликуем?",
            {
                "inline_keyboard": [
                    [
                        {"text": "Публикуем", "callback_data": f"approve:{post.id}"},
                        {"text": "Этот пропустим", "callback_data": f"reject:{post.id}"},
                    ]
                ]
            },
        )
    elif created and not requires_approval:
        _maybe_notify_new_author(author, post)


def _handle_verification_code(chat_id: int, code: str) -> None:
    record = (
        AuthorVerificationCode.objects.select_related("user")
        .filter(code__iexact=code, used_at__isnull=True)
        .first()
    )
    if not record:
        _send_bot_message(chat_id, "Код не найден или уже использован.")
        return

    authors = Author.objects.filter(admin_chat_id=chat_id, is_blocked=False).order_by("-updated_at")
    if not authors:
        _send_bot_message(
            chat_id,
            "Сначала подключите канал в боте, затем отправьте код повторно.",
        )
        return

    now = timezone.now()
    linked = []
    for author in authors:
        link, _ = AuthorAdmin.objects.get_or_create(user=record.user, author=author)
        link.telegram_user_id = chat_id
        link.verified_at = now
        link.save(update_fields=["telegram_user_id", "verified_at"])
        linked.append(f"@{author.username}")

    record.used_at = now
    record.save(update_fields=["used_at"])

    _send_bot_message(chat_id, "Канал подтверждён: " + ", ".join(linked))


def _handle_private_message(message: dict) -> None:
    chat = message.get("chat", {})
    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")
    if not chat_id:
        return

    text = (message.get("text") or "").strip()
    if text == "/start":
        _send_bot_message_with_keyboard(
            chat_id,
            "Привет! Это бот Comuna.ru он публикует твои посты на сайте, они "
            "собирают аудиторию из поисковых систем и ведут ее к тебе в канал. "
            "Чтобы запустить бота добавь его администратором к себе в канал и "
            "выбери тематику канала и настройки публикации ниже",
            {"keyboard": [["Помощь", "Настройка"], ["Ссылка для подписки"]], "resize_keyboard": True},
        )
        _send_setup_options(chat_id)
        return

    if text in {"/help", "Помощь"}:
        _send_bot_message(
            chat_id,
            "Как подключить канал:\n"
            "1) Выберите рубрику и режим публикации в настройке.\n"
            "2) Добавьте бота админом в канал.\n"
            "3) Дайте права: «Читать сообщения» и «Публиковать сообщения».\n"
            "4) По желанию добавьте ссылку приглашения на канал.\n"
            "5) Для старых постов — пересылайте их сюда.\n"
            "Сайт: https://comuna.ru/authors",
        )
        return

    if text.upper().startswith("COMUNA-"):
        _handle_verification_code(chat_id, text.strip())
        return

    if text == "Настройка":
        _send_setup_options(chat_id)
        return

    if text == "Ссылка для подписки":
        _send_bot_message(
            chat_id,
            "Пришлите ссылку приглашения на ваш канал (например, https://t.me/+xxxx). "
            "Мы будем использовать её в кнопках подписки на сайте.",
        )
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id,
            defaults={"invite_waiting": True},
        )
        return

    if text.startswith("https://t.me/") or text.startswith("http://t.me/"):
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if session and session.invite_waiting:
            invite_url = text.strip()
            session.invite_url = invite_url
            session.invite_waiting = False
            session.save(update_fields=["invite_url", "invite_waiting", "updated_at"])
            Author.objects.filter(admin_chat_id=chat_id).update(invite_url=invite_url)
            _send_bot_message(
                chat_id,
                "Ссылка сохранена. Мы будем использовать её для кнопок подписки.",
            )
            return


    forward_chat = message.get("forward_from_chat")
    forward_message_id = message.get("forward_from_message_id")
    if forward_chat and forward_chat.get("type") == "channel" and forward_message_id:
        if not forward_chat.get("username"):
            _send_bot_message(
                chat_id,
                "У канала нет публичного username. Сделайте канал публичным и повторите пересылку.",
            )
            return

        token = settings.TELEGRAM_BOT_TOKEN
        channel_id = forward_chat.get("id")
        if token and channel_id and not _is_bot_admin(channel_id, token):
            _send_bot_message(
                chat_id,
                "Бот не является админом этого канала. Добавьте бота в админы и "
                "дайте права на чтение/публикацию, затем повторите пересылку.",
            )
            return

        forwarded = {
            "chat": forward_chat,
            "message_id": forward_message_id,
            "text": message.get("text"),
            "caption": message.get("caption"),
            "photo": message.get("photo"),
            "video": message.get("video"),
            "video_note": message.get("video_note"),
            "audio": message.get("audio"),
            "voice": message.get("voice"),
            "animation": message.get("animation"),
            "document": message.get("document"),
            "entities": message.get("entities"),
            "caption_entities": message.get("caption_entities"),
            "media_group_id": message.get("media_group_id"),
        }

        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        author = Author.objects.filter(username__iexact=forward_chat.get("username")).first()

        if session and not session.rubric:
            _send_bot_message(
                chat_id,
                "Перед первой публикацией необходимо выбрать тематику канала.",
            )
            return

        if not author and session and session.rubric:
            author, _ = Author.objects.get_or_create(
                username=forward_chat.get("username"),
                defaults={
                    "title": forward_chat.get("title", ""),
                    "channel_url": f"https://t.me/{forward_chat.get('username')}",
                    "channel_id": forward_chat.get("id"),
                },
            )

        if author and not author.rubric and not (session and session.rubric):
            _send_bot_message(
                chat_id,
                "Перед первой публикацией необходимо выбрать тематику канала.",
            )
            return

        if session and author:
            author.auto_publish = session.auto_publish
            author.admin_chat_id = chat_id
            if session.rubric:
                author.rubric = session.rubric
            if session.invite_url:
                author.invite_url = session.invite_url
            author.save(
                update_fields=["auto_publish", "admin_chat_id", "rubric", "invite_url", "updated_at"]
            )
            if author.rubric:
                Post.objects.filter(author=author).update(rubric=author.rubric)
            session.delete()

        existing_post = Post.objects.filter(
            author__username__iexact=forward_chat.get("username"),
            message_id=forward_message_id,
        ).first()
        if existing_post:
            BotSession.objects.update_or_create(
                telegram_user_id=chat_id,
                defaults={
                    "pending_update_post_id": existing_post.id,
                    "pending_update_message": forwarded,
                },
            )
            _send_bot_message_with_keyboard(
                chat_id,
                "Этот пост уже был опубликован, вы хотите его обновить?",
                {
                    "inline_keyboard": [
                        [
                            {"text": "Да", "callback_data": f"update:{existing_post.id}"},
                            {"text": "Нет", "callback_data": f"skip_update:{existing_post.id}"},
                        ]
                    ]
                },
            )
            return

        _handle_channel_post(forwarded)
        if author and session:
            _send_bot_message(chat_id, f"Настройки применены для @{author.username}.")
        else:
            _send_bot_message(chat_id, "Пост добавлен на сайт.")
        return

    _send_bot_message(
        chat_id,
        "Перешлите пост из канала, чтобы добавить его на сайт. Для помощи — /help.",
    )


def _handle_my_chat_member(update: dict) -> None:
    chat = update.get("chat", {})
    if chat.get("type") != "channel":
        return

    new_member = update.get("new_chat_member", {})
    status = new_member.get("status")
    if status not in {"administrator", "member"}:
        return

    actor = update.get("from", {})
    admin_chat_id = actor.get("id")
    if not admin_chat_id:
        return

    username = chat.get("username")
    if not username:
        _send_bot_message(
            admin_chat_id,
            "У канала нет публичного username. Сделайте канал публичным и повторите.",
        )
        return

    author = Author.objects.filter(username__iexact=username).first()
    if not author:
        author = Author.objects.create(
            username=username,
            title=chat.get("title", ""),
            channel_id=chat.get("id"),
            channel_url=f"https://t.me/{username}",
        )

    session = BotSession.objects.filter(telegram_user_id=admin_chat_id).first()
    author.admin_chat_id = admin_chat_id
    author.channel_id = chat.get("id") or author.channel_id
    if chat.get("title"):
        author.title = chat["title"]

    update_fields = ["admin_chat_id", "channel_id", "updated_at"]
    if chat.get("title"):
        update_fields.append("title")

    if session:
        author.auto_publish = session.auto_publish
        update_fields.append("auto_publish")
        if session.rubric:
            author.rubric = session.rubric
            update_fields.append("rubric")
        if session.invite_url:
            author.invite_url = session.invite_url
            update_fields.append("invite_url")

    author.save(update_fields=update_fields)

    if session and author.rubric:
        Post.objects.filter(author=author).update(rubric=author.rubric)

    token = settings.TELEGRAM_BOT_TOKEN
    if token:
        _refresh_author_from_telegram(author, f"@{username}", token)

    _send_bot_message(
        admin_chat_id,
        f"Канал @{author.username} подключён. Настройки применены.",
    )


def _handle_callback_query(callback_query: dict) -> None:
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if data.startswith("mode:") and chat_id:
        mode = data.split(":", 1)[1]
        auto_publish = mode == "auto"
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id,
            defaults={"auto_publish": auto_publish, "mode_selected": True},
        )
        Author.objects.filter(admin_chat_id=chat_id).update(auto_publish=auto_publish)
        _answer_callback_query(callback_id, "Настройка сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("rubric:") and chat_id:
        try:
            rubric_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректная рубрика")
            return
        rubric = Rubric.objects.filter(id=rubric_id, is_active=True).first()
        if not rubric:
            _answer_callback_query(callback_id, "Рубрика не найдена")
            return
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id, defaults={"rubric": rubric}
        )
        Author.objects.filter(admin_chat_id=chat_id).update(rubric=rubric)
        _answer_callback_query(callback_id, "Рубрика сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("approve:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        post = Post.objects.filter(id=post_id, is_pending=True).first()
        if post:
            post.is_pending = False
            post.save(update_fields=["is_pending", "updated_at"])
            _maybe_notify_new_author(post.author, post)
            _answer_callback_query(callback_id, "Опубликовано")
        else:
            _answer_callback_query(callback_id, "Пост не найден")
        return

    if data.startswith("reject:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        post = Post.objects.filter(id=post_id, is_pending=True).first()
        if post:
            post.is_pending = False
            post.is_blocked = True
            post.save(update_fields=["is_pending", "is_blocked", "updated_at"])
            _answer_callback_query(callback_id, "Пропущено")
        else:
            _answer_callback_query(callback_id, "Пост не найден")
        return

    if data.startswith("update:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if not session or session.pending_update_post_id != post_id or not session.pending_update_message:
            _answer_callback_query(callback_id, "Обновление не найдено")
            return
        _handle_channel_post(session.pending_update_message, force_publish=True)
        session.pending_update_post_id = None
        session.pending_update_message = None
        session.save(update_fields=["pending_update_post_id", "pending_update_message", "updated_at"])
        _answer_callback_query(callback_id, "Пост обновлён")
        _send_bot_message(chat_id, "Пост обновлён на сайте.")
        return

    if data.startswith("skip_update:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if session and session.pending_update_post_id == post_id:
            session.pending_update_post_id = None
            session.pending_update_message = None
            session.save(update_fields=["pending_update_post_id", "pending_update_message", "updated_at"])
        _answer_callback_query(callback_id, "Отменено")
        return


@csrf_exempt
def telegram_webhook(request: HttpRequest, token: str) -> HttpResponse:
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected_secret:
        return JsonResponse({"ok": False, "error": "TELEGRAM_WEBHOOK_SECRET not set"}, status=500)

    if token != expected_secret:
        return JsonResponse({"ok": False, "error": "invalid token"}, status=403)

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret != expected_secret:
        return JsonResponse({"ok": False, "error": "invalid secret"}, status=403)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if "channel_post" in payload:
        _handle_channel_post(payload["channel_post"])
    elif "edited_channel_post" in payload:
        _handle_channel_post(payload["edited_channel_post"])
    elif "my_chat_member" in payload:
        _handle_my_chat_member(payload["my_chat_member"])
    elif "message" in payload:
        _handle_private_message(payload["message"])
    elif "callback_query" in payload:
        _handle_callback_query(payload["callback_query"])

    return JsonResponse({"ok": True})


@csrf_exempt
def register_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()

    if not username or not password:
        return JsonResponse({"ok": False, "error": "username and password are required"}, status=400)
    if len(password) < 8:
        return JsonResponse({"ok": False, "error": "пароль слишком короткий"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"ok": False, "error": "username already exists"}, status=400)
    if email and User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"ok": False, "error": "email already exists"}, status=400)

    user = User.objects.create_user(username=username, email=email or None, password=password)
    token = _issue_token(user)
    return JsonResponse({"ok": True, "token": token, "user": _serialize_user(user)})


@csrf_exempt
def login_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    username_or_email = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username_or_email or not password:
        return JsonResponse({"ok": False, "error": "invalid credentials"}, status=400)

    user = None
    if "@" in username_or_email:
        user = User.objects.filter(email__iexact=username_or_email).first()
        if user and not user.check_password(password):
            user = None
    else:
        user = authenticate(username=username_or_email, password=password)

    if not user:
        return JsonResponse({"ok": False, "error": "invalid credentials"}, status=401)

    token = _issue_token(user)
    return JsonResponse({"ok": True, "token": token, "user": _serialize_user(user)})


def auth_me(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    return JsonResponse({"ok": True, "user": _serialize_user(user)})


@csrf_exempt
def author_verification_code(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    active = (
        AuthorVerificationCode.objects.filter(user=user, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if active and active.created_at >= timezone.now() - timedelta(days=1):
        return JsonResponse({"ok": True, "code": active.code})

    code = _generate_verification_code()
    while AuthorVerificationCode.objects.filter(code=code).exists():
        code = _generate_verification_code()

    AuthorVerificationCode.objects.create(user=user, code=code)
    return JsonResponse({"ok": True, "code": code})


def _serialize_post_for_user(request: HttpRequest, post: Post) -> dict:
    rubric = post.rubric
    author_channel_url = post.author.invite_url or post.author.channel_url
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "is_pending": post.is_pending,
        "rubric": rubric.name if rubric else None,
        "rubric_slug": rubric.slug if rubric else None,
        "rubric_icon_url": _media_url(request, rubric.icon_url) if rubric else None,
        "author": {
            "username": post.author.username,
            "title": post.author.title,
            "channel_url": author_channel_url,
            "avatar_url": _author_avatar_url(request, post.author),
        },
    }


def user_posts(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    limit_raw = request.GET.get("limit", "20")
    offset_raw = request.GET.get("offset", "0")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    author_ids = list(
        AuthorAdmin.objects.filter(user=user, verified_at__isnull=False).values_list(
            "author_id", flat=True
        )
    )
    if not author_ids:
        return JsonResponse({"ok": True, "posts": [], "total": 0})

    posts_qs = (
        Post.objects.filter(author_id__in=author_ids, is_blocked=False, author__is_blocked=False)
        .select_related("author", "rubric")
        .order_by("-created_at")
    )

    total = posts_qs.count()
    posts = posts_qs[offset : offset + limit]
    serialized = [_serialize_post_for_user(request, post) for post in posts]
    return JsonResponse({"ok": True, "posts": serialized, "total": total})


@csrf_exempt
def user_post_update(request: HttpRequest, post_id: int) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in {"PATCH", "PUT"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        post = Post.objects.select_related("author", "rubric").get(
            id=post_id, is_blocked=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    is_linked = AuthorAdmin.objects.filter(
        user=user, author=post.author, verified_at__isnull=False
    ).exists()
    if not is_linked:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    title = payload.get("title") if "title" in payload else None
    content = payload.get("content") if "content" in payload else None

    if title is None and content is None:
        return JsonResponse({"ok": False, "error": "nothing to update"}, status=400)

    if content is not None:
        content = str(content).strip()
        if not content:
            return JsonResponse({"ok": False, "error": "content is empty"}, status=400)
        if len(content) > 100000:
            return JsonResponse({"ok": False, "error": "content too long"}, status=400)
        post.content = content
        raw_data = dict(post.raw_data or {})
        raw_data["manual_edit"] = True
        raw_data["manual_updated_at"] = timezone.now().isoformat()
        post.raw_data = raw_data

    if title is not None:
        title = str(title).strip()
        if title:
            post.title = title[:255]
        else:
            source_text = _strip_html(post.content)
            post.title = _build_title(source_text)

    post.save(update_fields=["title", "content", "raw_data", "updated_at"])
    return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post)})


@csrf_exempt
def post_comments(request: HttpRequest, post_id: int) -> HttpResponse:
    try:
        post = Post.objects.select_related("author").get(
            id=post_id, is_blocked=False, is_pending=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    if request.method == "GET":
        user = _get_user_from_request(request)
        comments = (
            PostComment.objects.filter(post=post)
            .select_related("user")
            .annotate(likes_count=Count("likes", distinct=True))
            .order_by("created_at")
        )
        liked_ids = set()
        if user:
            liked_ids = set(
                PostCommentLike.objects.filter(user=user, comment__post=post).values_list(
                    "comment_id", flat=True
                )
            )
        serialized = [
            {
                "id": comment.id,
                "body": "" if comment.is_deleted else comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "parent_id": comment.parent_id,
                "is_deleted": comment.is_deleted,
                "likes_count": comment.likes_count,
                "liked_by_me": comment.id in liked_ids,
                "can_edit": bool(user and comment.user_id == user.id and not comment.is_deleted),
                "user": {"username": comment.user.username},
            }
            for comment in comments
        ]
        return JsonResponse({"ok": True, "comments": serialized})

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    body = (payload.get("body") or "").strip()
    parent_id = payload.get("parent_id")
    if not body:
        return JsonResponse({"ok": False, "error": "comment is empty"}, status=400)
    if len(body) > 2000:
        return JsonResponse({"ok": False, "error": "comment too long"}, status=400)

    parent = None
    if parent_id:
        try:
            parent = PostComment.objects.get(id=int(parent_id), post=post, is_deleted=False)
        except (PostComment.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "parent comment not found"}, status=404)

    comment = PostComment.objects.create(post=post, user=user, body=body, parent=parent)
    Post.objects.filter(id=post.id).update(comments_count=F("comments_count") + 1)
    post.refresh_from_db(fields=["comments_count"])

    return JsonResponse(
        {
            "ok": True,
            "comment": {
                "id": comment.id,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "parent_id": comment.parent_id,
                "is_deleted": comment.is_deleted,
                "likes_count": 0,
                "liked_by_me": False,
                "can_edit": True,
                "user": {"username": user.username},
            },
            "comments_count": post.comments_count,
        }
    )


@csrf_exempt
def comment_detail(request: HttpRequest, comment_id: int) -> HttpResponse:
    if request.method not in ("PATCH", "DELETE"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        comment = PostComment.objects.select_related("post", "user").get(id=comment_id)
    except PostComment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    if comment.is_deleted:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    if comment.user_id != user.id:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    if request.method == "PATCH":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

        body = (payload.get("body") or "").strip()
        if not body:
            return JsonResponse({"ok": False, "error": "comment is empty"}, status=400)
        if len(body) > 2000:
            return JsonResponse({"ok": False, "error": "comment too long"}, status=400)

        comment.body = body
        comment.save(update_fields=["body", "updated_at"])
        likes_count = PostCommentLike.objects.filter(comment=comment).count()
        liked_by_me = PostCommentLike.objects.filter(comment=comment, user=user).exists()

        return JsonResponse(
            {
                "ok": True,
                "comment": {
                    "id": comment.id,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat(),
                    "parent_id": comment.parent_id,
                    "is_deleted": comment.is_deleted,
                    "likes_count": likes_count,
                    "liked_by_me": liked_by_me,
                    "can_edit": True,
                    "user": {"username": comment.user.username},
                },
            }
        )

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])
    Post.objects.filter(id=comment.post_id, comments_count__gt=0).update(
        comments_count=F("comments_count") - 1
    )

    return JsonResponse({"ok": True, "comment_id": comment.id})


@csrf_exempt
def comment_like(request: HttpRequest, comment_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        comment = PostComment.objects.select_related("post", "post__author").get(
            id=comment_id,
            is_deleted=False,
            post__is_blocked=False,
            post__is_pending=False,
            post__author__is_blocked=False,
        )
    except PostComment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    existing = PostCommentLike.objects.filter(comment=comment, user=user).first()
    if existing:
        existing.delete()
        liked = False
    else:
        PostCommentLike.objects.create(comment=comment, user=user)
        liked = True

    likes_count = PostCommentLike.objects.filter(comment=comment).count()

    return JsonResponse({"ok": True, "liked": liked, "likes_count": likes_count})


@csrf_exempt
def post_like(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        post = Post.objects.select_related("author").get(
            id=post_id, is_blocked=False, is_pending=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    vote_value = 1
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            vote_value = int(payload.get("value", payload.get("vote", payload.get("score", 1))))

    if vote_value not in (-1, 0, 1):
        return JsonResponse({"ok": False, "error": "invalid vote value"}, status=400)

    existing = PostLike.objects.filter(post=post, user=user).first()
    delta = 0
    new_vote = 0
    if existing:
        if vote_value == 0 or existing.value == vote_value:
            delta = -existing.value
            existing.delete()
            new_vote = 0
        else:
            delta = vote_value - existing.value
            existing.value = vote_value
            existing.save(update_fields=["value"])
            new_vote = vote_value
    else:
        if vote_value != 0:
            PostLike.objects.create(post=post, user=user, value=vote_value)
            delta = vote_value
            new_vote = vote_value

    if delta:
        Post.objects.filter(id=post.id).update(rating=F("rating") + delta)

    liked = new_vote == 1

    post.refresh_from_db(fields=["rating"])
    return JsonResponse(
        {
            "ok": True,
            "liked": liked,
            "vote": new_vote,
            "likes_count": post.rating,
        }
    )


def author_posts(request: HttpRequest, username: str) -> HttpResponse:
    try:
        author = Author.objects.get(username__iexact=username)
    except Author.DoesNotExist:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    if author.is_blocked:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    limit_raw = request.GET.get("limit", "20")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20

    posts = (
        Post.objects.filter(author=author, is_blocked=False, is_pending=False)
        .order_by("-created_at")
        .all()[:limit]
    )

    posts_count = Post.objects.filter(
        author=author, is_blocked=False, is_pending=False
    ).count()
    author_channel_url = author.invite_url or author.channel_url
    serialized = []
    for post in posts:
        rubric = post.rubric
        serialized.append(
            {
                "id": post.id,
                "title": post.title,
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _media_url(request, rubric.icon_url) if rubric else None,
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url or post.channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "author": {
                    "username": author.username,
                    "title": author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_url(request, author),
                    "description": author.description,
                    "subscribers_count": author.subscribers_count,
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "author": {
                "username": author.username,
                "title": author.title,
                "channel_url": author_channel_url,
                "avatar_url": _author_avatar_url(request, author),
                "description": author.description,
                "subscribers_count": author.subscribers_count,
                "posts_count": posts_count,
            },
            "posts": serialized,
        }
    )


def rubrics_list(request: HttpRequest) -> HttpResponse:
    rubrics = Rubric.objects.filter(is_active=True).order_by("sort_order", "name")
    serialized = [
        {
            "id": rubric.id,
            "name": rubric.name,
            "slug": rubric.slug,
            "icon_url": _media_url(request, rubric.icon_url),
            "cover_image_url": _media_url(request, rubric.cover_image_url),
            "description": rubric.description,
            "subscribe_url": rubric.subscribe_url,
        }
        for rubric in rubrics
    ]
    return JsonResponse({"ok": True, "rubrics": serialized})


def rubric_posts(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        rubric = Rubric.objects.get(slug=slug, is_active=True)
    except Rubric.DoesNotExist:
        return JsonResponse({"ok": False, "error": "rubric not found"}, status=404)

    limit_raw = request.GET.get("limit", "20")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20

    posts = (
        Post.objects.filter(
            rubric=rubric,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .order_by("-created_at")
        .all()[:limit]
    )

    serialized = []
    for post in posts:
        author_channel_url = post.author.invite_url or post.author.channel_url
        serialized.append(
            {
                "id": post.id,
                "title": post.title,
                "rubric": rubric.name,
                "rubric_slug": rubric.slug,
                "rubric_icon_url": _media_url(request, rubric.icon_url),
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url or post.channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "author": {
                    "username": post.author.username,
                    "title": post.author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_url(request, post.author),
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "rubric": {
                "name": rubric.name,
                "slug": rubric.slug,
                "icon_url": _media_url(request, rubric.icon_url),
                "cover_image_url": _media_url(request, rubric.cover_image_url),
                "description": rubric.description,
                "subscribe_url": rubric.subscribe_url,
            },
            "posts": serialized,
        }
    )


def post_detail(request: HttpRequest, post_id: int) -> HttpResponse:
    try:
        post = Post.objects.select_related("author", "rubric").get(
            id=post_id, is_blocked=False, is_pending=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    rubric = post.rubric
    author_channel_url = post.author.invite_url or post.author.channel_url
    return JsonResponse(
        {
            "ok": True,
            "post": {
                "id": post.id,
                "title": post.title,
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _media_url(request, rubric.icon_url) if rubric else None,
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url or post.channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "author": {
                    "username": post.author.username,
                    "title": post.author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_url(request, post.author),
                },
            },
        }
    )


def home_feed(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "50")
    try:
        limit = min(max(int(limit_raw), 1), 200)
    except ValueError:
        limit = 50

    posts = list(
        Post.objects.filter(
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
            rating__gte=0,
        )
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
        .select_related("author", "rubric")
        .order_by("-created_at")[: limit * 3]
    )

    serialized_posts = []
    remaining = posts[:]
    last_author_id = None

    while remaining and len(serialized_posts) < limit:
        next_index = None
        for idx, candidate in enumerate(remaining):
            if candidate.author_id != last_author_id:
                next_index = idx
                break
        if next_index is None:
            next_index = 0
        post = remaining.pop(next_index)
        rubric = post.rubric
        author_channel_url = post.author.invite_url or post.author.channel_url
        serialized_posts.append(
            {
                "id": post.id,
                "title": post.title,
                "rubric": rubric.name if rubric else None,
                "rubric_slug": rubric.slug if rubric else None,
                "rubric_icon_url": _media_url(request, rubric.icon_url) if rubric else None,
                "content": post.content,
                "source_url": post.source_url,
                "channel_url": author_channel_url or post.channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": post.author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_url(request, post.author),
                },
                "score": post.rating + post.comments_count * 5,
                "rating": post.rating,
                "comments_count": post.comments_count,
                "likes_count": post.rating,
            }
        )
        last_author_id = post.author_id

    return JsonResponse({"ok": True, "posts": serialized_posts})


def top_authors_month(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "5")
    try:
        limit = min(max(int(limit_raw), 1), 20)
    except ValueError:
        limit = 5

    cutoff = timezone.now() - timedelta(days=30)
    score_expr = Cast(F("posts__rating"), IntegerField()) + Cast(
        F("posts__comments_count"), IntegerField()
    ) * Value(5)
    posts_filter = Q(
        posts__created_at__gte=cutoff,
        posts__is_blocked=False,
        posts__is_pending=False,
    )

    authors = (
        Author.objects.filter(is_blocked=False)
        .filter(Q(shadow_banned=False) | Q(force_home=True))
        .annotate(
            month_score=Sum(score_expr, filter=posts_filter),
            month_posts=Count("posts", filter=posts_filter),
        )
        .filter(month_posts__gt=0)
        .order_by("-month_score", "-month_posts", "username")[:limit]
    )

    serialized = []
    for author in authors:
        serialized.append(
            {
                "username": author.username,
                "title": author.title,
                "avatar_url": _author_avatar_url(request, author),
                "channel_url": author.invite_url or author.channel_url,
                "month_score": author.month_score or 0,
                "month_posts": author.month_posts or 0,
            }
        )

    return JsonResponse({"ok": True, "authors": serialized})


def search_content(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse(
            {
                "ok": True,
                "query": "",
                "page": 1,
                "limit": 0,
                "posts": [],
                "authors": [],
                "total_posts": 0,
                "total_authors": 0,
            }
        )

    type_filter = (request.GET.get("type") or "All").lower()
    sort = (request.GET.get("sort") or "New").lower()

    limit_raw = request.GET.get("limit", "20")
    page_raw = request.GET.get("page", "1")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20
    try:
        page = max(int(page_raw), 1)
    except ValueError:
        page = 1

    offset = (page - 1) * limit

    posts: list[dict] = []
    authors: list[dict] = []
    total_posts = 0
    total_authors = 0

    if type_filter in ("all", "posts"):
        post_query = Q(title__icontains=query) | Q(content__icontains=query)
        post_query |= Q(author__username__icontains=query) | Q(
            author__title__icontains=query
        )
        posts_qs = (
            Post.objects.filter(
                post_query,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .select_related("author", "rubric")
            .order_by("-created_at" if sort == "new" else "-created_at")
        )
        total_posts = posts_qs.count()
        for post in posts_qs[offset : offset + limit]:
            rubric = post.rubric
            author_channel_url = post.author.invite_url or post.author.channel_url
            posts.append(
                {
                    "id": post.id,
                    "title": post.title,
                    "rubric": rubric.name if rubric else None,
                    "rubric_slug": rubric.slug if rubric else None,
                    "rubric_icon_url": _media_url(request, rubric.icon_url)
                    if rubric
                    else None,
                    "content": post.content,
                    "source_url": post.source_url,
                    "channel_url": author_channel_url or post.channel_url,
                    "created_at": post.created_at.isoformat(),
                    "comments_count": post.comments_count,
                    "likes_count": post.rating,
                    "author": {
                        "username": post.author.username,
                        "title": post.author.title,
                        "channel_url": author_channel_url,
                        "avatar_url": _author_avatar_url(request, post.author),
                        "description": post.author.description,
                        "subscribers_count": post.author.subscribers_count,
                    },
                }
            )

    if type_filter in ("all", "users", "authors"):
        authors_qs = Author.objects.filter(is_blocked=False).filter(
            Q(username__icontains=query)
            | Q(title__icontains=query)
            | Q(description__icontains=query)
        )
        total_authors = authors_qs.count()
        for author in authors_qs[offset : offset + limit]:
            authors.append(
                {
                    "username": author.username,
                    "title": author.title,
                    "avatar_url": _author_avatar_url(request, author),
                    "description": author.description,
                    "channel_url": author.invite_url or author.channel_url,
                    "subscribers_count": author.subscribers_count,
                }
            )

    return JsonResponse(
        {
            "ok": True,
            "query": query,
            "page": page,
            "limit": limit,
            "posts": posts,
            "authors": authors,
            "total_posts": total_posts,
            "total_authors": total_authors,
        }
    )


def sitemap_xml(request: HttpRequest) -> HttpResponse:
    base_url = request.build_absolute_uri("/").rstrip("/")
    urls: list[str] = []

    def add_url(path: str, lastmod: str | None = None) -> None:
        loc = f"{base_url}{path}"
        entry = f"<url><loc>{xml_escape(loc)}</loc>"
        if lastmod:
            entry += f"<lastmod>{xml_escape(lastmod)}</lastmod>"
        entry += "</url>"
        urls.append(entry)

    static_paths = [
        "/",
        "/authors",
        "/about",
        "/advertisement",
        "/rules",
        "/legal",
    ]
    for path in static_paths:
        add_url(path)

    rubrics = Rubric.objects.filter(is_active=True).order_by("slug")
    for rubric in rubrics:
        add_url(f"/rubrics/{rubric.slug}/posts", _format_lastmod(rubric.updated_at))

    authors = Author.objects.filter(is_blocked=False).order_by("username")
    for author in authors:
        add_url(f"/{author.username}", _format_lastmod(author.updated_at))

    posts = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .only("id", "title", "updated_at", "created_at")
        .order_by("-created_at")[:5000]
    )
    for post in posts:
        lastmod = _format_lastmod(post.updated_at or post.created_at)
        slug = _slugify_title(post.title)
        path = f"/b/post/{post.id}-{slug}" if slug else f"/b/post/{post.id}"
        add_url(path, lastmod)

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(body, content_type="application/xml")
