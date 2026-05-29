from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0123_posttemplateconfig_is_active"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="postread",
            index=models.Index(fields=["user", "post"], name="postread_user_post_idx"),
        ),
    ]
