from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SpecialProjectLetterImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project_slug", models.SlugField(default="landname", max_length=80)),
                ("letter", models.CharField(max_length=4)),
                ("title", models.CharField(max_length=160)),
                ("location_name", models.CharField(blank=True, max_length=220)),
                ("image_url", models.URLField(blank=True, max_length=700)),
                ("map_url", models.URLField(blank=True, max_length=700)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("source_name", models.CharField(blank=True, max_length=160)),
                ("source_url", models.URLField(blank=True, max_length=700)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="special_project_letter_images",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Буква спецпроекта",
                "verbose_name_plural": "Буквы спецпроекта",
                "ordering": ("project_slug", "letter", "sort_order", "id"),
            },
        ),
        migrations.CreateModel(
            name="SpecialProjectLetterSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project_slug", models.SlugField(default="landname", max_length=80)),
                ("letter", models.CharField(max_length=4)),
                ("map_url", models.URLField(blank=True, max_length=700)),
                ("coordinates_text", models.CharField(blank=True, max_length=120)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("location_note", models.CharField(blank=True, max_length=280)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "На модерации"), ("approved", "Одобрено"), ("rejected", "Отклонено")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_special_project_letter_suggestions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="special_project_letter_suggestions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Предложение буквы спецпроекта",
                "verbose_name_plural": "Предложения букв спецпроекта",
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="specialprojectletterimage",
            index=models.Index(fields=["project_slug", "letter", "is_active"], name="special_pro_project_9a8ea3_idx"),
        ),
        migrations.AddIndex(
            model_name="specialprojectletterimage",
            index=models.Index(fields=["project_slug", "is_active", "sort_order"], name="special_pro_project_32b153_idx"),
        ),
        migrations.AddIndex(
            model_name="specialprojectlettersuggestion",
            index=models.Index(fields=["project_slug", "letter", "status"], name="special_pro_project_a157c2_idx"),
        ),
        migrations.AddIndex(
            model_name="specialprojectlettersuggestion",
            index=models.Index(fields=["submitted_by", "created_at"], name="special_pro_submitt_fae002_idx"),
        ),
    ]
