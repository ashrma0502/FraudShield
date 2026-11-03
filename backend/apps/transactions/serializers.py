from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import MerchantProfile

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


class MerchantOptionSerializer(serializers.ModelSerializer):
    """Minimal representation of active merchants for simulation dropdowns."""

    class Meta:
        model = MerchantProfile
        fields = ["id", "business_name"]


class TransactionSimulateSerializer(serializers.Serializer):
    """Mock payment gateway simulation input payload."""
    merchant = serializers.CharField(required=False, allow_blank=True, default="")
    merchant_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    submitted_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    card4 = serializers.CharField(max_length=32, required=False, default="visa")
    card6 = serializers.CharField(max_length=32, required=False, default="credit")
    product_cd = serializers.CharField(max_length=16, required=False, default="W")
    p_emaildomain = serializers.CharField(max_length=64, required=False, default="gmail.com")
    r_emaildomain = serializers.CharField(max_length=64, required=False, default="gmail.com")
    customer_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    source = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")
    feature_snapshot = serializers.DictField(required=False, default=dict)

