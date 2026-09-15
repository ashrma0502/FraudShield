"""
Tests for ML threshold config and model registry permission boundaries.
"""
import pytest
from rest_framework import status

THRESHOLD_LIST_URL = "/api/v1/ml/thresholds/"
THRESHOLD_ADD_URL  = "/api/v1/ml/thresholds/add/"
MODEL_LIST_URL     = "/api/v1/ml/models/"


# ── Unauthenticated ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUnauthenticated:
    def test_threshold_list_requires_auth(self, api_client):
        assert api_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_threshold_add_requires_auth(self, api_client):
        assert api_client.post(THRESHOLD_ADD_URL, {}).status_code == status.HTTP_401_UNAUTHORIZED

    def test_model_list_requires_auth(self, api_client):
        assert api_client.get(MODEL_LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED


# ── Customer — denied from all ML endpoints ────────────────────────────────────

@pytest.mark.django_db
class TestCustomerMLAccess:
    def test_cannot_view_thresholds(self, customer_client):
        assert customer_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_add_threshold(self, customer_client):
        assert customer_client.post(THRESHOLD_ADD_URL, {}).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_view_models(self, customer_client):
        assert customer_client.get(MODEL_LIST_URL).status_code == status.HTTP_403_FORBIDDEN


# ── Merchant — denied from all ML endpoints ───────────────────────────────────

@pytest.mark.django_db
class TestMerchantMLAccess:
    def test_cannot_view_thresholds(self, merchant_client):
        assert merchant_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_add_threshold(self, merchant_client):
        assert merchant_client.post(THRESHOLD_ADD_URL, {}).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_view_models(self, merchant_client):
        assert merchant_client.get(MODEL_LIST_URL).status_code == status.HTTP_403_FORBIDDEN


# ── Analyst — can view models but cannot change thresholds ────────────────────

@pytest.mark.django_db
class TestAnalystMLAccess:
    def test_can_view_model_list(self, analyst_client):
        res = analyst_client.get(MODEL_LIST_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_cannot_view_thresholds(self, analyst_client):
        assert analyst_client.get(THRESHOLD_LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_add_threshold(self, analyst_client):
        res = analyst_client.post(THRESHOLD_ADD_URL, {
            "name": "flag_score", "value": 0.6, "rationale": "Analyst tweak"
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN


# ── Admin — full access to thresholds ─────────────────────────────────────────

@pytest.mark.django_db
class TestAdminThresholdAccess:
    def test_admin_can_list_thresholds(self, admin_client):
        res = admin_client.get(THRESHOLD_LIST_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_admin_can_add_threshold(self, admin_client):
        res = admin_client.post(THRESHOLD_ADD_URL, {
            "name":      "flag_score",
            "value":     0.7,
            "rationale": "Tightening flag threshold based on Q3 review.",
        })
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["value"] == 0.7

    def test_threshold_is_append_only(self, admin_client):
        """Verify ThresholdConfig rows cannot be updated."""
        from apps.accounts.models import User
        from apps.ml.models import ThresholdConfig
        admin = User.objects.get(username="admin1")
        cfg = ThresholdConfig.objects.create(
            name="block_score", value=0.9, changed_by=admin,
            rationale="Initial value."
        )
        with pytest.raises(ValueError, match="immutable"):
            cfg.value = 0.8
            cfg.save()

    def test_threshold_cannot_be_deleted(self, admin_client):
        """Verify ThresholdConfig rows cannot be deleted via the model."""
        from apps.accounts.models import User
        from apps.ml.models import ThresholdConfig
        admin = User.objects.get(username="admin1")
        cfg = ThresholdConfig.objects.create(
            name="block_score", value=0.95, changed_by=admin,
            rationale="Test."
        )
        with pytest.raises(ValueError, match="cannot be deleted"):
            cfg.delete()

    def test_admin_can_view_model_list(self, admin_client):
        res = admin_client.get(MODEL_LIST_URL)
        assert res.status_code == status.HTTP_200_OK


# ── Analytics permission boundary ─────────────────────────────────────────────

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
