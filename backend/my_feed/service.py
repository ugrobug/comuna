from __future__ import annotations

from django.contrib.auth import get_user_model

from my_feed.models import UserFeedSettings, default_feed_tag_rules

User = get_user_model()

VALID_HOME_FEEDS = {"hot", "mine"}
VALID_INTERFACE_LANGUAGES = {"ru", "en", "es", "pt", "de", "fr", "tr", "id"}
VALID_TAG_RULES = {"hide", "blur"}


def _normalize_unique_string_list(value: object, *, lowercase: bool = False, limit: int = 200) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value[:limit]:
        text = str(item or "").strip()
        if lowercase:
            text = text.lower()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_comun_category_selection(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for raw_comun_slug, raw_category_slugs in value.items():
        comun_slug = str(raw_comun_slug or "").strip()
        if not comun_slug:
            continue
        category_slugs = _normalize_unique_string_list(raw_category_slugs)
        if category_slugs:
            result[comun_slug] = category_slugs
    return result


def _normalize_tag_rules(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return default_feed_tag_rules()
    result: dict[str, str] = {}
    for raw_tag, raw_rule in value.items():
        tag = str(raw_tag or "").strip().lower()
        rule = str(raw_rule or "").strip().lower()
        if not tag or rule not in VALID_TAG_RULES:
            continue
        result[tag] = rule
    return result


def _normalize_interface_language(value: object) -> str:
    language = str(value or "").strip().lower()
    return language if language in VALID_INTERFACE_LANGUAGES else ""


def _get_or_create_user_feed_settings(user: User) -> UserFeedSettings:
    settings, _created = UserFeedSettings.objects.get_or_create(user=user)
    return settings


def _feed_settings_have_customizations(settings: UserFeedSettings) -> bool:
    default_rules = default_feed_tag_rules()
    return any(
        [
            settings.home_feed != "hot",
            bool(settings.hide_read_posts),
            bool(settings.my_feed_authors),
            bool(settings.my_feed_tags),
            bool(settings.my_feed_comuns),
            bool(settings.my_feed_comun_categories),
            bool(settings.hidden_authors),
            not bool(settings.my_feed_hide_negative),
            dict(settings.tag_rules or {}) != default_rules,
            bool(settings.interface_language_manual and settings.interface_language),
            bool(settings.keyboard_shortcuts_hint_dismissed),
        ]
    )


def _serialize_user_feed_settings(settings: UserFeedSettings) -> dict:
    return {
        "home_feed": settings.home_feed if settings.home_feed in VALID_HOME_FEEDS else "hot",
        "hide_read_posts": bool(settings.hide_read_posts),
        "my_feed_authors": _normalize_unique_string_list(settings.my_feed_authors),
        "my_feed_tags": _normalize_unique_string_list(settings.my_feed_tags, lowercase=True),
        "my_feed_comuns": _normalize_unique_string_list(settings.my_feed_comuns),
        "my_feed_comun_categories": _normalize_comun_category_selection(
            settings.my_feed_comun_categories
        ),
        "hidden_authors": _normalize_unique_string_list(settings.hidden_authors),
        "my_feed_hide_negative": bool(settings.my_feed_hide_negative),
        "tag_rules": _normalize_tag_rules(settings.tag_rules),
        "interface_language": (
            _normalize_interface_language(settings.interface_language)
            if settings.interface_language_manual
            else ""
        ),
        "interface_language_manual": bool(settings.interface_language_manual),
        "keyboard_shortcuts_hint_dismissed": bool(settings.keyboard_shortcuts_hint_dismissed),
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def _apply_user_feed_settings_payload(settings: UserFeedSettings, payload: dict) -> UserFeedSettings:
    if "home_feed" in payload:
        home_feed = str(payload.get("home_feed") or "").strip()
        if home_feed in VALID_HOME_FEEDS:
            settings.home_feed = home_feed
    if "hide_read_posts" in payload:
        settings.hide_read_posts = bool(payload.get("hide_read_posts"))
    if "my_feed_authors" in payload:
        settings.my_feed_authors = _normalize_unique_string_list(payload.get("my_feed_authors"))
    if "my_feed_tags" in payload:
        settings.my_feed_tags = _normalize_unique_string_list(
            payload.get("my_feed_tags"), lowercase=True
        )
    if "my_feed_comuns" in payload:
        settings.my_feed_comuns = _normalize_unique_string_list(payload.get("my_feed_comuns"))
    if "my_feed_comun_categories" in payload:
        settings.my_feed_comun_categories = _normalize_comun_category_selection(
            payload.get("my_feed_comun_categories")
        )
    if "hidden_authors" in payload:
        settings.hidden_authors = _normalize_unique_string_list(payload.get("hidden_authors"))
    if "my_feed_hide_negative" in payload:
        settings.my_feed_hide_negative = bool(payload.get("my_feed_hide_negative"))
    if "tag_rules" in payload:
        settings.tag_rules = _normalize_tag_rules(payload.get("tag_rules"))
    if "interface_language" in payload:
        settings.interface_language = _normalize_interface_language(payload.get("interface_language"))
    if "interface_language_manual" in payload:
        settings.interface_language_manual = bool(payload.get("interface_language_manual"))
        if not settings.interface_language_manual:
            settings.interface_language = ""
    if "keyboard_shortcuts_hint_dismissed" in payload:
        settings.keyboard_shortcuts_hint_dismissed = bool(
            payload.get("keyboard_shortcuts_hint_dismissed")
        )
    settings.save()
    return settings


__all__ = [
    "VALID_HOME_FEEDS",
    "VALID_INTERFACE_LANGUAGES",
    "VALID_TAG_RULES",
    "_apply_user_feed_settings_payload",
    "_feed_settings_have_customizations",
    "_get_or_create_user_feed_settings",
    "_serialize_user_feed_settings",
]
