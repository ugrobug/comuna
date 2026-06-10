# Тестовый перенос на стенде

Пилот 4 статей, без 301. Справка: [PROD_RUNBOOK.md](PROD_RUNBOOK.md)

```bash
COMPOSE="docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env"
cd /opt/comuna/app
```

---

## Шаг 0. MySQL ✅

```bash
$COMPOSE ps mysql57
# deploy-mysql57-1   Up

$COMPOSE exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 \
  -e "SELECT COUNT(*) AS published_posts FROM wp_posts WHERE post_type='post' AND post_status='publish';"
# published_posts: 1546

$COMPOSE exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 \
  -e "SELECT COUNT(*) AS users FROM wp_users;"
# users: 2956
```

---

## Шаг 1. Env backend

`/opt/comuna/app/deploy/.env.backend` — проверить:

```env
MYSQL_ROMAWHO_HOST=mysql57
MYSQL_ROMAWHO_PORT=3306
MYSQL_ROMAWHO_DB=romawho_posl1
MYSQL_ROMAWHO_USER=romawho_posl1
MYSQL_ROMAWHO_PASSWORD=<пароль>
ALLOW_PASSWORD_REGISTRATION=1
```

---

## Шаг 2. Выкат кода

```bash
git pull
```

---

## Шаг 3. Пересборка

```bash
$COMPOSE up -d --build
$COMPOSE restart nginx
```

Только env без кода: `$COMPOSE up -d --force-recreate backend frontend`

---

## Шаг 4. Миграции Postgres

```bash
$COMPOSE exec -T backend python manage.py migrate
```

Если «таблица уже существует»:

```bash
$COMPOSE exec -T backend python manage.py migrate legacy_migration 0002_wp_legacy_maps --fake
$COMPOSE exec -T backend python manage.py migrate
```

---

## Пилот

```bash
WP_IDS="28741,28808,507,19938"
```

Порядок важен. Сначала `--dry-run`, потом боевой прогон.

| # | Команда | Зачем |
|---|---------|-------|
| 5 | `import_wp_authors` | Авторы статей ПТ → `feeds.Author` + `LegacyWpUserMap` (без `User`) |
| 6 | `link_wp_posts_to_existing_tambur_posts` | ~100 постов канала уже на Tambur — связать с WP, не дублировать |
| 7 | `import_wp_posts` | Статьи WP → `feeds.Post` + `LegacyWpPostMap`; Gutenberg → Editor.js |
| 8 | `mirror_wp_post_media` | Картинки из `posletitrov.ru` → S3, URL в `Post.content` |
| 9 | `import_wp_post_meta` | Комментарии, лайки `wp_ulike`, просмотры `wp_post_views` |
| 10 | `import_wp_users` | `wp_users` → `auth.User` (пароль WP) + маппинг |
| 11 | `import_wp_post_tags` | Метки WP `post_tag` → `Post.tags` |
| 12 | `import_wp_post_supplement` | `post_excerpt` → врезка; `_thumbnail_id` → URL обложки |
| 13 | `rewrite_wp_post_content` | Ссылки `/articles/` → `/b/post/`, блоки post_link / author |
| 14 | `assign_wp_post_comuns` | Категория внутри коммуны: filmy / serialy / animatsiya |
| 15 | `recount_comun_cached_counts` | Пересчёт «Подписчиков» / «Авторов» на карточке коммуны |
| 16 | `export_wp_redirects` | Файл 301 со старых URL ПТ (на стенде **не** включать в nginx) |

**Лента коммуны (вариант B):** в шаге 7 всегда `--comun-manual-membership` — в `raw_data` пишется `source=manual_comun` + `comun_slug=after_the_credits`, как у живого поста через сайт. Шаг 14 — только **раздел** (`?category=filmy`), без него пост в ленте есть, но без вкладки.

### 5. Авторы

WP `post_author` → карточка автора на Tambur. Один раз на всю БД, до импорта постов.

```bash
$COMPOSE exec -T backend python manage.py import_wp_authors --dry-run
$COMPOSE exec -T backend python manage.py import_wp_authors
```

### 6. Связка с постами Tambur

Читает `pt_tambur_post_links.csv` + сопоставление по URL. Уже смапленные WP-посты `import_wp_posts` пропускает.

```bash
$COMPOSE exec -T backend python manage.py link_wp_posts_to_existing_tambur_posts --dry-run
$COMPOSE exec -T backend python manage.py link_wp_posts_to_existing_tambur_posts
```

### 7. Статьи (+ membership в ленту коммуны)

Создаёт пост: заголовок, даты как на ПТ, контент JSON, `raw_data.legacy_wp_id`. `--comun-manual-membership` — чтобы пост попал в `/comuns/after_the_credits`.

```bash
$COMPOSE exec -T backend python manage.py import_wp_posts --wp-ids "$WP_IDS" --comun-manual-membership --dry-run
$COMPOSE exec -T backend python manage.py import_wp_posts --wp-ids "$WP_IDS" --comun-manual-membership
```

