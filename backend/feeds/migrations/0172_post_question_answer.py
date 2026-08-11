from django.db import migrations, models
import django.db.models.deletion


def ensure_question_template(apps, schema_editor):
    PostTemplateConfig = apps.get_model("feeds", "PostTemplateConfig")
    basic = PostTemplateConfig.objects.filter(template_type="basic").first()
    enabled_blocks = list(
        getattr(basic, "enabled_editor_blocks", [])
        or [
            "header",
            "toc",
            "list",
            "table",
            "image",
            "quote",
            "callout",
            "author",
            "code",
            "poll",
            "divider",
            "spoiler",
            "gallery",
            "map",
            "compare",
            "link",
            "embed",
            "post_link",
            "music",
            "movie_time",
            "post_rating",
        ]
    )
    PostTemplateConfig.objects.update_or_create(
        template_type="question",
        defaults={
            "label": "Вопрос",
            "description": "Вопрос с возможностью выбрать правильный ответ из комментариев.",
            "enabled_editor_blocks": enabled_blocks,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0171_comun_telegram_ai_summary_and_bot_forward_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="accepted_answer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="accepted_for_questions",
                to="feeds.postcomment",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="question_solved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(ensure_question_template, migrations.RunPython.noop),
    ]
