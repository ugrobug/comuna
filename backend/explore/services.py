from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from communities.models import Comun
from communities.serializers import _subscribed_comun_slugs_for_user
from communities.service import _sync_comun_subscriber_counts
from my_feed.models import UserFeedSettings
from my_feed.service import _serialize_user_feed_settings
from notifications.service import create_user_notification
from .models import Edge, GraphState, Node, PropertyDefinition, PropertyOption, Subscription


class GraphQuery:
    """Reads a graph once and supports multi-parent descendant traversal."""

    def __init__(self, *, include_hidden=False):
        nodes = Node.objects.select_related("community").prefetch_related("properties")
        if not include_hidden:
            nodes = nodes.filter(is_active=True).filter(Q(community__isnull=True) | Q(community__is_active=True))
        self.nodes = {node.pk: node for node in nodes}
        self.edges = list(Edge.objects.filter(source_id__in=self.nodes, target_id__in=self.nodes))
        self.children = defaultdict(set)
        for edge in self.edges:
            self.children[edge.source_id].add(edge.target_id)

    def communities_under(self, node_id):
        visited, pending, communities = set(), [node_id], set()
        while pending:
            current = pending.pop()
            if current in visited or current not in self.nodes:
                continue
            visited.add(current)
            node = self.nodes[current]
            if node.community_id:
                communities.add(node.community_id)
            pending.extend(self.children[current])
        return communities

    @staticmethod
    def catalog():
        return [{"id": item.pk, "key": item.key, "name": item.name,
                 "options": [{"id": option.pk, "label": option.label} for option in item.options.all()]}
                for item in PropertyDefinition.objects.prefetch_related("options")]

    def serialize(self, user=None):
        subscribed = set(Subscription.objects.filter(user=user).values_list("node_id", flat=True)) if user else set()
        communities = _subscribed_comun_slugs_for_user(user)
        return {
            "nodes": [{"id": node.pk, "kind": node.kind, "title": node.label,
                       "description": node.description, "is_active": node.is_active,
                       "image_url": node.image.url if node.image else None,
                       "community_description": node.community.product_description if node.community_id else "",
                       "subscribers_count": node.community.subscribers_count if node.community_id else None,
                       "show_properties": node.show_properties,
                       "property_ids": [option.pk for option in node.properties.all()],
                       "community_id": node.community_id,
                       "community_url": f"/comuns/{node.community.slug}" if node.community_id else None,
                       "subscribed": node.community.slug in communities if node.community_id else node.pk in subscribed}
                      for node in self.nodes.values()],
            "edges": [{"id": edge.pk, "source": edge.source_id, "target": edge.target_id} for edge in self.edges],
            "properties": self.catalog(),
        }


class GraphNotifications:
    """One site notification per user/community, even through several paths."""

    @classmethod
    def notify_changes(cls, before, after):
        changes = defaultdict(list)
        users = {}
        for subscription in Subscription.objects.select_related("user", "node").filter(user__is_active=True):
            new = after.communities_under(subscription.node_id) - before.communities_under(subscription.node_id)
            for community_id in new:
                changes[(subscription.user_id, community_id)].append(subscription.node.title)
                users[subscription.user_id] = subscription.user
        communities = Comun.objects.in_bulk({key[1] for key in changes})
        for (user_id, community_id), titles in changes.items():
            community = communities[community_id]
            create_user_notification(
                user=users[user_id], event_key="explore_new_community",
                title=f"Новое сообщество: {community.name}",
                message=f"В ваших увлечениях ({', '.join(sorted(set(titles)))}) появилось сообщество «{community.name}».",
                link_url=f"/comuns/{community.slug}",
                payload={"community_id": community_id, "elements": sorted(set(titles))},
                # Explore announcements are in-site; no external messages during a graph edit.
                force_telegram=False, force_push=False,
            )


