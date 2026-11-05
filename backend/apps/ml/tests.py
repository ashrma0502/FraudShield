"""
Tests for ML threshold config and model registry permission boundaries.
"""
from datetime import timedelta
from io import StringIO

import pytest
import sklearn
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework import status

from apps.ml.models import PredictionLog, ThresholdConfig
from apps.ml.services import check_model_compatibility
from apps.transactions.models import Transaction

THRESHOLD_LIST_URL = "/api/v1/ml/thresholds/"
THRESHOLD_ADD_URL  = "/api/v1/ml/thresholds/add/"
MODEL_LIST_URL     = "/api/v1/ml/models/"
PREDICT_URL        = "/api/v1/ml/predict/"


@pytest.mark.django_db
class TestUnauthenticated:
    def test_threshold_list_requires_auth(self, api_client):
        assert api_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_threshold_add_requires_auth(self, api_client):
        assert api_client.post(THRESHOLD_ADD_URL, {}).status_code == status.HTTP_401_UNAUTHORIZED

    def test_model_list_requires_auth(self, api_client):
        assert api_client.get(MODEL_LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCustomerMLAccess:
    def test_cannot_view_thresholds(self, customer_client):
        assert customer_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_add_threshold(self, customer_client):
        assert customer_client.post(THRESHOLD_ADD_URL, {}).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_view_models(self, customer_client):
        assert customer_client.get(MODEL_LIST_URL).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMerchantMLAccess:
    def test_cannot_view_thresholds(self, merchant_client):
        assert merchant_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_add_threshold(self, merchant_client):
        assert merchant_client.post(THRESHOLD_ADD_URL, {}).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_view_models(self, merchant_client):
        assert merchant_client.get(MODEL_LIST_URL).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAnalystMLAccess:
    def test_can_view_model_list(self, analyst_client):
        res = analyst_client.get(MODEL_LIST_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_cannot_view_thresholds(self, analyst_client):
        assert analyst_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_add_threshold(self, analyst_client):
        res = analyst_client.post(THRESHOLD_ADD_URL, {
            "auto_block_threshold": 0.9, "flag_threshold": 0.6, "rationale": "Analyst tweak"
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminThresholdAccess:
    def test_admin_can_list_thresholds(self, admin_client):
        res = admin_client.get(THRESHOLD_LIST_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_admin_can_add_threshold(self, admin_client):
        res = admin_client.post(THRESHOLD_ADD_URL, {
            "auto_block_threshold": 0.9,
            "flag_threshold":       0.7,
            "rationale": "Tightening flag threshold based on Q3 review.",
        })
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["flag_threshold"] == 0.7

    def test_admin_can_view_model_list(self, admin_client):
        res = admin_client.get(MODEL_LIST_URL)
        assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAnalyticsPermissions:
    SUMMARY_URL = "/api/v1/analytics/summary/"
    DAILY_URL   = "/api/v1/analytics/daily/"

    def test_unauthenticated_denied(self, api_client):
        assert api_client.get(self.SUMMARY_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_denied(self, customer_client):
        assert customer_client.get(self.SUMMARY_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_merchant_denied(self, merchant_client):
        assert merchant_client.get(self.SUMMARY_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_analyst_can_access_summary(self, analyst_client):
        assert analyst_client.get(self.SUMMARY_URL).status_code == status.HTTP_200_OK

    def test_admin_can_access_summary(self, admin_client):
        assert admin_client.get(self.SUMMARY_URL).status_code == status.HTTP_200_OK

    def test_analyst_can_access_daily(self, analyst_client):
        assert analyst_client.get(self.DAILY_URL).status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestRealtimeFraudInference:
    def test_predict_requires_auth(self, api_client):
        res = api_client.post(PREDICT_URL, {"amount": 50.0})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_obvious_legitimate_small_purchase(self, customer_client):
        res = customer_client.post(PREDICT_URL, {
            "amount": 15.00,
            "product_cd": "W",
            "card4": "visa",
            "card6": "debit",
            "p_emaildomain": "gmail.com",
        })
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["fraud_score"] < 0.45
        assert data["is_fraud"] is False
        assert data["flagged_by"] == "none"
        assert data["contributing_layer"] == "none"
        assert data["rule_flagged"] is False
        assert len(data["triggered_rules"]) == 0
        assert data["layers"]["rules"]["flagged"] is False
        assert data["layers"]["model"]["flagged"] is False

    def test_obvious_legitimate_standard_retail(self, customer_client):
        res = customer_client.post(PREDICT_URL, {
            "amount": 45.50,
            "product_cd": "W",
            "card4": "mastercard",
            "card6": "credit",
        })
        assert res.status_code == status.HTTP_200_OK
        assert res.data["is_fraud"] is False
        assert res.data["flagged_by"] == "none"

    def test_obvious_fraud_high_amount_rule(self, customer_client):
        res = customer_client.post(PREDICT_URL, {
            "amount": 18500.00,
            "product_cd": "W",
        })
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["is_fraud"] is True
        assert data["rule_flagged"] is True
        assert "high_amount" in data["triggered_rules"]
        assert data["contributing_layer"] in ["rules", "both"]
        assert data["fraud_score"] >= 0.90

    def test_obvious_fraud_velocity_spike(self, customer_client, customer, merchant_user):
        now = timezone.now()
        Transaction.objects.create(
            customer=customer,
            merchant=merchant_user.merchant_profile,
            amount="120.00",
            submitted_at=now - timedelta(minutes=2),
            status=Transaction.Status.APPROVED,
        )
        Transaction.objects.create(
            customer=customer,
            merchant=merchant_user.merchant_profile,
            amount="140.00",
            submitted_at=now - timedelta(minutes=1),
            status=Transaction.Status.APPROVED,
        )

        res = customer_client.post(PREDICT_URL, {
            "amount": 150.00,
            "submitted_at": now.isoformat(),
        })
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["is_fraud"] is True
        assert data["rule_flagged"] is True
        assert "velocity_limit" in data["triggered_rules"]
        assert data["contributing_layer"] in ["rules", "both"]
        assert data["fraud_score"] >= 0.90

    def test_obvious_fraud_model_layer(self, customer_client):
        ThresholdConfig.objects.create(
            flag_threshold=0.50,
            auto_block_threshold=0.90,
            rationale="Test threshold for high risk detection",
        )
        res = customer_client.post(PREDICT_URL, {
            "amount": 2500.00,
            "product_cd": "C",
            "p_emaildomain": "anonymous.com",
            "r_emaildomain": "mail.com",
            "card4": "discover",
            "card6": "credit",
            "feature_snapshot": {
                "id_01": -45.0,
                "id_02": 100000.0,
                "C1": 50.0,
                "C2": 50.0,
                "D1": 0.0,
                "V258": 5.0,
                "V283": 10.0,
            },
        }, format="json")
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["is_fraud"] is True
        assert data["model_flagged"] is True
        assert data["contributing_layer"] in ["model", "both"]
        assert data["fraud_score"] >= 0.50

    def test_audit_prediction_log_created(self, customer_client):
        count_before = PredictionLog.objects.count()
        res = customer_client.post(PREDICT_URL, {"amount": 75.00})
        assert res.status_code == status.HTTP_200_OK
        assert PredictionLog.objects.count() == count_before + 1
        log = PredictionLog.objects.latest("created_at")
        assert log.fraud_score == res.data["fraud_score"]
        assert "latency_ms" in res.data
        assert res.data["latency_ms"] >= 0


class TestModelCompatibility:
    def test_compatibility_passes_on_matching_version(self):
        bundle = {"sklearn_version": sklearn.__version__}
        assert check_model_compatibility(bundle) is True

    def test_compatibility_refuses_on_mismatched_version(self):
        bundle = {"sklearn_version": "0.19.1"}
        with pytest.raises(RuntimeError, match="scikit-learn version mismatch"):
            check_model_compatibility(bundle, raise_exception=True)


@pytest.mark.django_db
class TestRetrainModelManagementCommand:
    def test_refuses_when_min_fraud_not_met(self):
        out = StringIO()
        err = StringIO()
        with pytest.raises(CommandError, match="Refusing to retrain"):
            call_command("retrain_model", min_fraud=50, stdout=out, stderr=err)
