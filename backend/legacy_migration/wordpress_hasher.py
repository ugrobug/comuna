"""Проверка паролей WordPress (phpass, bcrypt) для импорта wp_users.user_pass.

WP 6.8+ (pluggable.php): префикс $wp — bcrypt от HMAC-SHA384(пароль, 'wp-sha384'), не от сырого пароля.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from django.contrib.auth.hashers import BasePasswordHasher

_WP_SHA384_KEY = b"wp-sha384"


def wp_password_hash_usable(encoded: object) -> bool:
    raw = str(encoded or "").strip()
    if not raw or raw.startswith("*"):
        return False
    if raw.startswith(("$P$", "$H$")):
        return len(raw) >= 34
    if raw.startswith("$wp") and len(raw) > 10:
        return True
    if raw.startswith(("$2y$", "$2a$", "$2b$")):
        return len(raw) >= 60
    return False


def _wp_password_to_verify_bytes(password: str) -> bytes:
    """Как wp_check_password / wp_hash_password для префикса $wp (PHP 6.8+)."""
    digest = hmac.new(_WP_SHA384_KEY, password.encode("utf-8"), hashlib.sha384).digest()
    return base64.b64encode(digest)


def _verify_wp_prefixed_bcrypt(password: str, encoded: str) -> bool:
    """$wp + password_hash(bcrypt) — substr($hash, 3) затем password_verify."""
    import bcrypt

    if not encoded.startswith("$wp"):
        return False
    bcrypt_hash = encoded[3:]
    if bcrypt_hash.startswith("$2y$"):
        bcrypt_hash = "$2b$" + bcrypt_hash[4:]
    try:
        return bcrypt.checkpw(_wp_password_to_verify_bytes(password), bcrypt_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _verify_bcrypt(password: str, encoded: str) -> bool:
    import bcrypt

    raw = (encoded or "").strip()
    if raw.startswith("$2y$"):
        raw = "$2b$" + raw[4:]
    elif raw.startswith("$2a$"):
        raw = "$2b$" + raw[4:]
    try:
        return bcrypt.checkpw(password.encode("utf-8"), raw.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_wordpress_password(password: str, encoded: str) -> bool:
    if not password or not wp_password_hash_usable(encoded):
        return False
    encoded = encoded.strip()
    try:
        if encoded.startswith(("$P$", "$H$")):
            from passlib.hash import phpass

            return phpass.verify(password, encoded)
        if encoded.startswith("$wp"):
            return _verify_wp_prefixed_bcrypt(password, encoded)
        if encoded.startswith(("$2y$", "$2a$", "$2b$")):
            return _verify_bcrypt(password, encoded)
    except Exception:
        return False
    return False


def wordpress_password_field_value(wp_user_pass: str) -> str:
    """Значение для User.password: Django находит hasher по префиксу algorithm$."""
    raw = (wp_user_pass or "").strip()
    if not wp_password_hash_usable(raw):
        return ""
    if raw.startswith(f"{WordPressPasswordHasher.algorithm}$"):
        return raw
    return f"{WordPressPasswordHasher.algorithm}${raw}"


def wordpress_password_hash_from_field(encoded: str) -> str:
    prefix = f"{WordPressPasswordHasher.algorithm}$"
    if (encoded or "").startswith(prefix):
        return encoded[len(prefix) :]
    return encoded


class WordPressPasswordHasher(BasePasswordHasher):
    """
    Хеш из wp_users.user_pass без перехеширования.
    В PASSWORD_HASHERS ставить первым — только для проверки импортированных паролей.
    """

    algorithm = "wordpress"

    def verify(self, password: str, encoded: str) -> bool:
        return verify_wordpress_password(password, wordpress_password_hash_from_field(encoded))

    def encode(self, password: str, salt: str | None = None) -> str:
        from passlib.hash import phpass

        return wordpress_password_field_value(phpass.hash(password))

    def safe_summary(self, encoded: str) -> dict:
        return {"algorithm": self.algorithm, "hash": "********", "truncated": "********"}

    def must_update(self, encoded: str) -> bool:
        return False

    def harden_runtime(self, password: str, encoded: str) -> None:
        pass

    @classmethod
    def identify(cls, encoded: str) -> bool:
        if (encoded or "").startswith(f"{cls.algorithm}$"):
            return wp_password_hash_usable(wordpress_password_hash_from_field(encoded))
        return wp_password_hash_usable(encoded)
