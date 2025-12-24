from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from django.db.models import F, IntegerField, Value
from django.db.models.functions import Cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Author, Post, Rubric


def _media_url(request: HttpRequest, field) -> str | None:
    if not field:
        return None
    try:
        return request.build_absolute_uri(field.url)
    except Exception:
        return None


def _build_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().splitlines()[0].strip()
    if len(first_line) <= 120:
        return first_line
    return first_line[:117] + "..."


def _extract_content(message: dict) -> str:
    return (message.get("text") or message.get("caption") or "").strip()


def _fetch_telegram_json(method: str, token: str, payload: dict) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        timeout = 30 if method == "getUpdates" else 5
        with urllib.request.urlopen(url, data=data, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _send_bot_message(chat_id: int, text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    _fetch_telegram_json("sendMessage", token, {"chat_id": chat_id, "text": text})


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


def _handle_channel_post(message: dict) -> None:
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

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = chat.get("id")
    if token and chat_id:
        _refresh_author_from_telegram(author, chat_id, token)

    content = _extract_content(message)
    title = _build_title(content)
    channel_url = f"https://t.me/{username}"
    source_url = f"{channel_url}/{message_id}"

    post, created = Post.objects.get_or_create(
        author=author,
        message_id=message_id,
        defaults={
            "title": title,
            "content": content,
            "source_url": source_url,
            "channel_url": channel_url,
            "raw_data": message,
        },
    )

    if not created:
        post.title = title
        post.content = content
        post.source_url = source_url
        post.channel_url = channel_url
        post.raw_data = message
        post.save(update_fields=["title", "content", "source_url", "channel_url", "raw_data", "updated_at"])


def _handle_private_message(message: dict) -> None:
    chat = message.get("chat", {})
    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")
    if not chat_id:
        return

    text = (message.get("text") or "").strip()
    if text in {"/start", "/help"}:
        _send_bot_message(
            chat_id,
            "Как подключить канал:\n"
            "1) Добавьте бота админом в ваш канал.\n"
            "2) Дайте права: «Читать сообщения» и «Публиковать сообщения».\n"
            "3) Опубликуйте новый пост — он появится на сайте.\n\n"
            "Догрузка истории: пересылайте посты из канала сюда, и они будут добавлены на сайт.",
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

        forwarded = {
            "chat": forward_chat,
            "message_id": forward_message_id,
            "text": message.get("text"),
            "caption": message.get("caption"),
        }
        _handle_channel_post(forwarded)
        _send_bot_message(chat_id, "Пост добавлен на сайт.")
        return

    _send_bot_message(
        chat_id,
        "Перешлите пост из канала, чтобы добавить его на сайт. Для помощи — /help.",
    )


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
        Post.objects.filter(author=author, is_blocked=False)
        .order_by("-created_at")
        .all()[:limit]
    )

    posts_count = Post.objects.filter(author=author, is_blocked=False).count()
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
                "channel_url": post.channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": author.username,
                    "title": author.title,
                    "channel_url": author.channel_url,
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
                "channel_url": author.channel_url,
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
        Post.objects.filter(rubric=rubric, is_blocked=False, author__is_blocked=False)
        .order_by("-created_at")
        .all()[:limit]
    )

    serialized = [
        {
            "id": post.id,
            "title": post.title,
            "rubric": rubric.name,
            "rubric_slug": rubric.slug,
            "rubric_icon_url": _media_url(request, rubric.icon_url),
            "content": post.content,
            "source_url": post.source_url,
            "channel_url": post.channel_url,
            "created_at": post.created_at.isoformat(),
            "author": {
                "username": post.author.username,
                "title": post.author.title,
                "channel_url": post.author.channel_url,
                "avatar_url": post.author.avatar_url,
            },
        }
        for post in posts
    ]

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
            id=post_id, is_blocked=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    rubric = post.rubric
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
                "channel_url": post.channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": post.author.title,
                    "channel_url": post.author.channel_url,
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
                rubric=rubric, is_blocked=False, author__is_blocked=False
            )
            .annotate(
                score=Cast(F("rating"), IntegerField())
                + Cast(F("comments_count"), IntegerField()) * Value(5)
            )
            .order_by("-score", "-created_at")[:limit]
        )

        for post in posts:
            serialized_posts.append(
                {
                    "id": post.id,
                    "title": post.title,
                    "rubric": rubric.name,
                    "rubric_slug": rubric.slug,
                    "rubric_icon_url": _media_url(request, rubric.icon_url),
                    "content": post.content,
                    "source_url": post.source_url,
                    "channel_url": post.channel_url,
                    "created_at": post.created_at.isoformat(),
                    "author": {
                        "username": post.author.username,
                        "title": post.author.title,
                        "channel_url": post.author.channel_url,
                        "avatar_url": post.author.avatar_url,
                    },
                    "score": post.rating + post.comments_count * 5,
                    "rating": post.rating,
                    "comments_count": post.comments_count,
                }
            )

    return JsonResponse({"ok": True, "posts": serialized_posts})
