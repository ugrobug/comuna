from django.db import migrations


def seed(apps, schema_editor):
    Definition = apps.get_model("explore", "PropertyDefinition")
    Option = apps.get_model("explore", "PropertyOption")
    money = ["Бесплатно", "Меньше 1 000 ₽", "1–5 тыс. ₽", "5–10 тыс. ₽", "10–50 тыс. ₽", "50–100 тыс. ₽", "100–300 тыс. ₽", "Больше 300 тыс. ₽"]
    catalog = [
        ("company", "Компания", ["Можно одному", "С друзьями", "С детьми", "Всей семьёй"]),
        ("entry_cost", "Стоимость входа", money),
        ("monthly_cost", "Стоимость в месяц активности", money),
        ("danger", "Опасность", ["Безопасно", "Умеренно", "Экстремально"]),
        ("difficulty", "Сложность вхождения", ["Лёгкая", "Средняя", "Сложная"]),
    ]
    for position, (key, name, options) in enumerate(catalog):
        definition = Definition.objects.create(key=key, name=name, position=position)
        for index, label in enumerate(options):
            Option.objects.create(property=definition, value=str(index), label=label, position=index)
    apps.get_model("explore", "GraphState").objects.create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("explore", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
