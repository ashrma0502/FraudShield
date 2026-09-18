import time

import joblib
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsAnalystOrAdmin

from .models import MLModel, PredictionLog, ThresholdConfig
from .serializers import (
    MLModelSerializer,
    PredictionRequestSerializer,
    ThresholdConfigSerializer,
)


class MLModelListView(generics.ListAPIView):
    """List all registered ML models."""
    queryset           = MLModel.objects.all()
    serializer_class   = MLModelSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]


class MLModelDetailView(generics.RetrieveAPIView):
    """Retrieve a single ML model by ID."""
    queryset           = MLModel.objects.all()
    serializer_class   = MLModelSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]


class ThresholdConfigListView(generics.ListAPIView):
    """Full history of fraud-score threshold changes (admin only)."""
    queryset           = ThresholdConfig.objects.all()
    serializer_class   = ThresholdConfigSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]


class ThresholdConfigCreateView(generics.CreateAPIView):
    """Append a new threshold config row; rationale is required (admin only)."""
    serializer_class   = ThresholdConfigSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsAdmin])
def predict(request):
    """Run the active ML model on a transaction and return a fraud score."""
    serializer = PredictionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        active_model = MLModel.objects.get(is_active=True)
    except MLModel.DoesNotExist:
        return Response(
            {"detail": "No active model. Train and activate one first."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    t0          = time.time()
    clf         = joblib.load(active_model.model_file.path)
    # Placeholder feature vector — replace with real feature engineering
    features    = [[data["amount"]]]
    fraud_score = float(clf.predict_proba(features)[0][1])
    latency_ms  = int((time.time() - t0) * 1000)
    is_fraud    = fraud_score >= 0.5

    PredictionLog.objects.create(
        ml_model=active_model,
        transaction_id=data["transaction_id"],
        input_features=data,
        fraud_score=fraud_score,
        is_fraud=is_fraud,
        latency_ms=latency_ms,
    )

    return Response({
        "transaction_id": data["transaction_id"],
        "fraud_score":    round(fraud_score, 4),
        "is_fraud":       is_fraud,
        "latency_ms":     latency_ms,
        "model":          "%s v%s" % (active_model.name, active_model.version),
    })
