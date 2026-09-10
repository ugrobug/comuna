# Tambur Analytics API

Read-only API for product-analysis agents. It exposes aggregated site and community
metrics, never database credentials or user-level records.

## Endpoints

- `GET /api/agent/v1/analytics/site/?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /api/agent/v1/analytics/product/?date=YYYY-MM-DD`
- `GET /api/agent/v1/analytics/communities/`
- `GET /api/agent/v1/analytics/communities/<slug>/`

Every request requires `Authorization: Bearer <token>`. Responses use
`Cache-Control: private, no-store`; nginx also bypasses its API cache when the
Authorization header is present.

## Issue a key

Run inside the production backend container:

```bash
python manage.py create_analytics_api_key \
  --name product-agent \
  --scope site \
  --scope communities \
  --all-communities \
  --expires-in-days 90
```

To restrict the key further, replace `--all-communities` with repeated
`--community <slug>` options and optionally add `--allow-ip <address-or-cidr>`.
The raw token is printed once. The database stores only its SHA-256 hash.

Store the token in a file outside the repository and configure the agent:

```bash
export TAMBUR_ANALYTICS_API_BASE_URL=https://tambur.pub
export TAMBUR_ANALYTICS_API_TOKEN_FILE=/secure/path/tambur-analytics.token
```

The weekly `tambur_product_report` command will prefer the HTTPS API when
`TAMBUR_ANALYTICS_API_BASE_URL` is set and keep SSH only as a compatibility
fallback.

## Rotation and revocation

Create a new key, update the agent's secret file, verify one request, then revoke
the previous key in Django admin under `Product analytics > Ключи API аналитики`.
The same section shows the last-use timestamp/IP and an access log by endpoint.
