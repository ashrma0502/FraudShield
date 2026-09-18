from rest_framework import serializers

from .models import AnalystDecision, Transaction


class TransactionSubmitSerializer(serializers.ModelSerializer):
    """Customer-facing: system fills customer, status, and fraud fields."""

    class Meta:
        model  = Transaction
        fields = ["id", "amount", "submitted_at"]
        read_only_fields = ["id"]


class TransactionReadSerializer(serializers.ModelSerializer):
    """Full read-only representation for analysts/admins."""
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    merchant_name  = serializers.CharField(source="merchant.business_name", read_only=True)
    analyst_decision = serializers.SerializerMethodField()

    class Meta:
        model  = Transaction
        fields = "__all__"

    def get_analyst_decision(self, obj):
        try:
            d = obj.analyst_decision
            return {
                "analyst":  d.analyst.email if d.analyst else None,
                "decision": d.decision,
            }
        except AnalystDecision.DoesNotExist:
            return None


class MerchantTransactionSerializer(serializers.ModelSerializer):
    """Merchant-facing: exposes outcome fields only."""

    class Meta:
        model  = Transaction
        fields = ["id", "amount", "submitted_at", "status", "fraud_score", "flagged_by"]
        read_only_fields = fields


class AnalystDecisionSerializer(serializers.ModelSerializer):
    """Analyst decision creation; analyst is set server-side from the request."""

    class Meta:
        model  = AnalystDecision
        fields = ["id", "transaction", "decision"]
        read_only_fields = ["id"]
