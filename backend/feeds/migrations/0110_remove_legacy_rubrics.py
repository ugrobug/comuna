from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0109_posttemplateconfig_description"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="author",
            name="rubric",
        ),
        migrations.RemoveField(
            model_name="botsession",
            name="rubric",
        ),
        migrations.RemoveField(
            model_name="comun",
            name="source_rubric",
        ),
        migrations.RemoveField(
            model_name="post",
            name="rubric",
        ),
        migrations.RemoveField(
            model_name="thematicfeed",
            name="rubrics",
        ),
        migrations.RemoveField(
            model_name="userfeedsettings",
            name="my_feed_rubrics",
        ),
        migrations.DeleteModel(
            name="Rubric",
        ),
    ]
