import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from communities.models import Comun, ComunPostCategoryAssignment
from feeds.models import Author, Post


@override_settings(
    SITE_BASE_URL="https://tambur.pub",
    WHEREFILMED_IMPORT_TOKEN="shared-secret",
)
class WhereFilmedImportTests(TestCase):
    def setUp(self):
        self.comun = Comun.objects.create(name="WhereFilmed", slug="wherefilmed")

    def _payload(self):
        return {
            "payload_version": 1,
            "source": {
                "site": "wherefilmed",
                "movie_id": 123,
                "slug": "example-movie",
                "url": "https://wherefilmed.org/ru/example-movie/",
            },
            "movie": {
                "id": 123,
                "title": "Дружба",
                "original_title": "Friendship",
                "year": 2024,
                "description_html": "<p>Описание фильма</p>",
                "poster_url": "https://wherefilmed.org/media/poster.jpg",
                "countries": [{"title": "Россия"}],
                "genres": [{"title": "Драма"}],
            },
            "locations": [
                {
                    "id": 77,
                    "title": "Набережная",
                    "scene_description_html": "<p>Сцена у воды</p>",
                    "movie_spot_html": "<p>на набережной возле моста</p>",
                    "address": "Москва",
                    "gps_coordinate": "55.751244, 37.618423",
                    "movie_gallery": [
                        {"image_url": "https://wherefilmed.org/media/movie.jpg"},
                    ],
                    "reality_gallery": [
                        {"image_url": "https://wherefilmed.org/media/reality.jpg"},
                    ],
                }
            ],
        }

    def test_requires_bearer_token(self):
        response = self.client.post(
            reverse("wherefilmed-import"),
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Post.objects.count(), 0)

    @patch("feeds.wherefilmed_import._download_image")
    def test_creates_post_in_wherefilmed_locations_category(self, download_image):
        download_image.side_effect = [
            "https://tambur.pub/media/posts/wherefilmed/123/poster-960.webp",
            "https://tambur.pub/media/posts/wherefilmed/123/movie-960.webp",
            "https://tambur.pub/media/posts/wherefilmed/123/reality-960.webp",
        ]

        response = self.client.post(
            reverse("wherefilmed-import"),
            data=json.dumps(self._payload()),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer shared-secret",
        )

        self.assertEqual(response.status_code, 201, response.content.decode())
        payload = response.json()
        self.assertRegex(
            payload["url"],
            r"^https://tambur\.pub/b/post/\d+-gde-snimali-druzhba-friendship-2024$",
        )

        author = Author.objects.get(username="wherefilmed")
        post = Post.objects.get(author=author, message_id=-3000000000123)
        self.assertEqual(payload["id"], str(post.id))
        self.assertEqual(post.title, "Где снимали «Дружба / Friendship (2024)»")
        self.assertEqual(post.source_url, "https://wherefilmed.org/ru/example-movie/")
        self.assertEqual(post.raw_data["source"], "manual_comun")
        self.assertEqual(post.raw_data["comun_slug"], "wherefilmed")
        self.assertEqual(post.raw_data["wherefilmed"]["movie_id"], 123)
        self.assertEqual(post.raw_data["template"]["type"], "movie_review")
        self.assertEqual(post.raw_data["template"]["data"]["title"], "Дружба")
        self.assertEqual(post.raw_data["template"]["data"]["original_title"], "Friendship")
        self.assertEqual(
            post.raw_data["template"]["data"]["poster_url"],
            "https://tambur.pub/media/posts/wherefilmed/123/poster-960.webp",
        )

        assignment = ComunPostCategoryAssignment.objects.select_related("category").get(
            comun=self.comun,
            post=post,
        )
        self.assertEqual(assignment.category.name, "локации")
        content = json.loads(post.content)
        block_types = [block["type"] for block in content["blocks"]]
        self.assertEqual(
            block_types,
            [
                "paragraph",
                "header",
                "header",
                "header",
                "gallery",
                "paragraph",
                "header",
                "gallery",
                "map",
                "paragraph",
            ],
        )
        self.assertIn("Описание [ru]:", content["blocks"][0]["data"]["text"])
        self.assertEqual(content["blocks"][1]["data"]["text"], "Локации съемок:")
        self.assertEqual(content["blocks"][3]["data"]["text"], "В кино")
        self.assertEqual(content["blocks"][6]["data"]["text"], "В реальности")
        self.assertIn("Сцена, где", content["blocks"][5]["data"]["text"])
        self.assertIn("Сцена была снята", content["blocks"][9]["data"]["text"])
        self.assertEqual(content["blocks"][8]["data"]["lat"], 55.751244)
        self.assertEqual(content["blocks"][8]["data"]["lng"], 37.618423)

    @patch("feeds.wherefilmed_import._download_image")
    def test_repeated_import_returns_existing_post_without_downloading_again(self, download_image):
        download_image.return_value = "https://tambur.pub/media/posts/wherefilmed/123/poster-960.webp"

        first = self.client.post(
            reverse("wherefilmed-import"),
            data=json.dumps(self._payload()),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer shared-secret",
        )
        self.assertEqual(first.status_code, 201, first.content.decode())

        download_image.reset_mock()
        second = self.client.post(
            reverse("wherefilmed-import"),
            data=json.dumps(self._payload()),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer shared-secret",
        )

        self.assertEqual(second.status_code, 200, second.content.decode())
        self.assertEqual(second.json()["url"], first.json()["url"])
        self.assertEqual(Post.objects.count(), 1)
        download_image.assert_not_called()
