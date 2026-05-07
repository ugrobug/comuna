from __future__ import annotations

import json
import os
import secrets
from datetime import timedelta

from communities import views as community_views
from communities import service as community_service
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, UnidentifiedImageError

from editor.models import (
    POST_TEMPLATE_TYPE_MOVIE_REVIEW,
    PostPollVote,
    PostRatingVote,
)
from editor.serializers import (
    _serialize_post_for_user,
    _serialize_post_rating_block,
    _serialize_post_ratings,
)
from editor.service import (
    _canonical_imdb_url,
    _extract_imdb_id,
    _extract_inline_post_rating_blocks,
    _get_or_create_personal_author,
    _is_post_draft,
    _normalize_editor_block_identifier,
    _normalize_movie_review_template_data,
    _normalize_post_template_payload,
    _requested_template_type,
    _resolve_manual_post_author,
    _resolve_site_post_author_context,
    _set_post_draft_state,
    _sync_template_derived_raw_data,
    _template_not_allowed_error,
)
from editor import service as editor_service
from feeds.models import Post
from users.models import AuthorAdmin


def _fv():
    from feeds import views as feed_views

    return feed_views


def _payload_has_any(payload: dict, keys: tuple[str, ...]) -> bool:
    return any(key in payload for key in keys)


_COMUN_PAYLOAD_KEYS = ("comun_slug", "community_slug", "comun", "community", "comun_id", "community_id")
_COMUN_CATEGORY_PAYLOAD_KEYS = ("comun_category_id", "category_id")


