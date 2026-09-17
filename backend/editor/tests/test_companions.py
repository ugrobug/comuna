import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from editor.companions import CompanionError, CompanionService, normalize_companion_data
from editor.models import CompanionResponse, CompanionSearch
from editor.service import _normalize_post_template_payload
from feeds.models import Author, Post, PublicFeedItem
from feeds.seo_indexing import public_posts_queryset, seo_indexable_posts_queryset
from users.models import SiteChatMessage
from users.service import _issue_token

User = get_user_model()


class CompanionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="invitation-owner", password="secret")
        self.guest = User.objects.create_user(username="invitation-guest", password="secret")
        self.other = User.objects.create_user(username="invitation-other", password="secret")
        self.comun = Comun.objects.create(name="Companion club", slug="companion-club", creator=self.owner, allowed_post_templates=["basic", "companion"])
        self.data = {"description": "Прогулка по парку", "place": "Главный вход", "lat": 55.75, "lng": 37.61,
                     "radius_m": 500, "starts_at": (timezone.now() + timedelta(days=3)).isoformat()}
        self.payload = {"title": "Ищу спутника", "content": "", "author_source": "site", "comun_slug": self.comun.slug,
                        "template": {"type": "companion", "version": 1, "data": self.data}}

    def headers(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(user)}"} if user else {}

    def create(self, **changes):
        response = self.client.post(reverse("auth-posts"), data=json.dumps({**self.payload, **changes}), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(response.status_code, 200, response.content.decode())
        return Post.objects.get(pk=response.json()["post"]["id"])

    def action(self, post, user, **payload):
        return self.client.post(reverse("post-companion", args=[post.id]), data=json.dumps(payload), content_type="application/json", **self.headers(user))

    def test_create_with_short_description_without_extra_body_and_community_endpoint(self):
        post = self.create()
        self.assertEqual(post.companion_search.organizer_id, self.owner.id)
        self.assertEqual(post.raw_data["template"]["data"]["radius_m"], 500)
        response = self.client.post(reverse("comun-posts", args=[self.comun.slug]), data=json.dumps(self.payload), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual(CompanionSearch.objects.count(), 2)

    def test_optional_radius_and_zero_coordinates(self):
        self.data.update(lat=0, lng=0, radius_m=None)
        post = self.create()
        self.assertIsNone(post.raw_data["template"]["data"]["radius_m"])
        self.assertEqual(post.raw_data["template"]["data"]["lat"], 0)

    def test_validation_on_both_publication_endpoints(self):
        for endpoint in (reverse("auth-posts"), reverse("comun-posts", args=[self.comun.slug])):
            for invalid in ({"description": ""}, {"lat": None}, {"lng": 190}, {"lat": float("nan")}, {"radius_m": -1}, {"radius_m": 100001}, {"starts_at": ""}, {"starts_at": (timezone.now() - timedelta(hours=1)).isoformat()}):
                with self.subTest(endpoint=endpoint, invalid=invalid):
                    payload = {**self.payload, "template": {"type": "companion", "data": {**self.data, **invalid}}}
                    response = self.client.post(endpoint, data=json.dumps(payload), content_type="application/json", **self.headers(self.owner))
                    self.assertEqual(response.status_code, 400, response.content.decode())
        self.assertEqual(Post.objects.count(), 0)

    def test_incomplete_draft_is_saved_but_cannot_be_published(self):
        post = self.create(is_draft=True, template={"type": "companion", "data": {}})
        response = self.client.patch(reverse("auth-post-update", args=[post.id]), data=json.dumps({"is_draft": False}), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.action(post, self.guest).status_code, 404)

    def test_schedule_cannot_be_after_meeting(self):
        response = self.client.post(reverse("auth-posts"), data=json.dumps({**self.payload, "publish_at": (timezone.now() + timedelta(days=4)).isoformat()}), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(response.status_code, 400)

    def test_respond_requires_login_no_self_responses_and_idempotent(self):
        post = self.create()
        self.assertEqual(self.action(post, None).status_code, 401)
        self.assertEqual(self.action(post, self.owner).status_code, 400)
        self.assertEqual(self.action(post, self.guest, message="Буду рад!").status_code, 200)
        self.assertEqual(self.action(post, self.guest).status_code, 200)
        self.assertEqual(post.companion_search.responses.count(), 1)
        guest_state = self.client.get(reverse("post-companion", args=[post.id]), **self.headers(self.guest)).json()["companion"]
        self.assertTrue(guest_state["has_responded"])
        self.assertEqual(guest_state["responses"], [])
        owner_state = self.client.get(reverse("post-companion", args=[post.id]), **self.headers(self.owner)).json()["companion"]
        self.assertEqual(owner_state["responses"][0]["user"]["id"], self.guest.id)
        self.assertEqual(self.action(post, self.guest, action="withdraw").status_code, 200)
        self.assertFalse(post.companion_search.responses.exists())

    def test_approval_creates_one_confirmation_and_hides_post(self):
        post = self.create()
        PublicFeedItem.objects.create(feed="home", post=post, rank=1, score=10, post_created_at=post.created_at, author_id_snapshot=post.author_id)
        self.action(post, self.guest)
        self.action(post, self.other)
        chosen = CompanionResponse.objects.get(user=self.guest)
        second = CompanionResponse.objects.get(user=self.other)
        self.assertEqual(self.action(post, self.other, action="approve", response_id=chosen.id).status_code, 403)
        with self.captureOnCommitCallbacks(execute=True), patch("notifications.service.send_site_notification_to_push"), patch("notifications.service.send_site_notification_to_telegram"):
            response = self.action(post, self.owner, action="approve", response_id=chosen.id)
        self.assertEqual(response.status_code, 200, response.content.decode())
        chat_id = response.json()["companion"]["chat_id"]
        message = SiteChatMessage.objects.get(chat_id=chat_id)
        self.assertEqual(message.event["place"], "Главный вход")
        self.assertEqual(message.event["lat"], 55.75)
        self.assertEqual(message.event["starts_at"], _normalize_post_template_payload(self.payload["template"])[0]["data"]["starts_at"])
        from notifications.models import SiteNotification
        self.assertEqual(SiteNotification.objects.filter(event_key="chat_message", payload__chat_id=chat_id).count(), 2)
        self.assertEqual(self.action(post, self.owner, action="approve", response_id=chosen.id).status_code, 200)
        self.assertEqual(self.action(post, self.owner, action="approve", response_id=second.id).status_code, 409)
        self.assertEqual(SiteChatMessage.objects.filter(chat_id=chat_id).count(), 1)
        self.assertEqual(self.action(post, self.other).status_code, 404)
        for user in (None, self.other):
            self.assertEqual(self.client.get(reverse("post-detail", args=[post.id]), **self.headers(user)).status_code, 404)
            self.assertEqual(self.client.get(reverse("post-companion", args=[post.id]), **self.headers(user)).status_code, 404)
        for user in (self.owner, self.guest):
            self.assertEqual(self.client.get(reverse("post-detail", args=[post.id]), **self.headers(user)).status_code, 200)
            self.assertEqual(self.client.get(reverse("post-companion", args=[post.id]), **self.headers(user)).status_code, 200)
        self.assertFalse(public_posts_queryset().filter(id=post.id).exists())
        self.assertFalse(PublicFeedItem.objects.filter(post=post).exists())
        posts_response = self.client.get(reverse("comun-posts", args=[self.comun.slug]))
        self.assertNotIn(post.id, [item["id"] for item in posts_response.json()["posts"]])
        edit = self.client.patch(reverse("auth-post-update", args=[post.id]), data=json.dumps({"title": "Изменить"}), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(edit.status_code, 409)

    def test_invitation_and_lists_are_not_cached_or_indexed(self):
        post = self.create()
        for url in (reverse("post-detail", args=[post.id]), reverse("comun-posts", args=[self.comun.slug]), reverse("post-companion", args=[post.id])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.content.decode())
            self.assertIn("no-store", response["Cache-Control"])
            self.assertNotEqual(response.get("X-Cache"), "HIT")
        self.assertFalse(seo_indexable_posts_queryset().filter(pk=post.id).exists())

    def test_response_fields_cannot_change_after_someone_responds(self):
        post = self.create()
        self.action(post, self.guest)
        changed = {"template": {"type": "companion", "data": {**self.data, "lat": 50}}}
        response = self.client.patch(reverse("auth-post-update", args=[post.id]), data=json.dumps(changed), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(response.status_code, 409)
        unchanged = self.client.patch(reverse("auth-post-update", args=[post.id]), data=json.dumps({"template": self.payload["template"]}), content_type="application/json", **self.headers(self.owner))
        self.assertEqual(unchanged.status_code, 200, unchanged.content.decode())

    def test_embedded_welcome_post_is_not_cached_and_is_removed_after_match(self):
        post = self.create()
        self.comun.welcome_post = post
        self.comun.save(update_fields=["welcome_post"])
        detail_url = f"/api/comuns/{self.comun.slug}/"
        before = self.client.get(detail_url)
        self.assertEqual(before.status_code, 200, before.content.decode())
        self.assertIn("no-store", before["Cache-Control"])
        self.action(post, self.guest)
        chosen = CompanionResponse.objects.get(user=self.guest)
        result = self.action(post, self.owner, action="approve", response_id=chosen.id)
        chat_id = result.json()["companion"]["chat_id"]
        after = self.client.get(detail_url)
        self.assertIsNone(after.json()["comun"]["welcome_post"])
        for participant in (self.owner, self.guest):
            chat = self.client.get(reverse("auth-chat-detail", args=[chat_id]), **self.headers(participant))
            self.assertEqual(chat.status_code, 200, chat.content.decode())
            self.assertEqual(chat.json()["messages"][0]["event"]["kind"], "companion_confirmed")
        self.assertEqual(self.client.get(reverse("auth-chat-detail", args=[chat_id]), **self.headers(self.other)).status_code, 404)

    def test_expired_and_invalid_requests(self):
        post = self.create()
        self.assertEqual(self.action(post, self.guest, action="approve", response_id="bad").status_code, 400)
        self.assertEqual(self.action(post, self.guest, message="x" * 501).status_code, 400)
        with patch("editor.companions.timezone.now", return_value=timezone.now() + timedelta(days=5)):
            self.assertEqual(self.action(post, self.guest).status_code, 409)

    def test_blocked_chat_prevents_approval_without_closing_post(self):
        from users.chat_service import get_or_create_chat_for_users
        from users.models import SiteChatParticipantState
        post = self.create()
        self.action(post, self.guest)
        chat, _ = get_or_create_chat_for_users(self.owner, self.guest)
        SiteChatParticipantState.objects.create(chat=chat, user=self.guest, is_blocked=True)
        response = self.action(post, self.owner, action="approve", response_id=CompanionResponse.objects.get(user=self.guest).id)
        self.assertEqual(response.status_code, 409)
        post.refresh_from_db()
        self.assertIsNone(post.companion_matched_at)
        self.assertEqual(SiteChatMessage.objects.count(), 0)


class CompanionConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_approvals_select_only_one_person(self):
        owner, first, second = [User.objects.create_user(username=name) for name in ("race-owner", "race-first", "race-second")]
        author = Author.objects.create(username="race-author")
        post = Post.objects.create(author=author, message_id=17, raw_data={"template": {"type": "companion", "data": {"description": "Walk", "lat": 0, "lng": 0, "starts_at": (timezone.now() + timedelta(days=1)).isoformat()}}})
        search = CompanionSearch.objects.create(post=post, organizer=owner)
        responses = [CompanionResponse.objects.create(search=search, user=user) for user in (first, second)]
        def approve(response_id):
            close_old_connections()
            try:
                CompanionService.approve(post.id, owner, response_id)
                return 200
            except CompanionError as error:
                return error.status
            finally:
                close_old_connections()
        with patch("editor.companions.create_user_notification"), ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(approve, [response.id for response in responses]))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(SiteChatMessage.objects.count(), 1)
        post.refresh_from_db()
        self.assertIsNotNone(post.companion_matched_at)
