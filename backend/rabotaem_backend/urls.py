from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from feeds.views import (
    author_posts,
    home_feed,
    post_detail,
    rubric_posts,
    rubrics_list,
    search_content,
    sitemap_xml,
    telegram_webhook,
    top_authors_month,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/authors/<str:username>/posts/", author_posts, name="author-posts"),
    path("api/rubrics/", rubrics_list, name="rubrics-list"),
    path("api/rubrics/<str:slug>/posts/", rubric_posts, name="rubric-posts"),
    path("api/posts/<int:post_id>/", post_detail, name="post-detail"),
    path("api/home/", home_feed, name="home-feed"),
    path("api/search/", search_content, name="search-content"),
    path("api/authors/top-month/", top_authors_month, name="top-authors-month"),
    path("sitemap.xml", sitemap_xml, name="sitemap-xml"),
    path("tg/webhook/<str:token>/", telegram_webhook, name="telegram-webhook"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
