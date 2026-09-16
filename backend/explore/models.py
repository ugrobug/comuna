from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PropertyDefinition(models.Model):
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=160)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")

    def __str__(self):
        return self.name


class PropertyOption(models.Model):
    property = models.ForeignKey(PropertyDefinition, on_delete=models.CASCADE, related_name="options")
    value = models.SlugField()
    label = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("property__position", "position", "id")
        constraints = [models.UniqueConstraint(fields=("property", "value"), name="explore_unique_option")]

    def __str__(self):
        return f"{self.property}: {self.label}"


class GraphState(models.Model):
    """A shared write lock serializes graph edits and notification snapshots."""
    revision = models.PositiveBigIntegerField(default=0)


class Node(models.Model):
    class Kind(models.TextChoices):
        ELEMENT = "element", "Элемент"
        COMMUNITY = "community", "Сообщество"

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.ELEMENT)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=4000)
    community = models.OneToOneField("feeds.Comun", null=True, blank=True, on_delete=models.CASCADE, related_name="explore_node")
    properties = models.ManyToManyField(PropertyOption, blank=True, related_name="nodes")
    show_properties = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind", "title", "id")
        constraints = [models.CheckConstraint(condition=(models.Q(kind="element", community__isnull=True) | models.Q(kind="community", community__isnull=False)), name="explore_node_kind_community")]

    def clean(self):
        super().clean()
        if (self.kind == self.Kind.COMMUNITY) != bool(self.community_id):
            raise ValidationError("Укажите существующее сообщество только для узла «Сообщество».")

    @property
    def label(self):
        return self.community.name if self.community_id else self.title

    def __str__(self):
        return self.title


class Edge(models.Model):
    source = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="outgoing_edges")
    target = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="incoming_edges")

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("source", "target"), name="explore_unique_edge"),
            models.CheckConstraint(condition=~models.Q(source=models.F("target")), name="explore_no_self_edge"),
        ]

    def clean(self):
        super().clean()
        if self.source_id == self.target_id:
            raise ValidationError("Нельзя связать элемент с самим собой.")
        if Edge.objects.exclude(pk=self.pk).filter(source_id=self.target_id, target_id=self.source_id).exists():
            raise ValidationError("Эти узлы уже связаны.")


class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="explore_subscriptions")
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "node"), name="explore_unique_subscription")]

    def clean(self):
        if self.node.kind != Node.Kind.ELEMENT:
            raise ValidationError("На сообщество подписываются через ленту сообществ.")
