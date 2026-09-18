import uuid

from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """Core transaction record as per the ER diagram."""

    class Status(models.TextChoices):
        PENDING      = "pending",      "Pending"
        APPROVED     = "approved",     "Approved"
        DECLINED     = "declined",     "Declined"
        UNDER_REVIEW = "under_review", "Under Review"

    class FlaggedBy(models.TextChoices):
        NONE  = "none",  "None"
        RULE  = "rule",  "Rule Engine"
        MODEL = "model", "ML Model"

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
    )
    merchant         = models.ForeignKey(
        "accounts.MerchantProfile",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
    )
    amount           = models.DecimalField(max_digits=14, decimal_places=2)
    submitted_at     = models.DateTimeField()
    fraud_score      = models.FloatField(null=True, blank=True)
    status           = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    flagged_by       = models.CharField(max_length=8, choices=FlaggedBy.choices, default=FlaggedBy.NONE)
    model_version    = models.CharField(max_length=64, blank=True)
    feature_snapshot = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["fraud_score"]),
            models.Index(fields=["flagged_by"]),
            models.Index(fields=["submitted_at"]),
        ]

    def __str__(self):
        return "%s | %s | %s" % (self.id, self.amount, self.status)


class AnalystDecision(models.Model):
    """Analyst review decision — at most one per transaction."""

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="analyst_decision"
    )
    analyst     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="decisions",
        limit_choices_to={"role": "analyst"},
    )
    decision    = models.CharField(max_length=16)

    class Meta:
        verbose_name = "Analyst Decision"
        verbose_name_plural = "Analyst Decisions"

    def __str__(self):
        return "%s → %s by %s" % (self.transaction_id, self.decision, self.analyst)
