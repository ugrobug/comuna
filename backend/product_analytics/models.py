from __future__ import annotations

import hashlib
import ipaddress
import secrets
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


SCOPE_SITE_ANALYTICS = "site_analytics:read"
SCOPE_COMMUNITY_ANALYTICS = "community_analytics:read"
ANALYTICS_API_SCOPES = {
    SCOPE_SITE_ANALYTICS,
    SCOPE_COMMUNITY_ANALYTICS,
}


class AnalyticsApiCredential(models.Model):
    name = models.CharField(max_length=120, unique=True)
    key_prefix = models.CharField(max_length=16, unique=True, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    scopes = models.JSONField(default=list)
    allowed_community_slugs = models.JSONField(default=list, blank=True)
    allowed_ip_networks = models.JSONField(default=list, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Ключ API аналитики"
        verbose_name_plural = "Ключи API аналитики"

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix})"

    def clean(self) -> None:
        super().clean()
        scopes = {str(scope).strip() for scope in self.scopes or [] if str(scope).strip()}
        unknown_scopes = scopes - ANALYTICS_API_SCOPES
        if unknown_scopes:
            raise ValidationError({"scopes": f"Unknown scopes: {', '.join(sorted(unknown_scopes))}"})

        community_slugs = [str(value).strip() for value in self.allowed_community_slugs or []]
        if any(not value for value in community_slugs):
            raise ValidationError({"allowed_community_slugs": "Empty community slug is not allowed"})
        for value in self.allowed_ip_networks or []:
            try:
                ipaddress.ip_network(str(value).strip(), strict=False)
            except ValueError as exc:
                raise ValidationError({"allowed_ip_networks": f"Invalid IP network: {value}"}) from exc

    @classmethod
    def issue(
        cls,
        *,
        name: str,
        scopes: list[str],
        allowed_community_slugs: list[str] | None = None,
        allowed_ip_networks: list[str] | None = None,
        expires_in_days: int | None = 90,
    ) -> tuple["AnalyticsApiCredential", str]:
        key_prefix = secrets.token_hex(6)
        raw_token = f"tambur_analytics_{key_prefix}.{secrets.token_urlsafe(32)}"
        expires_at = (
            timezone.now() + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        )
        credential = cls(
            name=name,
            key_prefix=key_prefix,
            token_hash=cls.hash_token(raw_token),
            scopes=sorted(set(scopes)),
            allowed_community_slugs=sorted(set(allowed_community_slugs or [])),
            allowed_ip_networks=sorted(set(allowed_ip_networks or [])),
            expires_at=expires_at,
        )
        credential.full_clean()
        credential.save()
        return credential, raw_token

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def is_active(self, *, now=None) -> bool:
        current_time = now or timezone.now()
        return self.revoked_at is None and (
            self.expires_at is None or self.expires_at > current_time
        )

    def has_scope(self, scope: str) -> bool:
        return scope in set(self.scopes or [])

    def allows_community(self, slug: str) -> bool:
        allowed = set(self.allowed_community_slugs or [])
        return "*" in allowed or slug in allowed


class AnalyticsApiAccessLog(models.Model):
    credential = models.ForeignKey(
        AnalyticsApiCredential,
        null=True,
        on_delete=models.SET_NULL,
        related_name="access_logs",
    )
    endpoint = models.CharField(max_length=80)
    community_slug = models.SlugField(max_length=160, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("credential", "-created_at"), name="analytics_key_access_idx"),
            models.Index(fields=("endpoint", "-created_at"), name="analytics_endpoint_idx"),
        ]
        verbose_name = "Обращение к API аналитики"
        verbose_name_plural = "Обращения к API аналитики"

    def __str__(self) -> str:
        return f"{self.credential_id}:{self.endpoint}:{self.created_at.isoformat()}"
