from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def backfill_comun_cached_counts(apps, schema_editor):
    Comun = apps.get_model("feeds", "Comun")
    Post = apps.get_model("feeds", "Post")
    User = apps.get_model("auth", "User")
    UserFeedSettings = apps.get_model("feeds", "UserFeedSettings")

    subscriber_counts = {}
    for settings in UserFeedSettings.objects.using(schema_editor.connection.alias).all().iterator(chunk_size=500):
        subscribed_slugs = {
            str(slug or "").strip()
            for slug in (settings.my_feed_comuns or [])
            if str(slug or "").strip()
        }
        category_selection = settings.my_feed_comun_categories or {}
        if isinstance(category_selection, dict):
            subscribed_slugs.update(
                str(slug or "").strip()
                for slug in category_selection.keys()
                if str(slug or "").strip()
            )
        for slug in subscribed_slugs:
            subscriber_counts[slug] = subscriber_counts.get(slug, 0) + 1

    now = timezone.now()
    site_usernames = User.objects.using(schema_editor.connection.alias).filter(
        is_active=True,
    ).values("username")
    for comun in Comun.objects.using(schema_editor.connection.alias).all().iterator(chunk_size=200):
        membership_filter = Q(
            raw_data__source="manual_comun",
            raw_data__comun_slug=comun.slug,
        ) | Q(comun_category_assignments__comun_id=comun.id)
        if comun.telegram_source_author_id:
            membership_filter |= Q(author_id=comun.telegram_source_author_id)

        posts = (
            Post.objects.using(schema_editor.connection.alias)
            .filter(
                membership_filter,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now))
            .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
        )

        excluded_author_ids = list(
            comun.excluded_authors.using(schema_editor.connection.alias)
            .filter(is_blocked=False)
            .values_list("id", flat=True)
        )
        if excluded_author_ids:
            posts = posts.exclude(author_id__in=excluded_author_ids)

        site_authors_count = (
            posts.filter(
                author__channel_id__isnull=True,
                author__channel_url="",
                author__invite_url="",
                author__username__in=site_usernames,
            )
            .exclude(author_id__isnull=True)
            .values("author_id")
            .distinct()
            .count()
        )
        authors_count = site_authors_count or (1 if posts.exists() else 0)
        Comun.objects.using(schema_editor.connection.alias).filter(id=comun.id).update(
            subscribers_count=int(subscriber_counts.get(comun.slug, 0) or 0),
            authors_count=int(authors_count or 0),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0133_siteuserprofile_registration_path_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="authors_count",
            field=models.PositiveIntegerField(default=0, verbose_name="Авторов"),
        ),
        migrations.AddField(
            model_name="comun",
            name="subscribers_count",
            field=models.PositiveIntegerField(default=0, verbose_name="Подписчиков"),
        ),
        migrations.RunPython(backfill_comun_cached_counts, migrations.RunPython.noop),
    ]
