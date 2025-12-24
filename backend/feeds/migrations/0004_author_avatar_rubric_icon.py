from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0003_rubric_model_and_post_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="avatar_url",
            field=models.URLField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="rubric",
            name="icon_url",
            field=models.URLField(blank=True, max_length=255),
        ),
    ]
