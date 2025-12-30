from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0018_author_first_post_notified"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="avatar_file_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="author",
            name="avatar_image",
            field=models.ImageField(blank=True, upload_to="authors/avatars/"),
        ),
    ]