class GraphEditor:
    """The write boundary: validation, graph lock and notifications are atomic."""

    @staticmethod
    def lock():
        state, _ = GraphState.objects.get_or_create(pk=1)
        return GraphState.objects.select_for_update().get(pk=state.pk)

    @classmethod
    @transaction.atomic
    def apply(cls, operation):
        state = cls.lock()
        before = GraphQuery()
        result = operation()
        state.revision += 1
        state.save(update_fields=["revision"])
        GraphNotifications.notify_changes(before, GraphQuery())
        return result

    @staticmethod
    def save_node(data, node_id=None):
        node = get_object_or_404(Node, pk=node_id) if node_id else Node()
        original_kind, original_community = node.kind, node.community_id
        for field in ("title", "description", "kind"):
            if field in data:
                if not isinstance(data[field], str):
                    raise ValidationError(f"Поле {field} должно быть строкой.")
                setattr(node, field, data[field].strip())
        for field in ("is_active", "show_properties"):
            if field in data:
                if type(data[field]) is not bool:
                    raise ValidationError(f"Поле {field} должно быть логическим значением.")
                setattr(node, field, data[field])
        if "community_id" in data:
            community_id = data["community_id"]
            if community_id is not None and (type(community_id) is not int or community_id <= 0):
                raise ValidationError("Выберите существующее сообщество.")
            node.community = get_object_or_404(Comun, pk=community_id, is_active=True) if community_id else None
        if node_id and (node.kind != original_kind or node.community_id != original_community):
            raise ValidationError("Тип и сообщество существующего узла менять нельзя. Добавьте новый узел.")
        if node.community_id:
            node.title = node.community.name
        node.full_clean()
        selected = None
        if "property_ids" in data:
            ids = data["property_ids"]
            if not isinstance(ids, list) or any(type(item) is not int for item in ids):
                raise ValidationError("Свойства должны быть списком выбранных вариантов.")
            selected = list(PropertyOption.objects.filter(pk__in=ids))
            if len(selected) != len(set(ids)):
                raise ValidationError("Неизвестный вариант свойства.")
        node.save()
        if selected is not None:
            node.properties.set(selected)
        return node

    @staticmethod
    def add_edge(data, edge_id=None):
        ids = [data.get("source"), data.get("target")]
        if any(type(item) is not int or item <= 0 for item in ids):
            raise ValidationError("Укажите оба узла связи.")
        edge = get_object_or_404(Edge, pk=edge_id) if edge_id else Edge()
        edge.source = get_object_or_404(Node, pk=ids[0])
        edge.target = get_object_or_404(Node, pk=ids[1])
        # Community placement is independent of the order selected in the UI.
        # Keep it below the element so existing descendant subscriptions work.
        if edge.source.kind == Node.Kind.COMMUNITY and edge.target.kind == Node.Kind.ELEMENT:
            edge.source, edge.target = edge.target, edge.source
        edge.full_clean()
        edge.save()
        return edge


class SubscriptionService:
    @classmethod
    @transaction.atomic
    def set(cls, user, node_id, enabled):
        GraphEditor.lock()
        node = get_object_or_404(Node.objects.select_related("community"), pk=node_id, is_active=True)
        if node.community_id:
            if not node.community.is_active:
                raise ValidationError("Сообщество недоступно.")
            settings, _ = UserFeedSettings.objects.get_or_create(user=user)
            settings = UserFeedSettings.objects.select_for_update().get(pk=settings.pk)
            previous = _serialize_user_feed_settings(settings)
            slugs = set(settings.my_feed_comuns or [])
            categories = dict(settings.my_feed_comun_categories or {})
            if enabled:
                slugs.add(node.community.slug)
            else:
                slugs.discard(node.community.slug)
                categories.pop(node.community.slug, None)
            settings.my_feed_comuns = sorted(slugs)
            settings.my_feed_comun_categories = categories
            settings.save(update_fields=["my_feed_comuns", "my_feed_comun_categories", "updated_at"])
            _sync_comun_subscriber_counts(previous, _serialize_user_feed_settings(settings), user_id=user.pk)
            node.community.refresh_from_db(fields=["subscribers_count"])
            return node.community.subscribers_count
        elif enabled:
            Subscription.objects.get_or_create(user=user, node=node)
        else:
            Subscription.objects.filter(user=user, node=node).delete()
