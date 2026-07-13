from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _csv_env(name: str, default: str = "") -> list[str]:
    return [value.strip().rstrip("/") for value in os.environ.get(name, default).split(",") if value.strip()]


def _domain_env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default).strip()
    return value.removeprefix("https://").removeprefix("http://").strip("/")


def _domain_env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default).strip()
    return value.removeprefix("https://").removeprefix("http://").strip("/")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-unsafe-secret-key"
    else:
        raise ValueError("DJANGO_SECRET_KEY is required")

if not DEBUG and SECRET_KEY == "dev-unsafe-secret-key":
    raise ValueError("Refusing to run with an unsafe DJANGO_SECRET_KEY in production")

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "feeds.apps.FeedsConfig",
    "my_feed.apps.MyFeedConfig",
    "communities.apps.CommunitiesConfig",
    "users.apps.UsersConfig",
    "notifications.apps.NotificationsConfig",
    "moderator.apps.ModeratorConfig",
    "post.apps.PostConfig",
    "ratings.apps.RatingsConfig",
    "editor.apps.EditorConfig",
    "telegram_integration.apps.TelegramIntegrationConfig",
    "special_projects.apps.SpecialProjectsConfig",
    "landing_pages.apps.LandingPagesConfig",
    "legacy_migration.apps.LegacyMigrationConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "rabotaem_backend.security.UnsafeOriginProtectionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "rabotaem_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "rabotaem_backend.wsgi.application"
