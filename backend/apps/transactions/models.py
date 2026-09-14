from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """
    Core transaction record. Captures IEEE-CIS dataset fields alongside
    fraud-scoring metadata produced by the rule/model pipeline.
    """

    class Status(models.TextChoices):
        PENDING      = "pending",      "Pending"
        APPROVED     = "approved",     "Approved"
        DECLINED     = "declined",     "Declined"
        UNDER_REVIEW = "under_review", "Under Review"

    class FlagLayer(models.TextChoices):
        NONE  = "none",  "None"
        RULE  = "rule",  "Rule Engine"
        MODEL = "model", "ML Model"

    # ── Identity ────────────────────────────────────────────────────────────
    transaction_id = models.CharField(max_length=64, unique=True)

    # ── Parties ─────────────────────────────────────────────────────────────
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
    )
    merchant = models.ForeignKey(
        "accounts.MerchantProfile",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
    )

    # ── Core financials ─────────────────────────────────────────────────────
    amount   = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    occurred_at = models.DateTimeField(help_text="When the transaction took place.")

    # ── Product & card (IEEE-CIS ProductCD / card1-card6) ───────────────────
    product_type    = models.CharField(max_length=8,  blank=True, help_text="ProductCD: W H C S R")
    card_number_bin = models.CharField(max_length=16, blank=True, help_text="card1 — first digits of card number")
    card_expiry     = models.CharField(max_length=8,  blank=True, help_text="card2 — expiry info")
    card_cvv_result = models.CharField(max_length=8,  blank=True, help_text="card3 — CVV check result")
    card_type       = models.CharField(max_length=32, blank=True, help_text="card4: debit/credit")
    card_network    = models.CharField(max_length=32, blank=True, help_text="card5: Visa/MC/Discover/Amex")
    card_bank       = models.CharField(max_length=64, blank=True, help_text="card6 — issuing bank")

    # ── Email domains (IEEE-CIS P_emaildomain / R_emaildomain) ──────────────
    p_email_domain = models.CharField(max_length=128, blank=True, help_text="Purchaser email domain")
    r_email_domain = models.CharField(max_length=128, blank=True, help_text="Recipient email domain")

    # ── Address & distance ───────────────────────────────────────────────────
    addr1 = models.IntegerField(null=True, blank=True, help_text="Billing zip code")
    addr2 = models.IntegerField(null=True, blank=True, help_text="Billing country code")
    dist1 = models.FloatField(null=True, blank=True,   help_text="Distance between card & billing address")
    dist2 = models.FloatField(null=True, blank=True,   help_text="Distance between card & billing zip")

    # ── Network / device ────────────────────────────────────────────────────
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=256, blank=True)

    # ── IEEE-CIS aggregate features (stored as JSON to avoid 300+ columns) ──
    # C1-C15: count-based features (e.g., # of addresses linked to the card)
    c_features = models.JSONField(null=True, blank=True, help_text="C1–C15 count features")
    # D1-D15: timedelta features (e.g., days since last transaction)
    d_features = models.JSONField(null=True, blank=True, help_text="D1–D15 timedelta features")
    # M1-M9:  match features (T/F/NaN — name on card vs address match, etc.)
    m_features = models.JSONField(null=True, blank=True, help_text="M1–M9 boolean match features")
    # V1-V339: Vesta proprietary engineered features (anonymized)
    v_features = models.JSONField(null=True, blank=True, help_text="V1–V339 Vesta anonymized features")

    # ── ML / rule output ─────────────────────────────────────────────────────
    fraud_score      = models.FloatField(null=True, blank=True, help_text="0–1 probability of fraud")
    flag_layer       = models.CharField(max_length=8, choices=FlagLayer.choices, default=FlagLayer.NONE)
    model_version    = models.CharField(max_length=64, blank=True, help_text="Identifier of the model that scored this")
    feature_snapshot = models.JSONField(null=True, blank=True, help_text="Input feature values used to produce fraud_score")

    # ── Review status ────────────────────────────────────────────────────────
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["fraud_score"]),
            models.Index(fields=["flag_layer"]),
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["merchant"]),
        ]

    def __str__(self):
        return "%s | %s %s | %s" % (self.transaction_id, self.amount, self.currency, self.status)


class AnalystDecision(models.Model):
    """
    Analyst review decision for a transaction. At most one per transaction —
    absence means the transaction hasn't been reviewed yet.
    """

    class Decision(models.TextChoices):
        APPROVED     = "approved",     "Approved"
        DECLINED     = "declined",     "Declined"
        UNDER_REVIEW = "under_review", "Escalate for Further Review"

    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="analyst_decision"
    )
    analyst = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="decisions",
        limit_choices_to={"role": "analyst"},
    )
    decision   = models.CharField(max_length=16, choices=Decision.choices)
    rationale  = models.TextField(blank=True, help_text="Analyst notes justifying the decision")
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Analyst Decision"
        verbose_name_plural = "Analyst Decisions"

    def __str__(self):
        return "%s → %s by %s" % (self.transaction_id, self.decision, self.analyst)
