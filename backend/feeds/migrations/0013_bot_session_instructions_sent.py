from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0012_author_rubric_session_rubric"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsession",
            name="mode_selected",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="botsession",
            name="instructions_sent",
            field=models.BooleanField(default=False),
        ),
    ]
