# Перенос Послетитров → Comuna (prod): пошаговая инструкция

Живая инструкция: дополняем по мере появления новых команд.  
ТЗ и контекст: [tz_migration.md](tz_migration.md). Поля: [post_field_mapping.md](post_field_mapping.md).  
Django-миграции app: [MIGRATIONS.md](MIGRATIONS.md). Деплой кода: [AGENTS.md](../../AGENTS.md) в корне репо.

---

## 0. Что уже есть в коде (на момент черновика)

| Шаг | Команда | Назначение |
|-----|---------|------------|
| Авторы статей | `import_wp_authors` | `feeds.Author` + `LegacyWpUserMap` (author) |
| Статьи | `import_wp_posts` | `feeds.Post` + `LegacyWpPostMap`, контент Gutenberg → Editor.js |
| Картинки в теле | `mirror_wp_post_media` | скачать `wp-content/uploads` → `media/legacy-wp/…`, переписать URL в `Post.content` |
| Мета (этап 3, частично) | `import_wp_post_meta` | комментарии, лайки `wp_ulike`, просмотры `wp_post_views` |
| Пользователи WP | `import_wp_users` | `auth.User` + пароль `user_pass` (phpass/bcrypt), `LegacyWpUserMap`, `Author` |
| Теги поста | `import_wp_post_tags` | `post_tag` → `Post.tags` |
| Врезка / обложка (URL) | `import_wp_post_supplement` | `post_excerpt`, `_thumbnail_id` → `previewDescription` / `previewImage` |
| Ссылки в контенте | `rewrite_wp_post_content` | post_link, author, href `/articles/` → `/b/post/` |
| Коммуна Tambur | `assign_wp_post_comuns` | `after_the_credits` + категории `filmy` / `serialy` / `animatsiya` |
| Счётчики коммуны | `recount_comun_cached_counts` | кэш подписчиков/авторов после импорта (только миграция) |
| Редиректы | `export_wp_redirects` | статьи из `LegacyWpPostMap`; опц. `--include-tags` → `/tag/{slug}/` → `/tags/{lemma}/` |

**Остаётся прогнать на данных:** массовый импорт ~1546 статей, стенд → prod, тест редиректов, переключение DNS.

Пароли WP: `legacy_migration.wordpress_hasher.WordPressPasswordHasher` в `PASSWORD_HASHERS` (первым). Зависимость: `passlib[bcrypt]` в `requirements.txt`.

---

## 1. Подготовка на prod

1. Выкатить нужный коммит на сервер (`git pull`, `docker compose … up -d --build`) — см. AGENTS.md.
2. Применить миграции Postgres (в т.ч. `legacy_migration`):

```bash
docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml \
  --env-file /opt/comuna/app/deploy/.env \
  exec -T backend python manage.py migrate
```

Если map-таблицы уже созданы старым `0001`:

```bash
docker compose … exec -T backend python manage.py migrate legacy_migration 0002_wp_legacy_maps --fake
```

3. Убедиться, что в **`deploy/.env.backend`** (или env backend-контейнера) заданы переменные MySQL (см. §2).
4. Сервис **`mysql57`** в compose должен быть поднят и доступен backend’у по имени хоста **`mysql57`** (не `127.0.0.1` изнутри контейнера).

---

## 2. MySQL: дамп WordPress (кратко)

Нужна только **read-only** копия БД ПТ (`romawho_posl1`), таблицы `wp_*`.

**Первый раз** (пустой volume MySQL):

- Положить SQL в `deploy/mysql57-init/` (как в dev: `01-romawho_posl1.sql` + дамп).
- Поднять `mysql57` — init выполнится один раз при создании volume.

**Обновить дамп** (volume уже есть):

```bash
# пример: залить дамп с хоста в контейнер и импортировать
docker compose -f …/docker-compose.prod.yml exec -T mysql57 \
  mysql -u romawho_posl1 romawho_posl1 < /path/to/dump.sql
```

Проверка:

```bash
docker compose … exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 \
  -e "SELECT COUNT(*) FROM wp_posts WHERE post_type='post' AND post_status='publish';"
```

Postgres Comuna (**рабочая** БД сайта) — отдельно; дамп WP в MySQL **не заменяет** prod Postgres.

---

