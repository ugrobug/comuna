from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from communities.views import (
    comun_create_from_telegram_channel,
    comun_detail_manage,
    comun_post_category_update,
    comun_posts,
    comun_vote,
    comuns_list_create,
)
from editor.views import (
    auth_movie_review_autofill,
    post_poll_vote,
    post_rating_vote,
    shared_draft_detail,
    user_post_update,
    user_posts,
    user_upload,
)
from feeds.views import (
    author_posts,
    comment_detail,
    comment_like,
    content_page_manage,
    favorites_feed,
    home_feed,
    post_detail,
    post_comments,
    post_favorite,
    post_like,
    post_read,
    post_view,
    recent_comments,
    search_content,
    sitemap_authors_xml,
    sitemap_posts_xml,
    sitemap_static_xml,
    sitemap_xml,
    tags_ensure,
    tags_list,
    tag_posts,
)
from my_feed.views import (
    auth_feed_settings,
    my_feed,
)
from notifications.views import (
    auth_notification_read,
    auth_notification_push_devices,
    auth_notification_settings,
    auth_notifications,
    auth_notifications_read_all,
)
from ratings.views import top_authors, top_authors_month, top_comuns, top_comuns_month
from special_projects.views import (
    landname_admin_letter_detail,
    landname_admin_letters,
    landname_admin_suggestion_approve,
    landname_admin_suggestion_detail,
    landname_alphabet,
    landname_render,
    landname_suggestions,
    landname_tile,
)
from telegram_integration.views import telegram_auth, telegram_webhook
from users.views import (
    auth_me,
    author_verification_code,
    login_user,
    public_user_profile,
    register_user,
    vk_auth,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/authors/<str:username>/posts/", author_posts, name="author-posts"),
    path("api/tags/", tags_list, name="tag-list"),
    path("api/tags/ensure/", tags_ensure, name="tag-ensure"),
    path("api/tags/<str:tag>/posts/", tag_posts, name="tag-posts"),
    path("api/posts/<int:post_id>/", post_detail, name="post-detail"),
    path("api/posts/<int:post_id>/comments/", post_comments, name="post-comments"),
    path("api/posts/<int:post_id>/favorite/", post_favorite, name="post-favorite"),
    path("api/posts/<int:post_id>/like/", post_like, name="post-like"),
    path("api/posts/<int:post_id>/poll-vote/", post_poll_vote, name="post-poll-vote"),
    path("api/posts/<int:post_id>/rating-vote/", post_rating_vote, name="post-rating-vote"),
    path("api/posts/<int:post_id>/read/", post_read, name="post-read"),
    path("api/posts/<int:post_id>/view/", post_view, name="post-view"),
    path("api/comments/<int:comment_id>/", comment_detail, name="comment-detail"),
    path("api/comments/<int:comment_id>/like/", comment_like, name="comment-like"),
    path("api/comments/recent/", recent_comments, name="recent-comments"),
    path("api/content-pages/<slug:slug>/", content_page_manage, name="content-page-manage"),
    path("api/home/", home_feed, name="home-feed"),
    path("api/home/favorites/", favorites_feed, name="favorites-feed"),
    path("api/home/my/", my_feed, name="my-feed"),
    path("api/comuns/", comuns_list_create, name="comuns-list-create"),
    path(
        "api/comuns/from-telegram-channel/",
        comun_create_from_telegram_channel,
        name="comun-create-from-telegram-channel",
    ),
    path("api/comuns/top/", top_comuns, name="top-comuns"),
    path("api/comuns/top-month/", top_comuns_month, name="top-comuns-month"),
    path("api/comuns/<slug:slug>/", comun_detail_manage, name="comun-detail-manage"),
    path("api/comuns/<slug:slug>/vote/", comun_vote, name="comun-vote"),
    path("api/comuns/<slug:slug>/posts/", comun_posts, name="comun-posts"),
    path(
        "api/comuns/<slug:slug>/posts/<int:post_id>/category/",
        comun_post_category_update,
        name="comun-post-category-update",
    ),
    path("api/search/", search_content, name="search-content"),
    path("api/authors/top/", top_authors, name="top-authors"),
    path("api/authors/top-month/", top_authors_month, name="top-authors-month"),
    path("api/auth/register/", register_user, name="auth-register"),
    path("api/auth/login/", login_user, name="auth-login"),
    path("api/auth/telegram/", telegram_auth, name="auth-telegram"),
    path("api/auth/vk/", vk_auth, name="auth-vk"),
    path("api/auth/me/", auth_me, name="auth-me"),
    path("api/auth/feed-settings/", auth_feed_settings, name="auth-feed-settings"),
    path(
        "api/auth/post-templates/movie-review/autofill/",
        auth_movie_review_autofill,
        name="auth-movie-review-autofill",
    ),
    path("api/auth/notifications/", auth_notifications, name="auth-notifications"),
    path(
        "api/auth/notifications/settings/",
        auth_notification_settings,
        name="auth-notification-settings",
    ),
    path(
        "api/auth/notifications/push-devices/",
        auth_notification_push_devices,
        name="auth-notification-push-devices",
    ),
    path(
        "api/auth/notifications/read-all/",
        auth_notifications_read_all,
        name="auth-notifications-read-all",
    ),
    path(
        "api/auth/notifications/<int:notification_id>/read/",
        auth_notification_read,
        name="auth-notification-read",
    ),
    path("api/site-users/<int:user_id>/profile/", public_user_profile, name="public-user-profile"),
    path("api/auth/verification-code/", author_verification_code, name="auth-verification-code"),
    path("api/auth/posts/", user_posts, name="auth-posts"),
    path("api/auth/posts/<int:post_id>/", user_post_update, name="auth-post-update"),
    path(
        "api/auth/drafts/shared/<str:share_token>/",
        shared_draft_detail,
        name="auth-shared-draft-detail",
    ),
    path("api/auth/uploads/", user_upload, name="auth-uploads"),
    path("api/special-projects/landname/", landname_render, name="special-landname-render"),
    path(
        "api/special-projects/landname/alphabet/",
        landname_alphabet,
        name="special-landname-alphabet",
    ),
    path(
        "api/special-projects/landname/suggestions/",
        landname_suggestions,
        name="special-landname-suggestions",
    ),
    path(
        "api/special-projects/landname/admin/letters/",
        landname_admin_letters,
        name="special-landname-admin-letters",
    ),
    path(
        "api/special-projects/landname/admin/letters/<int:image_id>/",
        landname_admin_letter_detail,
        name="special-landname-admin-letter-detail",
    ),
    path(
        "api/special-projects/landname/admin/suggestions/<int:suggestion_id>/",
        landname_admin_suggestion_detail,
        name="special-landname-admin-suggestion-detail",
    ),
    path(
        "api/special-projects/landname/admin/suggestions/<int:suggestion_id>/approve/",
        landname_admin_suggestion_approve,
        name="special-landname-admin-suggestion-approve",
    ),
    path(
        "api/special-projects/landname/tiles/<str:key>.svg",
        landname_tile,
        name="special-landname-tile",
    ),
    path("sitemap.xml", sitemap_xml, name="sitemap-xml"),
    path("sitemap-static.xml", sitemap_static_xml, name="sitemap-static-xml"),
    path("sitemap-authors.xml", sitemap_authors_xml, name="sitemap-authors-xml"),
    path("sitemap-posts-<int:page>.xml", sitemap_posts_xml, name="sitemap-posts-xml"),
    path("tg/webhook/<str:token>/", telegram_webhook, name="telegram-webhook"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
