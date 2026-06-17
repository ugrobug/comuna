Последовательность действий:

| # | Шаг | Статус |
|---|-----|--------|
| 1 | Скрипт переноса статей, пилот 3–5 статей | ✅ `import_wp_posts --wp-ids` |
| 2 | Все статьи (~1546) | ⏳ команда есть, массовый прогон на prod — нет |
| 3 | Пользователи + мета (лайки, комментарии, просмотры) | ✅ `import_wp_users`; мета ✅ `import_wp_post_meta` (пилот) |
| 4 | Повторная проверка редакцией | ⏳ |
| 5 | Файл редиректов ПТ → Tambur | ✅ код | `export_wp_redirects`; 301 после согласования |
| 6 | Тест редиректов | ⏳ | стенд: map + curl; prod — после Ромы |
| 7 | Завершение миграции | ⏳ | чеклист PROD_RUNBOOK §7 |

Задача: окно простоя не больше суток, без потери данных.

---

## Требования к переносу контента

| # | Требование | Статус | Команда / примечание |
|---|------------|--------|----------------------|
| 1 | Дата публикации как на ПТ | ✅ | `import_wp_posts` → `publish_at`, `created_at` |
| 2 | Внутренние ссылки → блок post_link | ✅ | `rewrite_wp_post_content` (нужен `LegacyWpPostMap`) |
| 3 | Вставки авторов → блок author | ✅ | там же; маппинг `LegacyWpUserMap` / `Author` |
| 4 | Видео VK/YouTube — embed | ✅ | `wp_content` → блок `embed` |

---

## Тз по переносу 1 (блоки и поля)

### Блоки Gutenberg → Editor.js

| Блок ПТ | Статус | Примечание |
|---------|--------|------------|
| Цитата | ✅ | `quote` |
| Ссылка | ✅ | в `paragraph` / link |
| Заголовки | ✅ | `header` |
| Разделитель | ✅ | `divider` |
| Оглавление | ✅ | `toc` + `_ez-toc-insert` |
| Изображение (+ подписи) | ✅ | `image`; файлы — `mirror_wp_post_media` |
| Таблица | ✅ | `table` |

### Поля поста (не блоки)

| Поле ПТ | У нас | Статус | Команда |
|---------|-------|--------|---------|
| **Метки** | теги поста | ✅ | `import_wp_post_tags` |
| **Выдержка** | врезка `previewDescription` | ✅ | при `import_wp_posts`; повтор — `import_wp_post_supplement --excerpt` |
| **Обложка** | `previewImage` (+ заголовок в `title`) | ✅/⏳ | URL: `import_wp_post_supplement --cover`; файл в S3 — `mirror_wp_post_media` |

Таблицы сопоставления: [post_field_mapping.md](post_field_mapping.md). Prod: [PROD_RUNBOOK.md](PROD_RUNBOOK.md).

---

## Разделы Tambur (редакционно)

См. [post_field_mapping.md](post_field_mapping.md). Импорт: ✅ `assign_wp_post_comuns` → коммуна `after_the_credits`, категории `filmy` / `serialy` / `animatsiya` (должны быть на Tambur до прогона).

---

Легенда: ✅ готово в коде · ⏳ не завершено на всех данных / нужен отдельный парсинг
