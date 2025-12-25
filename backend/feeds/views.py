from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from html import escape
from xml.sax.saxutils import escape as xml_escape
from django.db import transaction
from django.db.models import F, IntegerField, Value
from django.db.models.functions import Cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Author, BotSession, Post, Rubric

_BOT_ID: int | None = None


def _media_url(request: HttpRequest, field) -> str | None:
    if not field:
        return None
    try:
        return request.build_absolute_uri(field.url)
    except Exception:
        return None


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
    if len(first_line) <= 120:
        return first_line
    return first_line[:117] + "..."


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


def _extract_photo_url(message: dict, token: str) -> str | None:
    photos = message.get("photo") or []
    if not photos:
        return None
    largest = max(
        photos,
        key=lambda item: (item.get("file_size", 0), item.get("width", 0) * item.get("height", 0)),
    )
    file_id = largest.get("file_id")
    if not file_id:
        return None
    file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
    if not file_info or not file_info.get("ok") or not file_info.get("result"):
        return None
    file_path = file_info["result"].get("file_path")
    if not file_path:
        return None
    return f"https://api.telegram.org/file/bot{token}/{file_path}"


def _build_content_with_images(text_html: str, image_urls: list[str]) -> str:
    if not image_urls:
        return text_html
    preview = f'<img src="{image_urls[0]}" alt="" />'
    remaining = image_urls[1:]
    gallery_html = ""
    if remaining:
        gallery_imgs = "".join(f'<img src="{url}" alt="" />' for url in remaining)
        gallery_html = f'<div class="post-gallery">{gallery_imgs}</div>'
    parts = [preview]
    if text_html:
        parts.append(f"<br><br>{text_html}")
    if gallery_html:
        parts.append(f"<br><br>{gallery_html}")
    return "".join(parts)


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


def _refresh_author_from_telegram(author: Author, chat_id: int, token: str) -> None:
    chat = _fetch_telegram_json("getChat", token, {"chat_id": chat_id})
    if chat and chat.get("ok") and chat.get("result"):
        result = chat["result"]
        if result.get("title"):
            author.title = result["title"]
        if result.get("description"):
            author.description = result["description"]
        if result.get("username"):
            author.channel_url = f"https://t.me/{result['username']}"
        photo = result.get("photo")
        if photo and photo.get("big_file_id"):
            file_info = _fetch_telegram_json(
                "getFile", token, {"file_id": photo["big_file_id"]}
            )
            if file_info and file_info.get("ok") and file_info.get("result"):
                file_path = file_info["result"].get("file_path")
                if file_path:
                    author.avatar_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

    count = _fetch_telegram_json("getChatMemberCount", token, {"chat_id": chat_id})
    if count and count.get("ok") and isinstance(count.get("result"), int):
        author.subscribers_count = count["result"]

    author.save(
        update_fields=[
            "title",
            "description",
            "channel_url",
            "avatar_url",
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
    image_url = _extract_photo_url(message, token) if token else None
    gallery_urls = [image_url] if image_url else []
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
                raw_data["media_group_id"] = media_group_id
                if not raw_data.get("formatted_text") and formatted_text:
                    raw_data["formatted_text"] = formatted_text
                base_text = raw_data.get("formatted_text") or formatted_text
                content = _build_content_with_images(base_text, existing_urls)
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

    content = _build_content_with_images(formatted_text, gallery_urls)
    title = _build_title(raw_text)
    if not title and image_url:
        title = "Фото"
    channel_url = f"https://t.me/{username}"
    source_url = f"{channel_url}/{message_id}"

    requires_approval = (not author.auto_publish and author.admin_chat_id) and not force_publish

    raw_data = dict(message)
    if media_group_id:
        raw_data["media_group_id"] = media_group_id
    if media_group_id and gallery_urls:
        raw_data["gallery_urls"] = gallery_urls
        raw_data["formatted_text"] = formatted_text
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

    if text == "Настройка":
        _send_setup_options(chat_id)
        return

    if text == "Ссылка для подписки":
        _send_bot_message(
            chat_id,
            "Пришлите ссылку приглашения на ваш канал (например, https://t.me/+xxxx). "
            "Мы будем использовать её в кнопках подписки на сайте.",
        )
        BotSession.objects.update_or_create(telegram_user_id=chat_id, defaults={})
        return

    if text.startswith("https://t.me/") or text.startswith("http://t.me/"):
        invite_url = text.strip()
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if not session:
            session = BotSession.objects.create(telegram_user_id=chat_id)
        session.invite_url = invite_url
        session.save(update_fields=["invite_url", "updated_at"])
        Author.objects.filter(admin_chat_id=chat_id).update(invite_url=invite_url)
        _send_bot_message(chat_id, "Ссылка сохранена. Мы будем использовать её для кнопок подписки.")
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
            "entities": message.get("entities"),
            "caption_entities": message.get("caption_entities"),
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
    elif "message" in payload:
        _handle_private_message(payload["message"])
    elif "callback_query" in payload:
        _handle_callback_query(payload["callback_query"])

    return JsonResponse({"ok": True})


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
                "author": {
                    "username": author.username,
                    "title": author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": author.avatar_url,
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
                "avatar_url": author.avatar_url,
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
                "author": {
                    "username": post.author.username,
                    "title": post.author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": post.author.avatar_url,
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
                "author": {
                    "username": post.author.username,
                    "title": post.author.title,
                    "channel_url": author_channel_url,
                    "avatar_url": post.author.avatar_url,
                },
            },
        }
    )


def home_feed(request: HttpRequest) -> HttpResponse:
    rubrics = Rubric.objects.filter(is_active=True).order_by("sort_order", "name")
    serialized_posts = []

    for rubric in rubrics:
        limit = rubric.home_limit or 0
        if limit <= 0:
            continue

        posts = (
            Post.objects.filter(
                rubric=rubric,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .annotate(
                score=Cast(F("rating"), IntegerField())
                + Cast(F("comments_count"), IntegerField()) * Value(5)
            )
            .order_by("-score", "-created_at")[:limit]
        )

        for post in posts:
            author_channel_url = post.author.invite_url or post.author.channel_url
            serialized_posts.append(
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
                    "author": {
                        "username": post.author.username,
                        "title": post.author.title,
                        "channel_url": author_channel_url,
                        "avatar_url": post.author.avatar_url,
                    },
                    "score": post.rating + post.comments_count * 5,
                    "rating": post.rating,
                    "comments_count": post.comments_count,
                }
            )

    return JsonResponse({"ok": True, "posts": serialized_posts})


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
        .only("id", "updated_at", "created_at")
        .order_by("-created_at")[:5000]
    )
    for post in posts:
        lastmod = _format_lastmod(post.updated_at or post.created_at)
        add_url(f"/b/post/{post.id}", lastmod)

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(body, content_type="application/xml")
