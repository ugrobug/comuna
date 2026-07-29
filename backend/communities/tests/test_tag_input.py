from django.test import SimpleTestCase

from communities import service as community_service


class ComunTagInputTests(SimpleTestCase):
    def test_tag_payload_splits_commas_inside_list_items(self):
        self.assertEqual(
            community_service._parse_tag_payload(
                ["#App store, Google play, Разработка приложений, Rustore"]
            ),
            ["#App store", "Google play", "Разработка приложений", "Rustore"],
        )

    def test_tag_payload_removes_duplicates_after_splitting(self):
        self.assertEqual(
            community_service._parse_tag_payload(["Rustore, rustore", "Google play"]),
            ["Rustore", "Google play"],
        )
