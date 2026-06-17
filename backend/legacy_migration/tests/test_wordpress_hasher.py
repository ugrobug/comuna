from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings

from legacy_migration.wordpress_hasher import (
    WordPressPasswordHasher,
    verify_wordpress_password,
    wp_password_hash_usable,
)

User = get_user_model()

# phpass из дампа WP (пользователь kueke); пароль в тесте не проверяем — только формат
_PHPASS_SAMPLE = "$P$BTC5k/OBMyL.g415E3OJ78ulgf5pND/"
_WP_BCRYPT_SAMPLE = "$wp$2y$10$VtwTVIpfcOZ91WNCezxI6OEYSCEL.t1485zA46F85AM/0mBG0SWtm"


class WordPressHasherTests(SimpleTestCase):
    def test_identify_phpass(self) -> None:
        self.assertTrue(wp_password_hash_usable(_PHPASS_SAMPLE))
        self.assertFalse(wp_password_hash_usable(""))
        self.assertFalse(wp_password_hash_usable("*"))

    def test_verify_phpass_roundtrip(self) -> None:
        from passlib.hash import phpass

        encoded = phpass.hash("test-pass-legacy")
        self.assertTrue(verify_wordpress_password("test-pass-legacy", encoded))
        self.assertFalse(verify_wordpress_password("wrong", encoded))

    def test_wp_bcrypt_prefix_usable(self) -> None:
        self.assertTrue(wp_password_hash_usable(_WP_BCRYPT_SAMPLE))

    def test_verify_real_wp_bcrypt_hash_from_dump(self) -> None:
        """Вектор из wp_users (WP 6.8+ $wp + HMAC-SHA384 перед bcrypt)."""
        wp_pass = "$wp$2y$10$cVNgdHnqAIb3tfJswKY70O6K3FhowrIK9ObT1t9KHloGoN.0vZUea"
        self.assertTrue(verify_wordpress_password("test23335231", wp_pass))
        self.assertFalse(verify_wordpress_password("wrong", wp_pass))


@override_settings(
    PASSWORD_HASHERS=[
        "legacy_migration.wordpress_hasher.WordPressPasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
)
class WordPressUserPasswordTests(SimpleTestCase):
    def test_check_password_on_imported_hash(self) -> None:
        from passlib.hash import phpass

        from legacy_migration.wordpress_hasher import wordpress_password_field_value

        encoded = wordpress_password_field_value(phpass.hash("staging-secret"))
        user = User(username="wp-hash-test", password=encoded)
        self.assertTrue(user.check_password("staging-secret"))
        self.assertFalse(user.check_password("nope"))

    def test_check_password_real_wp_bcrypt_import_format(self) -> None:
        from legacy_migration.wordpress_hasher import wordpress_password_field_value

        wp_pass = "$wp$2y$10$cVNgdHnqAIb3tfJswKY70O6K3FhowrIK9ObT1t9KHloGoN.0vZUea"
        user = User(
            username="wp-bcrypt-real",
            password=wordpress_password_field_value(wp_pass),
        )
        self.assertTrue(user.check_password("test23335231"))
        self.assertFalse(user.check_password("nope"))
