from rest_framework import serializers

from .models import MLModel, PredictionLog, ThresholdConfig


class ThresholdConfigSerializer(serializers.ModelSerializer):
    updated_by_email = serializers.EmailField(source="updated_by.email", read_only=True)

    class Meta:
        model  = ThresholdConfig
        fields = ["id", "auto_block_threshold", "flag_threshold", "updated_by_email", "rationale"]
        read_only_fields = ["id", "updated_by_email"]


class MLModelSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MLModel
        fields = ["id", "name", "version", "algorithm", "description",
                  "metrics", "is_active", "trained_at", "created_at"]
        read_only_fields = ["id", "created_at"]


class PredictionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PredictionLog
        fields = ["id", "ml_model", "transaction_id", "input_features",
                  "fraud_score", "is_fraud", "latency_ms", "created_at"]
        read_only_fields = ["id", "created_at"]


class PredictionRequestSerializer(serializers.Serializer):
    """Input schema for the real-time prediction and screening endpoint."""
    transaction_id   = serializers.UUIDField(required=False)
    amount           = serializers.FloatField(min_value=0.0)
    submitted_at     = serializers.DateTimeField(required=False)
    customer_id      = serializers.CharField(required=False, allow_null=True)
    product_cd       = serializers.CharField(required=False, default="W", max_length=16)
    card4            = serializers.CharField(required=False, default="visa", max_length=32)
    card6            = serializers.CharField(required=False, default="credit", max_length=32)
    p_emaildomain    = serializers.CharField(required=False, default="gmail.com", max_length=64)
    r_emaildomain    = serializers.CharField(required=False, default="gmail.com", max_length=64)
    feature_snapshot = serializers.DictField(required=False, default=dict)
