# Сгенерировано: python manage.py inspectdb_romawho
# Не править вручную — перегенерировать командой.

# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Wp404To301(models.Model):
    id = models.BigAutoField(primary_key=True)
    date = models.DateTimeField()
    url = models.CharField(max_length=512)
    ref = models.CharField(max_length=512)
    ip = models.CharField(max_length=40)
    ua = models.CharField(max_length=512)
    redirect = models.CharField(max_length=512, blank=True, null=True)
    options = models.TextField(blank=True, null=True)
    status = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_404_to_301'


class WpActionschedulerActions(models.Model):
    action_id = models.BigAutoField(primary_key=True)
    hook = models.CharField(max_length=191)
    status = models.CharField(max_length=20)
    scheduled_date_gmt = models.DateTimeField(blank=True, null=True)
    scheduled_date_local = models.DateTimeField(blank=True, null=True)
    args = models.CharField(max_length=191, blank=True, null=True)
    schedule = models.TextField(blank=True, null=True)
    group_id = models.PositiveBigIntegerField()
    attempts = models.IntegerField()
    last_attempt_gmt = models.DateTimeField(blank=True, null=True)
    last_attempt_local = models.DateTimeField(blank=True, null=True)
    claim_id = models.PositiveBigIntegerField()
    extended_args = models.CharField(max_length=8000, blank=True, null=True)
    priority = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_actionscheduler_actions'


class WpActionschedulerClaims(models.Model):
    claim_id = models.BigAutoField(primary_key=True)
    date_created_gmt = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_actionscheduler_claims'


class WpActionschedulerGroups(models.Model):
    group_id = models.BigAutoField(primary_key=True)
    slug = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'wp_actionscheduler_groups'


class WpActionschedulerLogs(models.Model):
    log_id = models.BigAutoField(primary_key=True)
    action_id = models.PositiveBigIntegerField()
    message = models.TextField()
    log_date_gmt = models.DateTimeField(blank=True, null=True)
    log_date_local = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_actionscheduler_logs'


