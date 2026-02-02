from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0033_tag_mood_neutral"),
    ]

    operations = [
        migrations.CreateModel(
            name="TagRelationType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="tag",
            name="lemma",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="tag",
            name="synonym",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="tag",
            name="relation_tag",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="related_from", to="feeds.tag"),
        ),
        migrations.AddField(
            model_name="tag",
            name="relation_type",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tag_relations", to="feeds.tagrelationtype"),
        ),
    ]
