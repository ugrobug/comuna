from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0029_rubric_hidden_comuna"),
    ]

    operations = [
        migrations.CreateModel(
            name="PostRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="feeds.post")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="post_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("post", "user")},
            },
        ),
    ]

