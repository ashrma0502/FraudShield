"""Notification service interface for alerting Fraud Analysts.

Integrates Django's built-in email framework to dispatch alerts when transactions
are flagged for manual review above a configured urgency threshold.
"""

import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.db import DatabaseError

from apps.accounts.models import User

from .models import NotificationLog

logger = logging.getLogger(__name__)

URGENCY_LEVELS = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def calculate_urgency(transaction):
    """Determine urgency level based on fraud score, amount, and rule triggers."""
    score = float(transaction.fraud_score) if transaction.fraud_score is not None else 0.0
    amount = float(transaction.amount) if transaction.amount is not None else 0.0
    flagged_by = getattr(transaction, "flagged_by", "none")

    # Critical: severe score, extreme amount, or simultaneous rule and model violations
    if score >= 0.85 or amount >= 5000.0 or flagged_by == "both":
        return NotificationLog.Urgency.CRITICAL

    # High: elevated score or direct rule pre-filter violation
    if score >= 0.70 or flagged_by == "rule":
        return NotificationLog.Urgency.HIGH

    # Medium: moderate risk requiring standard analyst queue inspection
    if score >= 0.50:
        return NotificationLog.Urgency.MEDIUM

    return NotificationLog.Urgency.LOW


def get_analyst_recipients():
    """Retrieve active email addresses of Fraud Analysts and Admins."""
    analysts = User.objects.filter(
        role__in=[User.Role.ANALYST, User.Role.ADMIN],
        is_active=True,
    ).exclude(email="")

    recipients = [u.email for u in analysts if u.email]
    fallback = getattr(settings, "DEFAULT_ANALYST_EMAIL", None)
    if fallback and fallback not in recipients:
        recipients.append(fallback)

    if not recipients:
        recipients = ["analyst@example.com"]

    return list(dict.fromkeys(recipients))


def notify_analysts_transaction_review(transaction, urgency=None, min_urgency=NotificationLog.Urgency.HIGH):
    """Dispatch real-time email alert to Fraud Analysts for urgent transactions."""
    calculated_urgency = urgency or calculate_urgency(transaction)
    urgency_rank = URGENCY_LEVELS.get(calculated_urgency, 1)
    min_rank = URGENCY_LEVELS.get(min_urgency, 3)

    if urgency_rank < min_rank:
        logger.info(
            "Skipping notification for transaction %s: urgency %s is below minimum threshold %s",
            transaction.id,
            calculated_urgency,
            min_urgency,
        )
        return {
            "sent": False,
            "reason": "below_urgency_threshold",
            "urgency": calculated_urgency,
        }

    recipients = get_analyst_recipients()
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "alerts@fraudshield.internal")

    score_val = float(transaction.fraud_score or 0.0)
    amount_val = float(transaction.amount or 0.0)
    merchant_name = transaction.merchant.business_name if transaction.merchant else "N/A"
    customer_name = transaction.customer.username if transaction.customer else "N/A"
    short_id = str(transaction.id)[:8]

    subject = "[FraudShield %s Alert] Transaction %s Flagged for Review ($%.2f)" % (
        calculated_urgency,
        short_id,
        amount_val,
    )

    message = (
        "FraudShield Immediate Analyst Alert\n"
        "============================================================\n"
        "An urgent transaction has been flagged for manual review.\n\n"
        "Transaction ID : %s\n"
        "Urgency Level  : %s\n"
        "Amount         : $%.2f USD\n"
        "Fraud Score    : %.4f (%.1f%%)\n"
        "Flagged By     : %s\n"
        "Merchant       : %s\n"
        "Customer       : %s\n"
        "Submitted At   : %s\n\n"
        "Action Required:\n"
        "Please inspect the transaction in the Fraud Analyst Queue.\n\n"
        "FraudShield Automated Notification System\n"
    ) % (
        transaction.id,
        calculated_urgency,
        amount_val,
        score_val,
        score_val * 100,
        transaction.flagged_by,
        merchant_name,
        customer_name,
        transaction.submitted_at,
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=False,
        )
        send_status = NotificationLog.Status.SENT
        sent_success = True
    except (SMTPException, OSError, RuntimeError) as err:
        logger.error("Failed to send alert email for transaction %s: %s", transaction.id, err)
        send_status = NotificationLog.Status.FAILED
        sent_success = False

    try:
        NotificationLog.objects.create(
            transaction=transaction,
            notification_type="analyst_review_alert",
            urgency=calculated_urgency,
            recipient=", ".join(recipients),
            subject=subject,
            message=message,
            status=send_status,
        )
    except DatabaseError as db_err:
        logger.warning("Could not persist notification log: %s", db_err)

    return {
        "sent": sent_success,
        "urgency": calculated_urgency,
        "recipients": recipients,
        "subject": subject,
    }


def evaluate_and_notify_transaction(transaction, min_urgency=NotificationLog.Urgency.MEDIUM):
    """Convenience trigger point: alerts analysts if transaction is under review and meets urgency."""
    from apps.transactions.models import Transaction

    if transaction.status == Transaction.Status.UNDER_REVIEW:
        return notify_analysts_transaction_review(transaction, min_urgency=min_urgency)

    return {
        "sent": False,
        "reason": "transaction_not_under_review",
        "urgency": calculate_urgency(transaction),
    }

