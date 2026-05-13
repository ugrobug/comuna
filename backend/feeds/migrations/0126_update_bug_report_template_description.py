from django.db import migrations


def update_bug_report_template_description(apps, schema_editor):
    PostTemplateConfig = apps.get_model("feeds", "PostTemplateConfig")
    PostTemplateConfig.objects.filter(template_type="bug_report").update(
        description="Платформа, браузер, код ошибки и скриншот."
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0125_merge_bug_report_template_and_postread_index"),
    ]

    operations = [
        migrations.RunPython(update_bug_report_template_description, noop_reverse),
    ]
