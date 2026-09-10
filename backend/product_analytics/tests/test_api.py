from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from product_analytics.models import (
    AnalyticsApiAccessLog,
    AnalyticsApiCredential,
    SCOPE_COMMUNITY_ANALYTICS,
    SCOPE_SITE_ANALYTICS,
)


@override_settings(
    ANALYTICS_API_RATE_LIMIT_PER_MINUTE=100,
    ANALYTICS_API_REQUIRE_HTTPS=False,
)
class AnalyticsAgentApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.comun = Comun.objects.create(
            name="Allowed community",
            slug="allowed-community",
            subscribers_count=12,
        )
        self.other_comun = Comun.objects.create(
            name="Other community",
            slug="other-community",
            subscribers_count=5,
        )
        self.credential, self.token = AnalyticsApiCredential.issue(
            name="product-agent",
            scopes=[SCOPE_SITE_ANALYTICS, SCOPE_COMMUNITY_ANALYTICS],
            allowed_community_slugs=[self.comun.slug],
        )
        self.headers = {
            "HTTP_AUTHORIZATION": f"Bearer {self.token}",
            "HTTP_USER_AGENT": "tambur-product-agent/1.0",
        }

    def test_token_is_only_stored_as_hash(self):
        self.assertNotEqual(self.credential.token_hash, self.token)
        self.assertNotIn(self.token, str(self.credential.__dict__))

    def test_site_analytics_rejects_missing_and_invalid_tokens(self):
        url = reverse("agent-site-analytics")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Cache-Control"], "no-store")

        response = self.client.get(
            url,
            HTTP_AUTHORIZATION="Bearer tambur_analytics_unknown.invalid",
        )
        self.assertEqual(response.status_code, 401)

    def test_site_analytics_requires_scope_and_returns_moderator_payload(self):
        community_only, token = AnalyticsApiCredential.issue(
            name="community-only",
            scopes=[SCOPE_COMMUNITY_ANALYTICS],
            allowed_community_slugs=["*"],
        )
        response = self.client.get(
            reverse("agent-site-analytics"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse("agent-site-analytics"), **self.headers)
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertIn("totals", response.json())
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("Authorization", response["Vary"])
        self.assertTrue(
            AnalyticsApiAccessLog.objects.filter(
                credential=self.credential,
                endpoint="site",
            ).exists()
        )

    def test_expired_and_revoked_tokens_are_rejected(self):
        url = reverse("agent-site-analytics")
        self.credential.expires_at = timezone.now() - timedelta(seconds=1)
        self.credential.save(update_fields=["expires_at"])
        self.assertEqual(self.client.get(url, **self.headers).status_code, 401)

        self.credential.expires_at = timezone.now() + timedelta(days=1)
        self.credential.revoked_at = timezone.now()
        self.credential.save(update_fields=["expires_at", "revoked_at"])
        self.assertEqual(self.client.get(url, **self.headers).status_code, 401)

    def test_community_list_and_detail_are_restricted_to_allowed_slugs(self):
        response = self.client.get(reverse("agent-community-analytics-list"), **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in response.json()["communities"]],
            [self.comun.slug],
        )

        response = self.client.get(
            reverse("agent-community-analytics", kwargs={"slug": self.comun.slug}),
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["comun"]["slug"], self.comun.slug)

        response = self.client.get(
            reverse("agent-community-analytics", kwargs={"slug": self.other_comun.slug}),
            **self.headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_ip_allowlist_is_enforced(self):
        self.credential.allowed_ip_networks = ["10.0.0.0/8"]
        self.credential.save(update_fields=["allowed_ip_networks"])
        url = reverse("agent-site-analytics")
        self.assertEqual(
            self.client.get(url, REMOTE_ADDR="192.0.2.10", **self.headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(url, REMOTE_ADDR="10.2.3.4", **self.headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                url,
                REMOTE_ADDR="10.2.3.4",
                HTTP_X_FORWARDED_FOR="10.2.3.4",
                HTTP_X_REAL_IP="192.0.2.10",
                **self.headers,
            ).status_code,
            403,
        )

    @override_settings(ANALYTICS_API_RATE_LIMIT_PER_MINUTE=1)
    def test_rate_limit_is_scoped_to_credential(self):
        url = reverse("agent-site-analytics")
        self.assertEqual(self.client.get(url, **self.headers).status_code, 200)
        response = self.client.get(url, **self.headers)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")

    def test_endpoints_are_read_only(self):
        response = self.client.post(reverse("agent-site-analytics"), **self.headers)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")

    @override_settings(ANALYTICS_API_REQUIRE_HTTPS=True)
    def test_https_is_required_when_enabled(self):
        url = reverse("agent-site-analytics")
        self.assertEqual(self.client.get(url, **self.headers).status_code, 403)
        self.assertEqual(self.client.get(url, secure=True, **self.headers).status_code, 200)

    def test_product_report_is_available_without_personal_data(self):
        response = self.client.get(
            f"{reverse('agent-product-analytics')}?date=2026-09-10",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("north_star", payload)
        self.assertEqual(len(payload["weekly"]), 5)
        self.assertNotIn("users", payload["summary"])

    def test_site_analytics_rejects_excessive_period(self):
        response = self.client.get(
            f"{reverse('agent-site-analytics')}?from=2020-01-01&to=2026-01-01",
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "period must not exceed 366 days")

    def test_key_command_requires_known_community(self):
        with self.assertRaisesRegex(CommandError, "Не найдены сообщества"):
            call_command(
                "create_analytics_api_key",
                "--name",
                "unknown-community-agent",
                "--scope",
                "communities",
                "--community",
                "missing-community",
                stdout=StringIO(),
            )

    def test_key_command_issues_scoped_expiring_key(self):
        output = StringIO()
        call_command(
            "create_analytics_api_key",
            "--name",
            "scoped-agent",
            "--scope",
            "site",
            "--scope",
            "communities",
            "--community",
            self.comun.slug,
            "--expires-in-days",
            "30",
            stdout=output,
        )
        created = AnalyticsApiCredential.objects.get(name="scoped-agent")
        self.assertEqual(
            set(created.scopes),
            {SCOPE_SITE_ANALYTICS, SCOPE_COMMUNITY_ANALYTICS},
        )
        self.assertEqual(created.allowed_community_slugs, [self.comun.slug])
        self.assertIn(f"tambur_analytics_{created.key_prefix}.", output.getvalue())
