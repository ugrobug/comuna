from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0156_comun_post_feed_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="comuntranslation",
            name="name",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="comuntranslation",
            name="target_audience",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="comuntranslation",
            name="categories",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="comuntranslation",
            name="glossary_terms",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
