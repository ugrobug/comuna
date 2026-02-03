from datetime import timedelta

from django import template
from django.utils import timezone

from feeds.models import Author, Post, PostComment, PostLike

register = template.Library()


@register.simple_tag
def get_admin_metrics() -> dict:
    now = timezone.now()
    since = now - timedelta(days=30)

    posts_qs = Post.objects.filter(
        is_pending=False,
        is_blocked=False,
        author__is_blocked=False,
    )

    total_posts = posts_qs.count()
    posts_last_30 = posts_qs.filter(created_at__gte=since).count()
    authors_total = Author.objects.filter(is_blocked=False).count()
    likes_last_30 = PostLike.objects.filter(created_at__gte=since, value__gt=0).count()
    dislikes_last_30 = PostLike.objects.filter(created_at__gte=since, value__lt=0).count()
    comments_last_30 = PostComment.objects.filter(
        created_at__gte=since, is_deleted=False
    ).count()

    avg_posts_per_author = 0.0
    if authors_total:
        avg_posts_per_author = posts_last_30 / authors_total

    return {
        "authors": authors_total,
        "posts_total": total_posts,
        "posts_last_30": posts_last_30,
        "avg_posts_per_author": avg_posts_per_author,
        "likes_last_30": likes_last_30,
        "dislikes_last_30": dislikes_last_30,
        "comments_last_30": comments_last_30,
    }