def _payload_comun_slug(payload: dict) -> str:
    for key in ("comun_slug", "community_slug", "comun", "community"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _payload_comun_id(payload: dict) -> int | None:
    for key in ("comun_id", "community_id"):
        value = community_views._parse_post_reference_to_id(payload.get(key))
        if value:
            return value
    return None


def _payload_comun_category_id(payload: dict) -> int | None:
    for key in _COMUN_CATEGORY_PAYLOAD_KEYS:
        if key in payload:
            return community_views._parse_post_reference_to_id(payload.get(key))
    return None


def _post_comun_assignment(post: Post, comun: Comun | None = None) -> ComunPostCategoryAssignment | None:
    queryset = ComunPostCategoryAssignment.objects.select_related("category", "comun").filter(post=post)
    if comun is not None:
        queryset = queryset.filter(comun=comun)
    return queryset.first()


def _post_comun(post: Post) -> Comun | None:
    comun_slug = community_views._post_comun_slug(post)
    if comun_slug:
        comun = Comun.objects.filter(slug=comun_slug).first()
        if comun:
            return comun
    assignment = _post_comun_assignment(post)
    return assignment.comun if assignment else None


def _resolve_payload_comun(
    user,
    payload: dict,
    *,
    post: Post | None = None,
    allow_empty: bool = False,
) -> tuple[Comun | None, str | None]:
    comun_id = _payload_comun_id(payload)
    comun_slug = _payload_comun_slug(payload)
    category_id = _payload_comun_category_id(payload)

    comun = None
    if comun_id:
        comun = Comun.objects.filter(id=comun_id).first()
    elif comun_slug:
        comun = Comun.objects.filter(slug=comun_slug).first()
    elif category_id:
        category = ComunCategory.objects.select_related("comun").filter(id=category_id, is_active=True).first()
        comun = category.comun if category else None
    elif post is not None:
        comun = _post_comun(post)

    if not comun:
        if allow_empty:
            return None, None
        return None, "community required"
    if not comun.is_active and not community_views._comun_is_moderator(user, comun):
        return None, "community not found"
    return comun, None


def _resolve_payload_comun_category(
    payload: dict,
    comun: Comun | None,
    *,
    post: Post | None = None,
) -> tuple[ComunCategory | None, bool, str | None]:
    category_in_payload = _payload_has_any(payload, _COMUN_CATEGORY_PAYLOAD_KEYS)
    if not comun:
        return None, category_in_payload, None

    if category_in_payload:
        category_id = _payload_comun_category_id(payload)
        if not category_id:
            return None, True, None
        category = community_views._active_comun_category_queryset(comun).filter(id=category_id).first()
        if not category:
            return None, True, "category not found"
        return category, True, None

    if post is not None:
        assignment = _post_comun_assignment(post, comun)
        if assignment and assignment.category_id and getattr(assignment.category, "is_active", True):
            return assignment.category, False, None
    return None, False, None


def _apply_comun_membership_to_raw_data(raw_data: dict, comun: Comun | None, category: ComunCategory | None) -> dict:
    next_raw_data = dict(raw_data or {})
    if comun:
        next_raw_data["source"] = "manual_comun"
        next_raw_data["comun_slug"] = comun.slug
        next_raw_data["comun_category_id"] = category.id if category else None
    else:
        if next_raw_data.get("source") == "manual_comun":
            next_raw_data["source"] = "manual"
        next_raw_data.pop("comun_slug", None)
        next_raw_data.pop("comun_category_id", None)
    return next_raw_data


def _sync_comun_category_assignment(
    *,
    post: Post,
    comun: Comun | None,
    category: ComunCategory | None,
    actor,
) -> None:
    if not comun:
        ComunPostCategoryAssignment.objects.filter(post=post).delete()
        return
    ComunPostCategoryAssignment.objects.filter(post=post).exclude(comun=comun).delete()
    if category:
        ComunPostCategoryAssignment.objects.update_or_create(
            comun=comun,
            post=post,
            defaults={"category": category, "assigned_by": actor},
        )
    else:
        ComunPostCategoryAssignment.objects.filter(comun=comun, post=post).delete()


@csrf_exempt
def auth_movie_review_autofill(request: HttpRequest) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    imdb_input = payload.get("imdb_url") or payload.get("imdb") or payload.get("url") or ""
    imdb_id = _extract_imdb_id(imdb_input)
    if not imdb_id:
        return JsonResponse({"ok": False, "error": "invalid imdb url"}, status=400)

    autofill_data: dict[str, object] = {"imdb_url": _canonical_imdb_url(imdb_id)}
    sources: list[str] = []
    warnings: list[str] = []

    cinemeta_data = editor_service._movie_review_autofill_from_cinemeta(imdb_id)
    if cinemeta_data:
        sources.append("cinemeta")
        for key, value in cinemeta_data.items():
            if isinstance(value, str) and value.strip():
                autofill_data[key] = value.strip()

    wikidata_data = editor_service._movie_review_autofill_from_wikidata(imdb_id)
    if wikidata_data:
        sources.append("wikidata")
        for key in ("title", "original_title", "genre", "release_date", "content_kind", "poster_url"):
            value = wikidata_data.get(key)
            if isinstance(value, str) and value.strip() and not autofill_data.get(key):
                autofill_data[key] = value.strip()

    justwatch_data = editor_service._movie_review_autofill_from_justwatch(
        imdb_id,
        title=str(autofill_data.get("title") or ""),
        original_title=str(autofill_data.get("original_title") or ""),
        content_kind=str(autofill_data.get("content_kind") or ""),
    )
    if justwatch_data:
        sources.append("justwatch")
        watch_where = justwatch_data.get("watch_where")
        if isinstance(watch_where, list) and watch_where:
            autofill_data["watch_where"] = watch_where
    else:
        warnings.append("Не удалось определить площадки для просмотра")

    normalized_data, template_error = _normalize_movie_review_template_data(autofill_data)
    if template_error:
        return JsonResponse({"ok": False, "error": template_error}, status=400)
    if not normalized_data:
        return JsonResponse({"ok": False, "error": "could not fetch movie data"}, status=404)

    return JsonResponse(
        {
            "ok": True,
            "imdb_id": imdb_id,
            "sources": sources,
            "warnings": warnings,
            "template": {
                "type": POST_TEMPLATE_TYPE_MOVIE_REVIEW,
                "version": 1,
                "data": normalized_data,
            },
        }
    )


@csrf_exempt
def shared_draft_detail(request: HttpRequest, share_token: str) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    token = str(share_token or "").strip()
    if not token:
        return JsonResponse({"ok": False, "error": "draft not found"}, status=404)

    try:
        post = (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .filter(is_blocked=False, is_pending=True, author__is_blocked=False)
            .get(raw_data__draft=True, raw_data__draft_share_token=token)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "draft not found"}, status=404)

    return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post, user)})


