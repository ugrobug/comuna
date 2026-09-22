from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("explore", "0003_initial_interests")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="image",
            field=models.ImageField(blank=True, upload_to="explore/cards/"),
        ),
    ]
