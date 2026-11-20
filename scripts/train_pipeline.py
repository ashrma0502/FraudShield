#!/usr/bin/env python3
"""Convenience runner alias for the FraudShield ML training pipeline."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(BACKEND_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ml_pipeline.train import main

if __name__ == "__main__":
    main()
