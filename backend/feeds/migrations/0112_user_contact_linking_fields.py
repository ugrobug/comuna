from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0111_delete_thematic_feed"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteuserprofile",
            name="phone",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="vkaccount",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="vkaccount",
            name="phone",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddIndex(
            model_name="siteuserprofile",
            index=models.Index(fields=["phone"], name="feeds_siteu_phone_43c849_idx"),
        ),
        migrations.AddIndex(
            model_name="vkaccount",
            index=models.Index(fields=["email"], name="feeds_vkacc_email_255939_idx"),
        ),
        migrations.AddIndex(
            model_name="vkaccount",
            index=models.Index(fields=["phone"], name="feeds_vkacc_phone_c5f49a_idx"),
        ),
    ]
