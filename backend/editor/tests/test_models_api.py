from django.apps import apps
import json
from django.test import SimpleTestCase, TestCase

from editor import service as editor_service
from editor.models import (
    ComunCustomPostTemplate,
    ComunCustomPostTemplateBlock,
    ComunCustomPostTemplateField,
    POST_TEMPLATE_TYPE_MOVIE_REVIEW,
    PostPollVote,
    PostRatingVote,
    POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS,
    PostTemplateConfig,
    configured_post_template_type_values,
    normalize_allowed_post_templates,
    post_template_type_choices,
)


class EditorModelsApiTests(SimpleTestCase):
    def test_editor_app_is_installed(self):
        self.assertTrue(apps.is_installed("editor"))

    def test_editor_models_keep_feeds_app_label(self):
        self.assertEqual(PostTemplateConfig._meta.app_label, "feeds")
        self.assertEqual(ComunCustomPostTemplate._meta.app_label, "feeds")
        self.assertEqual(ComunCustomPostTemplateBlock._meta.app_label, "feeds")
        self.assertEqual(ComunCustomPostTemplateField._meta.app_label, "feeds")
        self.assertEqual(PostPollVote._meta.app_label, "feeds")
        self.assertEqual(PostRatingVote._meta.app_label, "feeds")

    def test_editor_models_remain_available_through_feeds_app_label(self):
        self.assertIs(apps.get_model("feeds", "PostTemplateConfig"), PostTemplateConfig)
        self.assertIs(apps.get_model("feeds", "ComunCustomPostTemplate"), ComunCustomPostTemplate)
        self.assertIs(
            apps.get_model("feeds", "ComunCustomPostTemplateBlock"),
            ComunCustomPostTemplateBlock,
        )
        self.assertIs(
            apps.get_model("feeds", "ComunCustomPostTemplateField"),
            ComunCustomPostTemplateField,
        )
        self.assertIs(apps.get_model("feeds", "PostPollVote"), PostPollVote)
        self.assertIs(apps.get_model("feeds", "PostRatingVote"), PostRatingVote)

    def test_custom_template_editor_exposes_full_editor_block_list(self):
        option_values = {item["value"] for item in POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS}
        self.assertIn("table", option_values)
        self.assertIn("post_link", option_values)
        self.assertIn("music", option_values)
        self.assertIn("movie_card", option_values)
        self.assertIn("post_rating", option_values)


class DynamicPostTemplateConfigTests(TestCase):
    def test_custom_template_config_is_available_as_post_template_type(self):
        PostTemplateConfig.objects.create(
            template_type="custom_123",
            label="Отзыв",
            description="Шаблон для отзывов о продукте",
            enabled_editor_blocks=["header", "table"],
        )

        self.assertEqual(normalize_allowed_post_templates(["custom_123"]), ["custom_123"])
        options = editor_service._serialize_post_template_type_options()
        self.assertIn(
            {
                "value": "custom_123",
                "label": "Отзыв",
                "description": "Шаблон для отзывов о продукте",
            },
            options,
        )
        blocks_by_template = editor_service._template_editor_blocks_by_template()
        self.assertEqual(blocks_by_template["custom_123"], ["header", "table"])

    def test_inactive_template_is_removed_from_choices_and_payload_normalization(self):
        config, _created = PostTemplateConfig.objects.get_or_create(
            template_type=POST_TEMPLATE_TYPE_MOVIE_REVIEW,
            defaults={
                "label": "Кинообзор",
                "enabled_editor_blocks": ["header", "image"],
            },
        )
        config.is_active = False
        config.save(update_fields=["is_active", "updated_at"])

        PostTemplateConfig.ensure_defaults()
        config.refresh_from_db()

        self.assertFalse(config.is_active)
        self.assertNotIn(POST_TEMPLATE_TYPE_MOVIE_REVIEW, configured_post_template_type_values())
        self.assertNotIn(
            POST_TEMPLATE_TYPE_MOVIE_REVIEW,
            {value for value, _label in post_template_type_choices()},
        )
        normalized_template, template_error = editor_service._normalize_post_template_payload(
            {
                "type": POST_TEMPLATE_TYPE_MOVIE_REVIEW,
                "data": {"title": "Test"},
            }
        )
        self.assertIsNone(normalized_template)
        self.assertEqual(template_error, "unsupported template type")


class TweetTemplateTests(SimpleTestCase):
    def test_builtin_tweet_template_type_is_exposed(self):
        options = editor_service._serialize_post_template_type_options()
        self.assertIn(
            {
                "value": "tweet",
                "label": "Твит",
                "description": "До 280 символов и один медиаблок с изображениями.",
            },
            options,
        )

    def test_tweet_template_rejects_too_long_text(self):
        content = json.dumps(
            {"blocks": [{"type": "paragraph", "data": {"text": "a" * 281}}]},
            ensure_ascii=False,
        )
        error = editor_service._validate_template_content_constraints(
            {"type": "tweet", "version": 1, "data": {}},
            content,
        )
        self.assertEqual(error, "Твит не может быть длиннее 280 символов.")

    def test_tweet_template_rejects_unsupported_blocks(self):
        content = json.dumps(
            {"blocks": [{"type": "quote", "data": {"text": "text"}}]},
            ensure_ascii=False,
        )
        error = editor_service._validate_template_content_constraints(
            {"type": "tweet", "version": 1, "data": {}},
            content,
        )
        self.assertEqual(error, "Шаблон «Твит» поддерживает только текст и изображения.")


class BugReportTemplateTests(SimpleTestCase):
    def test_builtin_bug_report_template_type_is_exposed(self):
        options = editor_service._serialize_post_template_type_options()
        self.assertIn(
            {
                "value": "bug_report",
                "label": "Баг-репорт",
                "description": "Статус, платформа, браузер, код ошибки и скриншот.",
            },
            options,
        )

    def test_bug_report_template_normalizes_structured_fields(self):
        template, error = editor_service._normalize_post_template_payload(
            {
                "type": "bug_report",
                "data": {
                    "status": "В работе",
                    "platforms": ["Windows", "android", "windows"],
                    "browsers": ["Chrome", "Яндекс Браузер"],
                    "error_code": "Traceback...",
                    "description": "Шаги воспроизведения",
                    "screenshot_url": "https://example.com/shot.png",
                },
            }
        )
        self.assertIsNone(error)
        self.assertEqual(template["type"], "bug_report")
        self.assertEqual(template["data"]["status"], "in_progress")
        self.assertEqual(template["data"]["platforms"], ["windows", "android"])
        self.assertEqual(template["data"]["browsers"], ["chrome", "yandex_browser"])
