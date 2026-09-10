from datetime import date
from unittest import TestCase
from unittest.mock import Mock, patch

from product_analytics.remote_internal_metrics import (
    RemoteInternalMetricsApiConfig,
    RemoteInternalMetricsConfig,
    fetch_remote_internal_product_report,
    parse_remote_report,
)
from product_analytics.weekly_report import (
    completed_week,
    match_goals,
    parse_by_time,
    parse_by_time_dimensions,
    percent_change,
)


class ProductAnalyticsHelpersTests(TestCase):
    def test_completed_week_is_previous_monday_through_sunday(self):
        period = completed_week(date(2026, 9, 10))
        self.assertEqual(period.start, date(2026, 8, 31))
        self.assertEqual(period.end, date(2026, 9, 6))

    def test_percent_change_handles_zero_baseline(self):
        self.assertEqual(percent_change(120, 100), 20.0)
        self.assertIsNone(percent_change(120, 0))

    def test_goal_matching_uses_name_or_nested_conditions(self):
        goals = [
            {"id": 1, "name": "Tambur valuable_action"},
            {
                "id": 2,
                "name": "Javascript event",
                "conditions": [{"type": "action", "url": "comment_created"}],
            },
        ]
        matches = match_goals(goals)
        self.assertEqual(matches["valuable_action"]["id"], 1)
        self.assertEqual(matches["comment_created"]["id"], 2)

    def test_parse_by_time_transposes_metric_series(self):
        payload = {
            "time_intervals": [["2026-08-24", "2026-08-30"], ["2026-08-31", "2026-09-06"]],
            "totals": [
                [100, 80],
                [110, 90],
                [130, 100],
                [25.0, 20.0],
                [1.2, 1.1],
                [60, 45],
                [70, 50],
            ],
        }
        rows = parse_by_time(payload)
        self.assertEqual(rows[1]["start"], "2026-08-31")
        self.assertEqual(rows[1]["users"], 80.0)
        self.assertEqual(rows[1]["avg_visit_duration_seconds"], 50.0)

    def test_parse_by_time_dimensions_preserves_each_segment(self):
        payload = {
            "time_intervals": [["2026-08-31", "2026-09-06"]],
            "data": [
                {
                    "dimensions": [{"name": "Smartphones"}],
                    "metrics": [[80], [90], [100], [95], [20], [1.1], [50]],
                }
            ],
        }
        rows = parse_by_time_dimensions(payload)
        self.assertEqual(rows[0]["name"], "Smartphones")
        self.assertEqual(rows[0]["weekly"][0]["page_depth"], 1.1)

    def test_remote_internal_report_parser_skips_command_preamble(self):
        payload = parse_remote_report(
            'Внутренний отчет сохранен: /tmp/report.json\n{"status":"fresh","weekly":[]}'
        )
        self.assertEqual(payload["status"], "fresh")

    def test_remote_internal_report_runs_inside_production_backend(self):
        args = RemoteInternalMetricsConfig(
            target="analytics@example.com",
            identity_file="/tmp/analytics-key",
        ).ssh_args(as_of=date(2026, 9, 10))
        self.assertEqual(args[0], "ssh")
        self.assertIn("analytics@example.com", args)
        remote_command = args[-1]
        self.assertIn("/opt/comuna/app/deploy/docker-compose.prod.yml", remote_command)
        self.assertIn("tambur_internal_report --date 2026-09-10 --stdout", remote_command)

    @patch("product_analytics.remote_internal_metrics.requests.get")
    def test_remote_internal_report_uses_read_only_https_api(self, get: Mock):
        response = Mock(status_code=200, is_redirect=False)
        response.json.return_value = {"status": "fresh", "weekly": []}
        get.return_value = response

        report = fetch_remote_internal_product_report(
            RemoteInternalMetricsApiConfig(
                base_url="https://tambur.pub",
                token="secret-token",
            ),
            as_of=date(2026, 9, 10),
        )

        self.assertEqual(report["transport"], "https_api")
        _, kwargs = get.call_args
        self.assertEqual(kwargs["params"], {"date": "2026-09-10"})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-token")
        self.assertFalse(kwargs["allow_redirects"])

    def test_remote_api_rejects_plain_http_outside_localhost(self):
        with patch.dict(
            "os.environ",
            {
                "TAMBUR_ANALYTICS_API_BASE_URL": "http://tambur.pub",
                "TAMBUR_ANALYTICS_API_TOKEN": "secret-token",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTPS"):
                RemoteInternalMetricsApiConfig.load()
