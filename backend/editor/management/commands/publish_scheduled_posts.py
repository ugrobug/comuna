import logging
import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils import timezone

from communities import service as community_service
from editor.scheduling import set_schedule_state
from feeds.models import Post
from rabotaem_backend.cache import bump_public_cache_prefix

logger = logging.getLogger(__name__)


def _due_posts(now):
    return Post.objects.filter(
        is_pending=True,
        is_blocked=False,
        author__is_blocked=False,
        publish_at__lte=now,
        raw_data__scheduled_publication=True,
    )


@transaction.atomic
def _publish_post(post_id, now):
    # Editor updates acquire the same lock; concurrent workers cannot publish twice.
    post = (
        _due_posts(now)
        .select_for_update(skip_locked=True, of=("self",))
        .select_related("author")
        .filter(id=post_id)
        .first()
    )
    if post is None:
        return False
    actor = get_user_model().objects.filter(
        id=(post.raw_data or {}).get("scheduled_by_user_id")
    ).first()
    post.raw_data = set_schedule_state(
        post.raw_data, publish_at=None, is_draft=False, actor_id=None
    )
    post.is_pending = False
    post.created_at = post.publish_at
    post.save(update_fields=["raw_data", "is_pending", "created_at", "updated_at"])
    comun = community_service._post_comun(post)
    assignment = (
        post.comun_category_assignments.filter(comun=comun).select_related("category").first()
        if comun else None
    )
    category = assignment.category if assignment else None
    community_service.sync_comun_map_points_for_post(post, comun=comun)
    community_service._maybe_increment_comun_author_count_for_post(post, comun=comun)
    community_service._recalculate_comun_ratings_for_post(post)
    community_service._maybe_notify_new_author(post.author, post)
    community_service._maybe_notify_post_published_to_subscribers(
        post, actor=actor, comun=comun, category=category
    )
    if comun:
        community_service._maybe_notify_post_added_to_voting(
            post=post, comun=comun, category=category, actor=actor
        )
    return True


def publish_due_posts(*, now=None, continue_on_error=False):
    now = now or timezone.now()
    published = 0
    ids = list(_due_posts(now).order_by("publish_at").values_list("id", flat=True)[:100])
    for post_id in ids:
        try:
            published += int(_publish_post(post_id, now))
        except Exception:
            if not continue_on_error:
                raise
            logger.exception("Failed to publish scheduled post %s; retrying next cycle", post_id)
    return published


class Command(BaseCommand):
    help = "Publish due editor posts; --loop checks every second and catches up after restarts."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")

    def handle(self, *args, **options):
        # Also refresh on startup in case the previous process stopped after publishing.
        refresh_feed = True
        while True:
            try:
                close_old_connections()
                count = publish_due_posts(continue_on_error=options["loop"])
                refresh_feed = refresh_feed or bool(count)
                if refresh_feed:
                    call_command("rebuild_public_feed", stdout=self.stdout)
                    for prefix in (
                        "home-feed", "comun-posts", "author-posts", "tag-posts", "search", "comuns-sidebar"
                    ):
                        bump_public_cache_prefix(prefix)
                    refresh_feed = False
                if count:
                    self.stdout.write(f"Published {count} scheduled posts")
            except Exception:
                if not options["loop"]:
                    raise
                logger.exception("Scheduled publication failed; retrying")
            if not options["loop"]:
                return
            time.sleep(1)
