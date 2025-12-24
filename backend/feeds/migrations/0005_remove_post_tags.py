from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0004_author_avatar_rubric_icon"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="post",
            name="tags",
        ),
    ]
