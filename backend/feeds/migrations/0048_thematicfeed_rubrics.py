from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0047_thematicfeed"),
    ]

    operations = [
        migrations.AddField(
            model_name="thematicfeed",
            name="rubrics",
            field=models.ManyToManyField(
                blank=True,
                help_text="Посты этих рубрик будут добавляться в папку.",
                related_name="thematic_feeds_included",
                to="feeds.rubric",
                verbose_name="Рубрики",
            ),
        ),
    ]
