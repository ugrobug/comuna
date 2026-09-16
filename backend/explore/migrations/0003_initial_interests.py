from django.db import migrations


def seed(apps, schema_editor):
    Node = apps.get_model("explore", "Node")
    Edge = apps.get_model("explore", "Edge")
    nodes = {title: Node.objects.create(title=title, kind="element") for title in [
        "Вождение", "Мотоциклы", "Мотоджимхана", "Питбайк", "Туризм",
    ]}
    for source, target in [("Вождение", "Мотоциклы"), ("Мотоциклы", "Мотоджимхана"),
                           ("Мотоциклы", "Питбайк"), ("Туризм", "Питбайк")]:
        Edge.objects.create(source=nodes[source], target=nodes[target])


class Migration(migrations.Migration):
    dependencies = [("explore", "0002_property_catalog")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