## 3. Переменные окружения (backend)

Минимум для миграции (значения на prod подставить свои):

```env
MYSQL_ROMAWHO_HOST=mysql57
MYSQL_ROMAWHO_PORT=3306
MYSQL_ROMAWHO_DB=romawho_posl1
MYSQL_ROMAWHO_USER=romawho_posl1
MYSQL_ROMAWHO_PASSWORD=…
```

**Prod: места на диске под legacy не нужно.** При `MEDIA_STORAGE_BACKEND=s3` команда `mirror_wp_post_media` скачивает с posletitrov.ru **сразу в bucket** (`default_storage`), URL в контенте — на CDN (`MEDIA_PUBLIC_URL_MODE=s3`, домен `AWS_S3_CUSTOM_DOMAIN`, напр. `media.tambur.pub`). Флаг `--backend-base` на prod не обязателен.

Локально без S3: файлы в `MEDIA_ROOT`, в контенте `/media/legacy-wp/…` (нужен `DJANGO_DEBUG=1` или nginx). Принудительно на диск при включённом S3: `--local-disk`.

**На потом (полный объём ~10 ГБ):** bulk FTP/rsync `wp-content/uploads` → тот же префикс в bucket, затем только:

```bash
python manage.py mirror_wp_post_media --wp-ids "…" --rewrite-only
```

без HTTP-скачивания с ПТ.

---

## 4. Общий шаблон команд

Все команды — **из backend-контейнера**, каталог приложения `/app`:

```bash
COMPOSE="docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env"

$COMPOSE exec -T backend python manage.py <команда> [флаги]
```

Сначала всегда **`--dry-run`**, где команда поддерживает.

---

## 5. Пилот (повторить на prod)

Порядок **строго такой**.

### 5.1. Авторы (один раз на БД)

```bash
$COMPOSE exec -T backend python manage.py import_wp_authors --dry-run
$COMPOSE exec -T backend python manage.py import_wp_authors
```

### 5.2. Связка с уже опубликованными постами канала (до массового import)

Чтобы не задублировать ~100 постов «После титров», уже перенесённых в Tambur:

```bash
$COMPOSE exec -T backend python manage.py link_wp_posts_to_existing_tambur_posts --dry-run
$COMPOSE exec -T backend python manage.py link_wp_posts_to_existing_tambur_posts
```

Сначала читается `backend/legacy_migration/pt_tambur_post_links.csv`, затем сопоставление по `source_url` / `raw_data.legacy_wp_id`. Для уже смапленных WP `import_wp_posts` делает **skip**.

### 5.3. Статьи

Пример ID (замените на свои или список через запятую):

```bash
WP_IDS="28741,28808,507,19938"

$COMPOSE exec -T backend python manage.py import_wp_posts --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_posts --wp-ids "$WP_IDS"
# лента коммуны с авторами ПТ (эксперимент до решения Ромы): добавить --comun-manual-membership
# перезапись пилота (контент + raw_data): --comun-manual-membership --force
```

Полезные флаги: `--force` (перезаписать уже смапленные), `--comun-manual-membership`, `--limit` / `--offset` (пакетами).

После импорта смотреть связку WP → Comuna:

```bash
$COMPOSE exec -T backend python manage.py shell -c "
from legacy_migration.models import LegacyWpPostMap
print(list(LegacyWpPostMap.objects.filter(wp_post_id__in=[28741,19938]).values('wp_post_id','post_id','legacy_slug')))
"
```

### 5.4. Картинки в статьях (пилот — скачивание с posletitrov.ru→ S3)

```bash
$COMPOSE exec -T backend python manage.py mirror_wp_post_media --wp-ids "$WP_IDS"
```

При `MEDIA_STORAGE_BACKEND=s3` файлы не занимают volume `media_data`. Проверка: URL в `Post.content` вида `https://media.tambur.pub/legacy-wp/uploads/…`.

На полном объёме позже: **FTP/rsync → bucket**, затем `--rewrite-only` (см. §3).

### 5.5. Мета: комментарии, лайки, просмотры

```bash
$COMPOSE exec -T backend python manage.py import_wp_post_meta --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_meta --wp-ids "$WP_IDS"
```

Повторный прогон без дублей лайков: без `--force`. Пересоздать комментарии/лайки поста: `--force`.

