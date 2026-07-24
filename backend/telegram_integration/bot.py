from __future__ import annotations

import json
import os
import urllib.request
from datetime import timedelta

from communities import service as community_service
from communities.models import Comun, ComunTelegramSubmission
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from feeds.language_detection import detect_post_language
from feeds.models import Author, Post
from telegram_integration.models import BotSession, TelegramAccount
from telegram_integration.media import is_private_telegram_file_url
from users.models import AuthorAdmin, AuthorVerificationCode

_BOT_ID: int | None = None
CHANNEL_FLOW_CREATE = "create_comun"
CHANNEL_FLOW_EXISTING = "link_existing"
User = get_user_model()


def _fv():
    from feeds import views as feed_views

    return feed_views


def _notification_service():
    from notifications import service as notification_service

    return notification_service


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_values.append(normalized)
    return unique_values


def _merge_media_group_image(
    raw_data: dict,
    *,
    image_url: str | None,
    photo_file_id: str | None,
    media_group_id: str,
) -> dict:
    next_raw_data = dict(raw_data or {})
    existing_urls = _unique_nonempty(list(next_raw_data.get("gallery_urls") or []))
    existing_file_ids = _unique_nonempty(list(next_raw_data.get("gallery_file_ids") or []))
    photo_file_seen = bool(photo_file_id and photo_file_id in existing_file_ids)

    if image_url and not photo_file_seen and image_url not in existing_urls:
        existing_urls.append(image_url)
    next_raw_data["gallery_urls"] = existing_urls

    if photo_file_id and not photo_file_seen:
        existing_file_ids.append(photo_file_id)
    if existing_file_ids:
        next_raw_data["gallery_file_ids"] = existing_file_ids

    next_raw_data["media_group_id"] = media_group_id
    return next_raw_data


def _fetch_telegram_json(method: str, token: str, payload: dict) -> dict | None:
    return _fv()._fetch_telegram_json(method, token, payload)


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


def _edit_bot_message_with_keyboard(chat_id: int, message_id: int, text: str, keyboard: dict) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": json.dumps(keyboard),
    }
    response = _fetch_telegram_json("editMessageText", token, payload)
    if response and response.get("ok"):
        return
    description = str((response or {}).get("description") or "").lower()
    if "message is not modified" in description:
        return
    _send_bot_message_with_keyboard(chat_id, text, keyboard)


def _answer_callback_query(callback_query_id: str, text: str = "") -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    _fetch_telegram_json("answerCallbackQuery", token, payload)


def _main_reply_keyboard() -> dict:
    return {
        "keyboard": [["Управление оповещениями", "Управление каналами"]],
        "resize_keyboard": True,
    }


def _send_main_menu(chat_id: int) -> None:
    _send_bot_message_with_keyboard(
        chat_id,
        "Привет! Это бот сайта Тамбур, у меня две основные задачи, я присылаю "
        "оповещения (только на которые подписан пользователь), а также я помогаю "
        "привязать канал телеграм к сообществу. Выбери что ты хочешь.",
        _main_reply_keyboard(),
    )


def _telegram_plain_text(message: dict) -> str:
    return str(message.get("text") or message.get("caption") or "").strip()


def _telegram_actor_name(actor: dict) -> str:
    username = str(actor.get("username") or "").strip()
    if username:
        return f"@{username}"
    full_name = " ".join(
        part
        for part in [
            str(actor.get("first_name") or "").strip(),
            str(actor.get("last_name") or "").strip(),
        ]
        if part
    ).strip()
    return full_name