ASGI_APPLICATION = "rabotaem_backend.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "rabotaem"),
        "USER": os.environ.get("POSTGRES_USER", "rabotaem"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "rabotaem"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    },
    "romawho": {
        "ENGINE": "legacy_migration.db_backends.mysql57",
        "NAME": os.environ.get("MYSQL_ROMAWHO_DB", "romawho_posl1"),
        "USER": os.environ.get("MYSQL_ROMAWHO_USER", "romawho_posl1"),
        "PASSWORD": os.environ.get("MYSQL_ROMAWHO_PASSWORD", ""),
        "HOST": os.environ.get("MYSQL_ROMAWHO_HOST", "localhost"),
        "PORT": os.environ.get("MYSQL_ROMAWHO_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    },
}

DATABASE_ROUTERS = ["legacy_migration.db_router.RomawhoRouter"]

CACHES = {
    "default": {
        "BACKEND": os.environ.get(
            "DJANGO_CACHE_BACKEND",
            "django.core.cache.backends.locmem.LocMemCache",
        ),
        "LOCATION": os.environ.get("DJANGO_CACHE_LOCATION", "rabotaem-default"),
    }
}

PUBLIC_API_CACHE_SECONDS = int(os.environ.get("PUBLIC_API_CACHE_SECONDS", "60"))
PUBLIC_API_STALE_SECONDS = int(os.environ.get("PUBLIC_API_STALE_SECONDS", "300"))
SNAPSHOT_FRONTEND_URL = os.environ.get("SNAPSHOT_FRONTEND_URL", "http://frontend:3000")
PUBLIC_HTML_SNAPSHOT_ROOT = os.environ.get("PUBLIC_HTML_SNAPSHOT_ROOT", "")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

PASSWORD_HASHERS = [
    "legacy_migration.wordpress_hasher.WordPressPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "ru-ru"
LANGUAGES = [
    ("ru", "Русский"),
    ("en", "English"),
    ("es", "Español"),
    ("pt", "Português"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("tr", "Türkçe"),
    ("id", "Bahasa Indonesia"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_LEGACY_URL = os.environ.get("MEDIA_LEGACY_URL", "/media/")
MEDIA_PUBLIC_URL_MODE = os.environ.get("MEDIA_PUBLIC_URL_MODE", "legacy").strip().lower()
MEDIA_PUBLIC_BASE_URL = os.environ.get("MEDIA_PUBLIC_BASE_URL", "").strip()
MEDIA_S3_PUBLIC_BASE_URL = os.environ.get("MEDIA_S3_PUBLIC_BASE_URL", "").strip()

MEDIA_STORAGE_BACKEND = os.environ.get("MEDIA_STORAGE_BACKEND", "local").strip().lower()
if MEDIA_STORAGE_BACKEND in {"s3", "beget_s3"}:
    from botocore.config import Config

    INSTALLED_APPS.append("storages")

    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ru1")
    AWS_S3_CUSTOM_DOMAIN = _domain_env("AWS_S3_CUSTOM_DOMAIN")
    AWS_S3_ADDRESSING_STYLE = os.environ.get("AWS_S3_ADDRESSING_STYLE", "path")
    AWS_S3_SIGNATURE_VERSION = os.environ.get("AWS_S3_SIGNATURE_VERSION", "s3v4")
    AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", "0") == "1"
    AWS_DEFAULT_ACL = os.environ.get("AWS_DEFAULT_ACL", "public-read") or None
    AWS_S3_FILE_OVERWRITE = os.environ.get("AWS_S3_FILE_OVERWRITE", "0") == "1"
    AWS_LOCATION = os.environ.get("AWS_LOCATION", "")
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": os.environ.get(
            "AWS_S3_CACHE_CONTROL",
            "public, max-age=31536000, immutable",
        )
    }
    AWS_S3_CLIENT_CONFIG = Config(
        signature_version=AWS_S3_SIGNATURE_VERSION,
        request_checksum_calculation=os.environ.get(
            "AWS_REQUEST_CHECKSUM_CALCULATION",
            "when_required",
        ),
        response_checksum_validation=os.environ.get(
            "AWS_RESPONSE_CHECKSUM_VALIDATION",
            "when_required",
        ),
        s3={
            "addressing_style": AWS_S3_ADDRESSING_STYLE,
        },
    )

    missing_s3_settings = [
        name
        for name, value in {
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
            "AWS_STORAGE_BUCKET_NAME": AWS_STORAGE_BUCKET_NAME,
            "AWS_S3_ENDPOINT_URL": AWS_S3_ENDPOINT_URL,
        }.items()
        if not value
    ]
    if missing_s3_settings:
        raise ValueError("MEDIA_STORAGE_BACKEND=s3 requires " + ", ".join(missing_s3_settings))

    STORAGES = {
        "default": {
            "BACKEND": "rabotaem_backend.storage.S3MediaStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

USER_UPLOAD_MAX_BYTES = int(os.environ.get("USER_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", str(max(USER_UPLOAD_MAX_BYTES + 2 * 1024 * 1024, 12 * 1024 * 1024)))
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("FILE_UPLOAD_MAX_MEMORY_SIZE", str(max(USER_UPLOAD_MAX_BYTES, 10 * 1024 * 1024)))
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_USE_POLLING = os.environ.get("TELEGRAM_USE_POLLING", "0") == "1"
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
TELEGRAM_OIDC_CLIENT_ID = os.environ.get("TELEGRAM_OIDC_CLIENT_ID", "")
if not TELEGRAM_OIDC_CLIENT_ID and TELEGRAM_BOT_TOKEN.split(":", 1)[0].isdigit():
    TELEGRAM_OIDC_CLIENT_ID = TELEGRAM_BOT_TOKEN.split(":", 1)[0]
TELEGRAM_OIDC_ISSUER = os.environ.get("TELEGRAM_OIDC_ISSUER", "https://oauth.telegram.org")
TELEGRAM_OIDC_JWKS_URL = os.environ.get(
    "TELEGRAM_OIDC_JWKS_URL",
    "https://oauth.telegram.org/.well-known/jwks.json",
)
TELEGRAM_AUTH_ALLOWED_ORIGINS = _csv_env(
    "TELEGRAM_AUTH_ALLOWED_ORIGINS",
    "https://app1299099924-login.tg.dev",
)
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
APPLE_OAUTH_CLIENT_ID = os.environ.get("APPLE_OAUTH_CLIENT_ID", "").strip()
APPLE_OAUTH_CLIENT_IDS = _csv_env("APPLE_OAUTH_CLIENT_IDS")
if APPLE_OAUTH_CLIENT_ID and APPLE_OAUTH_CLIENT_ID not in APPLE_OAUTH_CLIENT_IDS:
    APPLE_OAUTH_CLIENT_IDS.insert(0, APPLE_OAUTH_CLIENT_ID)
APPLE_OAUTH_TEAM_ID = os.environ.get("APPLE_OAUTH_TEAM_ID", "").strip()
APPLE_OAUTH_KEY_ID = os.environ.get("APPLE_OAUTH_KEY_ID", "").strip()
APPLE_OAUTH_PRIVATE_KEY = os.environ.get("APPLE_OAUTH_PRIVATE_KEY", "").strip()
APPLE_OAUTH_PRIVATE_KEY_FILE = os.environ.get("APPLE_OAUTH_PRIVATE_KEY_FILE", "").strip()
APPLE_OAUTH_REDIRECT_URI = os.environ.get("APPLE_OAUTH_REDIRECT_URI", "").strip()
APPLE_OAUTH_ISSUER = os.environ.get("APPLE_OAUTH_ISSUER", "https://appleid.apple.com").strip()
APPLE_OAUTH_JWKS_URL = os.environ.get(
    "APPLE_OAUTH_JWKS_URL",
    "https://appleid.apple.com/auth/keys",
).strip()
APPLE_OAUTH_TOKEN_URL = os.environ.get(
    "APPLE_OAUTH_TOKEN_URL",
    "https://appleid.apple.com/auth/token",
).strip()
AUTH_COUNTRY_LOOKUP_URL = os.environ.get(
    "AUTH_COUNTRY_LOOKUP_URL",
    "https://api.country.is/{ip}",
).strip()
AUTH_COUNTRY_LOOKUP_TIMEOUT_SECONDS = float(
    os.environ.get("AUTH_COUNTRY_LOOKUP_TIMEOUT_SECONDS", "2")
)
AUTH_COUNTRY_CACHE_SECONDS = int(os.environ.get("AUTH_COUNTRY_CACHE_SECONDS", str(24 * 60 * 60)))
AUTH_COUNTRY_FAILURE_CACHE_SECONDS = int(
    os.environ.get("AUTH_COUNTRY_FAILURE_CACHE_SECONDS", str(5 * 60))
)
AUTH_LOCAL_COUNTRY_CODE = os.environ.get("AUTH_LOCAL_COUNTRY_CODE", "").strip().upper()
PUSH_FCM_PROJECT_ID = os.environ.get("PUSH_FCM_PROJECT_ID", "")
PUSH_FCM_SERVICE_ACCOUNT_JSON = os.environ.get("PUSH_FCM_SERVICE_ACCOUNT_JSON", "")
PUSH_FCM_SERVICE_ACCOUNT_FILE = os.environ.get("PUSH_FCM_SERVICE_ACCOUNT_FILE", "")
APPLE_APNS_ENV = os.environ.get("APPLE_APNS_ENV", "").strip().lower()
PUSH_APNS_KEY_ID = os.environ.get("APPLE_APNS_KEY_ID", os.environ.get("PUSH_APNS_KEY_ID", ""))
PUSH_APNS_TEAM_ID = os.environ.get("APPLE_TEAM_ID", os.environ.get("PUSH_APNS_TEAM_ID", ""))
PUSH_APNS_TOPIC = os.environ.get("APPLE_APNS_TOPIC", os.environ.get("PUSH_APNS_TOPIC", ""))
PUSH_APNS_AUTH_KEY = os.environ.get("PUSH_APNS_AUTH_KEY", "")
PUSH_APNS_AUTH_KEY_FILE = os.environ.get("PUSH_APNS_AUTH_KEY_FILE", "")
PUSH_APNS_USE_SANDBOX = (
    APPLE_APNS_ENV == "sandbox"
    if APPLE_APNS_ENV
    else os.environ.get("PUSH_APNS_USE_SANDBOX", "0") == "1"
)
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:5173")
CONTENT_TRANSLATION_PROVIDER = os.environ.get("CONTENT_TRANSLATION_PROVIDER", "openrouter").strip().lower()
CONTENT_TRANSLATION_MODEL = os.environ.get("CONTENT_TRANSLATION_MODEL", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.environ.get(
    "OPENROUTER_API_URL",
    "https://openrouter.ai/api/v1/chat/completions",
)
OPENROUTER_TRANSLATION_MODEL = os.environ.get(
    "OPENROUTER_TRANSLATION_MODEL",
    "deepseek/deepseek-v4-flash",
)
OPENROUTER_APP_TITLE = os.environ.get("OPENROUTER_APP_TITLE", "Tambur")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.environ.get(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/chat/completions",
)
DEEPSEEK_TRANSLATION_MODEL = os.environ.get(
    "DEEPSEEK_TRANSLATION_MODEL",
    CONTENT_TRANSLATION_MODEL or "deepseek-v4-flash",
)
WHEREFILMED_IMPORT_TOKEN = os.environ.get(
    "WHEREFILMED_IMPORT_TOKEN",
    os.environ.get("TAMBUR_EXPORT_TOKEN", ""),
)
WHEREFILMED_IMPORT_IMAGE_MAX_BYTES = int(os.environ.get("WHEREFILMED_IMPORT_IMAGE_MAX_BYTES", str(15 * 1024 * 1024)))
ALLOW_PASSWORD_REGISTRATION = os.environ.get("ALLOW_PASSWORD_REGISTRATION", "0") == "1"
SITE_AUTH_TOKEN_MAX_AGE_SECONDS = int(os.environ.get("SITE_AUTH_TOKEN_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30)))
SITE_AUTH_COOKIE_NAME = os.environ.get("SITE_AUTH_COOKIE_NAME", "comuna_site_token")
SITE_AUTH_COOKIE_DOMAIN = os.environ.get("SITE_AUTH_COOKIE_DOMAIN", "")
SITE_AUTH_COOKIE_SAMESITE = os.environ.get("SITE_AUTH_COOKIE_SAMESITE", "Lax")
SITE_AUTH_COOKIE_SECURE = (
    os.environ.get(
        "SITE_AUTH_COOKIE_SECURE",
        "0" if DEBUG else "1",
    )
    == "1"
)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "0") == "1"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0" if DEBUG else "1") == "1"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "0" if DEBUG else "1") == "1"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Lax")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "SAMEORIGIN")
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.environ.get(
    "SECURE_CROSS_ORIGIN_OPENER_POLICY",
    "same-origin-allow-popups",
)
SECURE_REFERRER_POLICY = os.environ.get("SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0") == "1"
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "0") == "1"
VK_APP_ID = os.environ.get("VK_APP_ID", os.environ.get("PUBLIC_VK_APP_ID", ""))
VK_OIDC_ISSUER = os.environ.get("VK_OIDC_ISSUER", "")
VK_OIDC_JWKS_URL = os.environ.get("VK_OIDC_JWKS_URL", "")

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "0") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "webmaster@localhost",
)

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = list(
    dict.fromkeys(
        [
            *_csv_env("CORS_ALLOWED_ORIGINS"),
            *TELEGRAM_AUTH_ALLOWED_ORIGINS,
        ]
    )
)

CSRF_TRUSTED_ORIGINS = _csv_env("CSRF_TRUSTED_ORIGINS")
