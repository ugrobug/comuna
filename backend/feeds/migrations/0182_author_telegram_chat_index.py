from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('feeds', '0181_siteuserprofile_bio')]
    operations = [AddIndexConcurrently(
        model_name='author',
        index=models.Index(fields=['channel_id'], name='author_telegram_chat_idx'),
    )]
