from django.db import migrations


def forwards(apps, schema_editor):
    ComunCategory = apps.get_model("feeds", "ComunCategory")

    # Rename the seeded "feature ideas" category to a shorter label.
    ComunCategory.objects.update_or_create(
        slug="feature-ideas",
        defaults={
            "name": "Предложения",
            "description": "Идеи и пожелания по развитию продукта",
            "sort_order": 30,
            "is_active": True,
        },
    )

    # Add a dedicated backlog category for moderators/founders.
    ComunCategory.objects.update_or_create(
        slug="backlog",
        defaults={
            "name": "Беклог",
            "description": "Предложения и задачи, взятые в работу",
            "sort_order": 35,
            "is_active": True,
        },
    )


def backwards(apps, schema_editor):
    ComunCategory = apps.get_model("feeds", "ComunCategory")
    ComunCategory.objects.filter(slug="feature-ideas").update(
        name="Предложения будущих фич",
        description="Идеи и пожелания по развитию",
    )
    # Keep backlog category on rollback to avoid deleting user data/assignments.


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0051_comun_hide_from_fresh_comun_hide_from_home"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

