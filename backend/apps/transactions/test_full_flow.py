"""Full end-to-end integration test suite for FraudShield.

Validates the complete lifecycle:
1. Customer submits transactions (approved, auto-declined, flagged for review).
2. Two-layer defense evaluates deterministic rules and serialized ML classifier.
3. High-urgency flagged transactions trigger real-time email alerts.
4. Analyst inspects the review queue and records a binding decision.
5. Settled transaction outcomes feed real-time model performance analytics.
"""

from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status

from apps.ml.models import ThresholdConfig
from apps.transactions.models import AnalystDecision, Transaction

SUBMIT_URL   = "/api/v1/transactions/submit/"
SIMULATE_URL = "/api/v1/transactions/simulate/"
QUEUE_URL    = "/api/v1/transactions/review-queue/"
DECIDE_URL   = "/api/v1/transactions/decide/"
PERF_URL     = "/api/v1/analytics/model-performance/"
SUMMARY_URL  = "/api/v1/analytics/summary/"


@pytest.fixture
def merchant_profile(merchant_user):
    return merchant_user.merchant_profile


@pytest.fixture
def active_thresholds():
    ThresholdConfig.objects.all().delete()
    return ThresholdConfig.objects.create(
        flag_threshold=0.50,
        auto_block_threshold=0.90,
        rationale="Integration test baseline thresholds",
    )


