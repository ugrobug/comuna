from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0086_backfill_author_template_block"),
    ]

    operations = [
        migrations.AddField(
            model_name="postratingvote",
            name="block_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterUniqueTogether(
            name="postratingvote",
            unique_together={("post", "user", "block_id")},
        ),
    ]
