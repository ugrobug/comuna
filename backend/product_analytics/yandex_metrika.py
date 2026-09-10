from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

import requests


AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
API_ROOT = "https://api-metrika.yandex.net"
DEFAULT_REDIRECT_URI = "https://oauth.yandex.ru/verification_code"
DEFAULT_COUNTER_ID = "106046128"
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SECRET_FILE = BACKEND_DIR / "secrets" / "yandex_metrika.json"


class MetrikaConfigurationError(RuntimeError):
    pass


class MetrikaAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class MetrikaConfig:
    counter_id: str
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI
    access_token: str = ""
    refresh_token: str = ""
    expires_at: int = 0
    secret_file: Path = DEFAULT_SECRET_FILE

    @classmethod
    def load(cls, secret_file: str | Path | None = None) -> "MetrikaConfig":
        path = Path(
            secret_file
            or os.environ.get("YANDEX_METRIKA_SECRET_FILE", "")
            or DEFAULT_SECRET_FILE
        ).expanduser()
        stored: dict[str, Any] = {}
        if path.exists():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise MetrikaConfigurationError(
                    f"Не удалось прочитать OAuth-конфигурацию: {path}"
                ) from exc

        def value(env_name: str, key: str, default: Any = "") -> Any:
            return os.environ.get(env_name) or stored.get(key) or default

        return cls(
            counter_id=str(
                value("YANDEX_METRIKA_COUNTER_ID", "counter_id", DEFAULT_COUNTER_ID)
            ),
            client_id=str(value("YANDEX_METRIKA_CLIENT_ID", "client_id")),
            client_secret=str(
                value("YANDEX_METRIKA_CLIENT_SECRET", "client_secret")
            ),
            redirect_uri=str(
                value(
                    "YANDEX_METRIKA_REDIRECT_URI",
                    "redirect_uri",
                    DEFAULT_REDIRECT_URI,
                )
            ),
            access_token=str(value("YANDEX_METRIKA_ACCESS_TOKEN", "access_token")),
            refresh_token=str(
                value("YANDEX_METRIKA_REFRESH_TOKEN", "refresh_token")
            ),
            expires_at=int(value("YANDEX_METRIKA_EXPIRES_AT", "expires_at", 0) or 0),
            secret_file=path,
        )

    def require_oauth_application(self) -> None:
        if not self.client_id or not self.client_secret:
            raise MetrikaConfigurationError(
                "Не заданы YANDEX_METRIKA_CLIENT_ID и YANDEX_METRIKA_CLIENT_SECRET"
            )

    def as_secret_payload(self) -> dict[str, Any]:
        return {
            "counter_id": self.counter_id,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    def save(self) -> None:
        self.secret_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.secret_file.name}.", dir=self.secret_file.parent
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.as_secret_payload(), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temp_name, self.secret_file)
            self.secret_file.chmod(0o600)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def exchange_authorization_code(config: MetrikaConfig, code: str) -> MetrikaConfig:
    config.require_oauth_application()
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code.strip(),
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
        },
        timeout=30,
    )
    payload = _decode_response(response, "обменять код авторизации")
    updated = _config_with_token(config, payload)
    updated.save()
    return updated


def refresh_access_token(config: MetrikaConfig) -> MetrikaConfig:
    config.require_oauth_application()
    if not config.refresh_token:
        raise MetrikaConfigurationError(
            "Нет refresh token. Запустите yandex_metrika_auth для первичной авторизации."
        )
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": config.refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        timeout=30,
    )
    payload = _decode_response(response, "обновить OAuth-токен")
    updated = _config_with_token(config, payload)
    updated.save()
    return updated


def _config_with_token(config: MetrikaConfig, payload: Mapping[str, Any]) -> MetrikaConfig:
    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise MetrikaAPIError("OAuth не вернул access token")
    expires_in = int(payload.get("expires_in") or 0)
    return replace(
        config,
        access_token=access_token,
        refresh_token=str(payload.get("refresh_token") or config.refresh_token),
        expires_at=int(time.time()) + expires_in if expires_in else 0,
    )


def _decode_response(response: requests.Response, action: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise MetrikaAPIError(
            f"Не удалось {action}: HTTP {response.status_code}"
        ) from exc
    if not response.ok:
        detail = payload.get("error_description") or payload.get("message") or payload.get("error")
        raise MetrikaAPIError(f"Не удалось {action}: {detail or response.status_code}")
    return payload


class YandexMetrikaClient:
    def __init__(
        self,
        config: MetrikaConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config or MetrikaConfig.load()
        self.session = session or requests.Session()

    def _ensure_token(self) -> str:
        if self.config.access_token and (
            not self.config.expires_at or self.config.expires_at > int(time.time()) + 120
        ):
            return self.config.access_token
        if self.config.refresh_token:
            self.config = refresh_access_token(self.config)
            return self.config.access_token
        raise MetrikaConfigurationError(
            "Яндекс Метрика не авторизована. Запустите yandex_metrika_auth."
        )

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            f"{API_ROOT}{path}",
            params=params,
            headers={"Authorization": f"OAuth {self._ensure_token()}"},
            timeout=60,
        )
        if response.status_code == 401 and self.config.refresh_token:
            self.config = refresh_access_token(self.config)
            response = self.session.get(
                f"{API_ROOT}{path}",
                params=params,
                headers={"Authorization": f"OAuth {self.config.access_token}"},
                timeout=60,
            )
        return _decode_response(response, f"получить данные Метрики ({path})")

    def goals(self) -> list[dict[str, Any]]:
        payload = self.get(f"/management/v1/counter/{self.config.counter_id}/goals")
        return list(payload.get("goals") or [])

    def report(
        self,
        *,
        date1: str,
        date2: str,
        metrics: list[str],
        dimensions: list[str] | None = None,
        limit: int = 100,
        filters: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "ids": self.config.counter_id,
            "date1": date1,
            "date2": date2,
            "metrics": ",".join(metrics),
            "limit": limit,
            "accuracy": "full",
        }
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        if filters:
            params["filters"] = filters
        return self.get("/stat/v1/data", params=params)

    def report_by_time(
        self,
        *,
        date1: str,
        date2: str,
        metrics: list[str],
        dimensions: list[str] | None = None,
        group: str = "week",
        filters: str | None = None,
        top_keys: int = 30,
    ) -> dict[str, Any]:
        """Return chart-ready metric series grouped by a time interval."""
        params: dict[str, Any] = {
            "ids": self.config.counter_id,
            "date1": date1,
            "date2": date2,
            "metrics": ",".join(metrics),
            "group": group,
            "top_keys": top_keys,
            "accuracy": "full",
        }
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        if filters:
            params["filters"] = filters
        return self.get("/stat/v1/data/bytime", params=params)
