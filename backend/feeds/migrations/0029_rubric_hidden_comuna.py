from django.db import migrations, models


def ensure_comuna_rubric(apps, schema_editor):
    Rubric = apps.get_model('feeds', 'Rubric')
    rubric = Rubric.objects.filter(slug__iexact='comuna').first()
    if rubric is None:
        Rubric.objects.create(
            name='Comuna',
            slug='comuna',
            is_active=True,
            is_hidden=True,
            sort_order=0,
            home_limit=3,
        )
        return

    update_fields = []
    if rubric.name != 'Comuna':
        rubric.name = 'Comuna'
        update_fields.append('name')
    if not rubric.is_active:
        rubric.is_active = True
        update_fields.append('is_active')
    if not rubric.is_hidden:
        rubric.is_hidden = True
        update_fields.append('is_hidden')
    if update_fields:
        rubric.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0028_vk_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='rubric',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(ensure_comuna_rubric, migrations.RunPython.noop),
    ]
