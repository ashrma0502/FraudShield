"""
Tests for transaction endpoint role-permission boundaries.
"""
import pytest
from django.utils import timezone
from rest_framework import status

from apps.transactions.models import Transaction

SUBMIT_URL = "/api/v1/transactions/submit/"
SIMULATE_URL = "/api/v1/transactions/simulate/"
MINE_URL   = "/api/v1/transactions/mine/"
QUEUE_URL  = "/api/v1/transactions/review-queue/"
DECIDE_URL = "/api/v1/transactions/decide/"


@pytest.mark.django_db
class TestUnauthenticated:
    def test_submit_requires_auth(self, api_client):
        assert api_client.post(SUBMIT_URL, {}).status_code == status.HTTP_401_UNAUTHORIZED

    def test_mine_requires_auth(self, api_client):
        assert api_client.get(MINE_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_queue_requires_auth(self, api_client):
        assert api_client.get(QUEUE_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_decide_requires_auth(self, api_client):
        assert api_client.post(DECIDE_URL, {}).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCustomerPermissions:
    def test_customer_can_submit_transaction(self, customer_client):
        res = customer_client.post(SUBMIT_URL, {
            "amount":       "120.00",
            "submitted_at": timezone.now().isoformat(),
        })
        assert res.status_code == status.HTTP_201_CREATED

    def test_submitted_transaction_belongs_to_customer(self, customer_client, customer):
        customer_client.post(SUBMIT_URL, {
            "amount":       "50.00",
            "submitted_at": timezone.now().isoformat(),
        })
        txn = Transaction.objects.filter(customer=customer).first()
        assert txn is not None
        assert txn.customer == customer

    def test_customer_cannot_view_review_queue(self, customer_client):
        assert customer_client.get(QUEUE_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_customer_cannot_view_mine(self, customer_client):
        assert customer_client.get(MINE_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_customer_cannot_decide(self, customer_client, transaction):
        res = customer_client.post(DECIDE_URL, {
            "transaction": str(transaction.id), "decision": "approved"
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMerchantPermissions:
    def test_merchant_can_view_own_transactions(self, merchant_client, transaction):
        res = merchant_client.get(MINE_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_merchant_cannot_submit_transaction(self, merchant_client):
        res = merchant_client.post(SUBMIT_URL, {
            "amount":       "30.00",
            "submitted_at": timezone.now().isoformat(),
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_merchant_cannot_view_review_queue(self, merchant_client):
        assert merchant_client.get(QUEUE_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_merchant_cannot_decide(self, merchant_client, transaction):
        res = merchant_client.post(DECIDE_URL, {
            "transaction": str(transaction.id), "decision": "approved"
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAnalystPermissions:
    def test_analyst_can_view_review_queue(self, analyst_client, transaction):
        res = analyst_client.get(QUEUE_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_analyst_can_view_transaction_detail(self, analyst_client, transaction):
        res = analyst_client.get("/api/v1/transactions/%s/" % transaction.id)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["id"] == str(transaction.id)

    def test_analyst_can_record_decision(self, analyst_client, transaction):
        res = analyst_client.post(DECIDE_URL, {
            "transaction": str(transaction.id),
            "decision":    "approved",
        })
        assert res.status_code == status.HTTP_201_CREATED
        transaction.refresh_from_db()
        assert transaction.status == "approved"

    def test_analyst_cannot_submit_transaction(self, analyst_client):
        res = analyst_client.post(SUBMIT_URL, {
            "amount":       "99.00",
            "submitted_at": timezone.now().isoformat(),
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_analyst_cannot_view_own_transactions(self, analyst_client):
        assert analyst_client.get(MINE_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_one_decision_per_transaction(self, analyst_client, transaction):
        analyst_client.post(DECIDE_URL, {
            "transaction": str(transaction.id), "decision": "approved"
        })
        # Second decision on same transaction must fail (OneToOne constraint)
        res = analyst_client.post(DECIDE_URL, {
            "transaction": str(transaction.id), "decision": "declined"
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAdminTransactionAccess:
    def test_admin_can_view_review_queue(self, admin_client, transaction):
        res = admin_client.get(QUEUE_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_admin_can_view_transaction_detail(self, admin_client, transaction):
        res = admin_client.get("/api/v1/transactions/%s/" % transaction.id)
        assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTransactionSimulation:
    def test_simulation_options_metadata(self, api_client):
        res = api_client.get(SIMULATE_URL)
        assert res.status_code == status.HTTP_200_OK
        assert "merchants" in res.data
        assert "thresholds" in res.data
        assert "presets" in res.data
        assert len(res.data["presets"]) > 0

    def test_simulate_approved_legitimate_transaction(self, api_client):
        payload = {
            "amount": "14.50",
            "card4": "visa",
            "card6": "debit",
            "product_cd": "W",
            "p_emaildomain": "gmail.com",
            "r_emaildomain": "gmail.com",
        }
        res = api_client.post(SIMULATE_URL, payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["outcome"] == "approved"
        assert res.data["status"] == "approved"
        assert res.data["fraud_score"] < 0.75

        txn = Transaction.objects.filter(id=res.data["transaction_id"]).first()
        assert txn is not None
        assert txn.status == Transaction.Status.APPROVED
        assert txn.amount == 14.50

    def test_simulate_declined_high_amount_rule(self, api_client):
        payload = {
            "amount": "7500.00",
            "card4": "visa",
            "card6": "credit",
            "product_cd": "W",
        }
        res = api_client.post(SIMULATE_URL, payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["outcome"] == "declined"
        assert res.data["status"] == "declined"
        assert res.data["fraud_score"] >= 0.90
        assert res.data["rule_flagged"] is True
        assert "high_amount" in res.data["triggered_rules"]

        txn = Transaction.objects.filter(id=res.data["transaction_id"]).first()
        assert txn is not None
        assert txn.status == Transaction.Status.DECLINED

    def test_simulate_with_authenticated_customer(self, customer_client, customer):
        payload = {
            "amount": "25.00",
            "card4": "mastercard",
            "card6": "debit",
        }
        res = customer_client.post(SIMULATE_URL, payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["customer"] == customer.username

        txn = Transaction.objects.filter(id=res.data["transaction_id"]).first()
        assert txn is not None
        assert txn.customer == customer

