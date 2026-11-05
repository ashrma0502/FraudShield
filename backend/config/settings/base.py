"""Base settings shared across development and production environments."""

import os
import sys
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

ML_MODEL_PATH = Path(config("ML_MODEL_PATH", default=str(BASE_DIR / "ml_models" / "ieee_cis_rf.joblib")))

SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1,.vercel.app", cast=Csv())

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.transactions",
    "apps.ml",
    "apps.analytics",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

is_testing = (
    "test" in sys.argv
    or "pytest" in sys.modules
    or any("pytest" in a for a in sys.argv)
    or "PYTEST_CURRENT_TEST" in os.environ
)

db_url = config("DATABASE_URL", default=None)
is_placeholder_url = bool(
    db_url
    and any(
        p in db_url
        for p in ["YOUR_PASSWORD", "placeholder", "dummy", "replace-with-password"]
    )
)

if is_testing and not config("FORCE_REMOTE_TEST_DB", default=False, cast=bool):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
elif db_url and not is_placeholder_url:
    from urllib.parse import parse_qs, unquote, urlparse

    parsed_url = urlparse(db_url)
    qs = parse_qs(parsed_url.query)

    db_engine = "django.db.backends.postgresql"
    if parsed_url.scheme in ["sqlite", "sqlite3"]:
        db_engine = "django.db.backends.sqlite3"

    db_cfg = {
        "ENGINE": db_engine,
        "NAME": parsed_url.path.lstrip("/"),
        "USER": unquote(parsed_url.username or ""),
        "PASSWORD": unquote(parsed_url.password or ""),
        "HOST": parsed_url.hostname or "",
        "PORT": str(parsed_url.port or "5432"),
        "CONN_MAX_AGE": config("CONN_MAX_AGE", default=0, cast=int),
    }

    # Neon and cloud postgres require sslmode=require
    ssl_mode = qs.get("sslmode", [None])[0]
    if ssl_mode:
        db_cfg["OPTIONS"] = {"sslmode": ssl_mode}

    DATABASES = {"default": db_cfg}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="fraudshield"),
            "USER": config("DB_USER", default="fraudshield_user"),
            "PASSWORD": config("DB_PASSWORD", default="fraudshield_pass"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": config("CONN_MAX_AGE", default=0, cast=int),
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

SPECTACULAR_SETTINGS = {
    "TITLE": "FraudShield API",
    "DESCRIPTION": "Real-time fraud detection platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="alerts@fraudshield.internal")
DEFAULT_ANALYST_EMAIL = config("DEFAULT_ANALYST_EMAIL", default="analyst@example.com")