def _normalize_bot_command_text(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("/"):
        parts = value.split(" ", 1)
        command = parts[0].split("@", 1)[0]
        return " ".join([command, parts[1] if len(parts) > 1 else ""]).strip()
    return value


def _submission_type_from_text(text: str) -> str:
    value = _normalize_bot_command_text(text).strip().lower().replace("ё", "е")
    if not value:
        return ""
    if value in {"/kb", "/knowledge", "/knowledge_base"}:
        return ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE
    if value in {"/glossary", "/term"}:
        return ComunTelegramSubmission.TYPE_GLOSSARY
    if "глоссар" in value or "гласар" in value:
        return ComunTelegramSubmission.TYPE_GLOSSARY
    if "баз" in value and "знан" in value:
        return ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE
    return ""


def _parse_link_comun_slug(text: str) -> str:
    value = _normalize_bot_command_text(text)
    parts = value.split()
    if len(parts) < 2:
        return ""
    command = parts[0].lower()
    if command not in {"/link_comun", "/link_community", "/link"}:
        return ""
    return parts[1].strip().strip("/")


def _telegram_source_url(chat: dict, message_id: int | None) -> str:
    username = str(chat.get("username") or "").strip()
    if not username or not message_id:
        return ""
    return f"https://t.me/{username}/{message_id}"


def _glossary_candidate_from_text(text: str) -> tuple[str, str]:
    normalized = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    if not normalized:
        return "", ""
    first_line, _separator, rest = normalized.partition("\n")
    for separator in (" — ", " – ", " - ", ": "):
        if separator in first_line:
            term, definition = first_line.split(separator, 1)
            combined_definition = "\n".join(part for part in [definition.strip(), rest.strip()] if part)
            return term.strip()[:180], combined_definition.strip()[:5000]
    if rest.strip():
        return first_line.strip()[:180], rest.strip()[:5000]
    return first_line.strip()[:180], normalized.strip()[:5000]


def _title_candidate_from_text(text: str) -> str:
    for line in str(text or "").splitlines():
        title = line.strip()
        if title:
            return title[:255]
    return "Сообщение из Telegram"


def _requesting_user_from_message(message: dict) -> tuple[User | None, int | None, str]:
    actor = message.get("from") if isinstance(message.get("from"), dict) else {}
    telegram_user_id = actor.get("id")
    try:
        telegram_user_id = int(telegram_user_id)
    except (TypeError, ValueError):
        telegram_user_id = None
    account = (
        TelegramAccount.objects.select_related("user")
        .filter(telegram_id=telegram_user_id)
        .first()
        if telegram_user_id
        else None
    )
    return (account.user if account else None), telegram_user_id, _telegram_actor_name(actor)


def _notify_comun_team_about_telegram_submission(submission: ComunTelegramSubmission) -> None:
    team_user_ids = community_service._comun_team_user_ids(submission.comun)
    if not team_user_ids:
        return
    request_type_label = (
        "базу знаний"
        if submission.request_type == ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE
        else "глоссарий"
    )
    title = f"Новая заявка в {request_type_label}"
    message = (
        f"В сообщество «{submission.comun.name}» из Telegram-чата "
        f"предложили материал в {request_type_label}."
    )
    link_url = f"/comuns/{submission.comun.slug}/telegram-submissions?status=pending&id={submission.id}"
    for user in User.objects.filter(id__in=team_user_ids, is_active=True):
        _notification_service().create_user_notification(
            user=user,
            event_key="comun_telegram_submission",
            title=title,
            message=message,
            link_url=link_url,
            payload={
                "comun_id": submission.comun_id,
                "comun_slug": submission.comun.slug,
                "submission_id": submission.id,
                "request_type": submission.request_type,
            },
        )


def _handle_group_link_comun(message: dict, slug: str) -> None:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id")
    if not chat_id:
        return
    requester, telegram_user_id, _actor_name = _requesting_user_from_message(message)
    if not requester or not telegram_user_id:
        _send_bot_message(
            chat_id,
            "Чтобы привязать чат к сообществу, сначала привяжите Telegram к профилю на Тамбуре.",
        )
        return
    comun = Comun.objects.filter(slug=slug, is_active=True).prefetch_related("moderators").first()
    if not comun:
        _send_bot_message(chat_id, "Сообщество не найдено. Проверьте slug после команды.")
        return
    if not community_service._comun_is_moderator(requester, comun):
        _send_bot_message(
            chat_id,
            "Привязать чат может только создатель или модератор этого сообщества.",
        )
        return
    existing = Comun.objects.filter(telegram_chat_id=chat_id).exclude(id=comun.id).first()
    if existing:
        _send_bot_message(
            chat_id,
            f"Этот чат уже привязан к сообществу «{existing.name}».",
        )
        return
    comun.telegram_chat_id = int(chat_id)
    comun.telegram_chat_title = str(chat.get("title") or "").strip()[:255]
    comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
    _send_bot_message(
        chat_id,
        f"Чат привязан к сообществу «{comun.name}». Теперь ответьте на сообщение текстом "
        "команды /kb или /glossary, чтобы отправить заявку модераторам.",
    )


def _handle_group_submission_request(message: dict, request_type: str) -> None:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id")
    if not chat_id:
        return
    reply = message.get("reply_to_message") if isinstance(message.get("reply_to_message"), dict) else None
    if not reply:
        _send_bot_message(
            chat_id,
            "Ответьте этой командой на конкретное сообщение, которое нужно предложить.",
        )
        return
    comun = Comun.objects.filter(telegram_chat_id=chat_id, is_active=True).first()
    if not comun:
        _send_bot_message(
            chat_id,
            "Этот чат не привязан к сообществу. Создатель или модератор может привязать его командой /link_comun slug.",
        )
        return
    if request_type == ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE and not comun.knowledge_base_enabled:
        _send_bot_message(chat_id, "В этом сообществе база знаний пока выключена.")
        return
    if request_type == ComunTelegramSubmission.TYPE_GLOSSARY and not comun.glossary_enabled:
        _send_bot_message(chat_id, "В этом сообществе глоссарий пока выключен.")
        return
    source_text = _telegram_plain_text(reply)
    if not source_text:
        _send_bot_message(chat_id, "Пока можно отправлять на модерацию только текстовые сообщения.")
        return
    source_message_id = reply.get("message_id")
    try:
        source_message_id = int(source_message_id)
    except (TypeError, ValueError):
        return
    requester, telegram_user_id, actor_name = _requesting_user_from_message(message)
    source_author_name = _telegram_actor_name(reply.get("from") if isinstance(reply.get("from"), dict) else {})
    glossary_term = ""
    glossary_definition = ""
    title = ""
    if request_type == ComunTelegramSubmission.TYPE_GLOSSARY:
        glossary_term, glossary_definition = _glossary_candidate_from_text(source_text)
    else:
        title = _title_candidate_from_text(source_text)
    defaults = {
        "requested_by": requester,
        "telegram_user_id": telegram_user_id,
        "telegram_username": actor_name[:255],
        "telegram_chat_title": str(chat.get("title") or "").strip()[:255],
        "telegram_request_message_id": message.get("message_id"),
        "telegram_source_url": _telegram_source_url(chat, source_message_id),
        "source_author_name": source_author_name[:255],
        "source_text": source_text[:20000],
        "title": title,
        "glossary_term": glossary_term,
        "glossary_definition": glossary_definition,
        "source_payload": {
            "request_message": message,
            "source_message": reply,
        },
    }
    try:
        submission, created = ComunTelegramSubmission.objects.get_or_create(
            comun=comun,
            request_type=request_type,
            telegram_chat_id=int(chat_id),
            telegram_source_message_id=source_message_id,
            status=ComunTelegramSubmission.STATUS_PENDING,
            defaults=defaults,
        )
    except IntegrityError:
        submission = ComunTelegramSubmission.objects.filter(
            comun=comun,
            request_type=request_type,
            telegram_chat_id=int(chat_id),
            telegram_source_message_id=source_message_id,
            status=ComunTelegramSubmission.STATUS_PENDING,
        ).first()
        created = False
    if not submission:
        _send_bot_message(chat_id, "Не удалось создать заявку. Попробуйте позже.")
        return
    if not created:
        _send_bot_message(chat_id, "Такая заявка уже ожидает модерации.")
        return
    _notify_comun_team_about_telegram_submission(submission)
    target_label = "базу знаний" if request_type == ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE else "глоссарий"
    _send_bot_message(chat_id, f"Заявка на добавление в {target_label} отправлена модераторам.")


def _handle_group_message(message: dict) -> None:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    if chat.get("type") not in {"group", "supergroup"}:
        return
    text = _telegram_plain_text(message)
    slug = _parse_link_comun_slug(text)
    if slug:
        _handle_group_link_comun(message, slug)
        return
    request_type = _submission_type_from_text(text)
    if request_type:
        _handle_group_submission_request(message, request_type)


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
                telegram_file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                if is_private_telegram_file_url(author.avatar_url):
                    author.avatar_url = ""
                if file_id != author.avatar_file_id:
                    try:
                        with urllib.request.urlopen(telegram_file_url, timeout=10) as response:
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


def _get_admin_authors(chat_id: int) -> list[Author]:
    return list(
        Author.objects.filter(admin_chat_id=chat_id, is_blocked=False).order_by("username")
    )


def _format_delay_label(days: int) -> str:
    if days <= 0:
        return "без задержки"
    return f"{days} дн."


def _send_channel_picker(chat_id: int, prompt: str) -> bool:
    authors = _get_admin_authors(chat_id)
    if not authors:
        _send_bot_message(
            chat_id,
            "Сначала добавьте бота администратором в канал и дайте права "
            "на чтение - их достаточно для работы бота.",
        )
        return False
    keyboard: list[list[dict]] = []
    row: list[dict] = []
    for author in authors:
        row.append({"text": f"@{author.username}", "callback_data": f"channel:{author.id}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    _send_bot_message_with_keyboard(chat_id, prompt, {"inline_keyboard": keyboard})
    return True


def _send_channel_settings_menu(chat_id: int, author: Author) -> None:
    mode_label = "Автопубликация" if author.auto_publish else "Согласование"
    delay_label = _format_delay_label(author.publish_delay_days)
    invite_label = "установлена" if author.invite_url else "не задана"
    comments_notify_label = "включены" if author.notify_comments else "выключены"
    _send_bot_message_with_keyboard(
        chat_id,
        "Настройки для канала "
        f"@{author.username}:\n"
        f"Режим: {mode_label}\n"
        f"Задержка: {delay_label}\n"
        f"Ссылка: {invite_label}\n"
        f"Оповещения о комментариях: {comments_notify_label}",
        {
            "inline_keyboard": [
                [{"text": "Режим публикации", "callback_data": "settings:mode"}],
                [{"text": "Задержка публикации", "callback_data": "settings:delay"}],
                [{"text": "Оповещать о комментариях", "callback_data": "settings:comments_notify"}],
                [{"text": "Ссылка для подписки", "callback_data": "settings:invite"}],
            ]
        },
    )


def _channel_management_keyboard(chat_id: int) -> dict:
    inline_keyboard: list[list[dict]] = [
        [{"text": "Создать сообщество под канал", "callback_data": "channel_flow:create"}],
        [{"text": "Привязать к существующему сообществу", "callback_data": "channel_flow:existing"}],
    ]
    if _get_admin_authors(chat_id):
        inline_keyboard.append(
            [{"text": "Настроить подключенные каналы", "callback_data": "channel_flow:settings"}]
        )
    return {"inline_keyboard": inline_keyboard}


def _send_channel_management_menu(chat_id: int, message_id: int | None = None) -> None:
    text = (
        "Управление каналами:\n"
        "1) Можно создать новое сообщество под Telegram-канал.\n"
        "2) Можно привязать канал к уже существующему сообществу на сайте.\n"
        "3) Если канал уже подключен, можно изменить его настройки."
    )
    keyboard = _channel_management_keyboard(chat_id)
    if message_id:
        _edit_bot_message_with_keyboard(chat_id, message_id, text, keyboard)
        return
    _send_bot_message_with_keyboard(chat_id, text, keyboard)


def _notification_settings_for_chat(chat_id: int) -> tuple[TelegramAccount | None, dict | None]:
    account = TelegramAccount.objects.select_related("user").filter(telegram_id=chat_id).first()
    if not account:
        return None, None
    return account, _notification_service().serialize_notification_settings_for_user(account.user)


def _notification_menu_text(payload: dict) -> str:
    events = payload.get("events") or []
    lines = ["Ваши Telegram-оповещения:"]
    for index, event in enumerate(events, start=1):
        title = str(event.get("title") or event.get("key") or "").strip()
        enabled = bool(event.get("telegram_enabled"))
        lines.append(f"{index}) {title} - {'включены' if enabled else 'выключены'}")
    lines.append("")
    lines.append("Нажмите на пункт ниже, чтобы изменить подписку.")
    return "\n".join(lines)


def _notification_menu_keyboard(payload: dict) -> dict:
    inline_keyboard: list[list[dict]] = []
    for event in payload.get("events") or []:
        event_key = str(event.get("key") or "").strip()
        if not event_key:
            continue
        title = str(event.get("title") or event_key).strip()
        status = "ON" if bool(event.get("telegram_enabled")) else "OFF"
        inline_keyboard.append(
            [{"text": f"{status} {title}", "callback_data": f"notiftoggle:{event_key}"}]
        )
    inline_keyboard.append([{"text": "Назад к каналам", "callback_data": "menu:channels"}])
    return {"inline_keyboard": inline_keyboard}


def _send_notification_settings_menu(chat_id: int, message_id: int | None = None) -> None:
    account, payload = _notification_settings_for_chat(chat_id)
    if not account or not payload:
        text = (
            "Telegram-аккаунт пока не привязан к сайту Тамбур. "
            "Войдите на сайте через Telegram или привяжите Telegram в профиле, "
            "после этого здесь появятся настройки оповещений.\n\n"
            "Сайт: https://tambur.pub/settings#notifications"
        )
        if message_id:
            _edit_bot_message_with_keyboard(
                chat_id,
                message_id,
                text,
                {"inline_keyboard": [[{"text": "К управлению каналами", "callback_data": "menu:channels"}]]},
            )
            return
        _send_bot_message(chat_id, text)
        return

    text = _notification_menu_text(payload)
    keyboard = _notification_menu_keyboard(payload)
    if message_id:
        _edit_bot_message_with_keyboard(chat_id, message_id, text, keyboard)
        return
    _send_bot_message_with_keyboard(chat_id, text, keyboard)


def _send_setup_options(chat_id: int, *, channel_flow: str) -> None:
    BotSession.objects.update_or_create(
        telegram_user_id=chat_id,
        defaults={
            "selected_author": None,
            "invite_waiting": False,
            "instructions_sent": False,
            "mode_selected": False,
            "auto_publish": True,
            "publish_delay_days": 0,
            "channel_flow": channel_flow,
        },
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
    if channel_flow == CHANNEL_FLOW_EXISTING:
        _send_bot_message(
            chat_id,
            "Если хотите привязать канал к существующему сообществу, получите код "
            "подтверждения в настройках профиля на сайте, отправьте его в этот бот, "
            "а затем выберите канал в настройках сообщества на сайте.",
        )
    else:
        _send_bot_message(
            chat_id,
            "Под ваш канал на сайте будет создано одноименное сообщество. "
            "Чтобы управлять им, зарегистрируйтесь на сайте Тамбур.",
        )
    _send_bot_message_with_keyboard(
        chat_id,
        "Выберите задержку публикации:",
        {
            "inline_keyboard": [
                [{"text": "Без задержки", "callback_data": "delay:0"}],
                [{"text": "1 день", "callback_data": "delay:1"}],
                [{"text": "3 дня", "callback_data": "delay:3"}],
                [{"text": "7 дней", "callback_data": "delay:7"}],
            ]
        },
    )


def _send_setup_instructions(
    chat_id: int, auto_publish: bool, delay_days: int, channel_flow: str
) -> None:
    publish_line = (
        "Новые посты будут публиковаться автоматически."
        if auto_publish
        else "Новые посты будут отправляться на согласование в боте."
    )
    delay_line = (
        "Публикация будет с задержкой "
        f"{delay_days} дн."
        if delay_days
        else "Публикация без задержки."
    )
    if channel_flow == CHANNEL_FLOW_EXISTING:
        text = (
            "Отлично! Теперь:\n"
            "1) Получите код подтверждения в настройках профиля на сайте Тамбур.\n"
            "2) Отправьте этот код в бот.\n"
            "3) Добавьте бота в админы канала.\n"
            "4) Дайте права на чтение - их достаточно для работы бота.\n"
            "5) После подключения канала откройте настройки сообщества на сайте и "
            "выберите этот Telegram-канал.\n"
            "6) По желанию добавьте ссылку приглашения на канал.\n"
            "7) Для старых постов - пересылайте их сюда, и они появятся на сайте.\n"
            f"{publish_line}\n"
            f"{delay_line}"
        )
    else:
        text = (
            "Отлично! Теперь:\n"
            "1) Под ваш канал на сайте будет создано одноименное сообщество.\n"
            "2) Чтобы управлять им, зарегистрируйтесь на сайте Тамбур.\n"
            "3) Добавьте бота в админы канала.\n"
            "4) Дайте права на чтение - их достаточно для работы бота.\n"
            "5) По желанию добавьте ссылку приглашения на канал.\n"
            "6) Для старых постов - пересылайте их сюда, и они появятся на сайте.\n"
            f"{publish_line}\n"
            f"{delay_line}"
        )
    _send_bot_message(
        chat_id, text
    )


def _maybe_send_setup_instructions(chat_id: int) -> None:
    session = BotSession.objects.filter(telegram_user_id=chat_id).first()
    if not session or session.instructions_sent:
        return
    if session.mode_selected:
        _send_setup_instructions(
            chat_id,
            session.auto_publish,
            session.publish_delay_days,
            session.channel_flow or CHANNEL_FLOW_CREATE,
        )
        session.instructions_sent = True
        session.save(update_fields=["instructions_sent", "updated_at"])


def _handle_channel_post(message: dict, force_publish: bool = False) -> None:
    chat = message.get("chat", {})
    username = chat.get("username")
    if not username:
        return

    message_id = message.get("message_id")
    if message_id is None:
        return
    if _fv()._is_telegram_service_message(message):
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

    media_group_id = message.get("media_group_id") or ""

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = chat.get("id")
    if token and chat_id:
        if not _is_bot_admin(chat_id, token):
            return
        _refresh_author_from_telegram(author, chat_id, token)
    community_service._ensure_telegram_channel_comun_for_author(author)

    raw_text = _fv()._extract_plain_text(message)
    explicit_tags = _fv()._extract_hashtags(raw_text)
    formatted_text = _fv()._format_telegram_text(raw_text, _fv()._extract_entities(message))
    photo_file_id = _fv()._extract_photo_file_id(message)
    image_url = _fv()._extract_photo_url(message, token) if token else None
    gallery_urls = [image_url] if image_url else []
    embed_html, embed_label = _fv()._extract_telegram_embed(message, username, token)
    poll_html, poll_label = _fv()._extract_telegram_poll(message)
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
                raw_data = _merge_media_group_image(
                    existing_group_post.raw_data or {},
                    image_url=image_url,
                    photo_file_id=photo_file_id,
                    media_group_id=media_group_id,
                )
                existing_urls = list(raw_data.get("gallery_urls") or [])
                if not raw_data.get("formatted_text") and formatted_text:
                    raw_data["formatted_text"] = formatted_text
                if embed_html and not raw_data.get("embed_html"):
                    raw_data["embed_html"] = embed_html
                if poll_html and not raw_data.get("poll_html"):
                    raw_data["poll_html"] = poll_html
                base_text = raw_data.get("formatted_text") or formatted_text
                content = _fv()._build_content_with_images(
                    base_text,
                    existing_urls,
                    raw_data.get("embed_html") or embed_html,
                    raw_data.get("poll_html") or poll_html,
                )
                existing_group_post.content = content
                existing_group_post.original_language = detect_post_language(
                    existing_group_post.title,
                    content,
                    fallback=existing_group_post.original_language,
                )
                existing_group_post.raw_data = raw_data
                existing_group_post.channel_url = f"https://t.me/{username}"
                existing_group_post.source_url = (
                    f"{existing_group_post.channel_url}/{existing_group_post.message_id}"
                )
                existing_group_post.save(
                    update_fields=[
                        "content",
                        "original_language",
                        "raw_data",
                        "channel_url",
                        "source_url",
                        "media_group_id",
                        "updated_at",
                    ]
                )
                if not explicit_tags:
                    explicit_tags = [tag.name for tag in existing_group_post.tags.all()]
                _fv()._apply_post_tags(existing_group_post, explicit_tags)
                return

    has_publishable_content = bool(formatted_text.strip() or gallery_urls or embed_html or poll_html)
    if not has_publishable_content:
        return

    content = _fv()._build_content_with_images(formatted_text, gallery_urls, embed_html, poll_html)
    title = _fv()._build_title(raw_text)
    if not title and poll_label:
        title = poll_label
    if not title and image_url:
        title = "Фото"
    if not title and embed_label:
        title = embed_label
    channel_url = f"https://t.me/{username}"
    source_url = f"{channel_url}/{message_id}"
    delay_days = max(int(author.publish_delay_days or 0), 0)
    publish_at = timezone.now() + timedelta(days=delay_days) if delay_days else None

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
    if poll_html:
        raw_data["poll_html"] = poll_html
    post, created = Post.objects.get_or_create(
        author=author,
        message_id=message_id,
        defaults={
            "title": title,
            "content": content,
            "original_language": detect_post_language(title, content),
            "source_url": source_url,
            "channel_url": channel_url,
            "raw_data": raw_data,
            "is_pending": requires_approval,
            "media_group_id": media_group_id,
            "publish_at": publish_at,
        },
    )

    if not created:
        post.title = title
        post.content = content
        post.source_url = source_url
        post.channel_url = channel_url
        post.raw_data = raw_data
        post.original_language = detect_post_language(
            post.title,
            post.content,
            fallback=post.original_language,
        )
        if media_group_id and not post.media_group_id:
            post.media_group_id = media_group_id
        post.save(
            update_fields=[
                "title",
                "content",
                "source_url",
                "channel_url",
                "raw_data",
                "original_language",
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
        _fv()._maybe_notify_new_author(author, post)
    _fv()._apply_post_tags(post, explicit_tags)


def _attach_verified_user_to_author(chat_id: int, author: Author) -> None:
    session = BotSession.objects.filter(telegram_user_id=chat_id).first()
    verified_user_id = getattr(session, "verified_user_id", None) if session else None
    if not verified_user_id:
        return

    now = timezone.now()
    link, _ = AuthorAdmin.objects.get_or_create(user_id=verified_user_id, author=author)
    update_fields: list[str] = []
    if link.telegram_user_id != chat_id:
        link.telegram_user_id = chat_id
        update_fields.append("telegram_user_id")
    if link.verified_at is None:
        link.verified_at = now
        update_fields.append("verified_at")
    if update_fields:
        link.save(update_fields=update_fields)
    community_service._attach_pending_comuns_for_author(author)


def _handle_verification_code(chat_id: int, code: str) -> None:
    record = (
        AuthorVerificationCode.objects.select_related("user")
        .filter(code__iexact=code, used_at__isnull=True)
        .first()
    )
    if not record:
        _send_bot_message(chat_id, "Код не найден или уже использован.")
        return

    now = timezone.now()
    session, _ = BotSession.objects.get_or_create(telegram_user_id=chat_id)
    session.verified_user_id = record.user_id
    session.save(update_fields=["verified_user_id", "updated_at"])

    authors = Author.objects.filter(admin_chat_id=chat_id, is_blocked=False).order_by("-updated_at")
    linked = []
    for author in authors:
        link, _ = AuthorAdmin.objects.get_or_create(user=record.user, author=author)
        link.telegram_user_id = chat_id
        link.verified_at = now
        link.save(update_fields=["telegram_user_id", "verified_at"])
        community_service._attach_pending_comuns_for_author(author)
        linked.append(f"@{author.username}")

    record.used_at = now
    record.save(update_fields=["used_at"])

    if linked:
        linked_message = "Канал подтверждён: " + ", ".join(linked)
        if session.channel_flow == CHANNEL_FLOW_EXISTING:
            linked_message += (
                ". Теперь откройте настройки нужного сообщества на сайте и выберите "
                "этот Telegram-канал."
            )
        _send_bot_message(chat_id, linked_message)
        return

    _send_bot_message(
        chat_id,
        "Код подтверждения принят. Теперь добавьте бота в канал или перешлите сюда пост из "
        "канала. После подключения канал можно будет привязать к сообществу на сайте.",
    )


def _handle_private_message(message: dict) -> None:
    chat = message.get("chat", {})
    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")
    if not chat_id:
        return

    text = (message.get("text") or "").strip()
    command = ""
    if text.startswith("/"):
        command = text.split(" ", 1)[0].lower()

    if command in {"/start", "/start@comuna_tg_bot"}:
        _send_main_menu(chat_id)
        return

    if command in {"/help", "/help@comuna_tg_bot"} or text.lower() == "помощь":
        _send_bot_message(
            chat_id,
            "Как пользоваться ботом:\n"
            "1) В разделе \"Управление оповещениями\" можно посмотреть и изменить "
            "Telegram-оповещения из сайта.\n"
            "2) В разделе \"Управление каналами\" можно либо создать сообщество под "
            "канал, либо привязать канал к уже существующему сообществу.\n"
            "3) Для работы с каналом добавьте бота админом и дайте права на чтение - "
            "этого достаточно.\n"
            "4) Если канал нужно привязать к существующему сообществу, получите код "
            "подтверждения в настройках профиля на сайте и отправьте его сюда.\n"
            "Сайт: https://tambur.pub/settings",
        )
        return

    if text.upper().startswith("COMUNA-"):
        _handle_verification_code(chat_id, text.strip())
        return

    if text.lower() == "управление оповещениями":
        _send_notification_settings_menu(chat_id)
        return

    if text.lower() in {"управление каналами", "настройка"}:
        _send_channel_management_menu(chat_id)
        return

    if (
        command in {"/settings", "/settings@comuna_tg_bot", "/menu", "/menu@comuna_tg_bot"}
        or text.lower().startswith("меню")
    ):
        _send_main_menu(chat_id)
        return

    if text == "Ссылка для подписки":
        _send_channel_picker(chat_id, "Выберите канал для ссылки приглашения")
        return

    if text.startswith("https://t.me/") or text.startswith("http://t.me/"):
        session = BotSession.objects.filter(telegram_user_id=chat_id).first()
        if session and session.invite_waiting:
            author = session.selected_author
            if not author:
                _send_bot_message(chat_id, "Сначала выберите канал для настройки.")
                return
            invite_url = text.strip()
            session.invite_waiting = False
            session.save(update_fields=["invite_waiting", "updated_at"])
            author.invite_url = invite_url
            author.save(update_fields=["invite_url", "updated_at"])
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

        if not author:
            author, _ = Author.objects.get_or_create(
                username=forward_chat.get("username"),
                defaults={
                    "title": forward_chat.get("title", ""),
                    "channel_url": f"https://t.me/{forward_chat.get('username')}",
                    "channel_id": forward_chat.get("id"),
                },
            )

        if session and author:
            apply_session = session.selected_author is None or session.selected_author_id == author.id
            if apply_session:
                author.auto_publish = session.auto_publish
                author.admin_chat_id = chat_id
                if session.invite_url:
                    author.invite_url = session.invite_url
                if session.publish_delay_days:
                    author.publish_delay_days = session.publish_delay_days
                author.save(
                    update_fields=[
                        "auto_publish",
                        "admin_chat_id",
                        "invite_url",
                        "publish_delay_days",
                        "updated_at",
                    ]
                )
                _attach_verified_user_to_author(chat_id, author)
                if session.selected_author is None:
                    session.invite_waiting = False
                    session.pending_update_post_id = None
                    session.pending_update_message = None
                    session.save(
                        update_fields=[
                            "invite_waiting",
                            "pending_update_post_id",
                            "pending_update_message",
                            "updated_at",
                        ]
                    )

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
        _send_bot_message(chat_id, "Пост добавлен на сайт.")
        return

    _send_bot_message_with_keyboard(
        chat_id,
        "Выберите раздел: управление оповещениями или управление каналами.",
        _main_reply_keyboard(),
    )


def _handle_message(message: dict) -> None:
    chat = message.get("chat", {})
    chat_type = chat.get("type")
    if chat_type == "private":
        _handle_private_message(message)
        return
    if chat_type in {"group", "supergroup"}:
        _handle_group_message(message)


def _handle_my_chat_member(update: dict) -> None:
    chat = update.get("chat", {})
    if chat.get("type") in {"group", "supergroup"}:
        new_member = update.get("new_chat_member", {})
        status = new_member.get("status")
        if status in {"administrator", "member"}:
            chat_id = chat.get("id")
            if chat_id:
                _send_bot_message(
                    chat_id,
                    "Я могу отправлять сообщения из этого чата на модерацию в базу знаний "
                    "или глоссарий сообщества. Создатель или модератор сообщества должен "
                    "привязать чат командой /link_comun slug. После этого отвечайте на "
                    "сообщения командами /kb или /glossary.",
                )
        return

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

    if session and session.selected_author is None:
        author.auto_publish = session.auto_publish
        update_fields.append("auto_publish")
        if session.invite_url:
            author.invite_url = session.invite_url
            update_fields.append("invite_url")
        if session.publish_delay_days:
            author.publish_delay_days = session.publish_delay_days
            update_fields.append("publish_delay_days")

    author.save(update_fields=update_fields)
    _attach_verified_user_to_author(admin_chat_id, author)

    token = settings.TELEGRAM_BOT_TOKEN
    if token:
        _refresh_author_from_telegram(author, f"@{username}", token)
    community_service._ensure_telegram_channel_comun_for_author(author)

    channel_flow = session.channel_flow if session else ""
    if channel_flow == CHANNEL_FLOW_EXISTING:
        if session and session.verified_user_id:
            text = (
                f"Канал @{author.username} подключён. Теперь откройте настройки нужного "
                "сообщества на сайте и выберите этот Telegram-канал."
            )
        else:
            text = (
                f"Канал @{author.username} подключён. Теперь получите код подтверждения "
                "в настройках профиля на сайте, отправьте его в бот, а затем выберите "
                "этот Telegram-канал в настройках сообщества."
            )
    else:
        text = (
            f"Канал @{author.username} подключён. Для него на сайте будет создано "
            "одноименное сообщество. Чтобы управлять им, зарегистрируйтесь на сайте Тамбур."
        )
    _send_bot_message(admin_chat_id, text)


def _handle_callback_query(callback_query: dict) -> None:
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    session = None
    if chat_id:
        session = (
            BotSession.objects.filter(telegram_user_id=chat_id)
            .select_related("selected_author")
            .first()
        )

    if data == "menu:channels" and chat_id:
        _answer_callback_query(callback_id)
        _send_channel_management_menu(chat_id, message_id)
        return

    if data == "channel_flow:create" and chat_id:
        _answer_callback_query(callback_id, "Открываю настройку канала")
        _send_setup_options(chat_id, channel_flow=CHANNEL_FLOW_CREATE)
        return

    if data == "channel_flow:existing" and chat_id:
        _answer_callback_query(callback_id, "Открываю настройку канала")
        _send_setup_options(chat_id, channel_flow=CHANNEL_FLOW_EXISTING)
        return

    if data == "channel_flow:settings" and chat_id:
        _answer_callback_query(callback_id, "Выберите канал")
        _send_channel_picker(chat_id, "Выберите канал для настройки")
        return

    if data.startswith("notiftoggle:") and chat_id:
        event_key = data.split(":", 1)[1].strip()
        account, payload = _notification_settings_for_chat(chat_id)
        if not account or not payload:
            _answer_callback_query(callback_id, "Сначала привяжите Telegram к сайту")
            _send_notification_settings_menu(chat_id, message_id)
            return
        event = next(
            (item for item in payload.get("events") or [] if str(item.get("key") or "").strip() == event_key),
            None,
        )
        if not event:
            _answer_callback_query(callback_id, "Оповещение не найдено")
            return
        updated = _notification_service().update_notification_settings_for_user(
            account.user,
            [{"key": event_key, "telegram_enabled": not bool(event.get("telegram_enabled"))}],
        )
        _answer_callback_query(callback_id, "Подписка обновлена")
        _edit_bot_message_with_keyboard(
            chat_id,
            message_id,
            _notification_menu_text(updated),
            _notification_menu_keyboard(updated),
        )
        return

    if data.startswith("mode:") and chat_id:
        mode = data.split(":", 1)[1]
        auto_publish = mode == "auto"
        if session and session.selected_author:
            author = session.selected_author
            author.auto_publish = auto_publish
            author.save(update_fields=["auto_publish", "updated_at"])
            _answer_callback_query(callback_id, "Настройка сохранена")
            _send_bot_message(chat_id, f"Режим обновлён для @{author.username}.")
            return
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id,
            defaults={"auto_publish": auto_publish, "mode_selected": True},
        )
        _answer_callback_query(callback_id, "Настройка сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("delay:") and chat_id:
        try:
            delay_days = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректная задержка")
            return
        if delay_days not in (0, 1, 3, 7):
            _answer_callback_query(callback_id, "Некорректная задержка")
            return
        if session and session.selected_author:
            author = session.selected_author
            author.publish_delay_days = delay_days
            author.save(update_fields=["publish_delay_days", "updated_at"])
            _answer_callback_query(callback_id, "Задержка сохранена")
            _send_bot_message(
                chat_id,
                f"Задержка публикации обновлена для @{author.username}.",
            )
            return
        BotSession.objects.update_or_create(
            telegram_user_id=chat_id, defaults={"publish_delay_days": delay_days}
        )
        _answer_callback_query(callback_id, "Задержка сохранена")
        _maybe_send_setup_instructions(chat_id)
        return

    if data.startswith("comments_notify:") and chat_id:
        mode = data.split(":", 1)[1]
        if mode not in {"on", "off"}:
            _answer_callback_query(callback_id, "Некорректная настройка")
            return
        notify_comments = mode == "on"
        if not session or not session.selected_author:
            _answer_callback_query(callback_id, "Сначала выберите канал")
            _send_channel_picker(chat_id, "Выберите канал для настройки")
            return
        author = session.selected_author
        author.notify_comments = notify_comments
        author.save(update_fields=["notify_comments", "updated_at"])
        _answer_callback_query(callback_id, "Настройка сохранена")
        _send_bot_message(
            chat_id,
            (
                f"Оповещения о комментариях для @{author.username} "
                f"{'включены' if notify_comments else 'выключены'}."
            ),
        )
        return

    if data.startswith("channel:") and chat_id:
        try:
            author_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный канал")
            return
        author = Author.objects.filter(id=author_id, admin_chat_id=chat_id).first()
        if not author:
            _answer_callback_query(callback_id, "Канал не найден")
            return
        if session:
            session.selected_author = author
            session.invite_waiting = False
            session.save(update_fields=["selected_author", "invite_waiting", "updated_at"])
        else:
            BotSession.objects.update_or_create(
                telegram_user_id=chat_id,
                defaults={"selected_author": author, "invite_waiting": False},
            )
        _answer_callback_query(callback_id, "Канал выбран")
        _send_channel_settings_menu(chat_id, author)
        return

    if data.startswith("settings:") and chat_id:
        action = data.split(":", 1)[1]
        if not session or not session.selected_author:
            _answer_callback_query(callback_id, "Сначала выберите канал")
            _send_channel_picker(chat_id, "Выберите канал для настройки")
            return
        if action == "mode":
            _answer_callback_query(callback_id, "Выберите режим")
            _send_bot_message_with_keyboard(
                chat_id,
                "Выберите режим публикации:",
                {
                    "inline_keyboard": [
                        [{"text": "Автопубликация", "callback_data": "mode:auto"}],
                        [{"text": "Согласование", "callback_data": "mode:approval"}],
                    ]
                },
            )
            return
        if action == "delay":
            _answer_callback_query(callback_id, "Выберите задержку")
            _send_bot_message_with_keyboard(
                chat_id,
                "Выберите задержку публикации:",
                {
                    "inline_keyboard": [
                        [{"text": "Без задержки", "callback_data": "delay:0"}],
                        [{"text": "1 день", "callback_data": "delay:1"}],
                        [{"text": "3 дня", "callback_data": "delay:3"}],
                        [{"text": "7 дней", "callback_data": "delay:7"}],
                    ]
                },
            )
            return
        if action == "comments_notify":
            _answer_callback_query(callback_id, "Выберите режим оповещений")
            _send_bot_message_with_keyboard(
                chat_id,
                "Пользователи могут оставить комментарий к вашим постам на сайте, "
                "хотите бот будет писать вам о новых?",
                {
                    "inline_keyboard": [
                        [{"text": "Оповещать", "callback_data": "comments_notify:on"}],
                        [{"text": "Не оповещать", "callback_data": "comments_notify:off"}],
                    ]
                },
            )
            return
        if action == "invite":
            _answer_callback_query(callback_id, "Ожидаю ссылку")
            _send_bot_message(
                chat_id,
                "Пришлите ссылку приглашения на канал (например, https://t.me/+xxxx).",
            )
            session.invite_waiting = True
            session.save(update_fields=["invite_waiting", "updated_at"])
            return

    if data.startswith("approve:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        post = Post.objects.filter(id=post_id).first()
        if not post:
            _answer_callback_query(callback_id, "Пост не найден")
            return
        if post.is_pending:
            post.is_pending = False
            post.original_language = detect_post_language(
                post.title,
                post.content,
                fallback=post.original_language,
            )
            post.translations.filter(language=post.original_language).delete()
            post.save(update_fields=["is_pending", "original_language", "updated_at"])
            _fv()._maybe_notify_new_author(post.author, post)
            _answer_callback_query(callback_id, "Опубликовано")
            return
        if post.is_blocked:
            _answer_callback_query(callback_id, "Пост уже отклонён")
        else:
            _answer_callback_query(callback_id, "Пост уже опубликован")
        return

    if data.startswith("reject:") and chat_id:
        try:
            post_id = int(data.split(":", 1)[1])
        except ValueError:
            _answer_callback_query(callback_id, "Некорректный пост")
            return
        post = Post.objects.filter(id=post_id).first()
        if not post:
            _answer_callback_query(callback_id, "Пост не найден")
            return
        if post.is_pending:
            post.is_pending = False
            post.is_blocked = True
            post.save(update_fields=["is_pending", "is_blocked", "updated_at"])
            _answer_callback_query(callback_id, "Пропущено")
            return
        if post.is_blocked:
            _answer_callback_query(callback_id, "Пост уже отклонён")
        else:
            _answer_callback_query(callback_id, "Пост уже опубликован")
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


__all__ = [
    "_answer_callback_query",
    "_fetch_telegram_json",
    "_handle_callback_query",
    "_handle_channel_post",
    "_handle_message",
    "_handle_my_chat_member",
    "_handle_private_message",
    "_send_bot_message",
    "_send_bot_message_with_keyboard",
]
