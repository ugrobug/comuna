from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from feeds.views import (
    auth_me,
    author_verification_code,
    author_posts,
    comment_detail,
    comment_like,
    home_feed,
    login_user,
    post_detail,
    post_comments,
    post_like,
    recent_comments,
    register_user,
    rubric_posts,
    rubrics_list,
    search_content,
    sitemap_xml,
    telegram_webhook,
    top_authors_month,
    user_post_update,
    user_posts,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/authors/<str:username>/posts/", author_posts, name="author-posts"),
    path("api/rubrics/", rubrics_list, name="rubrics-list"),
    path("api/rubrics/<str:slug>/posts/", rubric_posts, name="rubric-posts"),
    path("api/posts/<int:post_id>/", post_detail, name="post-detail"),
    path("api/posts/<int:post_id>/comments/", post_comments, name="post-comments"),
    path("api/posts/<int:post_id>/like/", post_like, name="post-like"),
    path("api/comments/<int:comment_id>/", comment_detail, name="comment-detail"),
    path("api/comments/<int:comment_id>/like/", comment_like, name="comment-like"),
    path("api/comments/recent/", recent_comments, name="recent-comments"),
    path("api/home/", home_feed, name="home-feed"),
    path("api/search/", search_content, name="search-content"),
    path("api/authors/top-month/", top_authors_month, name="top-authors-month"),
    path("api/auth/register/", register_user, name="auth-register"),
    path("api/auth/login/", login_user, name="auth-login"),
    path("api/auth/me/", auth_me, name="auth-me"),
    path("api/auth/verification-code/", author_verification_code, name="auth-verification-code"),
    path("api/auth/posts/", user_posts, name="auth-posts"),
    path("api/auth/posts/<int:post_id>/", user_post_update, name="auth-post-update"),
    path("sitemap.xml", sitemap_xml, name="sitemap-xml"),
    path("tg/webhook/<str:token>/", telegram_webhook, name="telegram-webhook"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
