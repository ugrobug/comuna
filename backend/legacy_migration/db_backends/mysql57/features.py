from django.db.backends.mysql import features as mysql_features
from django.utils.functional import cached_property


class DatabaseFeatures(mysql_features.DatabaseFeatures):
    """MySQL 5.7 legacy (Django 5 официально требует 8.0.11+)."""

    @cached_property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:
            return (10, 5)
        return (5, 7)
