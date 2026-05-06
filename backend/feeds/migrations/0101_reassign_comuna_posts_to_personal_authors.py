from django.db import migrations


def reassign_comuna_posts_to_personal_authors(apps, schema_editor):
    Rubric = apps.get_model("feeds", "Rubric")
    Post = apps.get_model("feeds", "Post")
    Author = apps.get_model("feeds", "Author")
    AuthorAdmin = apps.get_model("feeds", "AuthorAdmin")
    User = apps.get_model("auth", "User")

    comuna_rubric = Rubric.objects.filter(slug__iexact="comuna").first()
    if not comuna_rubric:
        return

    links_by_author_id: dict[int, int] = {}
    for link in AuthorAdmin.objects.filter(verified_at__isnull=False).order_by("created_at", "id"):
        if link.author_id and link.author_id not in links_by_author_id:
            links_by_author_id[int(link.author_id)] = int(link.user_id)

    personal_authors_by_user_id: dict[int, int] = {}

    def get_or_create_personal_author_id(user_id: int) -> int | None:
        cached = personal_authors_by_user_id.get(user_id)
        if cached:
            return cached

        user = User.objects.filter(id=user_id).only("id", "username").first()
        if not user:
            return None

        username = str(getattr(user, "username", "") or "").strip()
        if not username:
            return None

        personal_author = (
            Author.objects.filter(
                username__iexact=username,
                channel_url="",
                channel_id__isnull=True,
            )
            .order_by("id")
            .first()
        )
        if personal_author is None:
            personal_author = Author.objects.create(username=username, title=username)

        personal_authors_by_user_id[user_id] = int(personal_author.id)
        return int(personal_author.id)

    for post in Post.objects.filter(rubric_id=comuna_rubric.id).only("id", "author_id"):
        if not post.author_id:
            continue
        user_id = links_by_author_id.get(int(post.author_id))
        if not user_id:
            continue
        personal_author_id = get_or_create_personal_author_id(user_id)
        if not personal_author_id or int(post.author_id) == personal_author_id:
            continue
        Post.objects.filter(id=post.id).update(author_id=personal_author_id)


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0100_userfeedsettings"),
    ]

    operations = [
        migrations.RunPython(reassign_comuna_posts_to_personal_authors, migrations.RunPython.noop),
    ]
