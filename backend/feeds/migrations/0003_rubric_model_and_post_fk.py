from django.db import migrations, models
import django.db.models.deletion


def migrate_rubrics(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    Rubric = apps.get_model("feeds", "Rubric")

    existing = (
        Post.objects.exclude(rubric="")
        .exclude(rubric__isnull=True)
        .values_list("rubric", flat=True)
        .distinct()
    )

    rubric_map = {}
    for name in existing:
        slug = str(name).strip().lower().replace(" ", "-")[:120]
        rubric, _ = Rubric.objects.get_or_create(name=name, defaults={"slug": slug})
        rubric_map[name] = rubric

    for post in Post.objects.all():
        if post.rubric:
            rubric = rubric_map.get(post.rubric)
            if rubric:
                post.rubric_ref = rubric
                post.save(update_fields=["rubric_ref"])


def reverse_migrate_rubrics(apps, schema_editor):
    Post = apps.get_model("feeds", "Post")
    for post in Post.objects.all():
        if post.rubric_ref:
            post.rubric = post.rubric_ref.name
            post.save(update_fields=["rubric"])


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0002_post_rubric_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="Rubric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="post",
            name="rubric_ref",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="posts", to="feeds.rubric"),
        ),
        migrations.RunPython(migrate_rubrics, reverse_migrate_rubrics),
        migrations.RemoveField(
            model_name="post",
            name="rubric",
        ),
        migrations.RenameField(
            model_name="post",
            old_name="rubric_ref",
            new_name="rubric",
        ),
    ]
