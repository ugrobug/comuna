from __future__ import annotations

import json
import statistics
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .remote_internal_metrics import (
    RemoteInternalMetricsApiConfig,
    RemoteInternalMetricsConfig,
    RemoteInternalMetricsError,
    fetch_remote_internal_product_report,
    load_remote_internal_metrics_config,
)
from .yandex_metrika import BACKEND_DIR, YandexMetrikaClient


SUMMARY_METRICS = [
    "ym:s:users",
    "ym:s:visits",
    "ym:s:pageviews",
    "ym:s:percentNewVisitors",
    "ym:s:bounceRate",
    "ym:s:pageDepth",
    "ym:s:avgVisitDurationSeconds",
]
SUMMARY_KEYS = [
    "users",
    "visits",
    "pageviews",
    "new_visitors_percent",
    "bounce_rate",
    "page_depth",
    "avg_visit_duration_seconds",
]
TRACKED_GOALS = [
    "valuable_action",
    "signup_completed",
    "meaningful_read",
    "community_subscribed",
    "comment_created",
    "vote_created",
    "post_published",
]
SEGMENTS = {
    "traffic_sources": "ym:s:trafficSource",
    "devices": "ym:s:deviceCategory",
    "landing_pages": "ym:s:startURLPath",
}
FEATURE_SEGMENTS = {
    "localized_routes": {
        "name": "Локализованные страницы",
        "release_date": "2026-07-01",
        "release_evidence": "Git 1e3ad0f / 5ce86b0; дата production-релиза не подтверждена",
        "filter": "ym:s:startURLPath=~'^/(en|de|fr|es|it|pt|pl|tr|uk)/'",
    },
    "wherefilmed": {
        "name": "WhereFilmed",
        "release_date": "2026-07-14",
        "release_evidence": "Git 5ce86b0; последующие редиректы 2026-08-24",
        "filter": "ym:s:startURLPath=~'/comuns/wherefilmed'",
    },
}
HUMAN_TRAFFIC_FILTER = "ym:s:isRobot=='No'"
REPO_ROOT = BACKEND_DIR.parent


@dataclass(frozen=True)
class WeekPeriod:
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


def completed_week(as_of: date | None = None, offset: int = 0) -> WeekPeriod:
    today = as_of or date.today()
    this_monday = today - timedelta(days=today.weekday())
    end = this_monday - timedelta(days=1 + offset * 7)
    return WeekPeriod(start=end - timedelta(days=6), end=end)


def percent_change(current: float | int | None, previous: float | int | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 2)


def _summary(client: YandexMetrikaClient, period: WeekPeriod) -> dict[str, float]:
    payload = client.report(
        date1=period.start.isoformat(),
        date2=period.end.isoformat(),
        metrics=SUMMARY_METRICS,
        limit=1,
        filters=HUMAN_TRAFFIC_FILTER,
    )
    totals = list(payload.get("totals") or [])
    return {
        key: round(float(totals[index]), 4) if index < len(totals) else 0.0
        for index, key in enumerate(SUMMARY_KEYS)
    }


