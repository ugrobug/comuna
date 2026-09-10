from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


class RemoteInternalMetricsError(RuntimeError):
    """Production analytics could not be collected."""


@dataclass(frozen=True)
class RemoteInternalMetricsApiConfig:
    base_url: str
    token: str
    timeout_seconds: int = 60

    @classmethod
    def load(
        cls,
        *,
        base_url: str | None = None,
        token_file: str | None = None,
    ) -> "RemoteInternalMetricsApiConfig":
        configured_url = (
            base_url or os.environ.get("TAMBUR_ANALYTICS_API_BASE_URL", "")
        ).strip().rstrip("/")
        configured_token_file = (
            token_file
            if token_file is not None
            else os.environ.get("TAMBUR_ANALYTICS_API_TOKEN_FILE", "")
        ).strip()
        token = ""
        if configured_token_file:
            try:
                token = Path(configured_token_file).expanduser().read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RemoteInternalMetricsError(
                    f"Не удалось прочитать TAMBUR_ANALYTICS_API_TOKEN_FILE: {exc}"
                ) from exc
        else:
            token = os.environ.get("TAMBUR_ANALYTICS_API_TOKEN", "").strip()

        if not configured_url:
            raise RemoteInternalMetricsError("Не задан TAMBUR_ANALYTICS_API_BASE_URL")
        parsed = urlparse(configured_url)
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and is_local):
            raise RemoteInternalMetricsError(
                "Analytics API требует HTTPS; HTTP разрешен только для localhost"
            )
        if not token:
            raise RemoteInternalMetricsError(
                "Не задан TAMBUR_ANALYTICS_API_TOKEN_FILE или TAMBUR_ANALYTICS_API_TOKEN"
            )
        return cls(base_url=configured_url, token=token)

    def product_report_url(self) -> str:
        return f"{self.base_url}/api/agent/v1/analytics/product/"


@dataclass(frozen=True)
class RemoteInternalMetricsConfig:
    target: str
    identity_file: str = ""
    port: int = 22
    connect_timeout_seconds: int = 15
    command_timeout_seconds: int = 180
    app_dir: str = "/opt/comuna/app"
    compose_file: str = "/opt/comuna/app/deploy/docker-compose.prod.yml"
    env_file: str = "/opt/comuna/app/deploy/.env"

    @classmethod
    def load(
        cls,
        *,
        target: str | None = None,
        identity_file: str | None = None,
    ) -> "RemoteInternalMetricsConfig":
        configured_target = (target or os.environ.get("TAMBUR_PROD_SSH_TARGET", "")).strip()
        configured_identity = (
            identity_file
            if identity_file is not None
            else os.environ.get("TAMBUR_PROD_SSH_IDENTITY_FILE", "")
        ).strip()
        try:
            port = int(os.environ.get("TAMBUR_PROD_SSH_PORT", "22"))
        except ValueError as exc:
            raise RemoteInternalMetricsError("TAMBUR_PROD_SSH_PORT должен быть числом") from exc
        if not configured_target:
            raise RemoteInternalMetricsError(
                "Не задан TAMBUR_PROD_SSH_TARGET (ожидается user@production-host)"
            )
        if any(character.isspace() for character in configured_target):
            raise RemoteInternalMetricsError("TAMBUR_PROD_SSH_TARGET не должен содержать пробелы")
        return cls(
            target=configured_target,
            identity_file=configured_identity,
            port=port,
        )

    def ssh_args(self, *, as_of: date | None = None) -> list[str]:
        report_date = as_of or date.today()
        remote_parts = [
            "docker",
            "compose",
            "--project-directory",
            self.app_dir,
            "-f",
            self.compose_file,
            "--env-file",
            self.env_file,
            "exec",
            "-T",
            "backend",
            "python",
            "manage.py",
            "tambur_internal_report",
            "--date",
            report_date.isoformat(),
            "--stdout",
        ]
        args = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.connect_timeout_seconds}",
            "-p",
            str(self.port),
        ]
        if self.identity_file:
            args.extend(["-i", str(Path(self.identity_file).expanduser())])
        args.extend([self.target, " ".join(shlex.quote(part) for part in remote_parts)])
        return args


def parse_remote_report(output: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(output):
        if character != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "weekly" in payload and "status" in payload:
            return payload
    raise RemoteInternalMetricsError("Production-команда не вернула JSON продуктовой аналитики")


def _fetch_remote_internal_product_report_via_ssh(
    config: RemoteInternalMetricsConfig,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            config.ssh_args(as_of=as_of),
            check=False,
            capture_output=True,
            text=True,
            timeout=config.command_timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RemoteInternalMetricsError(f"Не удалось выполнить SSH-сбор: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "SSH command failed").strip()
        raise RemoteInternalMetricsError(
            f"Production SSH-сбор завершился с кодом {result.returncode}: {detail}"
        )

    report = parse_remote_report(result.stdout)
    report["source"] = "Tambur production backend via SSH/Django ORM"
    report["transport"] = "ssh"
    return report


def _fetch_remote_internal_product_report_via_api(
    config: RemoteInternalMetricsApiConfig,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    params = {"date": as_of.isoformat()} if as_of else None
    try:
        response = requests.get(
            config.product_report_url(),
            params=params,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/json",
                "User-Agent": "tambur-product-agent/1.0",
            },
            timeout=config.timeout_seconds,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RemoteInternalMetricsError(f"Analytics API недоступен: {exc}") from exc
    if response.is_redirect:
        raise RemoteInternalMetricsError("Analytics API неожиданно вернул redirect")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RemoteInternalMetricsError("Analytics API вернул не JSON") from exc
    if response.status_code != 200:
        error = str(payload.get("error") or f"HTTP {response.status_code}")
        raise RemoteInternalMetricsError(f"Analytics API отказал: {error}")
    if not isinstance(payload, dict) or "weekly" not in payload or "status" not in payload:
        raise RemoteInternalMetricsError("Analytics API вернул некорректный отчет")
    payload["source"] = "Tambur production backend via read-only analytics API"
    payload["transport"] = "https_api"
    return payload


def load_remote_internal_metrics_config(
    *,
    api_base_url: str | None = None,
    api_token_file: str | None = None,
    ssh_target: str | None = None,
    ssh_identity_file: str | None = None,
) -> RemoteInternalMetricsApiConfig | RemoteInternalMetricsConfig:
    configured_api_url = api_base_url or os.environ.get("TAMBUR_ANALYTICS_API_BASE_URL", "")
    if configured_api_url or api_token_file:
        return RemoteInternalMetricsApiConfig.load(
            base_url=api_base_url,
            token_file=api_token_file,
        )
    return RemoteInternalMetricsConfig.load(
        target=ssh_target,
        identity_file=ssh_identity_file,
    )


def fetch_remote_internal_product_report(
    config: RemoteInternalMetricsApiConfig | RemoteInternalMetricsConfig,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    if isinstance(config, RemoteInternalMetricsApiConfig):
        return _fetch_remote_internal_product_report_via_api(config, as_of=as_of)
    return _fetch_remote_internal_product_report_via_ssh(config, as_of=as_of)
