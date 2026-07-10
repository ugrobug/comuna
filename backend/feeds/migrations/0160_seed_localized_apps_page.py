import base64
import json

from django.db import migrations
from django.utils import timezone


STORE_LINKS = (
    '<span style="display:flex; flex-wrap:wrap; gap:12px; align-items:center;">'
    '<a href="https://play.google.com/store/apps/details?id=ru.comuna.mobile" target="_blank" '
    'rel="noopener noreferrer" style="display:inline-flex; align-items:center; justify-content:center; '
    'min-height:44px; padding:0 18px; border-radius:10px; background:#111827; color:#ffffff; '
    'font-weight:600; text-decoration:none;">Google Play</a>'
    '<a href="https://www.rustore.ru/catalog/app/ru.comuna.mobile?_rsc=tf3rt" target="_blank" '
    'rel="noopener noreferrer" style="display:inline-flex; align-items:center; justify-content:center; '
    'min-height:44px; padding:0 18px; border-radius:10px; background:#0f766e; color:#ffffff; '
    'font-weight:600; text-decoration:none;">RuStore</a></span>'
)

LOCALIZATIONS = {
    "ru": ("Приложения", "Читайте ленту, статьи и сообщества Тамбура в мобильном приложении."),
    "en": ("Apps", "Read your feed, articles, and Tambur communities in the mobile app."),
    "es": (
        "Aplicaciones",
        "Lee tu feed, artículos y comunidades de Tambur en la aplicación móvil.",
    ),
    "pt": ("Aplicativos", "Leia seu feed, artigos e comunidades do Tambur no aplicativo móvel."),
    "de": ("Apps", "Lies deinen Feed, Artikel und Tambur-Communitys in der mobilen App."),
    "fr": (
        "Applications",
        "Consultez votre fil, les articles et les communautés Tambur dans l'application mobile.",
    ),
    "tr": ("Uygulamalar", "Akışınızı, makaleleri ve Tambur topluluklarını mobil uygulamada okuyun."),
    "id": ("Aplikasi", "Baca feed, artikel, dan komunitas Tambur melalui aplikasi seluler."),
}


def encode_content(intro):
    payload = {
        "blocks": [
            {"type": "paragraph", "data": {"text": intro}},
            {"type": "paragraph", "data": {"text": STORE_LINKS}},
        ]
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def seed_apps_page(apps, schema_editor):
    StaticPageContent = apps.get_model("feeds", "StaticPageContent")
    StaticPageTranslation = apps.get_model("feeds", "StaticPageTranslation")
    ContentTranslationTask = apps.get_model("feeds", "ContentTranslationTask")

    russian_title, russian_intro = LOCALIZATIONS["ru"]
    page, _created = StaticPageContent.objects.get_or_create(
        slug="apps",
        defaults={
            "title": russian_title,
            "content": encode_content(russian_intro),
        },
    )
    page_updates = []
    if not (page.title or "").strip():
        page.title = russian_title
        page_updates.append("title")
    if not (page.content or "").strip():
        page.content = encode_content(russian_intro)
        page_updates.append("content")
    if page_updates:
        page.save(update_fields=[*page_updates, "updated_at"])

    for language, (title, intro) in LOCALIZATIONS.items():
        if language == "ru":
            continue
        translation, created = StaticPageTranslation.objects.get_or_create(
            page_id=page.pk,
            language=language,
            defaults={
                "status": "translated",
                "title": title,
                "content": encode_content(intro),
                "model": "manual",
                "raw_response": {"source": "seed_localized_apps_page"},
            },
        )
        if not created and translation.status != "translated":
            translation.status = "translated"
            translation.title = title
            translation.content = encode_content(intro)
            translation.model = "manual"
            translation.error_message = ""
            translation.raw_response = {"source": "seed_localized_apps_page"}
            translation.save(
                update_fields=[
                    "status",
                    "title",
                    "content",
                    "model",
                    "error_message",
                    "raw_response",
                    "updated_at",
                ]
            )

    for existing_page in StaticPageContent.objects.exclude(pk=page.pk):
        ContentTranslationTask.objects.update_or_create(
            kind="static_page",
            object_id=existing_page.pk,
            defaults={
                "status": "pending",
                "scheduled_at": timezone.now(),
                "source_updated_at": existing_page.updated_at,
                "attempts": 0,
                "last_error": "",
                "locked_at": None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0159_userfeedsettings_interface_language_manual"),
    ]

    operations = [
        migrations.RunPython(seed_apps_page, migrations.RunPython.noop),
    ]
