from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0040_postpollvote"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubric",
            name="hide_from_home",
            field=models.BooleanField(
                default=False,
                help_text="Если включено, посты этой рубрики не попадут в ленту «Горячее».",
                verbose_name="Не показывать на главной",
            ),
        ),
        migrations.AddField(
            model_name="tag",
            name="hide_from_home",
            field=models.BooleanField(
                default=False,
                help_text="Если включено, посты с этим тегом не попадут в ленту «Горячее».",
                verbose_name="Не показывать на главной",
            ),
        ),
    ]
