"""Vercel serverless WSGI entrypoint for FraudShield Django backend."""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path so config and apps can be imported
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_DIR = BACKEND_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from config.wsgi import application

# Vercel looks for 'app' attribute
app = application

