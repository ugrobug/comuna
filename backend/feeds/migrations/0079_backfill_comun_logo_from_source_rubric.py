from django.db import migrations


def backfill_comun_logo_from_source_rubric(apps, schema_editor):
    Comun = apps.get_model("feeds", "Comun")
    db_alias = schema_editor.connection.alias

    for comun in (
        Comun.objects.using(db_alias)
        .select_related("source_rubric")
        .filter(source_rubric__isnull=False)
        .order_by("id")
    ):
        if (comun.logo_url or "").strip():
            continue

        rubric = comun.source_rubric
        if not rubric:
            continue

        icon_url = ""
        try:
            if getattr(rubric, "icon_thumb", None) and rubric.icon_thumb.name:
                icon_url = rubric.icon_thumb.url or ""
            elif getattr(rubric, "icon_url", None) and rubric.icon_url.name:
                icon_url = rubric.icon_url.url or ""
        except Exception:
            icon_url = ""

        icon_url = str(icon_url or "").strip()
        if not icon_url:
            continue

        comun.logo_url = icon_url[:500]
        comun.save(update_fields=["logo_url"])


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0078_comun_source_rubric_backfill_from_rubrics"),
    ]

    operations = [
        migrations.RunPython(backfill_comun_logo_from_source_rubric, migrations.RunPython.noop),
    ]
