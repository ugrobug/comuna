from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0052_comun_category_backlog_and_suggestions_rename"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="comun",
            name="rating_score",
            field=models.IntegerField(default=0, verbose_name="Рейтинг"),
        ),
        migrations.AddField(
            model_name="comun",
            name="votes_down",
            field=models.PositiveIntegerField(default=0, verbose_name="Не нравится"),
        ),
        migrations.AddField(
            model_name="comun",
            name="votes_up",
            field=models.PositiveIntegerField(default=0, verbose_name="Буду использовать"),
        ),
        migrations.CreateModel(
            name="ComunVote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.SmallIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "comun",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes",
                        to="feeds.comun",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comun_votes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Голос за коммуну",
                "verbose_name_plural": "Голоса за комуны",
                "unique_together": {("comun", "user")},
            },
        ),
    ]

