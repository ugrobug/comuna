from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import landing_pages.models


def create_initial_landing_page(apps, schema_editor):
    LandingPage = apps.get_model("landing_pages", "LandingPage")
    LandingPage.objects.get_or_create(
        slug="communities",
        defaults={
            "title": "Платформа для создания и развития сообществ",
            "description": (
                "Создайте самостоятельное сообщество с рубриками, правилами, "
                "базой знаний, дорожной картой, ролями и публикациями."
            ),
            "template_slug": "community-platform",
            "is_published": True,
            "sort_order": 10,
        },
    )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LandingPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("template_slug", models.SlugField(default="community-platform", max_length=80)),
                ("is_published", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_landing_pages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_landing_pages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Посадочная страница",
                "verbose_name_plural": "Посадочные страницы",
                "ordering": ("sort_order", "title", "id"),
            },
        ),
        migrations.CreateModel(
            name="LandingPageImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slot", models.SlugField(default="hero", max_length=80)),
                ("title", models.CharField(max_length=160)),
                ("alt_text", models.CharField(blank=True, max_length=220)),
                ("image", models.ImageField(blank=True, upload_to=landing_pages.models.landing_page_image_path)),
                ("image_url", models.URLField(blank=True, max_length=700)),
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
                        related_name="created_landing_page_images",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="landing_pages.landingpage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Картинка посадочной страницы",
                "verbose_name_plural": "Картинки посадочных страниц",
                "ordering": ("page", "sort_order", "id"),
            },
        ),
        migrations.CreateModel(
            name="LandingPageLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(blank=True, max_length=80)),
                ("contact", models.CharField(max_length=180)),
                ("community_url", models.URLField(blank=True, max_length=700)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leads",
                        to="landing_pages.landingpage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Заявка с посадочной страницы",
                "verbose_name_plural": "Заявки с посадочных страниц",
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="landingpage",
            index=models.Index(fields=["is_published", "sort_order"], name="landing_pag_is_publ_f232e8_idx"),
        ),
        migrations.AddIndex(
            model_name="landingpage",
            index=models.Index(fields=["template_slug", "is_published"], name="landing_pag_templat_cea982_idx"),
        ),
        migrations.AddIndex(
            model_name="landingpageimage",
            index=models.Index(fields=["page", "slot", "is_active"], name="landing_pag_page_id_437b93_idx"),
        ),
        migrations.AddIndex(
            model_name="landingpageimage",
            index=models.Index(fields=["page", "is_active", "sort_order"], name="landing_pag_page_id_456817_idx"),
        ),
        migrations.AddIndex(
            model_name="landingpagelead",
            index=models.Index(fields=["page", "created_at"], name="landing_pag_page_id_9370e7_idx"),
        ),
        migrations.AddIndex(
            model_name="landingpagelead",
            index=models.Index(fields=["source", "created_at"], name="landing_pag_source_bb3f43_idx"),
        ),
        migrations.RunPython(create_initial_landing_page, migrations.RunPython.noop),
    ]
