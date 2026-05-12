from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0115_strip_private_telegram_file_urls"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="author",
            index=models.Index(fields=["is_blocked", "shadow_banned", "force_home"], name="author_home_flags_idx"),
        ),
        migrations.AddIndex(
            model_name="author",
            index=models.Index(fields=["-rating_total"], name="author_rating_idx"),
        ),
        migrations.AddIndex(
            model_name="tag",
            index=models.Index(fields=["hide_from_home"], name="tag_hide_home_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["is_blocked", "is_pending", "-created_at"], name="post_public_created_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["author", "is_blocked", "is_pending", "-created_at"], name="post_author_created_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["publish_at", "-created_at"], name="post_publish_created_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["-rating", "-created_at"], name="post_rating_created_idx"),
        ),
        migrations.AddIndex(
            model_name="postcomment",
            index=models.Index(fields=["post", "is_deleted", "created_at"], name="comment_post_created_idx"),
        ),
        migrations.AddIndex(
            model_name="postcomment",
            index=models.Index(fields=["is_deleted", "-created_at"], name="comment_recent_idx"),
        ),
        migrations.AddIndex(
            model_name="postread",
            index=models.Index(fields=["user", "-read_at"], name="postread_user_recent_idx"),
        ),
        migrations.AddIndex(
            model_name="postfavorite",
            index=models.Index(fields=["user", "-created_at"], name="favorite_user_recent_idx"),
        ),
        migrations.AddIndex(
            model_name="comuncategory",
            index=models.Index(fields=["hide_from_home"], name="comcat_hide_home_idx"),
        ),
        migrations.AddIndex(
            model_name="comuncategory",
            index=models.Index(fields=["comun", "is_active", "sort_order"], name="comcat_active_sort_idx"),
        ),
        migrations.AddIndex(
            model_name="comun",
            index=models.Index(fields=["is_active", "-rating_score", "sort_order"], name="comun_active_rating_idx"),
        ),
        migrations.AddIndex(
            model_name="comun",
            index=models.Index(fields=["hide_from_home"], name="comun_hide_home_idx"),
        ),
        migrations.AddIndex(
            model_name="comunpostcategoryassignment",
            index=models.Index(fields=["category", "post"], name="compost_cat_post_idx"),
        ),
        migrations.AddIndex(
            model_name="comunpostcategoryassignment",
            index=models.Index(fields=["post", "comun"], name="compost_post_comun_idx"),
        ),
    ]
