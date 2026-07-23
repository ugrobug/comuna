import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities.models import Comun, ComunRoadmapItem
from feeds.models import Author, Post
from users import service as user_service


User = get_user_model()


class ComunRoadmapTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="roadmap-owner", password="secret")
        self.moderator = User.objects.create_user(username="roadmap-moderator", password="secret")
        self.outsider = User.objects.create_user(username="roadmap-outsider", password="secret")
        self.author = Author.objects.create(username="roadmap-author")
        self.comun = Comun.objects.create(
            name="Roadmap Community",
            slug="roadmap-community",
            creator=self.owner,
            roadmap_enabled=True,
        )
        self.comun.moderators.add(self.moderator)
        self.post = self.create_post("First roadmap post")
        self.roadmap_url = reverse("comun-roadmap", kwargs={"slug": self.comun.slug})

    def create_post(self, title, *, comun=None):
        comun = comun or self.comun
        return Post.objects.create(
            author=self.author,
            message_id=Post.objects.count() + 1,
            title=title,
            content=f"Content for {title}",
            raw_data={"source": "manual_comun", "comun_slug": comun.slug},
            is_pending=False,
            is_blocked=False,
        )

    def add_post(self, post=None, stage="planned"):
        return self.client.post(
            self.roadmap_url,
            data=json.dumps({"post_id": (post or self.post).id, "stage": stage}),
            content_type="application/json",
        )

    def authenticate(self, user):
        token = user_service._issue_token(user)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def logout(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

    def test_owner_can_add_and_public_can_read_roadmap_item(self):
        self.authenticate(self.owner)

        response = self.add_post(stage=ComunRoadmapItem.STAGE_IN_PROGRESS)

        self.assertEqual(response.status_code, 201, response.content.decode())
        item = ComunRoadmapItem.objects.get()
        self.assertEqual(item.comun, self.comun)
        self.assertEqual(item.post, self.post)
        self.assertEqual(item.stage, ComunRoadmapItem.STAGE_IN_PROGRESS)

        self.logout()
        response = self.client.get(self.roadmap_url)
        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertFalse(payload["can_manage"])
        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(payload["items"][0]["stage"], ComunRoadmapItem.STAGE_IN_PROGRESS)
        self.assertEqual(payload["items"][0]["post"]["id"], self.post.id)

    def test_same_post_cannot_be_added_twice(self):
        self.authenticate(self.owner)
        self.assertEqual(self.add_post().status_code, 201)

        response = self.add_post(stage=ComunRoadmapItem.STAGE_DONE)

        self.assertEqual(response.status_code, 409, response.content.decode())
        self.assertEqual(ComunRoadmapItem.objects.filter(post=self.post).count(), 1)
        self.assertEqual(
            ComunRoadmapItem.objects.get(post=self.post).stage,
            ComunRoadmapItem.STAGE_PLANNED,
        )

    def test_only_owner_can_manage_roadmap(self):
        for user in (self.moderator, self.outsider):
            self.authenticate(user)
            response = self.add_post()
            self.assertEqual(response.status_code, 403, response.content.decode())

        self.assertFalse(ComunRoadmapItem.objects.exists())

    def test_post_from_another_comun_cannot_be_added(self):
        other_comun = Comun.objects.create(
            name="Other Community",
            slug="other-community",
            creator=self.owner,
            roadmap_enabled=True,
        )
        other_post = self.create_post("Other post", comun=other_comun)
        self.authenticate(self.owner)

        response = self.add_post(post=other_post)

        self.assertEqual(response.status_code, 404, response.content.decode())
        self.assertFalse(ComunRoadmapItem.objects.exists())

    def test_candidates_are_searchable_and_exclude_added_posts(self):
        matched = self.create_post("Searchable release")
        other = self.create_post("Unrelated post")
        ComunRoadmapItem.objects.create(
            comun=self.comun,
            post=other,
            stage=ComunRoadmapItem.STAGE_DONE,
            added_by=self.owner,
        )
        self.authenticate(self.owner)

        response = self.client.get(
            reverse("comun-roadmap-posts", kwargs={"slug": self.comun.slug}),
            {"q": "Searchable"},
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual([post["id"] for post in response.json()["posts"]], [matched.id])

        response = self.client.get(
            reverse("comun-roadmap-posts", kwargs={"slug": self.comun.slug})
        )
        returned_ids = {post["id"] for post in response.json()["posts"]}
        self.assertIn(self.post.id, returned_ids)
        self.assertIn(matched.id, returned_ids)
        self.assertNotIn(other.id, returned_ids)

    def test_owner_can_check_and_remove_post(self):
        item = ComunRoadmapItem.objects.create(
            comun=self.comun,
            post=self.post,
            stage=ComunRoadmapItem.STAGE_PLANNED,
            added_by=self.owner,
        )
        self.authenticate(self.owner)
        item_url = reverse(
            "comun-roadmap-item",
            kwargs={"slug": self.comun.slug, "post_id": self.post.id},
        )

        response = self.client.get(item_url)
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(response.json()["in_roadmap"])
        self.assertEqual(response.json()["stage"], ComunRoadmapItem.STAGE_PLANNED)

        response = self.client.delete(item_url)
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertFalse(ComunRoadmapItem.objects.filter(id=item.id).exists())