class WpAioseoCache(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.CharField(unique=True, max_length=80)
    value = models.TextField()
    expiration = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField()
    updated = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_aioseo_cache'


class WpAioseoNotifications(models.Model):
    id = models.BigAutoField(primary_key=True)
    slug = models.CharField(unique=True, max_length=13)
    addon = models.CharField(max_length=64, blank=True, null=True)
    title = models.TextField()
    content = models.TextField()
    type = models.CharField(max_length=64)
    level = models.TextField()
    notification_id = models.PositiveBigIntegerField(blank=True, null=True)
    notification_name = models.CharField(max_length=255, blank=True, null=True)
    start = models.DateTimeField(blank=True, null=True)
    end = models.DateTimeField(blank=True, null=True)
    button1_label = models.CharField(max_length=255, blank=True, null=True)
    button1_action = models.CharField(max_length=255, blank=True, null=True)
    button2_label = models.CharField(max_length=255, blank=True, null=True)
    button2_action = models.CharField(max_length=255, blank=True, null=True)
    dismissed = models.IntegerField()
    new = models.IntegerField()
    created = models.DateTimeField()
    updated = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_aioseo_notifications'


class WpAioseoPosts(models.Model):
    id = models.BigAutoField(primary_key=True)
    post_id = models.PositiveBigIntegerField()
    title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    keywords = models.TextField(blank=True, null=True)
    keyphrases = models.TextField(blank=True, null=True)
    page_analysis = models.TextField(blank=True, null=True)
    primary_term = models.TextField(blank=True, null=True)
    canonical_url = models.TextField(blank=True, null=True)
    og_title = models.TextField(blank=True, null=True)
    og_description = models.TextField(blank=True, null=True)
    og_object_type = models.CharField(max_length=64, blank=True, null=True)
    og_image_type = models.CharField(max_length=64, blank=True, null=True)
    og_image_url = models.TextField(blank=True, null=True)
    og_image_width = models.IntegerField(blank=True, null=True)
    og_image_height = models.IntegerField(blank=True, null=True)
    og_image_custom_url = models.TextField(blank=True, null=True)
    og_image_custom_fields = models.TextField(blank=True, null=True)
    og_video = models.CharField(max_length=255, blank=True, null=True)
    og_custom_url = models.TextField(blank=True, null=True)
    og_article_section = models.TextField(blank=True, null=True)
    og_article_tags = models.TextField(blank=True, null=True)
    twitter_use_og = models.IntegerField(blank=True, null=True)
    twitter_card = models.CharField(max_length=64, blank=True, null=True)
    twitter_image_type = models.CharField(max_length=64, blank=True, null=True)
    twitter_image_url = models.TextField(blank=True, null=True)
    twitter_image_custom_url = models.TextField(blank=True, null=True)
    twitter_image_custom_fields = models.TextField(blank=True, null=True)
    twitter_title = models.TextField(blank=True, null=True)
    twitter_description = models.TextField(blank=True, null=True)
    seo_score = models.IntegerField()
    schema = models.TextField(blank=True, null=True)
    schema_type = models.CharField(max_length=20, blank=True, null=True)
    schema_type_options = models.TextField(blank=True, null=True)
    pillar_content = models.IntegerField(blank=True, null=True)
    robots_default = models.IntegerField()
    robots_noindex = models.IntegerField()
    robots_noarchive = models.IntegerField()
    robots_nosnippet = models.IntegerField()
    robots_nofollow = models.IntegerField()
    robots_noimageindex = models.IntegerField()
    robots_noodp = models.IntegerField()
    robots_notranslate = models.IntegerField()
    robots_max_snippet = models.IntegerField(blank=True, null=True)
    robots_max_videopreview = models.IntegerField(blank=True, null=True)
    robots_max_imagepreview = models.CharField(max_length=20, blank=True, null=True)
    images = models.TextField(blank=True, null=True)
    image_scan_date = models.DateTimeField(blank=True, null=True)
    priority = models.FloatField(blank=True, null=True)
    frequency = models.TextField(blank=True, null=True)
    videos = models.TextField(blank=True, null=True)
    video_thumbnail = models.TextField(blank=True, null=True)
    video_scan_date = models.DateTimeField(blank=True, null=True)
    local_seo = models.TextField(blank=True, null=True)
    limit_modified_date = models.IntegerField()
    options = models.TextField(blank=True, null=True)
    created = models.DateTimeField()
    updated = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_aioseo_posts'


class WpAnycommentEmailQueue(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    post_id = models.PositiveBigIntegerField(db_column='post_ID', blank=True, null=True)  # Field name made lowercase.
    comment_id = models.PositiveBigIntegerField(db_column='comment_ID', blank=True, null=True)  # Field name made lowercase.
    subject = models.CharField(max_length=255)
    email = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField(db_collation='utf8_unicode_ci')
    ip = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    user_agent = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    is_sent = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_anycomment_email_queue'


class WpAnycommentLikes(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    user_id = models.PositiveBigIntegerField(db_column='user_ID', blank=True, null=True)  # Field name made lowercase.
    comment_id = models.PositiveBigIntegerField(db_column='comment_ID')  # Field name made lowercase.
    post_id = models.PositiveBigIntegerField(db_column='post_ID')  # Field name made lowercase.
    type = models.IntegerField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    ip = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    liked_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_anycomment_likes'


class WpAnycommentRating(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    post_id = models.PositiveBigIntegerField(db_column='post_ID')  # Field name made lowercase.
    user_id = models.PositiveBigIntegerField(db_column='user_ID', blank=True, null=True)  # Field name made lowercase.
    rating = models.SmallIntegerField(blank=True, null=True)
    ip = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    user_agent = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    created_at = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_anycomment_rating'


class WpAnycommentSubscriptions(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    post_id = models.PositiveBigIntegerField(db_column='post_ID')  # Field name made lowercase.
    user_id = models.PositiveBigIntegerField(db_column='user_ID', blank=True, null=True)  # Field name made lowercase.
    email = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    is_active = models.SmallIntegerField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    ip = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    token = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    confirmed_at = models.BigIntegerField(blank=True, null=True)
    created_at = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_anycomment_subscriptions'


class WpAnycommentUploadedFiles(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    post_id = models.PositiveBigIntegerField(db_column='post_ID')  # Field name made lowercase.
    user_id = models.PositiveBigIntegerField(db_column='user_ID', blank=True, null=True)  # Field name made lowercase.
    type = models.CharField(max_length=255)
    ip = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    url = models.CharField(max_length=255, db_collation='utf8_unicode_ci')
    url_thumbnail = models.CharField(max_length=255, blank=True, null=True)
    user_agent = models.CharField(max_length=255, db_collation='utf8_unicode_ci', blank=True, null=True)
    created_at = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_anycomment_uploaded_files'


class WpCommentmeta(models.Model):
    meta_id = models.BigAutoField(primary_key=True)
    comment_id = models.PositiveBigIntegerField()
    meta_key = models.CharField(max_length=255, blank=True, null=True)
    meta_value = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_commentmeta'


class WpComments(models.Model):
    comment_id = models.BigAutoField(db_column='comment_ID', primary_key=True)  # Field name made lowercase.
    comment_post_id = models.PositiveBigIntegerField(db_column='comment_post_ID')  # Field name made lowercase.
    comment_author = models.TextField()
    comment_author_email = models.CharField(max_length=100)
    comment_author_url = models.CharField(max_length=200)
    comment_author_ip = models.CharField(db_column='comment_author_IP', max_length=100)  # Field name made lowercase.
    comment_date = models.DateTimeField()
    comment_date_gmt = models.DateTimeField()
    comment_content = models.TextField()
    comment_karma = models.IntegerField()
    comment_approved = models.CharField(max_length=20)
    comment_agent = models.CharField(max_length=255)
    comment_type = models.CharField(max_length=20)
    comment_parent = models.PositiveBigIntegerField()
    user_id = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_comments'


class WpEwwwioImages(models.Model):
    id = models.BigAutoField(primary_key=True)
    attachment_id = models.PositiveBigIntegerField(blank=True, null=True)
    gallery = models.CharField(max_length=10, blank=True, null=True)
    resize = models.CharField(max_length=75, blank=True, null=True)
    path = models.TextField()
    converted = models.TextField()
    image_size = models.PositiveIntegerField(blank=True, null=True)
    orig_size = models.PositiveIntegerField(blank=True, null=True)
    backup = models.CharField(max_length=100, blank=True, null=True)
    level = models.PositiveIntegerField(blank=True, null=True)
    pending = models.IntegerField()
    updates = models.PositiveIntegerField(blank=True, null=True)
    updated = models.DateTimeField()
    retrieve = models.CharField(max_length=100, blank=True, null=True)
    resized_width = models.PositiveSmallIntegerField(blank=True, null=True)
    resized_height = models.PositiveSmallIntegerField(blank=True, null=True)
    resize_error = models.PositiveIntegerField(blank=True, null=True)
    webp_size = models.PositiveIntegerField(blank=True, null=True)
    webp_error = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_ewwwio_images'


class WpEwwwioPages(models.Model):
    id = models.BigAutoField(primary_key=True)
    page = models.CharField(unique=True, max_length=255, blank=True, null=True)
    data = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_ewwwio_pages'


class WpEwwwioQueue(models.Model):
    attachment_id = models.PositiveBigIntegerField(blank=True, null=True)
    gallery = models.CharField(max_length=20, blank=True, null=True)
    scanned = models.IntegerField()
    new = models.IntegerField()
    id = models.BigAutoField(primary_key=True)
    convert_once = models.IntegerField()
    force_reopt = models.IntegerField()
    force_smart = models.IntegerField()
    webp_only = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_ewwwio_queue'


class WpExactmetricsCache(models.Model):
    cache_id = models.BigAutoField(primary_key=True)
    cache_key = models.CharField(max_length=255)
    cache_value = models.TextField()
    cache_group = models.CharField(max_length=64, blank=True, null=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_exactmetrics_cache'
        unique_together = (('cache_key', 'cache_group'),)


class WpLinks(models.Model):
    link_id = models.BigAutoField(primary_key=True)
    link_url = models.CharField(max_length=255)
    link_name = models.CharField(max_length=255)
    link_image = models.CharField(max_length=255)
    link_target = models.CharField(max_length=25)
    link_description = models.CharField(max_length=255)
    link_visible = models.CharField(max_length=20)
    link_owner = models.PositiveBigIntegerField()
    link_rating = models.IntegerField()
    link_updated = models.DateTimeField()
    link_rel = models.CharField(max_length=255)
    link_notes = models.TextField()
    link_rss = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'wp_links'


class WpMailpoetCustomFields(models.Model):
    name = models.CharField(unique=True, max_length=90)
    type = models.CharField(max_length=90)
    params = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_custom_fields'


class WpMailpoetDynamicSegmentFilters(models.Model):
    segment_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    filter_data = models.TextField(blank=True, null=True)
    filter_type = models.CharField(max_length=255, blank=True, null=True)
    action = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_dynamic_segment_filters'


class WpMailpoetFeatureFlags(models.Model):
    name = models.CharField(unique=True, max_length=100)
    value = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_feature_flags'


class WpMailpoetForms(models.Model):
    name = models.CharField(max_length=90)
    status = models.CharField(max_length=20)
    body = models.TextField(blank=True, null=True)
    settings = models.TextField(blank=True, null=True)
    styles = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_forms'


class WpMailpoetLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    level = models.IntegerField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_log'


class WpMailpoetMappingToExternalEntities(models.Model):
    pk = models.CompositePrimaryKey('old_id', 'type')
    old_id = models.PositiveIntegerField()
    type = models.CharField(max_length=50)
    new_id = models.PositiveIntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_mapping_to_external_entities'


class WpMailpoetNewsletterLinks(models.Model):
    newsletter_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField()
    url = models.CharField(max_length=2083)
    hash = models.CharField(max_length=20)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletter_links'


class WpMailpoetNewsletterOption(models.Model):
    newsletter_id = models.PositiveIntegerField()
    option_field_id = models.PositiveIntegerField()
    value = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletter_option'
        unique_together = (('newsletter_id', 'option_field_id'),)


class WpMailpoetNewsletterOptionFields(models.Model):
    name = models.CharField(max_length=90)
    newsletter_type = models.CharField(max_length=90)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletter_option_fields'
        unique_together = (('newsletter_type', 'name'),)


class WpMailpoetNewsletterPosts(models.Model):
    newsletter_id = models.PositiveIntegerField()
    post_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletter_posts'


class WpMailpoetNewsletterSegment(models.Model):
    newsletter_id = models.PositiveIntegerField()
    segment_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletter_segment'
        unique_together = (('newsletter_id', 'segment_id'),)


class WpMailpoetNewsletterTemplates(models.Model):
    newsletter_id = models.IntegerField(blank=True, null=True)
    name = models.CharField(max_length=250)
    categories = models.CharField(max_length=250)
    description = models.CharField(max_length=255)
    body = models.TextField(blank=True, null=True)
    thumbnail = models.TextField(blank=True, null=True)
    readonly = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    thumbnail_data = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletter_templates'


class WpMailpoetNewsletters(models.Model):
    hash = models.CharField(max_length=150, blank=True, null=True)
    parent_id = models.PositiveIntegerField(blank=True, null=True)
    subject = models.CharField(max_length=250)
    type = models.CharField(max_length=20)
    sender_address = models.CharField(max_length=150)
    sender_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20)
    reply_to_address = models.CharField(max_length=150)
    reply_to_name = models.CharField(max_length=150)
    preheader = models.CharField(max_length=250)
    body = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)
    unsubscribe_token = models.CharField(unique=True, max_length=15, blank=True, null=True)
    ga_campaign = models.CharField(max_length=250)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_newsletters'


class WpMailpoetScheduledTaskSubscribers(models.Model):
    pk = models.CompositePrimaryKey('task_id', 'subscriber_id')
    task_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    processed = models.IntegerField()
    failed = models.SmallIntegerField()
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_scheduled_task_subscribers'


class WpMailpoetScheduledTasks(models.Model):
    type = models.CharField(max_length=90, blank=True, null=True)
    status = models.CharField(max_length=12, blank=True, null=True)
    priority = models.IntegerField()
    scheduled_at = models.DateTimeField(blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)
    in_progress = models.IntegerField(blank=True, null=True)
    reschedule_count = models.IntegerField()
    meta = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_scheduled_tasks'


class WpMailpoetSegments(models.Model):
    name = models.CharField(unique=True, max_length=90)
    type = models.CharField(max_length=90)
    description = models.CharField(max_length=250)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)
    average_engagement_score = models.FloatField(blank=True, null=True)
    average_engagement_score_updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_segments'


class WpMailpoetSendingQueues(models.Model):
    task_id = models.PositiveIntegerField()
    newsletter_id = models.PositiveIntegerField()
    newsletter_rendered_body = models.TextField(blank=True, null=True)
    newsletter_rendered_subject = models.CharField(max_length=250, blank=True, null=True)
    subscribers = models.TextField(blank=True, null=True)
    count_total = models.PositiveIntegerField()
    count_processed = models.PositiveIntegerField()
    count_to_process = models.PositiveIntegerField()
    meta = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_sending_queues'


class WpMailpoetSettings(models.Model):
    name = models.CharField(unique=True, max_length=50)
    value = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_settings'


class WpMailpoetStatisticsBounces(models.Model):
    newsletter_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_bounces'


class WpMailpoetStatisticsClicks(models.Model):
    newsletter_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField()
    link_id = models.PositiveIntegerField()
    count = models.PositiveIntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    user_agent_id = models.PositiveIntegerField(blank=True, null=True)
    user_agent_type = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_clicks'


class WpMailpoetStatisticsForms(models.Model):
    form_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_forms'
        unique_together = (('form_id', 'subscriber_id'),)


class WpMailpoetStatisticsNewsletters(models.Model):
    newsletter_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField()
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_newsletters'


class WpMailpoetStatisticsOpens(models.Model):
    newsletter_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField()
    created_at = models.DateTimeField()
    user_agent_id = models.PositiveIntegerField(blank=True, null=True)
    user_agent_type = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_opens'


class WpMailpoetStatisticsUnsubscribes(models.Model):
    newsletter_id = models.PositiveIntegerField(blank=True, null=True)
    subscriber_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField()
    source = models.CharField(max_length=255, blank=True, null=True)
    meta = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_unsubscribes'


class WpMailpoetStatisticsWoocommercePurchases(models.Model):
    newsletter_id = models.PositiveIntegerField()
    subscriber_id = models.PositiveIntegerField()
    queue_id = models.PositiveIntegerField()
    click_id = models.PositiveIntegerField()
    order_id = models.PositiveBigIntegerField()
    order_currency = models.CharField(max_length=3)
    order_price_total = models.FloatField(db_comment='With shipping and taxes in order_currency')
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_statistics_woocommerce_purchases'
        unique_together = (('click_id', 'order_id'),)


class WpMailpoetStatsNotifications(models.Model):
    newsletter_id = models.PositiveIntegerField()
    task_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_stats_notifications'
        unique_together = (('newsletter_id', 'task_id'),)


class WpMailpoetSubscriberCustomField(models.Model):
    subscriber_id = models.PositiveIntegerField()
    custom_field_id = models.PositiveIntegerField()
    value = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_subscriber_custom_field'
        unique_together = (('subscriber_id', 'custom_field_id'),)


class WpMailpoetSubscriberIps(models.Model):
    pk = models.CompositePrimaryKey('created_at', 'ip')
    ip = models.CharField(max_length=45)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_subscriber_ips'


class WpMailpoetSubscriberSegment(models.Model):
    subscriber_id = models.PositiveIntegerField()
    segment_id = models.PositiveIntegerField()
    status = models.CharField(max_length=12)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_subscriber_segment'
        unique_together = (('subscriber_id', 'segment_id'),)


class WpMailpoetSubscribers(models.Model):
    wp_user_id = models.BigIntegerField(blank=True, null=True)
    is_woocommerce_user = models.IntegerField()
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.CharField(unique=True, max_length=150)
    status = models.CharField(max_length=12)
    subscribed_ip = models.CharField(max_length=45, blank=True, null=True)
    confirmed_ip = models.CharField(max_length=45, blank=True, null=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    last_subscribed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(blank=True, null=True)
    unconfirmed_data = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=20, blank=True, null=True)
    count_confirmations = models.PositiveIntegerField()
    unsubscribe_token = models.CharField(unique=True, max_length=15, blank=True, null=True)
    link_token = models.CharField(max_length=32, blank=True, null=True)
    engagement_score = models.FloatField(blank=True, null=True)
    engagement_score_updated_at = models.DateTimeField(blank=True, null=True)
    last_engagement_at = models.DateTimeField(blank=True, null=True)
    woocommerce_synced_at = models.DateTimeField(blank=True, null=True)
    email_count = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_subscribers'


class WpMailpoetUserAgents(models.Model):
    hash = models.CharField(unique=True, max_length=32)
    user_agent = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_user_agents'


class WpMailpoetUserFlags(models.Model):
    user_id = models.BigIntegerField()
    name = models.CharField(max_length=50)
    value = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_mailpoet_user_flags'
        unique_together = (('user_id', 'name'),)


class WpNxsLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    date = models.DateTimeField()
    uid = models.BigIntegerField()
    act = models.CharField(max_length=255)
    nt = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    flt = models.CharField(max_length=20)
    nttype = models.CharField(max_length=20, blank=True, null=True)
    msg = models.TextField()
    extinfo = models.TextField(db_column='extInfo', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'wp_nxs_log'


class WpNxsQuery(models.Model):
    id = models.BigAutoField(primary_key=True)
    datecreated = models.DateTimeField()
    type = models.CharField(max_length=55)
    postid = models.BigIntegerField(blank=True, null=True)
    uid = models.BigIntegerField()
    nttype = models.CharField(max_length=55, blank=True, null=True)
    timetorun = models.DateTimeField()
    refid = models.BigIntegerField(blank=True, null=True)
    descr = models.CharField(max_length=255, blank=True, null=True)
    extinfo = models.TextField(db_column='extInfo', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'wp_nxs_query'


class WpOptions(models.Model):
    option_id = models.BigAutoField(primary_key=True)
    option_name = models.CharField(unique=True, max_length=191)
    option_value = models.TextField()
    autoload = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'wp_options'


class WpPostViews(models.Model):
    pk = models.CompositePrimaryKey('type', 'period', 'id')
    id = models.PositiveBigIntegerField()
    type = models.PositiveIntegerField()
    period = models.CharField(max_length=8)
    count = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_post_views'
        unique_together = (('id', 'type', 'period', 'count'),)


class WpPostmeta(models.Model):
    meta_id = models.BigAutoField(primary_key=True)
    post_id = models.PositiveBigIntegerField()
    meta_key = models.CharField(max_length=255, blank=True, null=True)
    meta_value = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_postmeta'


class WpPosts(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    post_author = models.PositiveBigIntegerField()
    post_date = models.DateTimeField()
    post_date_gmt = models.DateTimeField()
    post_content = models.TextField()
    post_title = models.TextField()
    post_excerpt = models.TextField()
    post_status = models.CharField(max_length=20)
    comment_status = models.CharField(max_length=20)
    ping_status = models.CharField(max_length=20)
    post_password = models.CharField(max_length=255)
    post_name = models.CharField(max_length=200)
    to_ping = models.TextField()
    pinged = models.TextField()
    post_modified = models.DateTimeField()
    post_modified_gmt = models.DateTimeField()
    post_content_filtered = models.TextField()
    post_parent = models.PositiveBigIntegerField()
    guid = models.CharField(max_length=255)
    menu_order = models.IntegerField()
    post_type = models.CharField(max_length=20)
    post_mime_type = models.CharField(max_length=100)
    comment_count = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_posts'


class WpRankMath404Logs(models.Model):
    id = models.BigAutoField(primary_key=True)
    uri = models.CharField(max_length=255)
    accessed = models.DateTimeField()
    times_accessed = models.PositiveBigIntegerField()
    referer = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'wp_rank_math_404_logs'


class WpRankMathAnalyticsGsc(models.Model):
    id = models.BigAutoField(primary_key=True)
    created = models.DateTimeField()
    query = models.CharField(max_length=1000)
    page = models.CharField(max_length=500)
    clicks = models.IntegerField()
    impressions = models.IntegerField()
    position = models.FloatField()
    ctr = models.FloatField()

    class Meta:
        managed = False
        db_table = 'wp_rank_math_analytics_gsc'


class WpRankMathAnalyticsInspections(models.Model):
    id = models.BigAutoField(primary_key=True)
    page = models.CharField(max_length=500)
    created = models.DateTimeField()
    index_verdict = models.CharField(max_length=64)
    indexing_state = models.CharField(max_length=64)
    coverage_state = models.TextField()
    page_fetch_state = models.CharField(max_length=64)
    robots_txt_state = models.CharField(max_length=64)
    mobile_usability_verdict = models.CharField(max_length=64)
    mobile_usability_issues = models.TextField()
    rich_results_verdict = models.CharField(max_length=64)
    rich_results_items = models.TextField()
    last_crawl_time = models.DateTimeField()
    crawled_as = models.CharField(max_length=64)
    google_canonical = models.TextField()
    user_canonical = models.TextField()
    sitemap = models.TextField()
    referring_urls = models.TextField()
    raw_api_response = models.TextField()

    class Meta:
        managed = False
        db_table = 'wp_rank_math_analytics_inspections'


class WpRankMathAnalyticsObjects(models.Model):
    id = models.BigAutoField(primary_key=True)
    created = models.DateTimeField()
    title = models.TextField()
    page = models.CharField(max_length=500)
    object_type = models.CharField(max_length=100)
    object_subtype = models.CharField(max_length=100)
    object_id = models.PositiveBigIntegerField()
    primary_key = models.CharField(max_length=255)
    seo_score = models.IntegerField()
    page_score = models.IntegerField()
    is_indexable = models.IntegerField()
    schemas_in_use = models.CharField(max_length=500, blank=True, null=True)
    desktop_interactive = models.FloatField(blank=True, null=True)
    desktop_pagescore = models.FloatField(blank=True, null=True)
    mobile_interactive = models.FloatField(blank=True, null=True)
    mobile_pagescore = models.FloatField(blank=True, null=True)
    pagespeed_refreshed = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_rank_math_analytics_objects'


class WpRankMathInternalLinks(models.Model):
    id = models.BigAutoField(primary_key=True)
    url = models.CharField(max_length=255)
    post_id = models.PositiveBigIntegerField()
    target_post_id = models.PositiveBigIntegerField()
    type = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'wp_rank_math_internal_links'


class WpRankMathInternalMeta(models.Model):
    object_id = models.PositiveBigIntegerField(primary_key=True)
    internal_link_count = models.PositiveIntegerField(blank=True, null=True)
    external_link_count = models.PositiveIntegerField(blank=True, null=True)
    incoming_link_count = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_rank_math_internal_meta'


class WpRankMathRedirections(models.Model):
    id = models.BigAutoField(primary_key=True)
    sources = models.TextField()
    url_to = models.TextField()
    header_code = models.PositiveSmallIntegerField()
    hits = models.PositiveBigIntegerField()
    status = models.CharField(max_length=25)
    created = models.DateTimeField()
    updated = models.DateTimeField()
    last_accessed = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_rank_math_redirections'


class WpRankMathRedirectionsCache(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_url = models.TextField(db_collation='utf8mb4_bin')
    redirection_id = models.PositiveBigIntegerField()
    object_id = models.PositiveBigIntegerField()
    object_type = models.CharField(max_length=10)
    is_redirected = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_rank_math_redirections_cache'


class WpRp4WpCache(models.Model):
    pk = models.CompositePrimaryKey('post_id', 'word')
    post_id = models.PositiveBigIntegerField()
    word = models.CharField(max_length=255)
    weight = models.FloatField()
    post_type = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'wp_rp4wp_cache'


class WpTermRelationships(models.Model):
    pk = models.CompositePrimaryKey('object_id', 'term_taxonomy_id')
    object_id = models.PositiveBigIntegerField()
    term_taxonomy_id = models.PositiveBigIntegerField()
    term_order = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_term_relationships'


class WpTermTaxonomy(models.Model):
    term_taxonomy_id = models.BigAutoField(primary_key=True)
    term_id = models.PositiveBigIntegerField()
    taxonomy = models.CharField(max_length=32)
    description = models.TextField()
    parent = models.PositiveBigIntegerField()
    count = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_term_taxonomy'
        unique_together = (('term_id', 'taxonomy'),)


class WpTermmeta(models.Model):
    meta_id = models.BigAutoField(primary_key=True)
    term_id = models.PositiveBigIntegerField()
    meta_key = models.CharField(max_length=255, blank=True, null=True)
    meta_value = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_termmeta'


class WpTerms(models.Model):
    term_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=200)
    term_group = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_terms'


class WpUlike(models.Model):
    id = models.BigAutoField(primary_key=True)
    post_id = models.BigIntegerField()
    date_time = models.DateTimeField()
    ip = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'wp_ulike'


class WpUlikeActivities(models.Model):
    id = models.BigAutoField(primary_key=True)
    activity_id = models.BigIntegerField()
    date_time = models.DateTimeField()
    ip = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'wp_ulike_activities'


class WpUlikeComments(models.Model):
    id = models.BigAutoField(primary_key=True)
    comment_id = models.BigIntegerField()
    date_time = models.DateTimeField()
    ip = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'wp_ulike_comments'


class WpUlikeForums(models.Model):
    id = models.BigAutoField(primary_key=True)
    topic_id = models.BigIntegerField()
    date_time = models.DateTimeField()
    ip = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'wp_ulike_forums'


class WpUlikeMeta(models.Model):
    meta_id = models.BigAutoField(primary_key=True)
    item_id = models.PositiveBigIntegerField()
    meta_group = models.CharField(max_length=100, blank=True, null=True)
    meta_key = models.CharField(max_length=255, blank=True, null=True)
    meta_value = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_ulike_meta'


class WpUserfeedbackHeatmapRecordings(models.Model):
    id = models.BigAutoField(primary_key=True)
    heatmap_id = models.BigIntegerField()
    heatmap_data = models.TextField()
    created_at = models.DateTimeField()
    interaction_type = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'wp_userfeedback_heatmap_recordings'


class WpUserfeedbackHeatmaps(models.Model):
    id = models.BigAutoField(primary_key=True)
    page_id = models.BigIntegerField()
    created_at = models.DateTimeField()
    status = models.CharField(max_length=7, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_userfeedback_heatmaps'


class WpUserfeedbackPostRatings(models.Model):
    id = models.BigAutoField(primary_key=True)
    post_id = models.PositiveBigIntegerField()
    rating = models.PositiveIntegerField()
    user_id = models.PositiveBigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_userfeedback_post_ratings'


class WpUserfeedbackSurveyResponses(models.Model):
    id = models.BigAutoField(primary_key=True)
    survey = models.ForeignKey('WpUserfeedbackSurveys', models.DO_NOTHING)
    answers = models.TextField(blank=True, null=True)
    page_submitted = models.TextField(blank=True, null=True)
    user_ip = models.CharField(max_length=256, blank=True, null=True)
    user_browser = models.CharField(max_length=128, blank=True, null=True)
    user_os = models.CharField(max_length=128, blank=True, null=True)
    user_device = models.CharField(max_length=64, blank=True, null=True)
    submitted_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_userfeedback_survey_responses'


class WpUserfeedbackSurveys(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=128, blank=True, null=True)
    status = models.CharField(max_length=7, blank=True, null=True)
    questions = models.TextField(blank=True, null=True)
    impressions = models.BigIntegerField()
    settings = models.TextField(blank=True, null=True)
    notifications = models.TextField(blank=True, null=True)
    publish_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    type = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_userfeedback_surveys'


class WpUsermeta(models.Model):
    umeta_id = models.BigAutoField(primary_key=True)
    user_id = models.PositiveBigIntegerField()
    meta_key = models.CharField(max_length=255, blank=True, null=True)
    meta_value = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_usermeta'


class WpUsers(models.Model):
    id = models.BigAutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    user_login = models.CharField(max_length=60)
    user_pass = models.CharField(max_length=255)
    user_nicename = models.CharField(max_length=50)
    user_email = models.CharField(max_length=100)
    user_url = models.CharField(max_length=100)
    user_registered = models.DateTimeField()
    user_activation_key = models.CharField(max_length=255)
    user_status = models.IntegerField()
    display_name = models.CharField(max_length=250)

    class Meta:
        managed = False
        db_table = 'wp_users'


class WpWatuAnswer(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    question_id = models.PositiveIntegerField()
    answer = models.TextField(blank=True, null=True)
    correct = models.CharField(max_length=1)
    point = models.DecimalField(max_digits=8, decimal_places=2)
    sort_order = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_watu_answer'


class WpWatuGrading(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    exam_id = models.IntegerField()
    gtitle = models.CharField(max_length=255)
    gdescription = models.TextField()
    gfrom = models.DecimalField(max_digits=8, decimal_places=2)
    gto = models.DecimalField(max_digits=8, decimal_places=2)
    redirect_url = models.CharField(max_length=255)
    moola = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_watu_grading'


class WpWatuMaster(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    name = models.CharField(max_length=50)
    description = models.TextField()
    final_screen = models.TextField()
    added_on = models.DateTimeField()
    randomize = models.IntegerField()
    single_page = models.IntegerField()
    show_answers = models.IntegerField()
    require_login = models.IntegerField()
    notify_admin = models.IntegerField()
    randomize_answers = models.IntegerField()
    pull_random = models.PositiveIntegerField()
    dont_store_data = models.PositiveIntegerField()
    show_prev_button = models.PositiveIntegerField()
    dont_display_question_numbers = models.PositiveIntegerField()
    require_text_captcha = models.PositiveIntegerField()
    email_output = models.TextField(blank=True, null=True)
    notify_user = models.IntegerField()
    notify_email = models.CharField(max_length=255)
    take_again = models.IntegerField()
    times_to_take = models.IntegerField()
    no_ajax = models.IntegerField()
    no_alert_unanswered = models.IntegerField()
    use_honeypot = models.IntegerField()
    save_source_url = models.IntegerField()
    advanced_settings = models.TextField(blank=True, null=True)
    email_subject = models.TextField(blank=True, null=True)
    is_scheduled = models.PositiveIntegerField()
    schedule_from = models.DateTimeField(blank=True, null=True)
    schedule_to = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_watu_master'


class WpWatuQcats(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'wp_watu_qcats'


class WpWatuQuestion(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    exam_id = models.PositiveIntegerField()
    question = models.TextField()
    answer_type = models.CharField(max_length=15)
    sort_order = models.IntegerField()
    is_required = models.PositiveIntegerField()
    feedback = models.TextField(blank=True, null=True)
    is_inactive = models.PositiveIntegerField()
    is_survey = models.PositiveIntegerField()
    num_columns = models.IntegerField()
    cat_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_watu_question'


class WpWatuTakings(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    exam_id = models.IntegerField()
    user_id = models.IntegerField()
    ip = models.CharField(max_length=20)
    date = models.DateField()
    points = models.IntegerField()
    grade_id = models.PositiveIntegerField()
    result = models.TextField(blank=True, null=True)
    snapshot = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField(blank=True, null=True)
    email = models.CharField(max_length=255)
    percent_correct = models.PositiveIntegerField()
    source_url = models.CharField(max_length=255)
    num_correct = models.SmallIntegerField()
    num_wrong = models.SmallIntegerField()
    num_empty = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_watu_takings'


class WpWpcAccesslocks(models.Model):
    accesslock_id = models.BigAutoField(db_column='accesslock_ID', primary_key=True)  # Field name made lowercase.
    user_id = models.BigIntegerField()
    accesslock_date = models.DateTimeField()
    release_date = models.DateTimeField()
    accesslock_ip = models.CharField(db_column='accesslock_IP', max_length=100)  # Field name made lowercase.
    reason = models.CharField(max_length=200, blank=True, null=True)
    unlocked = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = 'wp_wpc_accesslocks'


class WpWpcLoginFails(models.Model):
    login_attempt_id = models.BigAutoField(db_column='login_attempt_ID', primary_key=True)  # Field name made lowercase.
    user_id = models.BigIntegerField()
    login_attempt_date = models.DateTimeField()
    login_attempt_ip = models.CharField(db_column='login_attempt_IP', max_length=100)  # Field name made lowercase.
    failed_user = models.CharField(max_length=200)
    failed_pass = models.CharField(max_length=200)
    reason = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_wpc_login_fails'


class WpWpfmBackup(models.Model):
    backup_name = models.TextField(blank=True, null=True)
    backup_date = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_wpfm_backup'


class WpWpformsLogs(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    types = models.CharField(max_length=255)
    create_at = models.DateTimeField()
    form_id = models.BigIntegerField(blank=True, null=True)
    entry_id = models.BigIntegerField(blank=True, null=True)
    user_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_wpforms_logs'


class WpWpformsPaymentMeta(models.Model):
    id = models.BigAutoField(primary_key=True)
    payment_id = models.BigIntegerField()
    meta_key = models.CharField(max_length=255, blank=True, null=True)
    meta_value = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'wp_wpforms_payment_meta'


class WpWpformsPayments(models.Model):
    id = models.BigAutoField(primary_key=True)
    form_id = models.BigIntegerField()
    status = models.CharField(max_length=10)
    subtotal_amount = models.DecimalField(max_digits=26, decimal_places=8)
    discount_amount = models.DecimalField(max_digits=26, decimal_places=8)
    total_amount = models.DecimalField(max_digits=26, decimal_places=8)
    currency = models.CharField(max_length=3)
    entry_id = models.BigIntegerField()
    gateway = models.CharField(max_length=20)
    type = models.CharField(max_length=12)
    mode = models.CharField(max_length=4)
    transaction_id = models.CharField(max_length=40)
    customer_id = models.CharField(max_length=40)
    subscription_id = models.CharField(max_length=40)
    subscription_status = models.CharField(max_length=10)
    title = models.CharField(max_length=255)
    date_created_gmt = models.DateTimeField()
    date_updated_gmt = models.DateTimeField()
    is_published = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'wp_wpforms_payments'


class WpWpformsTasksMeta(models.Model):
    id = models.BigAutoField(primary_key=True)
    action = models.CharField(max_length=255)
    data = models.TextField()
    date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'wp_wpforms_tasks_meta'
