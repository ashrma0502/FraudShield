from rest_framework import serializers

from .models import MLModel, PredictionLog, ThresholdConfig


class ThresholdConfigSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.EmailField(source="changed_by.email", read_only=True)

    class Meta:
        model  = ThresholdConfig
        fields = ["id", "name", "value", "changed_by_email", "changed_at", "rationale"]
        read_only_fields = ["id", "changed_by_email", "changed_at"]


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
    """Input schema for the real-time prediction endpoint."""
    transaction_id     = serializers.CharField(max_length=64)
    amount             = serializers.FloatField()
    ip_address         = serializers.IPAddressField(required=False, allow_blank=True)
    device_info        = serializers.CharField(max_length=256, required=False, allow_blank=True)
    device_fingerprint = serializers.CharField(max_length=256, required=False, allow_blank=True)
    occurred_at        = serializers.DateTimeField()
