from django.db import migrations, models
import django.db.models.deletion


def forwards_copy_relations(apps, schema_editor):
    Tag = apps.get_model("feeds", "Tag")
    TagRelation = apps.get_model("feeds", "TagRelation")

    for tag in Tag.objects.exclude(relation_tag__isnull=True):
        TagRelation.objects.create(
            from_tag=tag,
            to_tag=tag.relation_tag,
            relation_type=tag.relation_type,
        )


def backwards_restore_relations(apps, schema_editor):
    Tag = apps.get_model("feeds", "Tag")
    TagRelation = apps.get_model("feeds", "TagRelation")

    Tag.objects.update(relation_tag=None, relation_type=None)

    for relation in TagRelation.objects.order_by("id"):
        if relation.from_tag_id and relation.to_tag_id:
            tag = relation.from_tag
            if tag.relation_tag_id is None:
                tag.relation_tag_id = relation.to_tag_id
                tag.relation_type_id = relation.relation_type_id
                tag.save(update_fields=["relation_tag", "relation_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0034_tag_relations"),
    ]

    operations = [
        migrations.CreateModel(
            name="TagRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "from_tag",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="relations", to="feeds.tag"),
                ),
                (
                    "relation_type",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="relations", to="feeds.tagrelationtype"),
                ),
                (
                    "to_tag",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="related_to", to="feeds.tag"),
                ),
            ],
            options={
                "ordering": ["from_tag__name", "to_tag__name"],
            },
        ),
        migrations.RunPython(forwards_copy_relations, backwards_restore_relations),
        migrations.RemoveField(
            model_name="tag",
            name="relation_tag",
        ),
        migrations.RemoveField(
            model_name="tag",
            name="relation_type",
        ),
    ]
