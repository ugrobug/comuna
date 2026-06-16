from django.test import SimpleTestCase

from legacy_migration.wp_post_categories import term_is_serialy_category


class WpPostCategoryTermTests(SimpleTestCase):
    def test_serialy_by_russian_name(self) -> None:
        self.assertTrue(term_is_serialy_category("Сериалы", "anything"))

    def test_serialy_by_slug(self) -> None:
        self.assertTrue(term_is_serialy_category("", "serialy"))

    def test_not_serialy_obzory(self) -> None:
        self.assertFalse(term_is_serialy_category("Обзоры", "obzory"))
        self.assertFalse(term_is_serialy_category("Статьи", "stati"))
