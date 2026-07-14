import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities import service as community_service
from communities.models import Comun, ComunMapPoint
from feeds.models import Author, Post


User = get_user_model()


def editor_content(*blocks):
    return json.dumps({"time": 1, "blocks": list(blocks), "version": "2.30.0"})


def map_block(lat, lng, zoom=13, raw=""):
    return {"type": "map", "data": {"lat": lat, "lng": lng, "zoom": zoom, "raw": raw}}


def response_body(response):
    if response.streaming:
        return b"".join(response.streaming_content)
    return response.content


class ComunMapPointTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="map-owner", password="secret")
        self.author = Author.objects.create(username="map-author")
        self.comun = Comun.objects.create(
            name="Map Community",
            slug="map-community",
            creator=self.owner,
            community_map_enabled=True,
        )

    def create_post(self, content):
        return Post.objects.create(
            author=self.author,
            message_id=Post.objects.count() + 1,
            title="Map Post",
            content=content,
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )

    def test_sync_creates_points_from_editor_map_blocks(self):
        post = self.create_post(
            editor_content(
                {"type": "paragraph", "data": {"text": "Intro"}},
                map_block(55.751244, 37.618423, 12, "Moscow"),
                map_block("59.938630", "30.314130", 11, "SPB"),
            )
        )

        synced_count = community_service.sync_comun_map_points_for_post(post, comun=self.comun)

        self.assertEqual(synced_count, 2)
        points = list(ComunMapPoint.objects.filter(comun=self.comun, post=post).order_by("block_index"))
        self.assertEqual([point.block_index for point in points], [1, 2])
        self.assertEqual(float(points[0].lat), 55.751244)
        self.assertEqual(float(points[1].lng), 30.31413)

    def test_sync_replaces_points_and_respects_enabled_flag(self):
        post = self.create_post(editor_content(map_block(55.751244, 37.618423)))
        community_service.sync_comun_map_points_for_post(post, comun=self.comun)
        self.assertEqual(ComunMapPoint.objects.filter(post=post).count(), 1)

        post.content = editor_content(map_block(40.7128, -74.006, 10, "NYC"))
        post.save(update_fields=["content", "updated_at"])
        community_service.sync_comun_map_points_for_post(post, comun=self.comun)

        self.assertEqual(ComunMapPoint.objects.filter(post=post).count(), 1)
        point = ComunMapPoint.objects.get(post=post)
        self.assertEqual(float(point.lat), 40.7128)
        self.assertEqual(point.raw, "NYC")

        self.comun.community_map_enabled = False
        self.comun.save(update_fields=["community_map_enabled", "updated_at"])
        community_service.sync_comun_map_points_for_post(post, comun=self.comun)

        self.assertEqual(ComunMapPoint.objects.filter(post=post).count(), 0)

    def test_map_api_returns_saved_points_with_post_links(self):
        post = self.create_post(editor_content(map_block(55.751244, 37.618423, 12, "Moscow")))
        community_service.sync_comun_map_points_for_post(post, comun=self.comun)

        response = self.client.get(reverse("comun-map", kwargs={"slug": self.comun.slug}))

        body = response_body(response)
        self.assertEqual(response.status_code, 200, body.decode())
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["points"]), 1)
        self.assertEqual(payload["points"][0]["post_id"], post.id)
        self.assertTrue(payload["points"][0]["post_path"].startswith(f"/b/post/{post.id}-"))

    def test_disabled_map_api_is_not_public(self):
        self.comun.community_map_enabled = False
        self.comun.save(update_fields=["community_map_enabled", "updated_at"])

        response = self.client.get(reverse("comun-map", kwargs={"slug": self.comun.slug}))

        self.assertEqual(response.status_code, 404)
