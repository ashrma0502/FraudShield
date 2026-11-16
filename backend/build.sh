#!/usr/bin/env bash
# Production and local build script for FraudShield backend
set -e

# Detect Python binary: prefer active virtualenv, or existing backend/venv, or system python3
if [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/python3" ]; then
  PYTHON="$VIRTUAL_ENV/bin/python3"
  PIP="$VIRTUAL_ENV/bin/pip"
elif [ -f "backend/venv/bin/python3" ]; then
  PYTHON="backend/venv/bin/python3"
  PIP="backend/venv/bin/pip"
elif [ -f "venv/bin/python3" ]; then
  PYTHON="venv/bin/python3"
  PIP="venv/bin/pip"
else
  PYTHON="python3"
  PIP="python3 -m pip"
fi

# Locate requirements.txt and manage.py whether run from repo root or backend/
REQ_FILE="requirements.txt"
if [ ! -f "$REQ_FILE" ] && [ -f "backend/requirements.txt" ]; then
  REQ_FILE="backend/requirements.txt"
fi

MANAGE_PY="manage.py"
if [ ! -f "$MANAGE_PY" ] && [ -f "backend/manage.py" ]; then
  MANAGE_PY="backend/manage.py"
fi

echo "==> Using Python: $($PYTHON --version) ($PYTHON)"
echo "==> Installing Python dependencies..."

PIP_FLAGS=""
if [ "$PYTHON" = "python3" ]; then
  if $PIP install --help 2>&1 | grep -q -- '--break-system-packages'; then
    PIP_FLAGS="--break-system-packages"
  fi
fi

$PIP install -r "$REQ_FILE" $PIP_FLAGS

echo "==> Collecting static assets..."
$PYTHON "$MANAGE_PY" collectstatic --no-input

echo "==> Running database migrations..."
if [ -n "$DATABASE_URL" ]; then
  $PYTHON "$MANAGE_PY" migrate --no-input
else
  echo "DATABASE_URL not set; skipping migrate during build phase."
fi

echo "==> Build completed successfully."
