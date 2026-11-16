import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import MerchantProfile, User
from apps.notifications.models import NotificationLog
from apps.notifications.services import (
    calculate_urgency,
    evaluate_and_notify_transaction,
    get_analyst_recipients,
    notify_analysts_transaction_review,
)
from apps.transactions.models import Transaction

NOTIFS_URL = "/api/v1/notifications/"


@pytest.fixture
def merchant(customer):
    merchant_user = User.objects.create_user(
        username="notif_merchant",
        role=User.Role.MERCHANT,
        password="password123",
        email="merchant@notif.local",
    )
    return MerchantProfile.objects.create(user=merchant_user, business_name="Alert Test Store")


@pytest.fixture
def urgent_transaction(customer, merchant):
    return Transaction.objects.create(
        customer=customer,
        merchant=merchant,
        amount=1850.00,
        submitted_at=timezone.now(),
        fraud_score=0.78,
        status=Transaction.Status.UNDER_REVIEW,
        flagged_by=Transaction.FlaggedBy.MODEL,
    )


@pytest.mark.django_db
class TestUrgencyCalculation:
    def test_critical_urgency_by_score(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.89
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.CRITICAL

    def test_critical_urgency_by_high_amount(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.60
        urgent_transaction.amount = 7500.00
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.CRITICAL

    def test_critical_urgency_by_both_layers(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.65
        urgent_transaction.flagged_by = Transaction.FlaggedBy.BOTH
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.CRITICAL

    def test_high_urgency_by_score(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.76
        urgent_transaction.amount = 200.00
        urgent_transaction.flagged_by = Transaction.FlaggedBy.MODEL
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.HIGH

    def test_high_urgency_by_rule_flag(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.40
        urgent_transaction.amount = 300.00
        urgent_transaction.flagged_by = Transaction.FlaggedBy.RULE
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.HIGH

    def test_medium_urgency(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.55
        urgent_transaction.amount = 45.00
        urgent_transaction.flagged_by = Transaction.FlaggedBy.NONE
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.MEDIUM

    def test_low_urgency(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.12
        urgent_transaction.amount = 15.00
        urgent_transaction.flagged_by = Transaction.FlaggedBy.NONE
        assert calculate_urgency(urgent_transaction) == NotificationLog.Urgency.LOW


@pytest.mark.django_db
class TestNotificationDispatch:
    def test_recipients_include_active_analysts(self, analyst):
        analyst.email = "lead_analyst@example.com"
        analyst.save()
        recipients = get_analyst_recipients()
        assert "lead_analyst@example.com" in recipients

    def test_urgent_transaction_sends_email_and_creates_log(self, urgent_transaction, analyst):
        analyst.email = "analyst_on_duty@example.com"
        analyst.save()

        res = notify_analysts_transaction_review(urgent_transaction)
        assert res["sent"] is True
        assert res["urgency"] == NotificationLog.Urgency.HIGH

        # Verify Django mail outbox
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert "HIGH Alert" in sent_email.subject
        assert str(urgent_transaction.id) in sent_email.body
        assert "$1850.00" in sent_email.body
        assert "analyst_on_duty@example.com" in sent_email.to

        # Verify NotificationLog record
        log_entry = NotificationLog.objects.filter(transaction=urgent_transaction).first()
        assert log_entry is not None
        assert log_entry.urgency == NotificationLog.Urgency.HIGH
        assert log_entry.status == NotificationLog.Status.SENT

    def test_low_urgency_skips_email(self, urgent_transaction):
        urgent_transaction.fraud_score = 0.20
        urgent_transaction.flagged_by = Transaction.FlaggedBy.NONE
        urgent_transaction.amount = 20.00

        res = notify_analysts_transaction_review(urgent_transaction, min_urgency=NotificationLog.Urgency.HIGH)
        assert res["sent"] is False
        assert res["reason"] == "below_urgency_threshold"
        assert len(mail.outbox) == 0

    def test_evaluate_and_notify_ignores_approved_transactions(self, urgent_transaction):
        urgent_transaction.status = Transaction.Status.APPROVED
        urgent_transaction.save()

        res = evaluate_and_notify_transaction(urgent_transaction)
        assert res["sent"] is False
        assert res["reason"] == "transaction_not_under_review"
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestSimulationNotificationIntegration:
    SIMULATE_URL = "/api/v1/transactions/simulate/"

    def test_simulation_under_review_triggers_immediate_alert(self, customer_client, analyst):
        analyst.email = "fraud_ops@example.com"
        analyst.save()

        # Submit transaction crafted to land in review bracket (score >= 0.50 & < 0.90)
        payload = {
            "amount": "1499.99",
            "card4": "discover",
            "card6": "credit",
            "product_cd": "C",
            "p_emaildomain": "protonmail.com",
            "r_emaildomain": "anonymous.com",
        }
        res = customer_client.post(self.SIMULATE_URL, payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED

        # If flagged for review with high urgency, alert is sent
        if res.data["status"] == "under_review":
            assert len(mail.outbox) >= 1
            last_email = mail.outbox[-1]
            assert "FraudShield" in last_email.subject
            assert "fraud_ops@example.com" in last_email.to
            assert NotificationLog.objects.count() >= 1

    def test_simulation_approved_clean_does_not_alert(self, customer_client, analyst):
        # Clean $5 purchase
        payload = {
            "amount": "5.00",
            "card4": "visa",
            "card6": "debit",
            "product_cd": "W",
            "p_emaildomain": "gmail.com",
            "r_emaildomain": "gmail.com",
        }
        res = customer_client.post(self.SIMULATE_URL, payload, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["status"] == "approved"
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestNotificationLogEndpointPermissions:
    def test_unauthenticated_denied(self, api_client):
        assert api_client.get(NOTIFS_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_denied(self, customer_client):
        assert customer_client.get(NOTIFS_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_merchant_denied(self, merchant_client):
        assert merchant_client.get(NOTIFS_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_analyst_can_list_notifications(self, analyst_client, urgent_transaction, analyst):
        notify_analysts_transaction_review(urgent_transaction)
        res = analyst_client.get(NOTIFS_URL)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data["results"]) >= 1

