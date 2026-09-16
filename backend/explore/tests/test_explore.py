import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from communities.models import Comun
from my_feed.models import UserFeedSettings
from notifications.models import SiteNotification
from users.service import _issue_token
from explore.models import Edge, Node, PropertyDefinition, PropertyOption, Subscription
from explore.services import GraphEditor, GraphQuery, SubscriptionService


class ExploreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="explore-staff", is_staff=True)
        cls.member = User.objects.create_user(username="explore-member")
        cls.staff_token = _issue_token(cls.staff)
        cls.member_token = _issue_token(cls.member)
        cls.root = Node.objects.create(title="Велоспорт")
        cls.child = Node.objects.create(title="Гравийные велосипеды")
        cls.other = Node.objects.create(title="Путешествия")
        cls.community = Comun.objects.create(name="Велоклуб", slug="explore-cycling")
        cls.club = Node.objects.create(kind="community", title="Велоклуб", community=cls.community)

    def request(self, method, path, body=None, token=None):
        return getattr(self.client, method)("/api/explore/" + path, data=json.dumps(body or {}), content_type="application/json",
                                            **({"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}))

    def link(self, source, target):
        return GraphEditor.apply(lambda: GraphEditor.add_edge({"source": source.pk, "target": target.pk}))

    def test_public_graph_and_complete_multiselect_catalog(self):
        response = self.client.get("/api/explore/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([len(item["options"]) for item in response.json()["properties"]], [4, 8, 8, 3, 3])
        self.assertIn("no-store", response["Cache-Control"])

    def test_anonymous_cannot_subscribe_or_edit(self):
        for method, path in [("post", "nodes/"), ("post", "edges/"), ("post", f"nodes/{self.root.pk}/subscription/"),
                             ("delete", f"nodes/{self.root.pk}/"), ("patch", f"nodes/{self.root.pk}/")]:
            self.assertEqual(self.request(method, path).status_code, 401)
        self.assertEqual(self.client.get("/api/explore/manage/").status_code, 401)

    def test_community_card_reads_current_description_and_subscribers(self):
        self.community.product_description = "Поездки и встречи велосипедистов."
        self.community.subscribers_count = 1234
        self.community.save(update_fields=["product_description", "subscribers_count"])
        self.club.description = "Описание узла в графе"
        self.club.save(update_fields=["description"])
        nodes = {item["id"]: item for item in self.client.get("/api/explore/").json()["nodes"]}
        self.assertEqual(nodes[self.club.pk]["community_description"], self.community.product_description)
        self.assertEqual(nodes[self.club.pk]["subscribers_count"], 1234)
        self.assertEqual(nodes[self.club.pk]["description"], "Описание узла в графе")
        self.assertIsNone(nodes[self.root.pk]["subscribers_count"])

    def test_subscription_response_returns_updated_count_without_double_counting(self):
        path = f"nodes/{self.club.pk}/subscription/"
        for _ in range(2):
            response = self.request("post", path, token=self.member_token)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"subscribed": True, "subscribers_count": 1})
        response = self.request("delete", path, token=self.member_token)
        self.assertEqual(response.json(), {"subscribed": False, "subscribers_count": 0})

    def test_regular_user_cannot_manage_global_graph(self):
        self.community.moderators.add(self.member)
        self.assertEqual(self.request("post", "nodes/", {"title": "Нельзя"}, self.member_token).status_code, 403)
        self.assertEqual(self.client.get("/api/explore/manage/", HTTP_AUTHORIZATION=f"Bearer {self.member_token}").status_code, 403)

    def test_staff_crud_and_multiselect_hidden_properties(self):
        options = list(PropertyOption.objects.filter(property__key="company").values_list("id", flat=True))[:2]
        response = self.request("post", "nodes/", {"title": "Рыбалка", "property_ids": options, "show_properties": False}, self.staff_token)
        self.assertEqual(response.status_code, 201, response.content)
        node_id = response.json()["id"]
        public = next(item for item in self.client.get("/api/explore/").json()["nodes"] if item["id"] == node_id)
        self.assertCountEqual(public["property_ids"], options)
        self.assertFalse(public["show_properties"])
        self.assertEqual(self.request("patch", f"nodes/{node_id}/", {"title": "Морская рыбалка"}, self.staff_token).status_code, 200)
        self.assertEqual(self.request("delete", f"nodes/{node_id}/", token=self.staff_token).status_code, 200)
        self.assertFalse(Node.objects.filter(pk=node_id).exists())

    def test_invalid_properties_do_not_partially_save(self):
        response = self.request("patch", f"nodes/{self.root.pk}/", {"title": "Не сохранять", "property_ids": [999999]}, self.staff_token)
        self.assertEqual(response.status_code, 400)
        self.root.refresh_from_db()
        self.assertEqual(self.root.title, "Велоспорт")

    def test_invalid_types_and_json_return_validation_error(self):
        for body in [{"title": []}, {"title": "test", "is_active": "false"}, {"title": "test", "property_ids": [True]}]:
            self.assertEqual(self.request("post", "nodes/", body, self.staff_token).status_code, 400)
        response = self.client.post("/api/explore/nodes/", data="[", content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {self.staff_token}")
        self.assertEqual(response.status_code, 400)

    def test_community_identity_is_unique_and_immutable(self):
        duplicate = self.request("post", "nodes/", {"kind": "community", "community_id": self.community.pk}, self.staff_token)
        self.assertEqual(duplicate.status_code, 400)
        change = self.request("patch", f"nodes/{self.root.pk}/", {"kind": "community", "community_id": self.community.pk}, self.staff_token)
        self.assertEqual(change.status_code, 400)

    def test_multiple_parents_supported_and_self_links_and_duplicate_pairs_rejected(self):
        self.link(self.root, self.child)
        self.link(self.other, self.child)
        for source, target in [(self.child, self.root), (self.root, self.root), (self.root, self.child)]:
            with self.assertRaises(ValidationError):
                self.link(source, target)
        self.assertEqual(self.child.incoming_edges.count(), 2)

    def test_new_elements_are_immediately_available_for_connections(self):
        created = self.request("post", "nodes/", {"title": "Ракеточный спорт"}, self.staff_token)
        self.assertEqual(created.status_code, 201)
        node_id = created.json()["id"]
        graph = self.client.get("/api/explore/manage/", HTTP_AUTHORIZATION=f"Bearer {self.staff_token}").json()
        self.assertIn(node_id, [node["id"] for node in graph["nodes"]])
        linked = self.request("post", "edges/", {"source": self.root.pk, "target": node_id}, self.staff_token)
        self.assertEqual(linked.status_code, 201, linked.content)

    def test_community_can_be_selected_first_and_still_notifies_element_subscribers(self):
        SubscriptionService.set(self.member, self.root.pk, True)
        response = self.request("post", "edges/", {"source": self.club.pk, "target": self.root.pk}, self.staff_token)
        self.assertEqual(response.status_code, 201, response.content)
        edge = Edge.objects.get(pk=response.json()["id"])
        self.assertEqual((edge.source_id, edge.target_id), (self.root.pk, self.club.pk))
        self.assertEqual(GraphQuery().communities_under(self.root.pk), {self.community.pk})
        self.assertEqual(SiteNotification.objects.filter(user=self.member, event_key="explore_new_community").count(), 1)
        duplicate = self.request("post", "edges/", {"source": self.root.pk, "target": self.club.pk}, self.staff_token)
        self.assertEqual(duplicate.status_code, 400)

    def test_cycles_terminate_and_notify_once(self):
        self.link(self.root, self.child)
        self.link(self.child, self.other)
        self.link(self.other, self.root)
        SubscriptionService.set(self.member, self.root.pk, True)
        SubscriptionService.set(self.member, self.child.pk, True)
        self.link(self.other, self.club)
        self.assertEqual(GraphQuery().communities_under(self.root.pk), {self.community.pk})
        self.assertEqual(SiteNotification.objects.filter(user=self.member, event_key="explore_new_community").count(), 1)

    def test_communities_can_be_linked_to_each_other(self):
        community = Comun.objects.create(name="Второй клуб", slug="explore-second-club")
        club = Node.objects.create(kind="community", title=community.name, community=community)
        edge = self.link(self.club, club)
        self.assertEqual((edge.source_id, edge.target_id), (self.club.pk, club.pk))
        with self.assertRaises(ValidationError):
            self.link(club, self.club)

    def test_subscriptions_are_idempotent_and_unsubscribe(self):
        path = f"nodes/{self.root.pk}/subscription/"
        for _ in range(2):
            self.assertEqual(self.request("post", path, token=self.member_token).status_code, 200)
        self.assertEqual(Subscription.objects.filter(user=self.member, node=self.root).count(), 1)
        self.assertEqual(self.request("delete", path, token=self.member_token).status_code, 200)
        self.assertFalse(Subscription.objects.filter(user=self.member).exists())

    def test_community_subscription_uses_existing_feed_and_counts(self):
        for _ in range(2):
            SubscriptionService.set(self.member, self.club.pk, True)
        self.community.refresh_from_db()
        self.assertEqual(self.community.subscribers_count, 1)
        self.assertIn(self.community.slug, UserFeedSettings.objects.get(user=self.member).my_feed_comuns)
        self.assertFalse(Subscription.objects.filter(user=self.member).exists())
        SubscriptionService.set(self.member, self.club.pk, False)
        self.community.refresh_from_db()
        self.assertEqual(self.community.subscribers_count, 0)

    def test_new_descendant_community_notifies_once_across_subscribed_ancestors(self):
        self.link(self.root, self.child)
        SubscriptionService.set(self.member, self.root.pk, True)
        SubscriptionService.set(self.member, self.child.pk, True)
        self.link(self.child, self.club)
        notifications = SiteNotification.objects.filter(user=self.member, event_key="explore_new_community")
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(notifications.get().link_url, f"/comuns/{self.community.slug}")
        self.assertCountEqual(notifications.get().payload["elements"], [self.root.title, self.child.title])
        # Another path to an already reachable community is not a new community.
        self.link(self.root, self.club)
        self.assertEqual(notifications.count(), 1)

    def test_connecting_existing_branch_notifies_parent_subscribers(self):
        self.link(self.child, self.club)
        SubscriptionService.set(self.member, self.root.pk, True)
        self.link(self.root, self.child)
        self.assertEqual(SiteNotification.objects.filter(user=self.member, event_key="explore_new_community").count(), 1)

    def test_subscribing_does_not_send_old_communities(self):
        self.link(self.root, self.club)
        SubscriptionService.set(self.member, self.root.pk, True)
        GraphEditor.apply(lambda: GraphEditor.save_node({"description": "Обновлено"}, self.root.pk))
        self.assertFalse(SiteNotification.objects.filter(user=self.member, event_key="explore_new_community").exists())

    def test_unsubscribed_users_are_not_notified(self):
        SubscriptionService.set(self.member, self.root.pk, True)
        SubscriptionService.set(self.member, self.root.pk, False)
        self.link(self.root, self.club)
        self.assertFalse(SiteNotification.objects.filter(user=self.member, event_key="explore_new_community").exists())

    def test_hidden_nodes_and_inactive_communities_are_not_public(self):
        self.link(self.root, self.child)
        self.child.is_active = False
        self.child.save()
        self.community.is_active = False
        self.community.save()
        graph = self.client.get("/api/explore/").json()
        self.assertNotIn(self.child.pk, [node["id"] for node in graph["nodes"]])
        self.assertNotIn(self.club.pk, [node["id"] for node in graph["nodes"]])
        self.assertFalse(any(edge["target"] == self.child.pk for edge in graph["edges"]))
        self.assertEqual(self.request("post", f"nodes/{self.child.pk}/subscription/", token=self.member_token).status_code, 404)

    def test_deleting_graph_community_does_not_delete_site_community(self):
        self.assertEqual(self.request("delete", f"nodes/{self.club.pk}/", token=self.staff_token).status_code, 200)
        self.assertTrue(Comun.objects.filter(pk=self.community.pk).exists())

    def test_cross_site_writes_are_blocked(self):
        response = self.client.post("/api/explore/nodes/", data='{"title":"csrf"}', content_type="application/json",
                                    HTTP_AUTHORIZATION=f"Bearer {self.staff_token}", HTTP_ORIGIN="https://untrusted.example")
        self.assertEqual(response.status_code, 403)
