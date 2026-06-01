from django.test import TestCase
from django.urls import reverse

from feeds.models import Tag


class TagsListApiTests(TestCase):
    def test_tags_list_without_query_preserves_full_list(self):
        Tag.objects.create(name="cinema", lemma="cinema")
        Tag.objects.create(name="cars", lemma="car")

        response = self.client.get(reverse("tag-list"))

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual([tag["name"] for tag in response.json()["tags"]], ["cars", "cinema"])

    def test_tags_list_query_requires_two_characters(self):
        Tag.objects.create(name="cinema", lemma="cinema")

        response = self.client.get(reverse("tag-list"), {"q": "c"})

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual(response.json()["tags"], [])

    def test_tags_list_query_returns_limited_suggestions(self):
        Tag.objects.create(name="cinema", lemma="movie")
        Tag.objects.create(name="city", lemma="city")
        Tag.objects.create(name="cars", lemma="car")

        response = self.client.get(reverse("tag-list"), {"q": "ci", "limit": "1"})

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(len(payload["tags"]), 1)
        self.assertEqual(payload["tags"][0]["name"], "cinema")