def _flatten_text(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _flatten_text(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _flatten_text(nested)


def match_goals(goals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for goal in goals:
        haystack = " ".join(_flatten_text(goal)).lower()
        for identifier in TRACKED_GOALS:
            if identifier in haystack and identifier not in matches:
                matches[identifier] = goal
    return matches


def _goal_values(
    client: YandexMetrikaClient,
    period: WeekPeriod,
    matched_goals: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    identifiers = [name for name in TRACKED_GOALS if name in matched_goals]
    if not identifiers:
        return {}
    metrics = [
        f"ym:s:goal{int(matched_goals[name]['id'])}users" for name in identifiers
    ]
    payload = client.report(
        date1=period.start.isoformat(),
        date2=period.end.isoformat(),
        metrics=metrics,
        limit=1,
        filters=HUMAN_TRAFFIC_FILTER,
    )
    totals = list(payload.get("totals") or [])
    return {
        name: {
            "goal_id": int(matched_goals[name]["id"]),
            "users": round(float(totals[index]), 4) if index < len(totals) else 0.0,
        }
        for index, name in enumerate(identifiers)
    }


def _segment(
    client: YandexMetrikaClient,
    period: WeekPeriod,
    dimension: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    metrics = ["ym:s:users", "ym:s:visits", "ym:s:bounceRate"]
    payload = client.report(
        date1=period.start.isoformat(),
        date2=period.end.isoformat(),
        metrics=metrics,
        dimensions=[dimension],
        limit=limit,
        filters=HUMAN_TRAFFIC_FILTER,
    )
    rows: list[dict[str, Any]] = []
    for item in payload.get("data") or []:
        dimensions = item.get("dimensions") or []
        label = dimensions[0].get("name") if dimensions else "(не определено)"
        values = item.get("metrics") or []
        rows.append(
            {
                "name": label,
                "users": round(float(values[0]), 4) if len(values) > 0 else 0.0,
                "visits": round(float(values[1]), 4) if len(values) > 1 else 0.0,
                "bounce_rate": round(float(values[2]), 4) if len(values) > 2 else 0.0,
            }
        )
    return rows


def _traffic_quality(client: YandexMetrikaClient, period: WeekPeriod) -> dict[str, float]:
    metrics = [
        "ym:s:users",
        "ym:s:visits",
        "ym:s:robotVisits",
        "ym:s:robotPercentage",
    ]
    payload = client.report(
        date1=period.start.isoformat(),
        date2=period.end.isoformat(),
        metrics=metrics,
        limit=1,
    )
    totals = list(payload.get("totals") or [])
    keys = ["all_users", "all_visits", "robot_visits", "robot_visits_percent"]
    return {
        key: round(float(totals[index]), 4) if index < len(totals) else 0.0
        for index, key in enumerate(keys)
    }


def parse_by_time(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Metrica's metric-major bytime payload into one row per interval."""
    intervals = list(payload.get("time_intervals") or [])
    totals = list(payload.get("totals") or [])
    rows: list[dict[str, Any]] = []
    for index, interval in enumerate(intervals):
        values = [series[index] if index < len(series) else 0 for series in totals]
        row = {
            "start": interval[0],
            "end": interval[1],
        }
        row.update(
            {
                key: round(float(values[metric_index] or 0), 4)
                if metric_index < len(values)
                else 0.0
                for metric_index, key in enumerate(SUMMARY_KEYS)
            }
        )
        rows.append(row)
    return rows


def parse_by_time_dimensions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    intervals = list(payload.get("time_intervals") or [])
    result: list[dict[str, Any]] = []
    for item in payload.get("data") or []:
        dimensions = item.get("dimensions") or []
        name = dimensions[0].get("name") if dimensions else "(не определено)"
        metric_series = list(item.get("metrics") or [])
        weekly: list[dict[str, Any]] = []
        for index, interval in enumerate(intervals):
            row: dict[str, Any] = {"start": interval[0], "end": interval[1]}
            for metric_index, key in enumerate(SUMMARY_KEYS):
                series = metric_series[metric_index] if metric_index < len(metric_series) else []
                value = series[index] if index < len(series) else 0
                row[key] = round(float(value or 0), 4)
            weekly.append(row)
        result.append({"name": name, "weekly": weekly})
    return result


def _history(
    client: YandexMetrikaClient,
    start: date,
    end: date,
    *,
    extra_filter: str | None = None,
) -> list[dict[str, Any]]:
    filters = HUMAN_TRAFFIC_FILTER
    if extra_filter:
        filters = f"{filters} AND {extra_filter}"
    payload = client.report_by_time(
        date1=start.isoformat(),
        date2=end.isoformat(),
        metrics=SUMMARY_METRICS,
        group="week",
        filters=filters,
    )
    return parse_by_time(payload)


def _history_by_dimension(
    client: YandexMetrikaClient,
    start: date,
    end: date,
    dimension: str,
) -> list[dict[str, Any]]:
    payload = client.report_by_time(
        date1=start.isoformat(),
        date2=end.isoformat(),
        metrics=SUMMARY_METRICS,
        dimensions=[dimension],
        group="week",
        filters=HUMAN_TRAFFIC_FILTER,
    )
    return parse_by_time_dimensions(payload)


def _git_changes(period: WeekPeriod) -> list[dict[str, str]]:
    since = f"{period.start.isoformat()}T00:00:00"
    until = f"{(period.end + timedelta(days=1)).isoformat()}T00:00:00"
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={since}",
                f"--until={until}",
                "--pretty=format:%h%x09%aI%x09%s",
                "--no-merges",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    changes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            changes.append({"commit": parts[0], "authored_at": parts[1], "subject": parts[2]})
    return changes


def build_weekly_report(
    client: YandexMetrikaClient,
    *,
    as_of: date | None = None,
    include_git: bool = True,
    include_internal: bool = True,
    internal_config: RemoteInternalMetricsApiConfig | RemoteInternalMetricsConfig | None = None,
) -> dict[str, Any]:
    periods = [completed_week(as_of, offset) for offset in range(5)]
    summaries = [_summary(client, period) for period in periods]
    goals = client.goals()
    matched_goals = match_goals(goals)
    current_goals = _goal_values(client, periods[0], matched_goals)
    previous_goals = _goal_values(client, periods[1], matched_goals)

    baseline = {
        key: round(statistics.median(summary[key] for summary in summaries[1:]), 4)
        for key in SUMMARY_KEYS
    }
    exact_nsm = current_goals.get("valuable_action")
    previous_nsm = previous_goals.get("valuable_action")
    proxy_users = round(
        summaries[0]["users"] * (1 - summaries[0]["bounce_rate"] / 100), 4
    )
    history_start = periods[0].start - timedelta(weeks=13)

    internal_product: dict[str, Any] | None = None
    if include_internal:
        try:
            resolved_internal_config = internal_config or load_remote_internal_metrics_config()
            internal_product = fetch_remote_internal_product_report(
                resolved_internal_config,
                as_of=as_of,
            )
        except RemoteInternalMetricsError as exc:
            internal_product = {
                "status": "unavailable",
                "error": str(exc),
                "source": "Tambur production backend",
                "note": "Production backend недоступен по SSH; не интерпретировать отсутствие данных как нулевую активность.",
            }

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counter_id": client.config.counter_id,
        "data_policy": {
            "primary_filter": HUMAN_TRAFFIC_FILTER,
            "note": "Основные метрики и сегменты исключают визиты, распознанные Метрикой как роботы.",
        },
        "period": {"start": periods[0].start.isoformat(), "end": periods[0].end.isoformat()},
        "comparison_period": {
            "start": periods[1].start.isoformat(),
            "end": periods[1].end.isoformat(),
        },
        "north_star": {
            "name": "Weekly Valuable Users",
            "status": "exact" if exact_nsm else "proxy",
            "users": exact_nsm["users"] if exact_nsm else None,
            "previous_users": previous_nsm["users"] if previous_nsm else None,
            "week_over_week_percent": percent_change(
                exact_nsm["users"] if exact_nsm else None,
                previous_nsm["users"] if previous_nsm else None,
            ),
            "proxy_non_bounce_users": proxy_users if not exact_nsm else None,
            "note": (
                "Точное число уникальных пользователей цели valuable_action."
                if exact_nsm
                else "Цель valuable_action пока не найдена; proxy не является точной North Star."
            ),
        },
        "summary": summaries[0],
        "previous_summary": summaries[1],
        "week_over_week_percent": {
            key: percent_change(summaries[0][key], summaries[1][key])
            for key in SUMMARY_KEYS
        },
        "previous_four_weeks_median": baseline,
        "versus_four_week_median_percent": {
            key: percent_change(summaries[0][key], baseline[key]) for key in SUMMARY_KEYS
        },
        "goals": {
            name: {
                **current,
                "previous_users": previous_goals.get(name, {}).get("users"),
                "week_over_week_percent": percent_change(
                    current.get("users"), previous_goals.get(name, {}).get("users")
                ),
            }
            for name, current in current_goals.items()
        },
        "missing_product_goals": [name for name in TRACKED_GOALS if name not in matched_goals],
        "traffic_quality": {
            "current": _traffic_quality(client, periods[0]),
            "previous": _traffic_quality(client, periods[1]),
        },
        "internal_product": internal_product,
        "segments": {
            name: {
                "current": _segment(client, periods[0], dimension),
                "previous": _segment(client, periods[1], dimension),
            }
            for name, dimension in SEGMENTS.items()
        },
        "history": {
            "period": {
                "start": history_start.isoformat(),
                "end": periods[0].end.isoformat(),
            },
            "weekly": _history(client, history_start, periods[0].end),
            "devices": _history_by_dimension(
                client,
                history_start,
                periods[0].end,
                SEGMENTS["devices"],
            ),
            "feature_segments": {
                key: {
                    "name": definition["name"],
                    "release_date": definition["release_date"],
                    "release_evidence": definition["release_evidence"],
                    "weekly": _history(
                        client,
                        history_start,
                        periods[0].end,
                        extra_filter=definition["filter"],
                    ),
                }
                for key, definition in FEATURE_SEGMENTS.items()
            },
            "method": "Недельный ряд Reporting API /bytime; только человеческие визиты.",
        },
        "change_evidence": {
            "git_commits": _git_changes(periods[0]) if include_git else [],
            "caveat": "Git-коммиты — кандидаты на изменения продукта, а не подтверждение даты production-деплоя.",
        },
    }
    return report


def write_report(report: dict[str, Any], output: str | Path | None = None) -> Path:
    period_end = report["period"]["end"]
    path = Path(output) if output else BACKEND_DIR / "var" / "product-analytics" / f"{period_end}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
