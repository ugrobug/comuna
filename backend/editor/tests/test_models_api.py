from django.apps import apps
from django.test import SimpleTestCase, TestCase

from editor import service as editor_service
from editor.models import (
    ComunCustomPostTemplate,
    ComunCustomPostTemplateBlock,
    ComunCustomPostTemplateField,
    PostPollVote,
    PostRatingVote,
    POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS,
    PostTemplateConfig,
    normalize_allowed_post_templates,
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
