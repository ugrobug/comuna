from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from feeds.language_detection import detect_post_language
from feeds.models import Author, Post


class TelegramMediaDownloadError(RuntimeError):
    """A received photo must be retried rather than acknowledged without its file."""


class TelegramChannelPostWriter:
    """Serialize album creation and merging; network I/O stays outside row locks."""

    def __init__(self, views):
        self.views = views

    def save(self, *, author, message, **prepared):
        with transaction.atomic():
            if message.get("media_group_id"):
                # Evaluate the query, and hold this lock through first-row creation too.
                Author.objects.select_for_update().only("pk").get(pk=author.pk)
            return self._save(author=author, message=message, **prepared)

    def _save(self, *, author, message, formatted_text, raw_text, explicit_tags,
              photo_file_id, image_url, embed_html, embed_label, poll_html,
              poll_label, force_publish):
        username = message["chat"]["username"]
        message_id = message["message_id"]
        media_group_id = message.get("media_group_id") or ""
        gallery_urls = [image_url] if image_url else []
        if media_group_id:
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
                previous_raw = dict(existing_group_post.raw_data or {})
                if "gallery_message_ids" not in previous_raw and len(previous_raw.get("gallery_urls") or []) == 1:
                    previous_raw["gallery_message_ids"] = [existing_group_post.message_id]
                raw_data = self.merge_image(
                    previous_raw,
                    image_url=image_url,
                    photo_file_id=photo_file_id,
                    media_group_id=media_group_id,
                    message_id=message_id,
                )
                existing_urls = list(raw_data.get("gallery_urls") or [])
                if not raw_data.get("formatted_text") and formatted_text:
                    raw_data["formatted_text"] = formatted_text
                if embed_html and not raw_data.get("embed_html"):
                    raw_data["embed_html"] = embed_html
                if poll_html and not raw_data.get("poll_html"):
                    raw_data["poll_html"] = poll_html
                base_text = raw_data.get("formatted_text") or formatted_text
                content = self.views._build_content_with_images(
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
                self.views._apply_post_tags(existing_group_post, explicit_tags)
                return existing_group_post, False

        has_publishable_content = bool(formatted_text.strip() or gallery_urls or embed_html or poll_html)
        if not has_publishable_content:
            return None, False

        content = self.views._build_content_with_images(formatted_text, gallery_urls, embed_html, poll_html)
        title = self.views._build_title(raw_text)
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
            raw_data["gallery_message_ids"] = [message_id]
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

        self.views._apply_post_tags(post, explicit_tags)
        return post, created

    @staticmethod
    def unique_nonempty(values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(normalized)
        return unique_values

    @staticmethod
    def merge_image(
        raw_data: dict,
        *,
        image_url: str | None,
        photo_file_id: str | None,
        media_group_id: str,
        message_id: int | None = None,
    ) -> dict:
        next_raw_data = dict(raw_data or {})
        existing_urls = TelegramChannelPostWriter.unique_nonempty(list(next_raw_data.get("gallery_urls") or []))
        existing_file_ids = TelegramChannelPostWriter.unique_nonempty(list(next_raw_data.get("gallery_file_ids") or []))
        photo_file_seen = bool(photo_file_id and photo_file_id in existing_file_ids)
        message_ids = list(next_raw_data.get("gallery_message_ids") or [])
        message_seen = message_id is not None and message_id in message_ids

        if image_url and not photo_file_seen and not message_seen and image_url not in existing_urls:
            existing_urls.append(image_url)
            if message_id is not None:
                message_ids.append(message_id)
        if message_ids and len(message_ids) == len(existing_urls):
            # Downloads can finish out of order; retain the Telegram message order.
            ordered = sorted(zip(message_ids, existing_urls))
            next_raw_data["gallery_message_ids"] = [item[0] for item in ordered]
            existing_urls = [item[1] for item in ordered]
            if len(existing_file_ids) == len(message_ids) - 1 and photo_file_id and not photo_file_seen and not message_seen:
                existing_file_ids.append(photo_file_id)
                existing_file_ids = [file_id for _, file_id in sorted(zip(message_ids, existing_file_ids))]
                photo_file_seen = True
        next_raw_data["gallery_urls"] = existing_urls

        if photo_file_id and not photo_file_seen and not message_seen:
            existing_file_ids.append(photo_file_id)
        # Public-page recovery cannot reconstruct Bot API file IDs. A partial ID
        # list would make the image rehydrator truncate a complete local gallery.
        if next_raw_data.get("gallery_file_ids_complete") is False:
            next_raw_data["gallery_file_ids"] = []
        elif existing_file_ids:
            next_raw_data["gallery_file_ids"] = existing_file_ids

        next_raw_data["media_group_id"] = media_group_id
        return next_raw_data
