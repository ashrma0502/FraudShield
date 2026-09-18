from datetime import timedelta

from django.db.models import Avg, Count, Max, Q, Sum
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAnalystOrAdmin
from apps.transactions.models import Transaction

from .models import DailyStats
from .serializers import DailyStatsSerializer


class DailyStatsListView(generics.ListAPIView):
    """Paginated list of pre-aggregated daily stats (analyst/admin only)."""
    queryset           = DailyStats.objects.all()
    serializer_class   = DailyStatsSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsAnalystOrAdmin])
def dashboard_summary(request):
    """Aggregated transaction summary for the past 30 days (analyst/admin only)."""
    since = timezone.now() - timedelta(days=30)
    qs    = Transaction.objects.filter(submitted_at__gte=since)

    agg = qs.aggregate(
        total           = Count("id"),
        total_amount    = Sum("amount"),
        avg_fraud_score = Avg("fraud_score"),
        max_fraud_score = Max("fraud_score"),
        flagged         = Count("id", filter=Q(status="under_review")),
        blocked         = Count("id", filter=Q(status="declined")),
    )

    return Response({
        "period_days":        30,
        "total_transactions": agg["total"],
        "total_amount":       str(agg["total_amount"] or 0),
        "avg_fraud_score":    round(agg["avg_fraud_score"] or 0, 4),
        "max_fraud_score":    round(agg["max_fraud_score"] or 0, 4),
        "under_review_count": agg["flagged"],
        "declined_count":     agg["blocked"],
    })
