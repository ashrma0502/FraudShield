import uuid

from rest_framework import serializers

from .models import AnalystDecision, Transaction


class TransactionSubmitSerializer(serializers.ModelSerializer):
    """Customer-facing: system fills customer, status, and fraud fields."""

    class Meta:
        model  = Transaction
        fields = [
            "transaction_id", "amount", "currency", "occurred_at",
            "product_type",
            "card_number_bin", "card_expiry", "card_cvv_result",
            "card_type", "card_network", "card_bank",
            "p_email_domain", "r_email_domain",
            "addr1", "addr2", "dist1", "dist2",
            "ip_address", "device_info",
            "c_features", "d_features", "m_features", "v_features",
        ]

    def validate_transaction_id(self, value):
        return value or str(uuid.uuid4())


class TransactionReadSerializer(serializers.ModelSerializer):
    """Full read-only representation for analysts/admins."""
    customer_email   = serializers.EmailField(source="customer.email", read_only=True)
    merchant_name    = serializers.CharField(source="merchant.business_name", read_only=True)
    analyst_decision = serializers.SerializerMethodField()

    class Meta:
        model  = Transaction
        fields = "__all__"

    def get_analyst_decision(self, obj):
        try:
            d = obj.analyst_decision
            return {
                "analyst":    d.analyst.email if d.analyst else None,
                "decision":   d.decision,
                "rationale":  d.rationale,
                "decided_at": d.decided_at,
            }
        except AnalystDecision.DoesNotExist:
            return None


class MerchantTransactionSerializer(serializers.ModelSerializer):
    """Merchant-facing: exposes outcome fields only, hides internal ML data."""

    class Meta:
        model  = Transaction
        fields = [
            "transaction_id", "amount", "currency", "occurred_at",
            "status", "fraud_score", "flag_layer",
        ]
        read_only_fields = [
            "transaction_id", "amount", "currency", "occurred_at",
            "status", "fraud_score", "flag_layer",
        ]


class AnalystDecisionSerializer(serializers.ModelSerializer):
    """Analyst decision creation; analyst is set server-side from the request."""

    class Meta:
        model  = AnalystDecision
        fields = ["id", "transaction", "decision", "rationale", "decided_at"]
        read_only_fields = ["id", "decided_at"]