### 5.6. Пользователи WP (логин на Tambur, п.3 ТЗ)

Требования: в коде на prod — `passlib`, `bcrypt`, `WordPressPasswordHasher` в `PASSWORD_HASHERS`; MySQL с актуальным `wp_users`.

**Сколько строк в WP:**

```bash
$COMPOSE exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 -N -e \
  "SELECT COUNT(*) FROM wp_users;"
```

**Пилот одного аккаунта:**

```bash
$COMPOSE exec -T backend python manage.py import_wp_users --wp-ids "ВАШ_WP_ID" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_users --wp-ids "ВАШ_WP_ID"
```

**Все пользователи на prod (рекомендуется пакетами, можно продолжить с `--min-id`):**

```bash
# 1) выборочный dry-run
$COMPOSE exec -T backend python manage.py import_wp_users --dry-run --limit 10

# 2) полный перенос пакетами по 500
BATCH=500
MAX_ID=$($COMPOSE exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 -N -e "SELECT MAX(ID) FROM wp_users;")
MIN_ID=1
while [ "$MIN_ID" -le "$MAX_ID" ]; do
  $COMPOSE exec -T backend python manage.py import_wp_users --min-id "$MIN_ID" --limit "$BATCH"
  MIN_ID=$((MIN_ID + BATCH))
done

# Альтернатива одним прогоном (если пользователей немного, < ~2k):
# $COMPOSE exec -T backend python manage.py import_wp_users
```

**После импорта — сверка:**

```bash
$COMPOSE exec -T mysql57 mysql -u romawho_posl1 romawho_posl1 -N -e \
  "SELECT COUNT(*) FROM wp_users;"
$COMPOSE exec -T backend python manage.py shell -c "
from legacy_migration.models import LegacyWpUserMap
print('maps with user:', LegacyWpUserMap.objects.filter(user_id__isnull=False).count())
print('maps total:', LegacyWpUserMap.objects.count())
"
```

Вход на сайте: **email или `user_login`** + **тот же пароль**, что на ПТ (не хеш). На стенде нужен `ALLOW_PASSWORD_REGISTRATION=1`.

Проверка одного аккаунта в shell:

```bash
$COMPOSE exec -T backend python manage.py shell -c "
from legacy_migration.models import LegacyWpUserMap
m = LegacyWpUserMap.objects.filter(wp_user_id=ВАШ_WP_ID).select_related('user').first()
u = m.user
print(u.username, u.email, u.has_usable_password())
"
```

`--force-password` — перезаписать `user_pass` из WP поверх пароля, уже заданного на Comuna.

---

## 6. Проверка после пилота

1. **HTTP:** главная и пост (AGENTS.md), например пост по `LegacyWpPostMap.post_id` → `/b/post/{id}`.
2. **Контент:** блоки, embed, картинки (`/media/legacy-wp/…` отдаёт nginx/backend).
3. **Мета:** `comments_count`, лайки (rating), просмотры на карточке/в API.
4. **Комментарии:** пост с комментариями в WP (на стенде: wp **19938** → comuna **10004**).

---

## 7. Чеклист миграции

Легенда: `[код ✅]` команда есть · `[ ]` не сделано на данных · `[стенд]` / `[prod]`

### A. Подготовка

- [x] [код ✅] Команды импорта, коммуна, редиректы, пересчёт счётчиков
- [x] [код ✅] Uploads bulk → S3 (§3.1)
- [x] [prod] Сообщество `after_the_credits` + категории `filmy`, `serialy`, `animatsiya` (Рома)
- [х] [стенд] Выкат актуального коммита, `manage.py migrate`, доступ к MySQL `romawho`


### B. Пилот (4 статьи: 28741, 28808, 507, 19938)

- [х] [стенд] `import_wp_authors` → `import_wp_users` (авторы пилота)
- [х] [стенд] `import_wp_posts --wp-ids`
- [х] [стенд] `import_wp_post_tags` + `import_wp_post_supplement` + `mirror_wp_post_media`
- [х] [стенд] `import_wp_post_meta`
- [х] [стенд] `rewrite_wp_post_content`
- [х] [стенд] `assign_wp_post_comuns` → `recount_comun_cached_counts`
- [ ] [стенд] `export_wp_redirects --format redirection-json` → импорт в Redirection на ПТ
- [ ] [стенд] Проверка §6 (HTTP, контент, мета, комментарии, лента `/comuns/after_the_credits?category=filmy`)

