import logging
import os
import time
import uuid
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from apps.transactions.models import Transaction

from .models import MLModel, PredictionLog, ThresholdConfig

logger = logging.getLogger(__name__)

_MODEL_CACHE = None

HIGH_AMOUNT_THRESHOLD = 5000.0
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_MAX_TXNS = 2


def check_model_compatibility(bundle, raise_exception=True):
    """Verify that the loaded model bundle is compatible with current runtime dependencies."""
    if not bundle or not isinstance(bundle, dict):
        return True

    expected_sklearn = bundle.get("sklearn_version")
    if expected_sklearn:
        import sklearn

        current_sklearn = sklearn.__version__
        exp_parts = expected_sklearn.split(".")[:2]
        curr_parts = current_sklearn.split(".")[:2]
        if exp_parts != curr_parts:
            msg = (
                "scikit-learn version mismatch: model was serialized with %s, "
                "but runtime is %s." % (expected_sklearn, current_sklearn)
            )
            if raise_exception:
                raise RuntimeError(msg)
            logger.error(msg)
            return False

    return True


def get_model_bundle():
    """Load and cache the trained ML model bundle for real-time inference."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    active_entry = MLModel.objects.filter(is_active=True).first()
    if active_entry and active_entry.model_file and os.path.exists(active_entry.model_file.path):
        bundle = joblib.load(active_entry.model_file.path)
        check_model_compatibility(bundle, raise_exception=True)
        _MODEL_CACHE = {
            "model": bundle.get("model") if isinstance(bundle, dict) else bundle,
            "preprocessor": bundle.get("preprocessor") if isinstance(bundle, dict) else None,
            "name": active_entry.name,
            "version": active_entry.version,
            "entry": active_entry,
            "sklearn_version": bundle.get("sklearn_version") if isinstance(bundle, dict) else None,
        }
        return _MODEL_CACHE

    model_path = getattr(settings, "ML_MODEL_PATH", None)
    search_paths = [
        Path(model_path) if model_path else None,
        settings.BASE_DIR / "ml_models" / "ieee_cis_rf.joblib",
        settings.BASE_DIR.parent / "notebooks" / "outputs" / "models" / "ieee_cis_rf.joblib",
    ]

    for p in search_paths:
        if p and p.exists():
            bundle = joblib.load(str(p))
            check_model_compatibility(bundle, raise_exception=True)
            model_obj = bundle.get("model") if isinstance(bundle, dict) else bundle
            preprocessor_obj = bundle.get("preprocessor") if isinstance(bundle, dict) else None
            _MODEL_CACHE = {
                "model": model_obj,
                "preprocessor": preprocessor_obj,
                "name": "IEEE-CIS Random Forest",
                "version": bundle.get("version", "1.0.0") if isinstance(bundle, dict) else "1.0.0",
                "entry": active_entry,
                "sklearn_version": bundle.get("sklearn_version") if isinstance(bundle, dict) else None,
            }
            return _MODEL_CACHE

    return None


def evaluate_rules(amount, customer_id=None, submitted_at=None):
    """Run lightweight rule pre-filters before invoking ML model."""
    triggered_rules = []
    details = {}
    rule_score = 0.0

    submitted_at = submitted_at or timezone.now()
    amount_float = float(amount)

    if amount_float >= HIGH_AMOUNT_THRESHOLD:
        triggered_rules.append("high_amount")
        details["high_amount"] = {
            "amount": amount_float,
            "threshold": HIGH_AMOUNT_THRESHOLD,
        }
        rule_score = max(rule_score, 0.95)

    if customer_id:
        window_start = submitted_at - timedelta(minutes=VELOCITY_WINDOW_MINUTES)
        recent_txns = Transaction.objects.filter(
            customer_id=customer_id,
            submitted_at__gte=window_start,
            submitted_at__lte=submitted_at,
        ).exclude(status=Transaction.Status.DECLINED)
        recent_count = recent_txns.count()

        if recent_count >= VELOCITY_MAX_TXNS:
            triggered_rules.append("velocity_limit")
            details["velocity_limit"] = {
                "recent_count": recent_count,
                "threshold": VELOCITY_MAX_TXNS,
                "window_minutes": VELOCITY_WINDOW_MINUTES,
            }
            rule_score = max(rule_score, 0.95)

    rule_flagged = len(triggered_rules) > 0
    return rule_flagged, rule_score, triggered_rules, details


def predict_model(data):
    """Run transaction through the trained classifier for probabilistic scoring."""
    bundle = get_model_bundle()
    if not bundle or not bundle.get("model"):
        amt = float(data.get("amount", 0.0))
        fallback_score = min(0.99, max(0.05, amt / 10000.0))
        return fallback_score, fallback_score >= 0.50, "Fallback Heuristic", "0.1.0", 0.50

    model = bundle["model"]
    preprocessor = bundle.get("preprocessor")
    model_name = bundle.get("name", "IEEE-CIS Random Forest")
    model_version = bundle.get("version", "1.0.0")

    amt = float(data.get("amount", 0.0))
    submitted_at = data.get("submitted_at") or timezone.now()
    txn_dt = submitted_at.timestamp() if hasattr(submitted_at, "timestamp") else time.time()

    row = {
        "TransactionAmt": amt,
        "TransactionDT": txn_dt,
        "ProductCD": data.get("product_cd", "W"),
        "card4": data.get("card4", "visa"),
        "card6": data.get("card6", "credit"),
        "P_emaildomain": data.get("p_emaildomain", "gmail.com"),
        "R_emaildomain": data.get("r_emaildomain", "gmail.com"),
    }

    # Overlay any extra domain features supplied in feature_snapshot
    snapshot = data.get("feature_snapshot") or {}
    if isinstance(snapshot, dict):
        for k, v in snapshot.items():
            if k not in row:
                row[k] = v

    df_single = pd.DataFrame([row])

    if preprocessor and hasattr(preprocessor, "transform"):
        X = preprocessor.transform(df_single)
    else:
        X = [[amt]]

    if hasattr(model, "predict_proba"):
        model_score = float(model.predict_proba(X)[0][1])
    else:
        model_score = float(model.predict(X)[0])

    threshold_cfg = ThresholdConfig.objects.first()
    flag_threshold = threshold_cfg.flag_threshold if threshold_cfg else 0.50
    model_flagged = model_score >= flag_threshold

    return model_score, model_flagged, model_name, model_version, flag_threshold


def screen_transaction(data, customer=None):
    """Two-layer screening pipeline: lightweight rule pre-filter followed by ML model."""
    t0 = time.time()

    txn_id = data.get("transaction_id") or uuid.uuid4()
    amount = float(data.get("amount", 0.0))
    submitted_at = data.get("submitted_at") or timezone.now()
    customer_id = data.get("customer_id") or (customer.id if customer else None)

    rule_flagged, rule_score, triggered_rules, rule_details = evaluate_rules(
        amount=amount,
        customer_id=customer_id,
        submitted_at=submitted_at,
    )

    model_score, model_flagged, model_name, model_version, flag_threshold = predict_model(data)

    if rule_flagged and model_flagged:
        contributing_layer = "both"
        flagged_by = "both"
        combined_score = max(rule_score, model_score)
    elif rule_flagged and not model_flagged:
        contributing_layer = "rules"
        flagged_by = "rule"
        combined_score = max(0.92, model_score)
    elif not rule_flagged and model_flagged:
        contributing_layer = "model"
        flagged_by = "model"
        combined_score = model_score
    else:
        contributing_layer = "none"
        flagged_by = "none"
        combined_score = model_score

    combined_score = round(combined_score, 4)
    is_fraud = (contributing_layer != "none") or (combined_score >= flag_threshold)
    latency_ms = max(1, int((time.time() - t0) * 1000))

    bundle = get_model_bundle()
    active_entry = bundle.get("entry") if bundle else None

    try:
        PredictionLog.objects.create(
            ml_model=active_entry,
            transaction_id=txn_id,
            input_features={
                "amount": amount,
                "customer_id": str(customer_id) if customer_id else None,
                "submitted_at": str(submitted_at),
                "contributing_layer": contributing_layer,
                "triggered_rules": list(triggered_rules),
                "model_score": round(model_score, 4),
            },
            fraud_score=combined_score,
            is_fraud=is_fraud,
            latency_ms=latency_ms,
        )
    except (DatabaseError, ValueError) as err:
        logger.warning("Audit prediction log record failed: %s", err)

    return {
        "transaction_id": str(txn_id),
        "fraud_score": combined_score,
        "combined_score": combined_score,
        "is_fraud": is_fraud,
        "flagged": contributing_layer != "none",
        "flagged_by": flagged_by,
        "contributing_layer": contributing_layer,
        "rule_flagged": rule_flagged,
        "model_flagged": model_flagged,
        "triggered_rules": triggered_rules,
        "layers": {
            "rules": {
                "flagged": rule_flagged,
                "score": round(rule_score, 4),
                "triggered_rules": triggered_rules,
                "details": rule_details,
            },
            "model": {
                "flagged": model_flagged,
                "score": round(model_score, 4),
                "threshold": flag_threshold,
                "model_name": model_name,
                "model_version": model_version,
            },
        },
        "latency_ms": latency_ms,
    }
