from django.apps import AppConfig


class MyFeedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "my_feed"

    def ready(self) -> None:
        from my_feed import signals  # noqa: F401
