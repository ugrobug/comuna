# Django backend

## Quick start (local)

1. Create a virtualenv and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2. Set env vars:

```bash
export DJANGO_SECRET_KEY=dev-secret
export DJANGO_DEBUG=1
export POSTGRES_DB=rabotaem
export POSTGRES_USER=rabotaem
export POSTGRES_PASSWORD=rabotaem
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export TELEGRAM_WEBHOOK_SECRET=your-secret
```

3. Migrate and run:

```bash
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver 0.0.0.0:8000
```

## Telegram webhook

1. Create a bot with BotFather and add it as an admin in the channel.
2. Set webhook (replace domain and secret):

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/tg/webhook/<YOUR_SECRET>/" \
  -d "secret_token=<YOUR_SECRET>"
```

The backend accepts only channel posts and ignores other update types.

## API

- `GET /api/authors/<username>/posts/?limit=20`

Returns the latest posts for a channel/author. Blocked authors or posts are hidden.

## Admin

- `GET /admin/`

Use admin to block authors or individual posts.
