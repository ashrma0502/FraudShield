from rest_framework import filters, generics, permissions

from apps.accounts.permissions import (
    IsAnalyst,
    IsAnalystOrAdmin,
    IsCustomer,
    IsMerchant,
)

from .models import Transaction
from .serializers import (
    AnalystDecisionSerializer,
    MerchantTransactionSerializer,
    TransactionReadSerializer,
    TransactionSubmitSerializer,
)


class TransactionSubmitView(generics.CreateAPIView):
    """Customers submit a transaction for fraud screening."""
    serializer_class   = TransactionSubmitSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)


class ReviewQueueView(generics.ListAPIView):
    """Analysts/Admins: paginated pending/under-review transactions."""
    serializer_class   = TransactionReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ["fraud_score", "occurred_at", "status"]
    ordering           = ["-fraud_score"]

    def get_queryset(self):
        qs = Transaction.objects.filter(
            status__in=["pending", "under_review"]
        ).select_related("customer", "merchant")
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class TransactionDetailView(generics.RetrieveAPIView):
    """Analysts/Admins: retrieve any transaction by its transaction_id."""
    serializer_class   = TransactionReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]
    queryset           = Transaction.objects.select_related("customer", "merchant")
    lookup_field       = "transaction_id"


class MerchantTransactionListView(generics.ListAPIView):
    """Merchants: view outcomes for their own transactions only."""
    serializer_class   = MerchantTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsMerchant]
    filter_backends    = [filters.OrderingFilter]
    ordering           = ["-occurred_at"]

    def get_queryset(self):
        try:
            profile = self.request.user.merchant_profile
        except Exception:
            return Transaction.objects.none()
        return Transaction.objects.filter(merchant=profile)


class AnalystDecisionCreateView(generics.CreateAPIView):
    """Analysts record a decision (one per transaction); mirrors status onto the transaction."""
    serializer_class   = AnalystDecisionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalyst]

    def perform_create(self, serializer):
        decision = serializer.save(analyst=self.request.user)
        txn = decision.transaction
        txn.status = decision.decision
        txn.save(update_fields=["status", "updated_at"])
