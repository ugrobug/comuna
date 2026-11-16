from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("explore", "0004_node_image")]
    operations = [
        migrations.AddField(model_name="node", name="try_description", field=models.CharField(max_length=800, blank=True, default="")),
        migrations.AddField(model_name="node", name="try_step", field=models.CharField(max_length=180, blank=True, default="")),
    ]
