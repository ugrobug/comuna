# MAX integration

The bot uses the official MAX API at `https://platform-api2.max.ru`.

Set these values in the ignored `backend/.env` locally and in the backend environment on the server:

```
MAX_BOT_TOKEN=...
MAX_BOT_USERNAME=se14353168_bot
MAX_WEBHOOK_SECRET=...
```

Never commit tokens. To validate the token and the bot identity without sending messages:

```
.venv/bin/python backend/manage.py check_max_bot
```

The API client uses a dedicated TLS context. The bundled public Russian Trusted Root CA was obtained from `https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt`, as required by the [MAX API documentation](https://dev.max.ru/docs-api). It is not installed in the operating system trust store and is not used by other integrations.

## Setup and operation

1. Create a community on the website. In profile settings → MAX, request a one-time code and send it to the bot (expires after 15 minutes).
2. Add the bot as administrator to an existing channel or group. Forward a channel post to the bot if it was added before webhook registration. For groups, use `/link_comun community-slug` after linking the account.
3. Select the verified channel/group in community settings → MAX or in the bot. Linking requires both community moderation rights and current MAX administrator rights, including the bot's administrator status.
4. Run migrations, start `process_max_events --loop` (the `max-events` Compose service), and run `setup_max_webhook` after the HTTPS endpoint is available. `SITE_BASE_URL` must be the public site origin.

The webhook validates `X-Max-Bot-Api-Secret`, persists events and deduplicates retries before responding. The worker processes events and opted-in notifications with bounded retries. Pending/failed work is stored in `MaxUpdate` and `MaxNotificationDelivery`; errors contain exception types only. Check exhausted rows (`attempts >= 18`, completion timestamp absent) when troubleshooting.

Channels support post creation/editing, image and link attachments, manual approval, and 0/1/3/7-day publication delays. A source message is imported once. Media without a downloadable URL is linked back to MAX when a source URL is available. Telegram continues to operate independently.

Groups support `/search query` across the community knowledge base and glossary. Reply with `/kb` or `/glossary` to propose a text message; moderators review it in the bot or community settings → MAX. Group messages are not published automatically.

Notifications are individually enabled through the bot. MAX identities are independent of Telegram identities and are linked only by a website-issued code. The token and webhook secret belong only in ignored environment files. Never put invite links, account codes or credentials into Git.