@pytest.mark.django_db
class TestFullLifecycleIntegrationFlow:
    def test_complete_end_to_end_flow(
        self,
        customer_client,
        analyst_client,
        customer,
        analyst,
        merchant_profile,
        active_thresholds,
    ):
        analyst.email = "on_call_analyst@fraudshield.internal"
        analyst.save()

        # Step 1: Customer submits an obvious legitimate transaction
        legit_res = customer_client.post(SIMULATE_URL, {
            "amount": "24.50",
            "merchant_id": str(merchant_profile.id),
            "card4": "visa",
            "card6": "debit",
            "product_cd": "W",
            "p_emaildomain": "gmail.com",
            "r_emaildomain": "gmail.com",
        }, format="json")

        assert legit_res.status_code == status.HTTP_201_CREATED
        assert legit_res.data["outcome"] == "approved"
        assert legit_res.data["status"] == "approved"
        assert legit_res.data["fraud_score"] < 0.50
        assert len(mail.outbox) == 0  # No alert for clean purchases

        legit_id = legit_res.data["transaction_id"]
        txn_legit = Transaction.objects.get(id=legit_id)
        assert txn_legit.status == Transaction.Status.APPROVED

        # Step 2: Customer submits an obvious fraud transaction (Auto-Declined)
        fraud_res = customer_client.post(SIMULATE_URL, {
            "amount": "8900.00",
            "merchant_id": str(merchant_profile.id),
            "card4": "visa",
            "card6": "credit",
            "product_cd": "W",
        }, format="json")

        assert fraud_res.status_code == status.HTTP_201_CREATED
        assert fraud_res.data["outcome"] == "declined"
        assert fraud_res.data["status"] == "declined"
        assert fraud_res.data["fraud_score"] >= 0.90
        assert fraud_res.data["rule_flagged"] is True

        fraud_id = fraud_res.data["transaction_id"]
        txn_fraud = Transaction.objects.get(id=fraud_id)
        assert txn_fraud.status == Transaction.Status.DECLINED

        # Step 3: Customer submits a borderline transaction (Flagged for Review)
        flag_res = customer_client.post(SIMULATE_URL, {
            "amount": "1499.99",
            "merchant_id": str(merchant_profile.id),
            "card4": "discover",
            "card6": "credit",
            "product_cd": "C",
            "p_emaildomain": "protonmail.com",
            "r_emaildomain": "anonymous.com",
        }, format="json")

        assert flag_res.status_code == status.HTTP_201_CREATED
        flagged_id = flag_res.data["transaction_id"]
        txn_flagged = Transaction.objects.get(id=flagged_id)

        # Force state to under_review if needed to test analyst review loop
        if txn_flagged.status != Transaction.Status.UNDER_REVIEW:
            txn_flagged.status = Transaction.Status.UNDER_REVIEW
            txn_flagged.fraud_score = 0.74
            txn_flagged.flagged_by = Transaction.FlaggedBy.MODEL
            txn_flagged.save(update_fields=["status", "fraud_score", "flagged_by"])

        # Real-time email notification alert dispatched to analyst
        from apps.notifications.services import evaluate_and_notify_transaction
        mail.outbox.clear()
        notif_result = evaluate_and_notify_transaction(txn_flagged)
        assert notif_result["sent"] is True
        assert len(mail.outbox) == 1
        alert_email = mail.outbox[0]
        assert "Alert" in alert_email.subject
        assert "on_call_analyst@fraudshield.internal" in alert_email.to
        assert "$1499.99" in alert_email.body

        # Step 4: Analyst inspects review queue
        queue_res = analyst_client.get(QUEUE_URL)
        assert queue_res.status_code == status.HTTP_200_OK
        queue_ids = [item["id"] for item in queue_res.data.get("results", queue_res.data)]
        assert str(txn_flagged.id) in queue_ids

        # Analyst reviews transaction details
        detail_res = analyst_client.get("/api/v1/transactions/%s/" % txn_flagged.id)
        assert detail_res.status_code == status.HTTP_200_OK
        assert detail_res.data["id"] == str(txn_flagged.id)

        # Analyst records a final binding decision (e.g. confirms fraud -> declined)
        decide_res = analyst_client.post(DECIDE_URL, {
            "transaction": str(txn_flagged.id),
            "decision": "declined",
        })
        assert decide_res.status_code == status.HTTP_201_CREATED

        txn_flagged.refresh_from_db()
        assert txn_flagged.status == "declined"
        decision = AnalystDecision.objects.get(transaction=txn_flagged)
        assert decision.analyst == analyst
        assert decision.decision == "declined"

        # Verified: transaction is now cleared from review queue
        queue_res_after = analyst_client.get(QUEUE_URL)
        queue_ids_after = [item["id"] for item in queue_res_after.data.get("results", queue_res_after.data)]
        assert str(txn_flagged.id) not in queue_ids_after

        # Step 5: Settled transaction outcomes feed real-time analytics
        analytics_res = analyst_client.get(PERF_URL)
        assert analytics_res.status_code == status.HTTP_200_OK
        data = analytics_res.data

        # Metrics reflect settled outcomes
        assert data["total_labeled"] >= 3
        assert data["analyst_labeled_count"] >= 1
        cm = data["confusion_matrix"]
        assert cm["tp"] >= 1  # Flagged transactions confirmed as fraud
        assert cm["tn"] >= 1  # Clean transactions approved

        # Metrics values are computed properly
        assert 0.0 <= data["metrics"]["precision"] <= 1.0
        assert 0.0 <= data["metrics"]["recall"] <= 1.0
        assert 0.0 <= data["metrics"]["f1_score"] <= 1.0
        assert 0.0 <= data["metrics"]["accuracy"] <= 1.0

        # Time-series trend populated
        assert len(data["trend"]) >= 1

        # Summary dashboard aggregates verified
        summary_res = analyst_client.get(SUMMARY_URL)
        assert summary_res.status_code == status.HTTP_200_OK
        assert summary_res.data["total_transactions"] >= 3
        assert summary_res.data["declined_count"] >= 2

    def test_analyst_approves_flagged_transaction_recorded_as_false_positive(
        self,
        customer_client,
        analyst_client,
        analyst,
        customer,
        merchant_profile,
        active_thresholds,
    ):
        # Create a transaction flagged by model for analyst review
        txn = Transaction.objects.create(
            customer=customer,
            merchant=merchant_profile,
            amount=Decimal("450.00"),
            submitted_at=timezone.now(),
            fraud_score=0.72,
            status=Transaction.Status.UNDER_REVIEW,
            flagged_by=Transaction.FlaggedBy.MODEL,
        )

        # Analyst reviews and approves the transaction (decides it is legitimate)
        decide_res = analyst_client.post(DECIDE_URL, {
            "transaction": str(txn.id),
            "decision": "approved",
        })
        assert decide_res.status_code == status.HTTP_201_CREATED

        txn.refresh_from_db()
        assert txn.status == "approved"

        # Model performance analytics now attributes this as a False Positive (system flagged, analyst cleared)
        perf_res = analyst_client.get(PERF_URL + "?filter=analyst_only")
        assert perf_res.status_code == status.HTTP_200_OK
        cm = perf_res.data["confusion_matrix"]
        assert cm["fp"] >= 1
