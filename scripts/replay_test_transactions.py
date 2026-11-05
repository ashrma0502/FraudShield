"""Replay held-out test transactions through the live simulation endpoint.

Evaluates live two-layer fraud screening predictions against known ground truth.
Supports both HTTP requests against a running server and direct Django APIClient.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay held-out test transactions through live fraud detection endpoint."
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000/api/v1/transactions/simulate/",
        help="Target simulation endpoint URL (default: http://localhost:8000/api/v1/transactions/simulate/)",
    )
    parser.add_argument(
        "--csv-path",
        default="notebooks/data/held_out_test_sample.csv",
        help="Path to held-out test CSV file with ground truth (default: notebooks/data/held_out_test_sample.csv)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of test transactions to replay (default: 50)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Use direct Django API client instead of HTTP network calls",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed row-by-row prediction comparison",
    )
    return parser.parse_args()


def setup_django_environment():
    """Configure Django settings for in-process client calls."""
    backend_dir = Path(__file__).resolve().parent.parent / "backend"
    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    import django

    django.setup()


def load_test_data(csv_path_str, batch_size):
    """Load held-out transactions with ground truth labels."""
    p = Path(csv_path_str)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p

    if not p.exists():
        fallback_path = Path(__file__).resolve().parent.parent / "notebooks/data/ieee_cis/train_transaction.csv"
        if fallback_path.exists():
            print("Held-out sample not found. Loading tail from %s …" % fallback_path.name)
            df_full = pd.read_csv(fallback_path, skiprows=range(1, 540000))
            fraud = df_full[df_full["isFraud"] == 1].head(batch_size // 2)
            legit = df_full[df_full["isFraud"] == 0].head(batch_size - len(fraud))
            return pd.concat([fraud, legit]).reset_index(drop=True)
        raise FileNotFoundError("Could not find test dataset at %s" % p)

    df = pd.read_csv(p)
    if len(df) > batch_size:
        # Balanced sampling of fraud and legit cases to evaluate both classes
        label_col = "isFraud" if "isFraud" in df.columns else "is_fraud"
        if label_col in df.columns:
            n_fraud = batch_size // 2
            n_legit = batch_size - n_fraud
            fraud_subset = df[df[label_col] == 1].head(n_fraud)
            legit_subset = df[df[label_col] == 0].head(n_legit)
            df = pd.concat([fraud_subset, legit_subset]).sample(frac=1.0, random_state=42).reset_index(drop=True)
        else:
            df = df.head(batch_size)

    return df


def row_to_payload(row):
    """Map tabular dataset row to simulation endpoint schema."""
    amt_col = "TransactionAmt" if "TransactionAmt" in row else ("amt" if "amt" in row else "amount")
    amount = max(round(float(row[amt_col]), 2), 0.01)

    card4 = str(row.get("card4", "visa")) if pd.notna(row.get("card4")) else "visa"
    card6 = str(row.get("card6", "credit")) if pd.notna(row.get("card6")) else "credit"
    product_cd = str(row.get("ProductCD", "W")) if pd.notna(row.get("ProductCD")) else "W"
    p_email = str(row.get("P_emaildomain", "gmail.com")) if pd.notna(row.get("P_emaildomain")) else "gmail.com"
    r_email = str(row.get("R_emaildomain", "gmail.com")) if pd.notna(row.get("R_emaildomain")) else "gmail.com"

    # Compute UTC timestamp from TransactionDT offset if available
    dt_val = row.get("TransactionDT")
    if pd.notna(dt_val):
        base_ts = 1577836800.0  # reference epoch
        submitted_at = datetime.fromtimestamp(base_ts + float(dt_val) % 86400, tz=UTC).isoformat()
    else:
        submitted_at = datetime.now(tz=UTC).isoformat()

    # Capture extra numerical and categorical features in snapshot
    snapshot = {}
    ignored_keys = {
        "TransactionID", "isFraud", "is_fraud", "TransactionDT", "TransactionAmt",
        "card4", "card6", "ProductCD", "P_emaildomain", "R_emaildomain",
    }
    for k, v in row.items():
        if k not in ignored_keys and pd.notna(v):
            try:
                snapshot[str(k)] = float(v)
            except (ValueError, TypeError):
                snapshot[str(k)] = str(v)

    card1_val = row.get("card1")
    if pd.notna(card1_val):
        customer_id = "card_%s" % int(card1_val)
    else:
        customer_id = "replay_%s" % row.get("TransactionID", "cust")

    return {
        "amount": amount,
        "submitted_at": submitted_at,
        "card4": card4.lower(),
        "card6": card6.lower(),
        "product_cd": product_cd,
        "p_emaildomain": p_email,
        "r_emaildomain": r_email,
        "customer_id": customer_id,
        "source": "replay",
        "feature_snapshot": snapshot,
    }


def send_http_request(url, payload):
    """Post JSON payload to endpoint over HTTP."""
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=10) as resp:
        duration_ms = (time.time() - t0) * 1000
        body = resp.read().decode("utf-8")
        return json.loads(body), duration_ms


def create_direct_client():
    """Create in-process DRF APIClient."""
    from rest_framework.test import APIClient

    return APIClient()


def send_direct_request(client, url_path, payload):
    """Post JSON payload directly through Django test client."""
    t0 = time.time()
    resp = client.post(url_path, payload, format="json")
    duration_ms = (time.time() - t0) * 1000
    if resp.status_code != 201:
        raise RuntimeError("Direct client request failed (%d): %s" % (resp.status_code, resp.data))
    return resp.data, duration_ms


def replay():
    args = parse_args()
    print("=" * 72)
    print("  FraudShield — Test Transaction Replay & Ground Truth Evaluation")
    print("=" * 72)
    print("Loading test data from %s …" % args.csv_path)

    df = load_test_data(args.csv_path, args.batch_size)
    label_col = "isFraud" if "isFraud" in df.columns else "is_fraud"
    total_samples = len(df)
    actual_frauds = int(df[label_col].sum())
    actual_legits = total_samples - actual_frauds

    print("Loaded %d test transactions (%d fraud, %d legitimate)." % (total_samples, actual_frauds, actual_legits))

    # Decide execution mode: HTTP vs direct Django client
    use_direct = args.direct
    direct_client = None

    if not use_direct:
        # Check if HTTP endpoint is reachable
        try:
            test_req = urllib.request.Request(args.endpoint, method="GET")
            with urllib.request.urlopen(test_req, timeout=2):
                print("Connected to live endpoint: %s" % args.endpoint)
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            print("Live HTTP server not detected at %s. Switching to direct Django client." % args.endpoint)
            use_direct = True

    if use_direct:
        setup_django_environment()
        direct_client = create_direct_client()
        endpoint_path = "/api/v1/transactions/simulate/"
        print("Using direct Django test client (path: %s)" % endpoint_path)

    results = []
    tp = fp = tn = fn = 0
    layer_counts = {"rules": 0, "model": 0, "both": 0, "none": 0}
    latencies = []

    print("\nReplaying %d transactions through fraud screening pipeline …" % total_samples)

    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        ground_truth = int(row[label_col])
        payload = row_to_payload(row)

        if use_direct:
            resp_data, lat_ms = send_direct_request(direct_client, endpoint_path, payload)
        else:
            resp_data, lat_ms = send_http_request(args.endpoint, payload)

        latencies.append(lat_ms)
        fraud_score = float(resp_data.get("fraud_score", 0.0))
        outcome = resp_data.get("outcome", "approved")
        status_val = resp_data.get("status", "approved")
        contributing_layer = resp_data.get("contributing_layer", "none")

        # Classify as positive if flagged or score exceeds threshold
        predicted_fraud = outcome in ["declined", "flagged_for_review"] or status_val in ["declined", "under_review"]
        predicted_label = 1 if predicted_fraud else 0

        layer_counts[contributing_layer] = layer_counts.get(contributing_layer, 0) + 1

        if predicted_label == 1 and ground_truth == 1:
            tp += 1
            verdict = "TP [Hit]"
        elif predicted_label == 1 and ground_truth == 0:
            fp += 1
            verdict = "FP [False Alarm]"
        elif predicted_label == 0 and ground_truth == 0:
            tn += 1
            verdict = "TN [Correct Clean]"
        else:
            fn += 1
            verdict = "FN [Miss]"

        results.append({
            "idx": idx,
            "amount": payload["amount"],
            "ground_truth": ground_truth,
            "predicted_fraud": predicted_label,
            "verdict": verdict,
            "score": fraud_score,
            "outcome": outcome,
            "layer": contributing_layer,
            "latency_ms": lat_ms,
        })

        if args.verbose or idx % 10 == 0 or idx == total_samples:
            print("  [%3d/%3d] Amt: $%8.2f | GT: %d | Pred: %d | Score: %.4f | Outcome: %-18s | %s"
                  % (idx, total_samples, payload["amount"], ground_truth, predicted_label, fraud_score, outcome, verdict))

    # Compute evaluation metrics
    accuracy = (tp + tn) / total_samples if total_samples > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    print("\n" + "=" * 72)
    print("  CONFUSION MATRIX & GROUND TRUTH ALIGNMENT REPORT")
    print("=" * 72)
    print("  Total Replayed Transactions: %d" % total_samples)
    print("  True Positives  (TP) : %3d  (Correctly flagged fraud)" % tp)
    print("  False Positives (FP) : %3d  (Legitimate flagged as fraud)" % fp)
    print("  True Negatives  (TN) : %3d  (Correctly approved legitimate)" % tn)
    print("  False Negatives (FN) : %3d  (Undetected fraud)" % fn)
    print("-" * 72)
    print("  Accuracy  : %6.2f%%" % (accuracy * 100))
    print("  Precision : %6.2f%%" % (precision * 100))
    print("  Recall    : %6.2f%%" % (recall * 100))
    print("  F1-Score  : %6.4f" % f1)
    print("  Avg Latency: %6.2f ms (min: %.1f ms, max: %.1f ms)" % (avg_lat, min(latencies), max(latencies)))
    print("-" * 72)
    print("  Screening Layer Breakdown:")
    print("    Flagged by ML Model only : %d" % layer_counts.get("model", 0))
    print("    Flagged by Rules only    : %d" % layer_counts.get("rules", 0))
    print("    Flagged by Both Layers   : %d" % layer_counts.get("both", 0))
    print("    Not Flagged (Approved)   : %d" % layer_counts.get("none", 0))
    print("=" * 72)


if __name__ == "__main__":
    replay()