@csrf_exempt
def user_posts(request: HttpRequest) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    author_links, author_ids, _personal_author = _resolve_site_post_author_context(user)

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

        title = (payload.get("title") or "").strip()
        content = (payload.get("content") or "").strip()
        author_source = (payload.get("author_source") or "").strip().lower()
        author_username = (payload.get("author_username") or "").strip()
        is_draft = bool(payload.get("is_draft"))
        comun, comun_error = _resolve_payload_comun(
            user,
            payload,
            allow_empty=is_draft,
        )
        if comun_error:
            status_code = 404 if comun_error == "community not found" else 400
            return JsonResponse({"ok": False, "error": comun_error}, status=status_code)
        comun_category, _category_in_payload, category_error = _resolve_payload_comun_category(
            payload,
            comun,
        )
        if category_error:
            return JsonResponse({"ok": False, "error": category_error}, status=400)
        explicit_tags = _fv()._parse_tag_payload(payload.get("tags"))
        template_payload, template_error = _normalize_post_template_payload(
            payload.get("template"),
            resolve_post_refs=True,
        )
        if template_error:
            return JsonResponse({"ok": False, "error": template_error}, status=400)

        if not is_draft and not title:
            return JsonResponse({"ok": False, "error": "title is required"}, status=400)
        if not is_draft and not content:
            return JsonResponse({"ok": False, "error": "content is required"}, status=400)

        author, author_error = _resolve_manual_post_author(
            user,
            author_links=author_links,
            author_ids=author_ids,
            author_source=author_source,
            author_username=author_username,
            allow_default=is_draft,
        )
        if author_error:
            status_code = 404 if author_error == "author not found" else 400
            return JsonResponse({"ok": False, "error": author_error}, status=status_code)

        requested_template_type = _requested_template_type(template_payload)
        if comun:
            template_access_error = _template_not_allowed_error(
                requested_template_type,
                community_views._allowed_templates_for_comun_category(comun, comun_category),
                scope="comun category" if comun_category else "comun",
            )
            if template_access_error:
                return JsonResponse({"ok": False, "error": template_access_error}, status=400)
        if comun:
            personal_author, personal_author_error = _get_or_create_personal_author(user)
            if personal_author_error:
                return JsonResponse({"ok": False, "error": personal_author_error}, status=400)
            if personal_author:
                author = personal_author

        if comun and not is_draft:
            if bool(getattr(comun, "forbid_external_links", False)) and community_views._payload_contains_external_links(
                title=title,
                content=content,
                template_payload=template_payload,
            ):
                return JsonResponse(
                    {"ok": False, "error": community_views._COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR},
                    status=400,
                )
            can_post, _minimum_rating, author_rating = community_views._comun_post_access_state(
                user,
                comun,
                author=author,
                category=comun_category,
            )
            if not can_post:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": community_views._comun_post_access_error_message(
                            comun,
                            author_rating=author_rating,
                            category=comun_category,
                        ),
                    },
                    status=403,
                )

        channel_url = author.invite_url or author.channel_url
        try:
            message_id = _fv()._generate_manual_message_id(author)
        except ValueError:
            return JsonResponse({"ok": False, "error": "unable to create post"}, status=500)
        delay_days = max(int(author.publish_delay_days or 0), 0)
        publish_at = timezone.now() + timedelta(days=delay_days) if (delay_days and not is_draft) else None

        raw_data = {
            "source": "manual",
            **({"template": template_payload} if template_payload else {}),
        }
        raw_data = _apply_comun_membership_to_raw_data(raw_data, comun, comun_category)
        _sync_template_derived_raw_data(raw_data, template_payload, content)
        raw_data = _set_post_draft_state(raw_data, is_draft)

        post = Post.objects.create(
            author=author,
            message_id=message_id,
            title=title,
            content=content,
            channel_url=channel_url,
            source_url=channel_url,
            raw_data=raw_data,
            is_pending=is_draft,
            is_blocked=False,
            publish_at=publish_at,
        )
        _sync_comun_category_assignment(
            post=post,
            comun=comun,
            category=comun_category,
            actor=user,
        )
        _fv()._apply_post_tags(post, explicit_tags)
        if not is_draft:
            _fv()._maybe_notify_new_author(author, post)
            community_service._recalculate_comun_ratings_for_post(post)
        return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post, user)})

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

    if not author_ids:
        return JsonResponse({"ok": True, "posts": [], "total": 0})

    posts_qs = (
        Post.objects.filter(author_id__in=author_ids, is_blocked=False, author__is_blocked=False)
        .select_related("author")
        .prefetch_related("tags")
        .order_by("-created_at")
    )

    total = posts_qs.count()
    posts = posts_qs[offset : offset + limit]
    serialized = [_serialize_post_for_user(request, post, user) for post in posts]
    return JsonResponse({"ok": True, "posts": serialized, "total": total})


