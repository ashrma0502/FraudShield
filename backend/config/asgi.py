# ASGI entry point for async servers (e.g. daphne, uvicorn).
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
application = get_asgi_application()
