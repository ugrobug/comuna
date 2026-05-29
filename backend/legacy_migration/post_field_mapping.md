# Маппинг Comuna ↔ Послетитров

Таблица в CSV: [post_field_mapping.csv](post_field_mapping.csv) (колонки: раздел, Comuna, Послетитров, Комментарий).

Статья на ПТ: `WpPosts` где `post_type=post`, `post_status=publish` (`legacy_posts.articles_queryset()`).

## Post

| Comuna | Послетитров |
|--------|-------------|
| `Post.title` | `WpPosts.post_title` |
| `Post.content` | `WpPosts.post_content` *(конвертер HTML/Gutenberg → JSON `blocks` + `additional`)* |
| `Post.content.additional.previewDescription` | `WpPosts.post_excerpt` *(врезка)* |
| `Post.publish_at` | `WpPosts.post_date` |
| `Post.created_at` | `WpPosts.post_date` *(выставить вручную при импорте)* |
| `Post.author_id` | `WpPosts.post_author` → `WpUsers.ID` |
| `Post.source_url` | `WpPosts.guid` *(или URL из slug)* |
| `Post.comments_count` | `WpPosts.comment_count` *(сверить с `wp_comments`)* |
| `Post.raw_data.legacy_wp_id` | `WpPosts.ID` *(предположение: ключ в JSON)* |
| `Post.raw_data.legacy_slug` | `WpPosts.post_name` *(предположение: редиректы)* |
| `Post.raw_data.source` | — *(предположение: `"wordpress"`)* |
| `Post.message_id` | — *(синтетический, не WP ID)* |
| `/b/post/{Post.id}` | `/articles/{WpPosts.post_name}/` |

## Обложка, шаблон

| Comuna | Послетитров |
|--------|-------------|
| `Post.content` / `Post.raw_data.template` → `cover_image_url` *(предположение)* | `WpPostmeta` `meta_key=_thumbnail_id` → `WpPosts` attachment |
| `Post.title` (дубль заголовка обложки) | заголовок в разметке обложки ПТ *(как на карточке)* |

## Теги

| Comuna | Послетитров |
|--------|-------------|
| `Post.tags` → `Tag.name` | `wp_term_relationships` + `wp_term_taxonomy.taxonomy=post_tag` + `wp_terms.name` |

## Автор поста

| Comuna | Послетитров |
|--------|-------------|
| `Author.username` | `WpUsers.user_nicename` *(предположение)* |
| `Author.title` | `WpUsers.display_name` |
| `Author.description` | `wp_usermeta` *(предположение: biography)* |
| блок `author` в `Post.content` | ссылки `/author/{slug}/` в `post_content` |

## Блоки в теле

| Comuna (`content.blocks[].type`) | Послетитров |
|----------------------------------|-------------|
| `quote` | цитата |
| `link` | внешняя ссылка |
| `post_link` | внутренняя ссылка на материал |
| `header` | заголовок |
| `divider` | разделитель |
| `toc` | оглавление (галочка в редакторе) |
| `image` | изображение + подпись |
| `table` | таблица |
| `author` | вставка автора |
| `embed` | iframe VK / YouTube |

## Комментарии, реакции (этап 3)

| Comuna | Послетитров |
|--------|-------------|
| `PostComment.body` | `wp_comments.comment_content` |
| `PostComment.created_at` | `wp_comments.comment_date` |
| `PostComment.user_id` | `wp_comments.user_id` → `wp_users` |
| `PostLike` | — *(предположение: meta / плагин)* |
| `Post.real_views_count` | — *(предположение: meta просмотров)* |

---

## Без пары

| Comuna | Послетитров |
|--------|-------------|
| `Post.rubric` | — |
| `Post.rating` | — |
| `Post.fake_views_target` | — |
| `Post.channel_url` | — |
| `Post.media_group_id` | — |
| `Post.is_pending` | `WpPosts.post_status` ≠ publish |
| `Post.is_blocked` | — |
| `Post.updated_at` | `WpPosts.post_modified` *(можно выставить, не в ТЗ)* |
| — | `WpPosts.post_password` |
| — | `WpPosts.ping_status` |
| — | `WpPosts.comment_status` |
| — | `WpPosts.post_parent` |
| — | `WpPosts.menu_order` |
| — | `WpPosts.post_mime_type` |
| — | `WpPosts.post_content_filtered` |
| — | `rp4wp_link` и прочие `post_type` |
| — | `wp_404_to_301`, служебные таблицы плагинов |