**[prod] Пилот:** цепочка §5–§8 для `WP_IDS="28741,28808,507,19938"` **выполнена** (импорт и сопутствующие шаги на prod). Редиректы 301 — по §D.

### B.1. Правки перед массовым переносом (замечания после prod-пилота)

Не отменяют статус пилота, но **нужно закрыть до ~1546 статей** (или явно принять риск).

| # | Проблема | Сейчас в коде / на prod | Действие |
|---|----------|-------------------------|----------|
| 1 | **Нет подписей у картинок** (напр. «кадр из фильма «Хокум»») | Парсер: `figcaption` → `image.caption` в `wp_content.py`; эталон **28741** (`CONTENT_EXAMPLES.md`) | Проверить разметку WP на prod-постах (отдельный `wp:image` vs `figure`); отображение блока `image` на фронте Tambur |
| 2 | **Внутренние ссылки в тексте** (в т.ч. `/tag/…` в якорях) | `rewrite_wp_post_content`: только `/articles/…` → `/b/post/…`; ссылки `/tag/…` в HTML **не** переписываются. **Архивы меток:** `export_wp_redirects --include-tags` — `/tag/{wp_slug}/` → Tambur `/tags/{lemma}` (slug→lemma при экспорте, `Tag.lemma` не меняется). Пилот: `--include-tags` без `--tags-all` (метки только у постов из выборки). ; при необходимости позже — переписывание `/tag/…` в контенте |
| 3 | **Трейлер не виден** (нет фрейма видео) | Пилот **507** — YouTube `wp:embed` → блок `embed`; возможны парсер, CSP или рендер на фронте | Сверить JSON контента на prod с WP; проверить UI блока `embed`; smoke на **507** |

- [ ] [код/фронт] Подписи к изображениям (п.1)
- [ ] [продукт] Импорт редиректов в Redirection (п.2 — архивы тегов через `--include-tags`)
- [ ] [код/фронт] Отображение embed/трейлера (п.3)

### C. Массовый перенос (~1546 статей)

Порядок команд — §8 (одинаковый на стенде и prod). Пакеты: `--limit 200 --offset N`.

- [ ] [стенд] `import_wp_authors` (если ещё не полный)
- [ ] [стенд] `import_wp_users` пакетами (§5.5)
- [ ] [стенд] `import_wp_posts` без `--wp-ids` — **после закрытия B.1**
- [ ] [стенд] tags + supplement + `mirror_wp_post_media` (S3)
- [ ] [стенд] `import_wp_post_meta`
- [ ] [стенд] `rewrite_wp_post_content`
- [ ] [стенд] `assign_wp_post_comuns`
- [ ] [стенд] `recount_comun_cached_counts --comun-slug after_the_credits`
- [ ] [стенд] `export_wp_redirects --format redirection-json` → импорт в Redirection; выборочный `curl -I` старых URL

- [ ] [prod] Повторить цепочку C на prod (окно ≤ суток) или сверить стратегию «стенд = репетиция»
- [ ] [prod] Сверка `LegacyWpPostMap` / счётчиков / выборка постов для редакции

### D. Редиректы и запуск (согласование с Ромой)

- [ ] **Согласование списка редиректов** (обязательно до импорта в Redirection на ПТ)
- [ ] [prod] Импорт файла в Redirection; `curl -I` старые URL → 301 на `https://tambur.pub/b/post/…`
- [ ] [prod] Финальная проверка главной + постов (AGENTS.md)

### E. После импорта (ручное)

- [ ] Редакция: спорные `interview`, корень `/articles/{slug}/`, анимация
- [ ] Подписчики WP **не** переносим — только живые `UserFeedSettings` на Tambur

### F. После стабилизации SEO

Что снять с prod (MySQL, env, compose) и что **оставить** (301, S3 `legacy-wp/`, map-таблицы) — **[STAGE_STEPS.md](STAGE_STEPS.md) § «После перехода SEO»**.

---

## 8. Команды после `import_wp_posts` (пилот или массово)

