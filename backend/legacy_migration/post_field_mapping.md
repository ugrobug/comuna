# Маппинг Comuna ↔ Послетитров

**Таблица сопоставления полей:** [post_field_mapping.csv](post_field_mapping.csv)  
Только пары «куда на Comuna» ↔ «откуда на ПТ» и строки с пометкой **нужно сопоставить**.

Как импортировать (команды, prod): [PROD_RUNBOOK.md](PROD_RUNBOOK.md).  
ТЗ и этапы: [tz_migration.md](tz_migration.md).

## Что считается «статьёй» на ПТ

`wp_posts`: `post_type = post`, `post_status = publish` (см. `legacy_posts.articles_queryset()`).

## Кратко по смыслу

1. **Post** — заголовок, даты, автор, JSON-контент из `post_content`, врезка из `post_excerpt`, обложка из `_thumbnail_id`. **`message_id`** — ID сообщения Telegram (уникальность с `author`); у переноса с ПТ подставляется синтетический отрицательный ID, связь с WP — `raw_data.legacy_wp_id` / `LegacyWpPostMap`.
2. **URL** — у нас `/b/post/{id}`, на ПТ `/articles/…/{slug}/`; связь slug ↔ id в `LegacyWpPostMap`.
3. **Картинки** — те же пути `uploads/YYYY/MM`, но хост и каталог Comuna: `/media/legacy-wp/uploads/…`.
4. **Блоки** — Gutenberg сопоставлены; **post_link** / **author** — `rewrite_wp_post_content`; **теги** — `import_wp_post_tags`; **раздел Tambur** — `assign_wp_post_comuns` (см. ниже).

5. **Комментарии и лайки** — см. раздел ниже и строки **Комментарий** в CSV; просмотры поста — `wp_post_views`.

## Разделы Tambur (ПТ → три блока)

Редакционное решение (из ТЗ, [tz_migration.md](tz_migration.md)):

| Comuna (коммуна) | Откуда на ПТ |
|------------------|--------------|
| **Фильмы** | `/articles/movies/…`, `/news/movie-news/`, `/books/`, `/podborki/` |
| **Сериалы** | `/articles/tv-series/…`, `/news/tv-news/` |
| **Анимация** | аниме и мультфильмы — часть материалов вручную; правила по URL/тегам WP допишем при импорте |

**Спорные случаи (ещё не автоматизированы в коде, зафиксированы в маппинге):**

- **`/articles/interview/`** — и про фильмы, и про сериалы: один пост в **одной** коммуне, не дублировать; тип — тег `interview`, уточнение film/series — отдельными тегами или ручная правка.
- **Квизы и прочие нестандартные ветки** — тег по типу (например `quiz`); комuna по умолчанию **Фильмы**, если в `legacy_url` нет `tv-series`.
- **Корень `/articles/{slug}/`** без `movies` / `tv-series` в path — на импорте **Фильмы** + теги; после массового переноса — выборочно переразложить.

Черновое правило массового импорта: **всё неоднозначное → «Фильмы»**, навигация через **теги** (в т.ч. бывший подраздел ПТ) и при необходимости `ComunPostCategoryAssignment`. Источник path: `LegacyWpPostMap.legacy_url` / guid → желательно также `Post.raw_data.legacy_pt_path` при доработке импорта.

Подробные строки: раздел **Раздел Tambur** в [post_field_mapping.csv](post_field_mapping.csv).

## Комментарии

Подробные строки в CSV (раздел **Комментарий**): фильтры WP, гости vs зарегистрированные, дерево `comment_parent`, лайки `wp_ulike_comments`, таблица `LegacyWpCommentMap`.

Кратко:

- Источник текста: `wp_comments`, не отдельный API AnyComment.
- Переносим только `comment_approved = 1`, без pingback/trackback/spam.
- `user_id = 0` — гость (имя из `comment_author`); иначе связь с `wp_users` → `User`.
- Лайки к комментариям: `wp_ulike_comments` → `PostCommentLike` (те же анонимные `user_id`, что в `wp_ulike`).
- После импорта `Post.comments_count` = фактическое число `PostComment` на посте.

6. **User** — полный перенос аккаунтов и паролей WP в таблице отмечен как «нужно сопоставить»; строки **Пользователь** в CSV.

Подробные примеры контента: [CONTENT_EXAMPLES.md](CONTENT_EXAMPLES.md).
