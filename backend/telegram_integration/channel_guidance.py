from django.db.models import Q

from communities.models import Comun
from users.models import AuthorAdmin


class TelegramChannelLinkGuidance:
    """Offer existing, verified communities instead of sending owners to create another."""

    def message(self, author):
        owners = AuthorAdmin.objects.filter(
            author=author, verified_at__isnull=False,
        ).values("user_id")
        communities = list(Comun.objects.filter(
            Q(creator_id__in=owners) | Q(moderators__id__in=owners), is_active=True,
        ).order_by("id").values_list("slug", flat=True).distinct()[:3])
        if communities:
            links = "\n".join(f"https://tambur.pub/comuns/{slug}/settings?tab=telegram" for slug in communities)
            return (
                f"Канал @{author.username} подключён к боту, но ещё не привязан к сообществу на сайте. "
                "Подтверждение канала и сохранение привязки — разные шаги.\n"
                "Откройте настройки нужного сообщества:\n"
                f"{links}\n"
                f"В разделе Telegram выберите @{author.username} и сохраните настройки. "
                "Затем повторите пересылку поста. Создавать новое сообщество не нужно."
            )
        return (
            "Канал ещё не привязан к сообществу: сначала создайте сообщество "
            "на сайте: https://tambur.pub/comuns?create=1\n"
            "Затем привяжите канал в настройках сообщества → Telegram "
            "и подтвердите его кодом в боте. Если сообщество уже есть, "
            "используйте его настройки и сохраните привязку."
        )
