import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0165_postdraftaccess"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DraftBlockCommentThread",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("block_id", models.CharField(max_length=64)),
                ("block_index", models.PositiveIntegerField(default=0)),
                ("block_type", models.CharField(blank=True, default="", max_length=64)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="draft_comment_threads_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="draft_comment_threads",
                        to="feeds.post",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="draft_comment_threads_resolved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Обсуждение блока черновика",
                "verbose_name_plural": "Обсуждения блоков черновиков",
                "ordering": ("resolved_at", "created_at", "id"),
                "indexes": [
                    models.Index(
                        fields=["post", "block_id", "created_at"],
                        name="draftthread_post_block_idx",
                    ),
                    models.Index(
                        fields=["post", "resolved_at"],
                        name="draftthread_post_state_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DraftBlockComment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="feeds.draftblockcommentthread",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="draft_block_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Комментарий к блоку черновика",
                "verbose_name_plural": "Комментарии к блокам черновиков",
                "ordering": ("created_at", "id"),
                "indexes": [
                    models.Index(
                        fields=["thread", "created_at"],
                        name="draftcomment_thread_time_idx",
                    )
                ],
            },
        ),
    ]