@csrf_exempt
def user_upload(request: HttpRequest) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    upload = request.FILES.get("image") or request.FILES.get("file") or request.FILES.get("images[]")
    if not upload:
        return JsonResponse({"ok": False, "error": "image is required"}, status=400)

    content_type = (getattr(upload, "content_type", "") or "").lower()
    if not content_type.startswith("image/"):
        return JsonResponse({"ok": False, "error": "unsupported file type"}, status=400)

    max_bytes = getattr(settings, "USER_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
    if upload.size and upload.size > max_bytes:
        return JsonResponse({"ok": False, "error": "file is too large"}, status=400)

    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image.verify()
        upload.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid image file"}, status=400)

    base_name = get_valid_filename(os.path.splitext(upload.name or "image")[0])
    ext = os.path.splitext(upload.name or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    filename = f"uploads/manual/{base_name}-{secrets.token_hex(8)}{ext}"
    saved_path = default_storage.save(filename, upload)
    relative_url = default_storage.url(saved_path)
    site_base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    if site_base:
        url = f"{site_base}{relative_url}"
    else:
        url = request.build_absolute_uri(relative_url)

    return JsonResponse({"ok": True, "url": url})


@csrf_exempt
def user_post_update(request: HttpRequest, post_id: int) -> HttpResponse:
    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in {"GET", "PATCH", "PUT", "DELETE"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        post = Post.objects.select_related("author").get(
            id=post_id, is_blocked=False, author__is_blocked=False
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    previous_comun_ids = community_service._candidate_comun_ids_for_post(post)

    author_links, author_ids, personal_author = _resolve_site_post_author_context(user)
    is_linked = AuthorAdmin.objects.filter(
        user=user, author=post.author, verified_at__isnull=False
    ).exists()
    is_personal_author_owner = bool(personal_author and personal_author.id == post.author_id)
    can_staff_delete = bool(user.is_staff and request.method == "DELETE")
    if not is_linked and not is_personal_author_owner and not can_staff_delete:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    if request.method == "GET":
        if not is_linked and not is_personal_author_owner and not user.is_staff:
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post, user)})

    if request.method == "DELETE":
        raw_data = dict(post.raw_data or {})
        raw_data["manual_deleted"] = True
        raw_data["manual_deleted_at"] = timezone.now().isoformat()
        if user.is_staff and not is_linked:
            raw_data["manual_deleted_by_staff"] = True
            raw_data["manual_deleted_by_staff_user_id"] = user.id
            raw_data["manual_deleted_by_staff_username"] = user.username
        post.is_blocked = True
        post.raw_data = raw_data
        post.save(update_fields=["is_blocked", "raw_data", "updated_at"])
        for comun_id in previous_comun_ids:
            community_service._recalculate_comun_rating(comun_id)
        return JsonResponse({"ok": True, "deleted": True, "post_id": post.id})

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    title = payload.get("title") if "title" in payload else None
    content = payload.get("content") if "content" in payload else None
    tags_payload = payload.get("tags") if "tags" in payload else None
    author_in_payload = "author_username" in payload or "author_source" in payload
    comun_in_payload = _payload_has_any(payload, _COMUN_PAYLOAD_KEYS)
    comun_category_in_payload = _payload_has_any(payload, _COMUN_CATEGORY_PAYLOAD_KEYS)
    template_in_payload = "template" in payload
    draft_in_payload = "is_draft" in payload

    current_is_draft = _is_post_draft(post)
    target_is_draft = bool(payload.get("is_draft")) if draft_in_payload else current_is_draft

    next_comun, comun_error = _resolve_payload_comun(
        user,
        payload,
        post=post,
        allow_empty=target_is_draft,
    )
    if comun_error:
        status_code = 404 if comun_error == "community not found" else 400
        return JsonResponse({"ok": False, "error": comun_error}, status=status_code)
    next_comun_category, category_was_provided, category_error = _resolve_payload_comun_category(
        payload,
        next_comun,
        post=post,
    )
    if category_error:
        return JsonResponse({"ok": False, "error": category_error}, status=400)
    if comun_in_payload and not comun_category_in_payload:
        next_comun_category = None

    template_payload = None
    if template_in_payload:
        template_payload, template_error = _normalize_post_template_payload(
            payload.get("template"),
            resolve_post_refs=True,
        )
        if template_error:
            return JsonResponse({"ok": False, "error": template_error}, status=400)

    next_author = post.author
    if author_in_payload:
        author_source = str(payload.get("author_source") or "").strip().lower()
        author_username = str(payload.get("author_username") or "").strip()
        next_author, author_error = _resolve_manual_post_author(
            user,
            author_links=author_links,
            author_ids=author_ids,
            author_source=author_source,
            author_username=author_username,
            allow_default=target_is_draft,
        )
        if author_error:
            status_code = 404 if author_error == "author not found" else 400
            return JsonResponse({"ok": False, "error": author_error}, status=status_code)

    if next_comun:
        personal_author, personal_author_error = _get_or_create_personal_author(user)
        if personal_author_error:
            return JsonResponse({"ok": False, "error": personal_author_error}, status=400)
        if personal_author:
            next_author = personal_author

    raw_data = dict(post.raw_data or {})
    raw_data_changed = False

    if content is not None:
        post.content = str(content).strip()

    if template_in_payload:
        requested_template_type = _requested_template_type(template_payload)
        if next_comun:
            template_access_error = _template_not_allowed_error(
                requested_template_type,
                community_views._allowed_templates_for_comun_category(
                    next_comun, next_comun_category
                ),
                scope="comun category" if next_comun_category else "comun",
            )
        else:
            template_access_error = None
        if template_access_error:
            return JsonResponse({"ok": False, "error": template_access_error}, status=400)
        if template_payload:
            raw_data["template"] = template_payload
        else:
            raw_data.pop("template", None)
        _sync_template_derived_raw_data(raw_data, template_payload, post.content)
        raw_data["manual_edit"] = True
        raw_data["manual_updated_at"] = timezone.now().isoformat()
        raw_data_changed = True

    if content is not None or template_in_payload:
        effective_template_payload = raw_data.get("template") if isinstance(raw_data.get("template"), dict) else None
        _sync_template_derived_raw_data(raw_data, effective_template_payload, post.content)
        raw_data_changed = True

    if title is not None:
        title = str(title).strip()
        if target_is_draft:
            post.title = title[:255]
        elif title:
            post.title = title[:255]
        else:
            source_text = _fv()._strip_html(post.content)
            post.title = _fv()._build_title(source_text)

    if not target_is_draft and not next_comun:
        return JsonResponse({"ok": False, "error": "community required"}, status=400)

    if next_comun and not target_is_draft:
        effective_template_payload = raw_data.get("template") if isinstance(raw_data.get("template"), dict) else None
        if bool(getattr(next_comun, "forbid_external_links", False)) and community_views._payload_contains_external_links(
            title=post.title,
            content=post.content,
            template_payload=effective_template_payload,
        ):
            return JsonResponse(
                {"ok": False, "error": community_views._COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR},
                status=400,
            )
        can_post, _minimum_rating, author_rating = community_views._comun_post_access_state(
            user,
            next_comun,
            author=next_author,
            category=next_comun_category,
        )
        if not can_post:
            return JsonResponse(
                {
                    "ok": False,
                    "error": community_views._comun_post_access_error_message(
                        next_comun,
                        author_rating=author_rating,
                        category=next_comun_category,
                    ),
                },
                status=403,
            )

    if author_in_payload or next_author.id != post.author_id:
        post.author = next_author
        channel_url = next_author.invite_url or next_author.channel_url
        post.channel_url = channel_url
        post.source_url = channel_url

    if comun_in_payload or comun_category_in_payload or category_was_provided or next_comun:
        raw_data = _apply_comun_membership_to_raw_data(raw_data, next_comun, next_comun_category)
        raw_data_changed = True

    if target_is_draft:
        raw_data_changed = True
    if current_is_draft != target_is_draft:
        raw_data_changed = True
    raw_data = _set_post_draft_state(raw_data, target_is_draft)

    if raw_data_changed:
        post.raw_data = raw_data

    post.is_pending = target_is_draft
    if target_is_draft:
        post.publish_at = None
    elif current_is_draft and not target_is_draft:
        delay_days = max(int(post.author.publish_delay_days or 0), 0)
        post.publish_at = timezone.now() + timedelta(days=delay_days) if delay_days else None

    post.save(
        update_fields=[
            "author",
            "title",
            "content",
            "channel_url",
            "source_url",
            "is_pending",
            "publish_at",
            "raw_data",
            "updated_at",
        ]
    )
    _sync_comun_category_assignment(
        post=post,
        comun=next_comun,
        category=next_comun_category,
        actor=user,
    )
    if tags_payload is not None:
        explicit_tags = _fv()._parse_tag_payload(tags_payload)
    else:
        explicit_tags = [tag.name for tag in post.tags.all()]
    _fv()._apply_post_tags(post, explicit_tags)
    if current_is_draft and not target_is_draft:
        _fv()._maybe_notify_new_author(post.author, post)
    if (
        current_is_draft != target_is_draft
        or next_comun
        or comun_in_payload
        or comun_category_in_payload
        or tags_payload is not None
    ):
        for comun_id in previous_comun_ids:
            community_service._recalculate_comun_rating(comun_id)
        community_service._recalculate_comun_ratings_for_post(post)
    return JsonResponse({"ok": True, "post": _serialize_post_for_user(request, post, user)})


@csrf_exempt
def post_poll_vote(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        post = (
            Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_fv()._publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    raw_poll = raw_data.get("poll")
    poll_payload = _fv()._build_poll_payload(raw_poll)
    if not poll_payload:
        return JsonResponse({"ok": False, "error": "poll not found"}, status=404)
    if poll_payload.get("is_closed"):
        return JsonResponse({"ok": False, "error": "poll is closed"}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "invalid payload"}, status=400)

    submitted_options = payload.get("options")
    if submitted_options is None and "option" in payload:
        submitted_options = [payload.get("option")]
    if submitted_options is None:
        return JsonResponse({"ok": False, "error": "options are required"}, status=400)

    options_count = len(poll_payload.get("options") or [])
    normalized = _fv()._parse_poll_selection_payload(submitted_options, options_count)
    if normalized is None:
        return JsonResponse({"ok": False, "error": "invalid poll options"}, status=400)

    allows_multiple = bool(poll_payload.get("allows_multiple_answers"))
    if not allows_multiple and len(normalized) > 1:
        return JsonResponse({"ok": False, "error": "multiple options are not allowed"}, status=400)

    existing = PostPollVote.objects.filter(post=post, user=user).first()
    existing_selection = (
        _fv()._normalize_poll_selection(existing.selected_options, options_count) if existing else []
    )
    if existing_selection:
        live_poll = _fv()._live_poll_for_post(post, user)
        if not live_poll:
            return JsonResponse({"ok": False, "error": "poll not found"}, status=404)
        if normalized == existing_selection:
            return JsonResponse({"ok": True, "poll": live_poll["poll"], "poll_html": live_poll["html"]})
        return JsonResponse(
            {
                "ok": False,
                "error": "Вы уже проголосовали в этом опросе",
                "poll": live_poll["poll"],
                "poll_html": live_poll["html"],
            },
            status=400,
        )

    if not normalized:
        return JsonResponse({"ok": False, "error": "options are required"}, status=400)

    PostPollVote.objects.create(post=post, user=user, selected_options=normalized)

    live_poll = _fv()._live_poll_for_post(post, user)
    if not live_poll:
        return JsonResponse({"ok": False, "error": "poll not found"}, status=404)
    return JsonResponse({"ok": True, "poll": live_poll["poll"], "poll_html": live_poll["html"]})


@csrf_exempt
def post_rating_vote(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _fv()._get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        post = (
            Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_fv()._publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "invalid payload"}, status=400)

    raw_value = payload.get("value", payload.get("rating", payload.get("score")))
    try:
        rating_value = int(raw_value)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid rating value"}, status=400)

    if rating_value < 1 or rating_value > 10:
        return JsonResponse({"ok": False, "error": "invalid rating value"}, status=400)

    available_block_ids = _extract_inline_post_rating_blocks(post.content or "")
    if not available_block_ids:
        return JsonResponse({"ok": False, "error": "rating is not available"}, status=400)

    raw_block_id = str(payload.get("block_id") or payload.get("rating_block_id") or "").strip()
    if raw_block_id:
        block_id = _normalize_editor_block_identifier(
            raw_block_id,
            fallback_prefix="post-rating",
            fallback_index=0,
        )
    elif len(available_block_ids) == 1:
        block_id = available_block_ids[0]
    else:
        return JsonResponse({"ok": False, "error": "block_id is required"}, status=400)

    if block_id not in available_block_ids:
        return JsonResponse({"ok": False, "error": "rating block not found"}, status=404)

    PostRatingVote.objects.update_or_create(
        post=post,
        user=user,
        block_id=block_id,
        defaults={"value": rating_value},
    )

    rating_payload = _serialize_post_rating_block(post, user, block_id)
    return JsonResponse(
        {
            "ok": True,
            "block_id": block_id,
            "post_rating": rating_payload,
            "post_ratings": _serialize_post_ratings(post, user),
        }
    )


__all__ = [
    "auth_movie_review_autofill",
    "post_poll_vote",
    "post_rating_vote",
    "shared_draft_detail",
    "user_post_update",
    "user_posts",
    "user_upload",
]
