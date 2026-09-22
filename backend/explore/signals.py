from django.db.models.signals import post_delete
from django.dispatch import receiver

from .images import NodeImageService
from .models import Node


@receiver(post_delete, sender=Node)
def remove_node_image(sender, instance, **kwargs):
    NodeImageService.delete_after_commit(instance.image.storage, instance.image.name)
