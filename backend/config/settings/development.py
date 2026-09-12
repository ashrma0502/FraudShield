# Development overrides — DEBUG on, all hosts allowed, console email.

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Uncomment to enable Django Debug Toolbar:
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
# INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CORS_ALLOW_ALL_ORIGINS = True
