"""Preserve bot-managed links during unrelated community settings writes."""


class CommunitySettingsWriter:
    telegram_fields = {"telegram_source_author", "telegram_channel_username"}
    telegram_request_fields = {"telegram_source_author_id", "telegram_channel_username"}

    def save(self, comun, body):
        fields = {field.name for field in comun._meta.concrete_fields if not field.primary_key}
        if not self.telegram_request_fields.intersection(body):
            # The bot may have linked the channel after this object was loaded.
            # A full model save would overwrite that new link with stale values.
            fields -= self.telegram_fields
        comun.save(update_fields=fields)
