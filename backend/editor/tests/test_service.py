from django.test import SimpleTestCase

from editor.service import _normalize_movie_review_template_data, _parse_release_date_hint


class MovieReviewTemplateServiceTests(SimpleTestCase):
    def test_parse_release_date_hint_returns_year_only(self):
        self.assertEqual(_parse_release_date_hint("2024-05-10"), "2024")
        self.assertEqual(_parse_release_date_hint("2024-05"), "2024")
        self.assertEqual(_parse_release_date_hint("Released in 2024"), "2024")

    def test_movie_review_template_stores_release_year_only(self):
        normalized, error = _normalize_movie_review_template_data(
            {
                "title": "Movie",
                "release_date": "2024-05-10",
            }
        )

        self.assertIsNone(error)
        self.assertEqual(normalized["release_date"], "2024")

    def test_movie_review_template_accepts_release_year(self):
        normalized, error = _normalize_movie_review_template_data(
            {
                "title": "Movie",
                "release_date": "2024",
            }
        )

        self.assertIsNone(error)
        self.assertEqual(normalized["release_date"], "2024")
