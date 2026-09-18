from rest_framework import serializers

from .models import MLModel, PredictionLog, ThresholdConfig


class ThresholdConfigSerializer(serializers.ModelSerializer):
    updated_by_email = serializers.EmailField(source="updated_by.email", read_only=True)

    class Meta:
        model  = ThresholdConfig
        fields = ["id", "value", "updated_by_email", "rationale"]
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
    """Input schema for the real-time prediction endpoint."""
    transaction_id = serializers.UUIDField()
    amount         = serializers.FloatField()
    submitted_at   = serializers.DateTimeField()
