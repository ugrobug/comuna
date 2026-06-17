#!/bin/bash
# БД и пользователь создаёт entrypoint mysql:5.7 из compose:
#   MYSQL_DATABASE / MYSQL_USER / MYSQL_PASSWORD ← deploy/.env (MYSQL_ROMAWHO_*)
set -euo pipefail

if [ -z "${MYSQL_PASSWORD:-}" ]; then
  echo "mysql57 init: задайте MYSQL_ROMAWHO_PASSWORD в deploy/.env" >&2
  exit 1
fi

if [ -z "${MYSQL_USER:-}" ] || [ -z "${MYSQL_DATABASE:-}" ]; then
  echo "mysql57 init: задайте MYSQL_ROMAWHO_USER и MYSQL_ROMAWHO_DB в deploy/.env" >&2
  exit 1
fi

esc_user=$(printf '%s' "$MYSQL_USER" | sed "s/'/''/g")
esc_db=$(printf '%s' "$MYSQL_DATABASE" | sed 's/`/``/g')

if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
  echo "mysql57 init: задайте MYSQL57_ROOT_PASSWORD в deploy/.env" >&2
  exit 1
fi

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<EOSQL
GRANT ALL PRIVILEGES ON \`${esc_db}\`.* TO '${esc_user}'@'%';
FLUSH PRIVILEGES;
EOSQL
