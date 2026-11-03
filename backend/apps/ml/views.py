from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsAnalystOrAdmin

from .models import MLModel, ThresholdConfig
from .serializers import (
    MLModelSerializer,
    PredictionRequestSerializer,
    ThresholdConfigSerializer,
)
from .services import screen_transaction


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
@permission_classes([permissions.IsAuthenticated])
def predict(request):
    """Run rule-based pre-filter and trained classifier for real-time fraud inference."""
    serializer = PredictionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    result = screen_transaction(data, customer=request.user)
    return Response(result, status=status.HTTP_200_OK)
