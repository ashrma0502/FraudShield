"""Test settings: fast in-memory SQLite database and isolated test environment."""

from .base import *

DEBUG = False
ALLOWED_HOSTS = ["*"]

# Use fast in-memory SQLite database for automated test suite so tests do not
# attempt to execute CREATE DATABASE on remote managed databases like Neon.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
