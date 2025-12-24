from django.apps import AppConfig
from django.conf import settings


class FeedsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feeds"

    def ready(self) -> None:
        if settings.TELEGRAM_USE_POLLING:
            from .telegram_polling import start_polling_thread

            start_polling_thread()