Если шаг 7 уже прогнали **без** флага — только дописать `raw_data`:

```bash
$COMPOSE exec -T backend python manage.py import_wp_posts --wp-ids "$WP_IDS" --comun-manual-membership --force
```

```bash
$COMPOSE exec -T backend python manage.py shell -c "
from legacy_migration.models import LegacyWpPostMap
print(list(LegacyWpPostMap.objects.filter(wp_post_id__in=[28741,28808,507,19938]).values('wp_post_id','post_id','legacy_slug')))
"
```

### 8. Картинки в теле → S3

Скачивает `wp-content/uploads/…` с posletitrov.ru, кладёт в bucket (`media.tambur.pub/legacy-wp/…`), переписывает src в блоках `image`. `--dry-run` нет.

```bash
$COMPOSE exec -T backend python manage.py mirror_wp_post_media --wp-ids "$WP_IDS"
```

### 9. Мета (комменты, лайки, просмотры)

`wp_comments` → `PostComment` (дерево `comment_parent`); лайки постов и комментов; счётчик просмотров. Повтор без `--force` — без дублей лайков.

```bash
$COMPOSE exec -T backend python manage.py import_wp_post_meta --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_meta --wp-ids "$WP_IDS"
```

### 10. Пользователи WP

Аккаунты для входа на Tambur тем же паролем, что на ПТ. Гости комментариев — отдельно, на шаге 9. Пилот: авторы четырёх статей.

```bash
$COMPOSE exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 -e \
  "SELECT ID, post_author, post_title FROM wp_posts WHERE ID IN (28741,28808,507,19938);"
```

```bash
WP_USER_IDS="1,266,575"
$COMPOSE exec -T backend python manage.py import_wp_users --wp-ids "$WP_USER_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_users --wp-ids "$WP_USER_IDS"
```

Если email уже есть на Tambur — привязка по email, пароль **не** меняется (`linked-by-email` в выводе). `--force-password` — только если нужен WP-пароль.

### 11. Теги

Таксономия WP `post_tag` → теги поста на Tambur (не путать с категорией коммуны filmy/serialy).

```bash
$COMPOSE exec -T backend python manage.py import_wp_post_tags --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_tags --wp-ids "$WP_IDS"
```

### 12. Врезка + обложка

`post_excerpt` → `previewDescription` в JSON; `_thumbnail_id` → URL в `previewImage`. Сам файл обложки — шаг 8, если картинка только в обложке.

```bash
$COMPOSE exec -T backend python manage.py import_wp_post_supplement --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_supplement --wp-ids "$WP_IDS"
```

### 13. Ссылки в контенте

Внутренние ссылки ПТ и упоминания авторов → блоки `post_link` / `author` и href на `/b/post/{id}-slug`. Нужен заполненный `LegacyWpPostMap`.

```bash
$COMPOSE exec -T backend python manage.py rewrite_wp_post_content --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py rewrite_wp_post_content --wp-ids "$WP_IDS"
```

### 14. Коммуна (категории filmy / serialy / animatsiya)

По URL статьи на ПТ решает раздел: фильмы / сериалы / анимация → `ComunPostCategoryAssignment`. Спорные (`interview`, корень `/articles/{slug}/`) — по умолчанию filmy + теги.

```bash
$COMPOSE exec -T backend python manage.py assign_wp_post_comuns --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py assign_wp_post_comuns --wp-ids "$WP_IDS"
```

### 15. Счётчики коммуны

Поля `Comun.subscribers_count` / `authors_count` при импорте сами не обновляются — только эта команда (или живая активность на сайте).

```bash
$COMPOSE exec -T backend python manage.py recount_comun_cached_counts --comun-slug after_the_credits --dry-run
$COMPOSE exec -T backend python manage.py recount_comun_cached_counts --comun-slug after_the_credits
```

### 16. Редиректы (файл, без nginx)

Старые path ПТ → `/b/post/{id}-slug`. Источники: `legacy_url`, guid, Yoast/Rank Math. На prod 301 — только после согласования с Ромой.

```bash
OUT=deploy/pt-post-redirects-pilot.map
: > "$OUT"
$COMPOSE exec -T backend python manage.py export_wp_redirects \
  --format nginx-map --wp-ids "$WP_IDS" > "$OUT"
```

---

## Шаг 17. Проверка

- `/b/post/{post_id}` из map — 200, контент, картинки
- wp **19938** — комментарии
- `/comuns/after_the_credits?category=filmy` — пилотные посты **видны в ленте** (если нет — шаг 7 с `--comun-manual-membership --force`)

Массовый перенос (~1546): те же команды, `--comun-manual-membership` на `import_wp_posts`, пакетами `--limit 200 --offset N`.

**Не делать:** 301 в nginx, DNS posletitrov.ru.

---

*Старт: mysql57 ✅ · код и migrate — нет.*
