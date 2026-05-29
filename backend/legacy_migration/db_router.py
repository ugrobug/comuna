class RomawhoRouter:
    """Unmanaged mirror WP → romawho; таблицы маппинга → default (Postgres)."""

    def _is_romawho_mirror(self, model) -> bool:
        return model._meta.app_label == "legacy_migration" and not model._meta.managed

    def db_for_read(self, model, **hints):
        if self._is_romawho_mirror(model):
            return "romawho"
        return None

    def db_for_write(self, model, **hints):
        if self._is_romawho_mirror(model):
            return "romawho"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if "legacy_migration" in labels:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "romawho":
            return False
        if app_label == "legacy_migration":
            return db == "default"
        return None
