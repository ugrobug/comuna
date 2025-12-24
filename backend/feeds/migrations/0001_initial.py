from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Author",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("channel_url", models.URLField(blank=True, max_length=255)),
                ("is_blocked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message_id", models.BigIntegerField()),
                ("title", models.CharField(blank=True, max_length=255)),
                ("content", models.TextField(blank=True)),
                ("source_url", models.URLField(blank=True, max_length=255)),
                ("channel_url", models.URLField(blank=True, max_length=255)),
                ("is_blocked", models.BooleanField(default=False)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="posts", to="feeds.author"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("author", "message_id")},
            },
        ),
    ]
