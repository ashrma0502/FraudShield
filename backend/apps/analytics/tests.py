from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import MerchantProfile, User
from apps.transactions.models import AnalystDecision, Transaction

PERF_URL = "/api/v1/analytics/model-performance/"


@pytest.mark.django_db
class TestModelPerformancePermissions:
    def test_unauthenticated_denied(self, api_client):
        res = api_client.get(PERF_URL)
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_denied(self, customer_client):
        res = customer_client.get(PERF_URL)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_merchant_denied(self, merchant_client):
        res = merchant_client.get(PERF_URL)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_analyst_allowed(self, analyst_client):
        res = analyst_client.get(PERF_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_admin_allowed(self, admin_client):
        res = admin_client.get(PERF_URL)
        assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestModelPerformanceCalculations:
    @pytest.fixture
    def setup_labeled_transactions(self, customer, analyst):
        merchant_user = User.objects.create_user(
            username="perf_merchant", role=User.Role.MERCHANT, password="password123"
        )
        merchant = MerchantProfile.objects.create(user=merchant_user, business_name="Perf Store")

        now = timezone.now()

        # 1. True Positive: system flagged, analyst confirmed decline (fraud)
        tp_txn = Transaction.objects.create(
            customer=customer,
            merchant=merchant,
            amount=500.00,
            submitted_at=now - timedelta(days=2),
            fraud_score=0.92,
            status=Transaction.Status.DECLINED,
            flagged_by=Transaction.FlaggedBy.RULE,
        )
        AnalystDecision.objects.create(
            transaction=tp_txn,
            analyst=analyst,
            decision="declined",
        )

        # 2. False Positive: system flagged, analyst cleared as approved (legitimate)
        fp_txn = Transaction.objects.create(
            customer=customer,
            merchant=merchant,
            amount=200.00,
            submitted_at=now - timedelta(days=2),
            fraud_score=0.82,
            status=Transaction.Status.APPROVED,
            flagged_by=Transaction.FlaggedBy.MODEL,
        )
        AnalystDecision.objects.create(
            transaction=fp_txn,
            analyst=analyst,
            decision="approved",
        )

        # 3. True Negative: system cleared, auto-approved (legitimate)
        Transaction.objects.create(
            customer=customer,
            merchant=merchant,
            amount=25.00,
            submitted_at=now - timedelta(days=1),
            fraud_score=0.08,
            status=Transaction.Status.APPROVED,
            flagged_by=Transaction.FlaggedBy.NONE,
        )

        # 4. False Negative: system cleared, but settled as declined (fraud)
        Transaction.objects.create(
            customer=customer,
            merchant=merchant,
            amount=40.00,
            submitted_at=now - timedelta(days=1),
            fraud_score=0.15,
            status=Transaction.Status.DECLINED,
            flagged_by=Transaction.FlaggedBy.NONE,
        )

        # 5. Pending review (should be excluded from labeled ground truth metrics)
        Transaction.objects.create(
            customer=customer,
            merchant=merchant,
            amount=100.00,
            submitted_at=now,
            fraud_score=0.65,
            status=Transaction.Status.UNDER_REVIEW,
            flagged_by=Transaction.FlaggedBy.MODEL,
        )

    def test_metrics_and_confusion_matrix(self, analyst_client, setup_labeled_transactions):
        res = analyst_client.get(PERF_URL)
        assert res.status_code == status.HTTP_200_OK
        data = res.data

        # 4 labeled transactions (TP=1, FP=1, TN=1, FN=1), 1 pending
        assert data["total_labeled"] == 4
        assert data["pending_review_count"] == 1
        assert data["analyst_labeled_count"] == 2

        cm = data["confusion_matrix"]
        assert cm["tp"] == 1
        assert cm["fp"] == 1
        assert cm["tn"] == 1
        assert cm["fn"] == 1

        # Precision = 1 / (1 + 1) = 0.50
        # Recall    = 1 / (1 + 1) = 0.50
        # F1        = 2 * 0.5 * 0.5 / 1.0 = 0.50
        # Accuracy  = (1 + 1) / 4 = 0.50
        assert data["metrics"]["precision"] == 0.50
        assert data["metrics"]["recall"] == 0.50
        assert data["metrics"]["f1_score"] == 0.50
        assert data["metrics"]["accuracy"] == 0.50

        # Verify time-series trend list exists and has chronological buckets
        assert len(data["trend"]) >= 2
        for bucket in data["trend"]:
            assert "date" in bucket
            assert "precision" in bucket
            assert "recall" in bucket
            assert "f1_score" in bucket
            assert "cumulative_f1_score" in bucket

    def test_analyst_only_filter(self, analyst_client, setup_labeled_transactions):
        res = analyst_client.get(PERF_URL + "?filter=analyst_only")
        assert res.status_code == status.HTTP_200_OK
        data = res.data

        # Only the 2 transactions with AnalystDecision are counted
        assert data["total_labeled"] == 2
        cm = data["confusion_matrix"]
        assert cm["tp"] == 1
        assert cm["fp"] == 1
        assert cm["tn"] == 0
        assert cm["fn"] == 0

    def test_by_model_version_breakdown(self, analyst_client, setup_labeled_transactions):
        res = analyst_client.get(PERF_URL)
        assert res.status_code == status.HTTP_200_OK
        data = res.data

        assert "by_model_version" in data
        assert isinstance(data["by_model_version"], list)
        assert len(data["by_model_version"]) >= 1

        v1_entry = next((item for item in data["by_model_version"] if item["model_version"] == "1.0.0"), None)
        assert v1_entry is not None
        assert "metrics" in v1_entry
        assert "confusion_matrix" in v1_entry
        assert v1_entry["total_reviewed"] == 2
        assert v1_entry["confusion_matrix"]["tp"] == 1
        assert v1_entry["confusion_matrix"]["fp"] == 1
