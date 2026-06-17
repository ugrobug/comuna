"""Модели legacy_migration: маппинг (Postgres) + зеркало WP (MySQL, unmanaged)."""

from legacy_migration.models.mapping import (  # noqa: F401
    LegacyWpCommentMap,
    LegacyWpPostMap,
    LegacyWpUserMap,
)
from legacy_migration.models.wp_mirror import *  # noqa: F403
