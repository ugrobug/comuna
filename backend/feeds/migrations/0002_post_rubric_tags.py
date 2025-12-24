from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="rubric",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="post",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
