import logging
from datetime import timedelta

from django.db import DatabaseError
from django.db.models import Avg, Count, Max, Q, Sum
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from apps.accounts.permissions import IsAnalystOrAdmin
from apps.ml.models import ThresholdConfig
from apps.transactions.models import Transaction

from .models import DailyStats
from .serializers import DailyStatsSerializer


class DailyStatsListView(generics.ListAPIView):
    """Paginated list of pre-aggregated daily stats (analyst/admin only)."""
    queryset           = DailyStats.objects.all()
    serializer_class   = DailyStatsSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsAnalystOrAdmin])
def dashboard_summary(request):
    """Aggregated transaction summary for the past 30 days (analyst/admin only)."""
    since = timezone.now() - timedelta(days=30)
    qs    = Transaction.objects.filter(submitted_at__gte=since)

    agg = qs.aggregate(
        total           = Count("id"),
        total_amount    = Sum("amount"),
        avg_fraud_score = Avg("fraud_score"),
        max_fraud_score = Max("fraud_score"),
        flagged         = Count("id", filter=Q(status="under_review")),
        blocked         = Count("id", filter=Q(status="declined")),
    )

    return Response({
        "period_days":        30,
        "total_transactions": agg["total"],
        "total_amount":       str(agg["total_amount"] or 0),
        "avg_fraud_score":    round(agg["avg_fraud_score"] or 0, 4),
        "max_fraud_score":    round(agg["max_fraud_score"] or 0, 4),
        "under_review_count": agg["flagged"],
        "declined_count":     agg["blocked"],
    })


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsAnalystOrAdmin])
def model_performance_analytics(request):
    """Compute precision, recall, F1, confusion matrix, and time-series trends."""
    days_param = request.query_params.get("days", "30")
    filter_mode = request.query_params.get("filter", "all")
    threshold_param = request.query_params.get("threshold")

    threshold_cfg = ThresholdConfig.objects.first()
    flag_threshold = threshold_cfg.flag_threshold if threshold_cfg else 0.50
    if threshold_param:
        try:
            flag_threshold = float(threshold_param)
        except ValueError:
            pass

    qs = Transaction.objects.select_related("analyst_decision").all()

    if days_param and days_param != "all":
        try:
            days_int = int(days_param)
            since = timezone.now() - timedelta(days=days_int)
            qs = qs.filter(submitted_at__gte=since)
        except ValueError:
            days_int = 30
            since = timezone.now() - timedelta(days=30)
            qs = qs.filter(submitted_at__gte=since)
    else:
        days_int = None

    if filter_mode == "analyst_only":
        qs = qs.filter(analyst_decision__isnull=False)

    tp = fp = tn = fn = 0
    analyst_tp = analyst_fp = analyst_tn = analyst_fn = 0
    analyst_labeled_count = 0
    pending_count = 0

    daily_buckets = {}

    for t in qs.iterator():
        has_decision = hasattr(t, "analyst_decision") and t.analyst_decision is not None

        if has_decision:
            analyst_labeled_count += 1
            ground_truth = 1 if t.analyst_decision.decision == "declined" else 0
            is_labeled = True
        elif t.status == Transaction.Status.DECLINED:
            ground_truth = 1
            is_labeled = True
        elif t.status == Transaction.Status.APPROVED:
            ground_truth = 0
            is_labeled = True
        else:
            pending_count += 1
            is_labeled = False

        if not is_labeled:
            continue

        score = float(t.fraud_score) if t.fraud_score is not None else 0.0
        flagged = t.flagged_by in [
            Transaction.FlaggedBy.RULE,
            Transaction.FlaggedBy.MODEL,
            Transaction.FlaggedBy.BOTH,
        ]
        predicted = 1 if (flagged or score >= flag_threshold) else 0

        if predicted == 1 and ground_truth == 1:
            tp += 1
        elif predicted == 1 and ground_truth == 0:
            fp += 1
        elif predicted == 0 and ground_truth == 0:
            tn += 1
        else:
            fn += 1

        if has_decision:
            if predicted == 1 and ground_truth == 1:
                analyst_tp += 1
            elif predicted == 1 and ground_truth == 0:
                analyst_fp += 1
            elif predicted == 0 and ground_truth == 0:
                analyst_tn += 1
            else:
                analyst_fn += 1

        date_key = t.submitted_at.strftime("%Y-%m-%d") if t.submitted_at else timezone.now().strftime("%Y-%m-%d")
        b = daily_buckets.setdefault(date_key, {
            "date": date_key,
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
            "total": 0,
            "analyst_count": 0,
        })
        b["total"] += 1
        if has_decision:
            b["analyst_count"] += 1

        if predicted == 1 and ground_truth == 1:
            b["tp"] += 1
        elif predicted == 1 and ground_truth == 0:
            b["fp"] += 1
        elif predicted == 0 and ground_truth == 0:
            b["tn"] += 1
        else:
            b["fn"] += 1

    total_labeled = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total_labeled if total_labeled > 0 else 0.0

    analyst_total = analyst_tp + analyst_fp + analyst_tn + analyst_fn
    analyst_p = analyst_tp / (analyst_tp + analyst_fp) if (analyst_tp + analyst_fp) > 0 else 0.0
    analyst_r = analyst_tp / (analyst_tp + analyst_fn) if (analyst_tp + analyst_fn) > 0 else 0.0
    analyst_f1 = (
        2 * (analyst_p * analyst_r) / (analyst_p + analyst_r)
        if (analyst_p + analyst_r) > 0
        else 0.0
    )

    # Compute model version breakdown based on analyst-reviewed transactions only
    version_buckets = {}
    analyst_txns_qs = qs.filter(analyst_decision__isnull=False).select_related("analyst_decision")
    for t in analyst_txns_qs.iterator():
        mv = t.model_version or "1.0.0"
        gt = 1 if t.analyst_decision.decision.lower() in ["declined", "decline", "fraud"] else 0
        sc = float(t.fraud_score) if t.fraud_score is not None else 0.0
        fl = t.flagged_by in [
            Transaction.FlaggedBy.RULE,
            Transaction.FlaggedBy.MODEL,
            Transaction.FlaggedBy.BOTH,
        ]
        pred = 1 if (fl or sc >= flag_threshold) else 0

        vb = version_buckets.setdefault(mv, {
            "model_version": mv,
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
            "total": 0,
        })
        vb["total"] += 1
        if pred == 1 and gt == 1:
            vb["tp"] += 1
        elif pred == 1 and gt == 0:
            vb["fp"] += 1
        elif pred == 0 and gt == 0:
            vb["tn"] += 1
        else:
            vb["fn"] += 1

    # Include known registered ML models in breakdown
    try:
        from apps.ml.models import MLModel

        for m_obj in MLModel.objects.all():
            if m_obj.version not in version_buckets:
                version_buckets[m_obj.version] = {
                    "model_version": m_obj.version,
                    "tp": 0,
                    "fp": 0,
                    "tn": 0,
                    "fn": 0,
                    "total": 0,
                }
    except DatabaseError as exc:
        logger.warning("Could not query MLModel versions: %s", exc)

    by_model_version = []
    for mv in sorted(version_buckets.keys()):
        vb = version_buckets[mv]
        v_tp, v_fp, v_tn, v_fn = vb["tp"], vb["fp"], vb["tn"], vb["fn"]
        v_prec = v_tp / (v_tp + v_fp) if (v_tp + v_fp) > 0 else 0.0
        v_rec = v_tp / (v_tp + v_fn) if (v_tp + v_fn) > 0 else 0.0
        v_f1 = (
            2 * (v_prec * v_rec) / (v_prec + v_rec)
            if (v_prec + v_rec) > 0
            else 0.0
        )
        v_acc = (v_tp + v_tn) / vb["total"] if vb["total"] > 0 else 0.0

        by_model_version.append({
            "model_version": mv,
            "total_reviewed": vb["total"],
            "metrics": {
                "precision": round(v_prec, 4),
                "recall": round(v_rec, 4),
                "f1_score": round(v_f1, 4),
                "accuracy": round(v_acc, 4),
            },
            "confusion_matrix": {
                "tp": v_tp,
                "fp": v_fp,
                "tn": v_tn,
                "fn": v_fn,
            },
        })

    trend = []
    cum_tp = cum_fp = cum_tn = cum_fn = 0
    for date_key in sorted(daily_buckets.keys()):
        b = daily_buckets[date_key]
        d_tp, d_fp, d_tn, d_fn = b["tp"], b["fp"], b["tn"], b["fn"]
        d_tot = b["total"]

        cum_tp += d_tp
        cum_fp += d_fp
        cum_tn += d_tn
        cum_fn += d_fn

        d_p = d_tp / (d_tp + d_fp) if (d_tp + d_fp) > 0 else 0.0
        d_r = d_tp / (d_tp + d_fn) if (d_tp + d_fn) > 0 else 0.0
        d_f1 = 2 * (d_p * d_r) / (d_p + d_r) if (d_p + d_r) > 0 else 0.0

        c_p = cum_tp / (cum_tp + cum_fp) if (cum_tp + cum_fp) > 0 else 0.0
        c_r = cum_tp / (cum_tp + cum_fn) if (cum_tp + cum_fn) > 0 else 0.0
        c_f1 = 2 * (c_p * c_r) / (c_p + c_r) if (c_p + c_r) > 0 else 0.0

        trend.append({
            "date": date_key,
            "total_labeled": d_tot,
            "analyst_reviews": b["analyst_count"],
            "tp": d_tp,
            "fp": d_fp,
            "tn": d_tn,
            "fn": d_fn,
            "precision": round(d_p, 4),
            "recall": round(d_r, 4),
            "f1_score": round(d_f1, 4),
            "cumulative_precision": round(c_p, 4),
            "cumulative_recall": round(c_r, 4),
            "cumulative_f1_score": round(c_f1, 4),
        })

    return Response({
        "period_days": days_int,
        "filter": filter_mode,
        "threshold_used": flag_threshold,
        "total_labeled": total_labeled,
        "analyst_labeled_count": analyst_labeled_count,
        "pending_review_count": pending_count,
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
        },
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        },
        "analyst_reviewed_metrics": {
            "total": analyst_total,
            "precision": round(analyst_p, 4),
            "recall": round(analyst_r, 4),
            "f1_score": round(analyst_f1, 4),
            "confusion_matrix": {
                "tp": analyst_tp,
                "fp": analyst_fp,
                "tn": analyst_tn,
                "fn": analyst_fn,
            },
        },
        "by_model_version": by_model_version,
        "trend": trend,
    })
