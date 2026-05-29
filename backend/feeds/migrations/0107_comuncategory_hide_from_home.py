from django.db import migrations, models


def copy_comun_visibility_to_categories(apps, schema_editor):
    comun_category = apps.get_model("feeds", "ComunCategory")
    comun_category.objects.filter(comun__hide_from_home=True).update(hide_from_home=True)


def clear_category_visibility(apps, schema_editor):
    comun_category = apps.get_model("feeds", "ComunCategory")
    comun_category.objects.update(hide_from_home=False)


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0106_comun_rating_from_posts"),
    ]

    operations = [
        migrations.AddField(
            model_name="comuncategory",
            name="hide_from_home",
            field=models.BooleanField(
                default=False,
                help_text="Посты этой категории не будут попадать в Горячее.",
                verbose_name="Не показывать в горячем",
            ),
        ),
        migrations.RunPython(copy_comun_visibility_to_categories, clear_category_visibility),
    ]
