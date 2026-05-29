# AGENTS.md

## Deploy Playbook

Используй этот порядок для любого деплоя в прод.

### 1. Локальная проверка перед релизом

Из корня репозитория:

```bash
npm run build
.venv/bin/python backend/manage.py check
git status --short
```

Правила:

- Не деплой, если `npm run build` или `manage.py check` падают.
- Не тащи в релиз неожиданные локальные файлы.
- Если есть незакоммиченные пользовательские изменения, сначала явно понять, входят ли они в релиз.

### 2. Коммит и push

```bash
git add <нужные_файлы>
git commit -m "<message>"
git push origin main
git rev-parse --short HEAD
```

### 3. Прод-сервер

Прод-код лежит здесь:

- `/opt/comuna/app`

Compose-файлы и env лежат здесь:

- `/opt/comuna/app/deploy/docker-compose.prod.yml`
- `/opt/comuna/app/deploy/.env`

Важно:

- Не использовать `/opt/comuna/app/.env` — это неправильный путь.
- Для backend-контейнера внутри Docker использовать `python manage.py ...`, а не `.venv/bin/python backend/manage.py ...`.

### 4. Базовый деплой

Если миграций нет:

```bash
ssh <prod> 'cd /opt/comuna/app && git pull && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env up -d --build && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env restart nginx'
```

### 5. Деплой с миграциями

Если в релизе есть новые Django migration-файлы:

```bash
ssh <prod> 'cd /opt/comuna/app && git pull && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env up -d --build && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env exec -T backend python manage.py migrate && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env restart nginx'
```

Если нужно прогнать миграции отдельно после уже выполненного `up -d --build`:

```bash
ssh <prod> 'cd /opt/comuna/app && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env exec -T backend python manage.py migrate'
```

После любого `up -d --build` обязательно перезапустить nginx:

```bash
ssh <prod> 'cd /opt/comuna/app && docker compose -f /opt/comuna/app/deploy/docker-compose.prod.yml --env-file /opt/comuna/app/deploy/.env restart nginx'
```

Причина: при пересоздании `backend` или `frontend` Docker может выдать контейнеру новый IP, а живой nginx продолжит некоторое время ходить в старый upstream и отдавать `502 connect() failed`. Рестарт nginx обновляет upstream-адреса сразу.

### 6. Проверка после деплоя

Проверять лучше через локальный nginx на сервере, а не внешним `curl`, потому что внешний DNS иногда шумит.

Главная:

```bash
ssh <prod> "curl -sS -I -H 'Host: tambur.pub' http://127.0.0.1/ | head -n 10"
```

Страница существующего поста:

```bash
ssh <prod> "curl -sS -I -H 'Host: tambur.pub' http://127.0.0.1/b/post/4492-bred-ili-geniy-retsenziya-na-film-druzhba-2024 | head -n 10"
```

Ожидаемый результат:

- `HTTP/1.1 200 OK`

Дополнительно полезно проверить текущий коммит на сервере:

```bash
ssh <prod> 'cd /opt/comuna/app && git rev-parse --short HEAD'
```

### 7. Что считать успешным деплоем

Деплой завершен только если выполнены все условия:

- `git push` успешен
- `git pull` на сервере успешен
- `docker compose ... up -d --build` завершен без ошибок
- если есть миграции, `python manage.py migrate` завершен без ошибок
- `docker compose ... restart nginx` завершен без ошибок
- главная и хотя бы одна реальная страница поста отвечают `200`
- API endpoint, например `/api/special-projects/book/status/`, отвечает `200`

### 8. Частые ошибки

#### Неправильный env file

Неправильно:

```bash
--env-file /opt/comuna/app/.env
```

Правильно:

```bash
--env-file /opt/comuna/app/deploy/.env
```

#### Неправильный путь к Python внутри backend-контейнера

Неправильно:

```bash
python backend/manage.py migrate
.venv/bin/python backend/manage.py migrate
```

Правильно:

```bash
python manage.py migrate
```

#### Серверные env-файлы пачкают `git status`

На проде рабочими могут быть файлы:

- `/opt/comuna/app/deploy/.env.backend`
- `/opt/comuna/app/deploy/.env.frontend`

Они не должны мешать `git pull`.

Правильное поведение:

- Не коммитить их в репозиторий.
- Не удалять их в ходе обычного деплоя.
- На сервере держать их в `.git/info/exclude`, чтобы `git status` оставался чистым:

```bash
cd /opt/comuna/app
echo 'deploy/.env.backend' >> .git/info/exclude
echo 'deploy/.env.frontend' >> .git/info/exclude
```

#### На проде остались старые stash

Если `git pull` на проде блокируется из-за локальных изменений:

- Сначала посмотреть `git status --short`.
- Если это временные серверные правки, перед деплоем сохранить их в `git stash`.
- Если stash уже устарел и изменения есть в `main`, сначала сохранить patch-бэкап, потом удалить stash.

Безопасный шаблон:

```bash
cd /opt/comuna/app
mkdir -p deploy/git-cleanup-backups
git stash show -p stash@{0} > deploy/git-cleanup-backups/stash0.patch
git stash drop stash@{0}
```

Папку с backup patch-файлами тоже нужно держать в `.git/info/exclude`:

```bash
echo 'deploy/git-cleanup-backups/' >> .git/info/exclude
```

### 9. Поведение агента

- Если пользователь просит `деплой`, делать полный цикл, а не останавливаться на коммите.
- Если в процессе найден неожиданный мусор в рабочем дереве, остановиться и спросить пользователя.
- Если прод блокируется из-за локальных серверных файлов, сначала отделить рабочие env/stash от кода и только потом делать `git pull`.
- Если серверная команда упала из-за неверного пути, исправить и продолжить, а не завершать задачу частично.
- В финальном ответе всегда писать:
  - commit hash
  - что именно выкатили
  - какие проверки дали `200`
