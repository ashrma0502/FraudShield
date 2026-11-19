#!/usr/bin/env bash
# Production and local build script for FraudShield backend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python binary: prefer active virtualenv, local backend/venv, or system python3
if [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/python3" ]; then
  PYTHON="$VIRTUAL_ENV/bin/python3"
  PIP="$VIRTUAL_ENV/bin/pip"
elif [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
  PYTHON="$SCRIPT_DIR/venv/bin/python3"
  PIP="$SCRIPT_DIR/venv/bin/pip"
elif [ -f "$SCRIPT_DIR/../venv/bin/python3" ]; then
  PYTHON="$SCRIPT_DIR/../venv/bin/python3"
  PIP="$SCRIPT_DIR/../venv/bin/pip"
else
  PYTHON="python3"
  PIP="python3 -m pip"
fi

REQ_FILE="$SCRIPT_DIR/requirements.txt"
MANAGE_PY="$SCRIPT_DIR/manage.py"

echo "==> Using Python: $($PYTHON --version) ($PYTHON)"
echo "==> Installing Python dependencies..."

PIP_FLAGS=""
if [ -z "$VIRTUAL_ENV" ] && [ "$PYTHON" = "python3" ]; then
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
