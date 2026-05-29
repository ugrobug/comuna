from django.db import migrations


PRIVATE_TELEGRAM_FILE_MARKER = "api.telegram.org/file/bot"


def strip_private_telegram_file_urls(apps, schema_editor):
    Author = apps.get_model("feeds", "Author")
    Comun = apps.get_model("feeds", "Comun")
    SiteUserProfile = apps.get_model("feeds", "SiteUserProfile")
    TelegramAccount = apps.get_model("feeds", "TelegramAccount")
    VkAccount = apps.get_model("feeds", "VkAccount")

    Author.objects.filter(avatar_url__contains=PRIVATE_TELEGRAM_FILE_MARKER).update(avatar_url="")
    Comun.objects.filter(logo_url__contains=PRIVATE_TELEGRAM_FILE_MARKER).update(logo_url="")
    SiteUserProfile.objects.filter(avatar_url__contains=PRIVATE_TELEGRAM_FILE_MARKER).update(avatar_url="")
    TelegramAccount.objects.filter(avatar_url__contains=PRIVATE_TELEGRAM_FILE_MARKER).update(avatar_url="")
    VkAccount.objects.filter(avatar_url__contains=PRIVATE_TELEGRAM_FILE_MARKER).update(avatar_url="")


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0114_siteuserprofile_email_verified_at"),
    ]

    operations = [
        migrations.RunPython(strip_private_telegram_file_urls, migrations.RunPython.noop),
    ]
