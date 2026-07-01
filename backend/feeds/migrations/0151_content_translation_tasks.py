from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0150_userfeedsettings_interface_language"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentTranslationTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("post", "Пост"), ("comment", "Комментарий"), ("comun", "Сообщество")], max_length=16)),
                ("object_id", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("running", "Выполняется"), ("done", "Готово"), ("failed", "Ошибка"), ("skipped", "Пропущено")], db_index=True, default="pending", max_length=16)),
                ("scheduled_at", models.DateTimeField(db_index=True)),
                ("source_updated_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Задача перевода контента",
                "verbose_name_plural": "Задачи перевода контента",
            },
        ),
        migrations.CreateModel(
            name="ComunTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(choices=[("en", "Английский"), ("es", "Испанский"), ("pt", "Португальский"), ("de", "Немецкий"), ("fr", "Французский"), ("tr", "Турецкий"), ("id", "Индонезийский")], db_index=True, max_length=8)),
                ("product_description", models.TextField(blank=True)),
                ("rules_text", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "В процессе"), ("translated", "Переведен"), ("failed", "Ошибка")], db_index=True, default="pending", max_length=16)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("error_message", models.TextField(blank=True)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("comun", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="feeds.comun")),
            ],
            options={
                "verbose_name": "Перевод сообщества",
                "verbose_name_plural": "Переводы сообществ",
                "ordering": ["comun_id", "language"],
            },
        ),
        migrations.CreateModel(
            name="PostCommentTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(choices=[("en", "Английский"), ("es", "Испанский"), ("pt", "Португальский"), ("de", "Немецкий"), ("fr", "Французский"), ("tr", "Турецкий"), ("id", "Индонезийский")], db_index=True, max_length=8)),
                ("body", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "В процессе"), ("translated", "Переведен"), ("failed", "Ошибка")], db_index=True, default="pending", max_length=16)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("error_message", models.TextField(blank=True)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="feeds.postcomment")),
            ],
            options={
                "verbose_name": "Перевод комментария",
                "verbose_name_plural": "Переводы комментариев",
                "ordering": ["comment_id", "language"],
            },
        ),
        migrations.AddIndex(
            model_name="contenttranslationtask",
            index=models.Index(fields=["status", "scheduled_at"], name="content_trans_task_due_idx"),
        ),
        migrations.AddIndex(
            model_name="contenttranslationtask",
            index=models.Index(fields=["kind", "object_id"], name="content_trans_task_obj_idx"),
        ),
        migrations.AddConstraint(
            model_name="contenttranslationtask",
            constraint=models.UniqueConstraint(fields=("kind", "object_id"), name="unique_content_translation_task"),
        ),
        migrations.AddIndex(
            model_name="comuntranslation",
            index=models.Index(fields=["language", "status"], name="comun_trans_lang_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="comuntranslation",
            constraint=models.UniqueConstraint(fields=("comun", "language"), name="unique_comun_translation_language"),
        ),
        migrations.AddIndex(
            model_name="postcommenttranslation",
            index=models.Index(fields=["language", "status"], name="comment_trans_lang_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="postcommenttranslation",
            constraint=models.UniqueConstraint(fields=("comment", "language"), name="unique_comment_translation_language"),
        ),
    ]
