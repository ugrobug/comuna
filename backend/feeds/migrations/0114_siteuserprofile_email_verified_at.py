from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0113_site_auth_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteuserprofile",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
