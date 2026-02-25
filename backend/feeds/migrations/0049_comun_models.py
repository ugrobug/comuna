from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_comun_categories(apps, schema_editor):
    ComunCategory = apps.get_model("feeds", "ComunCategory")
    defaults = [
        ("release-notes", "Release note", "Обновления продукта и релизы", 10),
        ("reviews", "Отзывы", "Отзывы пользователей о продукте", 20),
        ("feature-ideas", "Предложения будущих фич", "Идеи и пожелания по развитию", 30),
        ("faq", "FAQ", "Частые вопросы и ответы", 40),
        ("cases", "Кейсы", "Примеры использования продукта", 50),
        ("announcements", "Анонсы", "Анонсы событий, запусков и новостей", 60),
    ]
    for slug, name, description, sort_order in defaults:
        ComunCategory.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


def unseed_comun_categories(apps, schema_editor):
    ComunCategory = apps.get_model("feeds", "ComunCategory")
    ComunCategory.objects.filter(
        slug__in=[
            "release-notes",
            "reviews",
            "feature-ideas",
            "faq",
            "cases",
            "announcements",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0048_thematicfeed_rubrics"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ComunCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Категория комуны",
                "verbose_name_plural": "Категории коммун",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Comun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, unique=True)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("website_url", models.URLField(blank=True, max_length=500, verbose_name="Веб-сайт")),
                ("logo_url", models.URLField(blank=True, max_length=500, verbose_name="Логотип (URL)")),
                ("product_description", models.TextField(blank=True, verbose_name="Описание продукта")),
                ("target_audience", models.TextField(blank=True, verbose_name="Целевая аудитория")),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "creator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="created_comuns",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Создатель",
                    ),
                ),
                (
                    "product_tag",
                    models.ForeignKey(
                        blank=True,
                        help_text="Все посты с этим тегом попадут в коммуну.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="comuns",
                        to="feeds.tag",
                        verbose_name="Тег продукта",
                    ),
                ),
                (
                    "welcome_post",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welcome_for_comuns",
                        to="feeds.post",
                        verbose_name="Приветственный пост",
                    ),
                ),
                (
                    "categories",
                    models.ManyToManyField(blank=True, related_name="comuns", to="feeds.comuncategory", verbose_name="Внутренние категории"),
                ),
                (
                    "moderators",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Пользователи, которые могут редактировать карточку комуны и категоризировать посты.",
                        related_name="moderated_comuns",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Модераторы",
                    ),
                ),
            ],
            options={
                "verbose_name": "Комуна",
                "verbose_name_plural": "Комуны",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="ComunPostCategoryAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_comun_post_categories",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="post_assignments",
                        to="feeds.comuncategory",
                    ),
                ),
                (
                    "comun",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="post_category_assignments",
                        to="feeds.comun",
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comun_category_assignments",
                        to="feeds.post",
                    ),
                ),
            ],
            options={
                "verbose_name": "Категория поста в комуне",
                "verbose_name_plural": "Категории постов в коммунах",
                "unique_together": {("comun", "post")},
            },
        ),
        migrations.RunPython(seed_comun_categories, unseed_comun_categories),
    ]

