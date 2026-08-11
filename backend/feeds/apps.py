from django.apps import AppConfig


class FeedsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feeds"

    def ready(self):
        import feeds.cache_signals  # noqa: F401
        import feeds.translation_signals  # noqa: F401
