# Перенос WP → Tambur (стенд / prod)

**Пилот на prod:** `WP_IDS="28741,28808,507,19938"` — цепочка ниже выполнена.  
**Полный перенос:** после [PROD_RUNBOOK.md §7 B.1](PROD_RUNBOOK.md) → [§ Полный перенос](#полный-перенос-prod-после-пилота).

Справка: [PROD_RUNBOOK.md](PROD_RUNBOOK.md)

```bash
COMPOSE="docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env"
cd /opt/comuna/app
```

---

## Шаг 0. MySQL ✅

```bash
$COMPOSE ps mysql57
# deploy-mysql57-1   Up

# пароль из deploy/.env (на хосте: PW=…; не вызывай mysql с пустым -p"" — будет user '-p')
PW="$(grep -m1 '^MYSQL_ROMAWHO_PASSWORD=' deploy/.env | cut -d= -f2-)"
$COMPOSE exec -T mysql57 mysql -u romawho_posl1 -p"$PW" romawho_posl1 \
  -e "SELECT COUNT(*) AS published_posts FROM wp_posts WHERE post_type='post' AND post_status='publish';"
# published_posts: 1546

$COMPOSE exec -T mysql57 mysql -u romawho_posl1 -p"$PW" romawho_posl1 \
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
MYSQL_ROMAWHO_PASSWORD=<пароль>   # deploy/.env → compose MYSQL_*; при новом volume — пользователь создаётся образом mysql:5.7
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
| 16 | `export_wp_redirects --format redirection-json` | JSON → **Redirection → Import** на posletitrov.ru; опционально `--include-tags` |

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

Аккаунты для входа на Tambur тем же паролем, что на ПТ. Гости комментариев — отдельно, на шаге 9.

**Пилот:** в `import_wp_users` передаём не ID статей (`WP_IDS`), а **`post_author`** из `wp_posts` — это `wp_users.ID` авторов этих статей. У четырёх пилотных постов три автора → `1,266,575` (у 507 и 28741 автор **1**).

```bash
PW="$(grep -m1 '^MYSQL_ROMAWHO_PASSWORD=' deploy/.env | cut -d= -f2-)"
$COMPOSE exec -T mysql57 mysql -u romawho_posl1 -p"$PW" romawho_posl1 -e \
  "SELECT ID AS wp_post_id, post_author AS wp_user_id, post_title FROM wp_posts WHERE ID IN (28741,28808,507,19938);"
# wp_user_id: 1, 575, 1, 266 → уникально: 1, 266, 575
```

```bash
WP_USER_IDS="1,266,575"
$COMPOSE exec -T backend python manage.py import_wp_users --wp-ids "$WP_USER_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_users --wp-ids "$WP_USER_IDS"
```

**Полный перенос:** все `wp_users` — без `--wp-ids` (см. § «Полный перенос», шаг 10).

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

### 16. Редиректы

Статьи из `LegacyWpPostMap` (несколько `from` на пост: guid, canonical, `/articles/slug/`).

Метки ПТ (опционально): `/tag/{wp_terms.slug}/` → `https://tambur.pub/tags/{lemma}` — slug из зеркала WP, цель как у `import_wp_post_tags` (`Tag.lemma` / `_lemmatize_tag(name)`), **без** записи slug в `lemma`.

**Пилот** (статьи + метки только у этих четырёх постов):

```bash
WP_IDS="28741,28808,507,19938"
OUT=deploy/pt-redirection-pilot.json
$COMPOSE exec -T backend python manage.py export_wp_redirects \
  --format redirection-json \
  --wp-ids "$WP_IDS" \
  --include-tags \
  -o "$OUT"
```

Без тегов (как раньше): убрать `--include-tags`.

Загрузить `OUT` в админке ПТ: **Инструменты → Redirection → Import**.

---

## Шаг 17. Проверка (пилот)

- `/b/post/{post_id}` из map — 200, контент, картинки
- wp **19938** — комментарии
- `/comuns/after_the_credits?category=filmy` — пилотные посты **видны в ленте** (если нет — шаг 7 с `--comun-manual-membership --force`)

**Не делать до согласования:** импорт файла в Redirection на ПТ.

---

## Полный перенос (prod, после пилота)

Пилот уже в `LegacyWpPostMap` — при полном `import_wp_posts` эти строки будут `skip`. Шаги 0–4 — как выше. Порядок 5→16 тот же.

### 6. Связка (если на prod ещё не делали на пилоте)

```bash
$COMPOSE exec -T backend python manage.py link_wp_posts_to_existing_tambur_posts --dry-run
$COMPOSE exec -T backend python manage.py link_wp_posts_to_existing_tambur_posts
```

### 10. Все пользователи WP (не только пилот)

```bash
$COMPOSE exec -T backend python manage.py import_wp_users --dry-run
$COMPOSE exec -T backend python manage.py import_wp_users
```

### 7. Все статьи

```bash
$COMPOSE exec -T backend python manage.py import_wp_posts --comun-manual-membership --dry-run
$COMPOSE exec -T backend python manage.py import_wp_posts --comun-manual-membership
```

### 8–9. Медиа и мета (все статьи, один прогон)

В контенте после `import_wp_posts` ещё URL `posletitrov.ru/wp-content/uploads/…`.  
**Bulk уже на S3** (`legacy-wp/uploads/…` как у `mirror`): **без** `--rewrite-only` — команда строит mapping PT → CDN и **не качает** файл, если объект уже есть в bucket.  
`--rewrite-only` — только если в JSON уже `/media/legacy-wp/…` или CDN, нужно лишь подправить режим раздачи (не для сырых URL ПТ).

```bash
WP_IDS=$($COMPOSE exec -T backend python manage.py shell -c "
from legacy_migration.legacy_posts import articles_q
from legacy_migration.models import WpPosts
ids = list(WpPosts.objects.filter(articles_q()).order_by('-post_date').values_list('id', flat=True))
print(','.join(str(i) for i in ids))
")
$COMPOSE exec -T backend python manage.py mirror_wp_post_media --wp-ids "$WP_IDS"
$COMPOSE exec -T backend python manage.py import_wp_post_meta --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_meta --wp-ids "$WP_IDS"
```

### 11. Теги (все)

```bash
$COMPOSE exec -T backend python manage.py import_wp_post_tags --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_tags
```

### 12. Врезка + обложка (все)

```bash
$COMPOSE exec -T backend python manage.py import_wp_post_supplement --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_supplement
```

### 13. Ссылки в контенте (все)

```bash
$COMPOSE exec -T backend python manage.py rewrite_wp_post_content --dry-run
$COMPOSE exec -T backend python manage.py rewrite_wp_post_content
```

### 14. Коммуна (все)

```bash
$COMPOSE exec -T backend python manage.py assign_wp_post_comuns --dry-run
$COMPOSE exec -T backend python manage.py assign_wp_post_comuns
```

### 15. Счётчики

```bash
$COMPOSE exec -T backend python manage.py recount_comun_cached_counts --comun-slug after_the_credits --dry-run
$COMPOSE exec -T backend python manage.py recount_comun_cached_counts --comun-slug after_the_credits
```

### 16. Редиректы (все замапленные)

Статьи — как раньше. Все архивы меток ПТ (~5k при `--tags-all`):

```bash
OUT=deploy/pt-redirection-full.json
$COMPOSE exec -T backend python manage.py export_wp_redirects \
  --format redirection-json \
  --include-tags \
  --tags-all \
  --tags-min-count 1 \
  -o "$OUT"
```

Только статьи (без `/tag/…`):

```bash
$COMPOSE exec -T backend python manage.py export_wp_redirects \
  --format redirection-json -o "$OUT"
```

**Redirection → Import** на ПТ (после согласования с Ромой).

### Проверка

```bash
$COMPOSE exec -T backend python manage.py shell -c \
  "from legacy_migration.models import LegacyWpPostMap; print(LegacyWpPostMap.objects.filter(post_id__isnull=False).count())"
```

---

## После перехода SEO (что убрать с prod)

Когда импорт завершён и редиректы в **Redirection** на ПТ работают — временную **инфраструктуру миграции** (MySQL mirror) можно снять. `LegacyWpPostMap` и правила на ПТ **не** откатываем.

### Оставить навсегда (не удалять)

| Что | Зачем |
|-----|--------|
| `LegacyWpPostMap` / `LegacyWpUserMap` в Postgres | связь WP ↔ пост/пользователь, отладка, повторный `export_wp_redirects` |
| `Post.raw_data` (`legacy_wp_id`, `legacy_slug`, …) | контент и аналитика |
| Правила в **Redirection** на posletitrov.ru | SEO со старых URL замапленных статей |
| Объекты **S3** `legacy-wp/uploads/…` | картинки в теле постов |
| `WordPressPasswordHasher` в `PASSWORD_HASHERS` | вход перенесённых пользователей с WP-хешем, пока сами не сменят пароль |

### Compose и сервер (убрать)

1. Остановить и удалить сервис **MySQL mirror WP** (дамп больше не нужен на prod):

```bash
$COMPOSE stop mysql57
$COMPOSE rm -f mysql57
docker volume rm deploy_mysql57_data   # имя: docker volume ls \| grep mysql57
```

2. В **`deploy/docker-compose.prod.yml`** удалить целиком блок `mysql57:` и volume `mysql57_data:`.

3. С **`deploy/.env`** убрать переменные:

- `MYSQL57_ROOT_PASSWORD`
- `MYSQL_ROMAWHO_DB`, `MYSQL_ROMAWHO_USER`, `MYSQL_ROMAWHO_PASSWORD`, `MYSQL_ROMAWHO_HOST`, `MYSQL_ROMAWHO_PORT`

4. С **`deploy/.env.backend`** убрать те же `MYSQL_ROMAWHO_*`.

5. На диске сервера (опционально, освободить место): каталог `deploy/mysql57-init/` с **дампом** `.sql` — хранить бэкап вне prod, с репозитория/сервера можно убрать.

6. Пересобрать стек без MySQL:

```bash
$COMPOSE up -d --build
$COMPOSE restart nginx
```

Проброс **`127.0.0.1:3306`** исчезнет вместе с сервисом — так и задумано.

### Django / backend env (убрать или выключить)

| Действие | Где |
|----------|-----|
| `ALLOW_PASSWORD_REGISTRATION=0` или удалить строку | `deploy/.env.backend` (включали только на окно переноса WP-логинов) |
| Убрать `MYSQL_ROMAWHO_*` из env контейнера | см. выше — иначе backend не должен ходить в MySQL |

Пока **не** трогать без отдельной задачи в коде:

- app **`legacy_migration`**, `DATABASES['romawho']`, `DATABASE_ROUTERS`, `pymysql` — после снятия MySQL команды `import_wp_*` на prod всё равно не запускают; вычищение кода — отдельный PR, когда точно не нужен повторный импорт.
- **`WordPressPasswordHasher`** и **`passlib`** — пока есть пользователи с WP-паролем.

### Чеклист «готово к уборке»

- [ ] `curl -I` по выборке старых URL ПТ → `301` на `https://tambur.pub/b/post/…`
- [ ] Повторный импорт из WP **не** планируется
- [ ] Бэкап дампа WP лежит **вне** prod (S3/архив), не только в `mysql57-init/`

---

*Пилот prod выполнен; полный перенос — после PROD_RUNBOOK §7 B.1.*