После `import_wp_posts` для пилота или всей выборки:

```bash
# Теги (post_tag)
$COMPOSE exec -T backend python manage.py import_wp_post_tags --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_tags --wp-ids "$WP_IDS"

# Врезка + URL обложки в JSON (файл обложки — ещё mirror_wp_post_media)
$COMPOSE exec -T backend python manage.py import_wp_post_supplement --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py import_wp_post_supplement --wp-ids "$WP_IDS"
# только врезка: --excerpt   только обложка: --cover
```

Массово: без `--wp-ids`, с `--limit` / `--offset` (как у постов).

| Задача | Команда | Статус |
|--------|---------|--------|
| Теги | `import_wp_post_tags` | ✅ |
| Врезка | `import_wp_post_supplement --excerpt` (также в `import_wp_posts`) | ✅ |
| Обложка URL | `import_wp_post_supplement --cover` | ✅ |
| Файл обложки в S3 | `mirror_wp_post_media` | ✅ |
| post_link / author / href | `rewrite_wp_post_content` | ✅ |

```bash
# post_link, author, href /articles/ → /b/post/{id}-slug
$COMPOSE exec -T backend python manage.py rewrite_wp_post_content --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py rewrite_wp_post_content --wp-ids "$WP_IDS"
# только href: --urls-only   без post_link: --no-post-link   без author: --no-author
```

```bash
# Коммуна «После Титров» (после import_wp_posts; коммуна и категории — на Tambur заранее)
$COMPOSE exec -T backend python manage.py assign_wp_post_comuns --wp-ids "$WP_IDS" --dry-run
$COMPOSE exec -T backend python manage.py assign_wp_post_comuns --wp-ids "$WP_IDS"
# нужны: comun slug=after_the_credits, категории filmy, serialy, animatsiya (активные)
```

```bash
# Счётчики «Подписчиков» / «Авторов» на карточке коммуны (после assign + import_wp_users)
# Поля Comun.subscribers_count / authors_count — кэш, при импорте сами не пересчитываются.
$COMPOSE exec -T backend python manage.py recount_comun_cached_counts --comun-slug after_the_credits --dry-run
$COMPOSE exec -T backend python manage.py recount_comun_cached_counts --comun-slug after_the_credits
# или --comun-id 164
```

Порядок: `import_wp_authors` → `import_wp_users` → `import_wp_posts` → … → `assign_wp_post_comuns` → **`recount_comun_cached_counts`** → `export_wp_redirects`.

---

## 9. Редиректы ПТ → Tambur

После `import_wp_posts` и `import_wp_post_tags` (для корректного `lemma` в цели тегов).

**Пилот на prod** (после `git pull` и `docker compose … up -d --build`):

```bash
cd /opt/comuna/app
WP_IDS="28741,28808,507,19938"
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T backend \
  python manage.py export_wp_redirects \
    --format redirection-json \
    --wp-ids "$WP_IDS" \
    --include-tags \
    -o /tmp/pt-redirection-pilot.json
```

Файл лежит в контейнере `backend`: скопировать на хост, например  
`docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env cp backend:/tmp/pt-redirection-pilot.json ./deploy/pt-redirection-pilot.json`

**Все замапленные статьи** (без тегов):

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T backend \
  python manage.py export_wp_redirects \
    --format redirection-json \
    -o /tmp/pt-redirection-posts.json
```

**Статьи + все архивы меток** (`post_tag`, `count ≥ 1`, ~5k правил):

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env exec -T backend \
  python manage.py export_wp_redirects \
    --format redirection-json \
    --include-tags \
    --tags-all \
    --tags-min-count 1 \
    -o /tmp/pt-redirection-full.json
```

**Полученный JSON** загрузить на ПТ: **Инструменты → Redirection → Import**.

Включать для всех статей **после согласования** (§7 D).

---

## 10. Порядок процесса (организационно)

1. Подготовка (команды, стенд, S3).
2. Рома: коммуна `after_the_credits` на Tambur.
3. Перенос на стенде → проверка (в т.ч. Рома).
4. Согласование редиректов → импорт в Redirection на ПТ.
5. Prod: импорт контента + редиректы.

---

*Последнее обновление: prod-пилот 4 статей выполнен; §B.1 — блокеры перед массовым переносом.*
