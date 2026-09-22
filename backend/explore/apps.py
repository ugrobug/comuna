from django.apps import AppConfig


class ExploreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "explore"
    verbose_name = "Explore — граф увлечений"

    def ready(self):
        from . import signals  # noqa: F401
