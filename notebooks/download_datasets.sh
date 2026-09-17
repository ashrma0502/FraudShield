#!/usr/bin/env bash
# Download both fraud datasets using the Kaggle CLI (v2.x).
# Prerequisites:
#   ~/.kaggle/access_token  — contains just the API key string
#   (see README.md for setup instructions)
#
# Usage:  bash notebooks/download_datasets.sh
#         (run from the FraudShield project root)

set -euo pipefail

KAGGLE="./backend/venv/bin/kaggle"
DATA="./notebooks/data"

# IEEE-CIS: competitions download has no --unzip; unpack manually
echo "==> IEEE-CIS Fraud Detection (Kaggle competition)"
mkdir -p "$DATA/ieee_cis"
$KAGGLE competitions download -c ieee-fraud-detection -p "$DATA/ieee_cis"
for z in "$DATA/ieee_cis"/*.zip; do
    [ -f "$z" ] || continue
    unzip -o -q "$z" -d "$DATA/ieee_cis"
    rm -f "$z"
done

# Sparkov: datasets download supports --unzip natively
echo "==> Sparkov Simulated Credit Card Transactions"
mkdir -p "$DATA/sparkov"
$KAGGLE datasets download -d kartik2112/fraud-detection -p "$DATA/sparkov" --unzip

echo ""
echo "Download complete. CSV files:"
find "$DATA" -name "*.csv" | sort
