from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, models
from django.utils import timezone
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import MerchantProfile, User
from apps.accounts.permissions import (
    IsAnalyst,
    IsAnalystOrAdmin,
    IsCustomer,
    IsMerchant,
)
from apps.ml.models import ThresholdConfig
from apps.ml.services import screen_transaction
from apps.notifications.services import evaluate_and_notify_transaction

from .models import Transaction
from .serializers import (
    AnalystDecisionSerializer,
    MerchantOptionSerializer,
    MerchantTransactionSerializer,
    TransactionReadSerializer,
    TransactionSimulateSerializer,
    TransactionSubmitSerializer,
)


class TransactionSubmitView(generics.CreateAPIView):
    """Customers submit a transaction for fraud screening."""
    serializer_class   = TransactionSubmitSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def perform_create(self, serializer):
        txn = serializer.save(customer=self.request.user, source=Transaction.Source.LIVE)
        res = screen_transaction({
            "transaction_id": txn.id,
            "amount": float(txn.amount),
            "submitted_at": txn.submitted_at,
            "customer_id": self.request.user.id,
        }, customer=self.request.user)

        txn.fraud_score = res["fraud_score"]
        txn.flagged_by = res["flagged_by"]
        txn.model_version = res.get("layers", {}).get("model", {}).get("model_version", "1.0.0")
        txn.feature_snapshot = {
            "TransactionAmt": float(txn.amount),
            "card4": "visa",
            "card6": "credit",
            "ProductCD": "W",
            "P_emaildomain": "gmail.com",
            "R_emaildomain": "gmail.com",
        }

        threshold_cfg = ThresholdConfig.objects.first()
        auto_block = threshold_cfg.auto_block_threshold if threshold_cfg else 0.90
        flag_t = threshold_cfg.flag_threshold if threshold_cfg else 0.75

        if txn.fraud_score >= auto_block:
            txn.status = Transaction.Status.DECLINED
        elif txn.fraud_score >= flag_t:
            txn.status = Transaction.Status.UNDER_REVIEW
        else:
            txn.status = Transaction.Status.APPROVED

        txn.save(update_fields=["fraud_score", "flagged_by", "status", "model_version", "feature_snapshot", "source"])
        evaluate_and_notify_transaction(txn)


class ReviewQueueView(generics.ListAPIView):
    """Analysts/Admins: paginated pending/under-review transactions."""
    serializer_class   = TransactionReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ["fraud_score", "submitted_at", "status"]
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
    """Analysts/Admins: retrieve any transaction by its UUID."""
    serializer_class   = TransactionReadSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]
    queryset           = Transaction.objects.select_related("customer", "merchant")
    lookup_field       = "pk"


class MerchantTransactionListView(generics.ListAPIView):
    """Merchants: view outcomes for their own transactions only."""
    serializer_class   = MerchantTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsMerchant]
    filter_backends    = [filters.OrderingFilter]
    ordering           = ["-submitted_at"]

    def get_queryset(self):
        try:
            profile = self.request.user.merchant_profile
        except (AttributeError, ObjectDoesNotExist):
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
        txn.save(update_fields=["status"])


class TransactionSimulateView(APIView):
    """Mock payment gateway simulation endpoint for real-time fraud evaluation."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        merchants = MerchantProfile.objects.all().order_by("business_name")
        merchant_data = MerchantOptionSerializer(merchants, many=True).data

        threshold_cfg = ThresholdConfig.objects.first()
        auto_block = threshold_cfg.auto_block_threshold if threshold_cfg else 0.90
        flag_t = threshold_cfg.flag_threshold if threshold_cfg else 0.75

        presets = [
            {
                "name": "Legitimate Morning Coffee ($4.50)",
                "amount": 4.50,
                "card4": "visa",
                "card6": "debit",
                "product_cd": "W",
                "p_emaildomain": "gmail.com",
                "r_emaildomain": "gmail.com",
            },
            {
                "name": "High-Risk Luxury Watch ($6,800.00)",
                "amount": 6800.00,
                "card4": "discover",
                "card6": "credit",
                "product_cd": "W",
                "p_emaildomain": "protonmail.com",
                "r_emaildomain": "anonymous.com",
            },
            {
                "name": "Medium-Risk Electronics ($1,499.99)",
                "amount": 1499.99,
                "card4": "mastercard",
                "card6": "credit",
                "product_cd": "C",
                "p_emaildomain": "yahoo.com",
                "r_emaildomain": "gmail.com",
            },
        ]

        return Response({
            "merchants": merchant_data,
            "thresholds": {
                "flag_threshold": flag_t,
                "auto_block_threshold": auto_block,
            },
            "presets": presets,
        })

    def post(self, request):
        serializer = TransactionSimulateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        amount = float(data["amount"])
        submitted_at = data.get("submitted_at") or timezone.now()
        product_cd = data.get("product_cd") or "W"
        card4 = data.get("card4") or "visa"
        card6 = data.get("card6") or "credit"
        p_emaildomain = data.get("p_emaildomain") or "gmail.com"
        r_emaildomain = data.get("r_emaildomain") or "gmail.com"
        feature_snapshot = data.get("feature_snapshot") or {}

        # Resolve merchant
        merchant_obj = None
        merchant_val = data.get("merchant_id") or data.get("merchant")
        if merchant_val:
            try:
                merchant_obj = MerchantProfile.objects.filter(
                    models.Q(id=merchant_val) | models.Q(business_name__iexact=str(merchant_val))
                ).first()
            except (ValueError, TypeError, ValidationError, DatabaseError):
                merchant_obj = MerchantProfile.objects.filter(business_name__iexact=str(merchant_val)).first()

        if not merchant_obj:
            merchant_obj = MerchantProfile.objects.first()

        if not merchant_obj:
            sim_user, _ = User.objects.get_or_create(
                username="sim_gateway_merchant",
                defaults={"role": User.Role.MERCHANT, "email": "merchant@simulated.local"},
            )
            merchant_obj, _ = MerchantProfile.objects.get_or_create(
                user=sim_user,
                defaults={"business_name": "Simulated Gateway Merchant"},
            )

        # Resolve customer
        customer_obj = None
        if request.user and request.user.is_authenticated:
            customer_obj = request.user
        else:
            cust_val = data.get("customer_id")
            if cust_val:
                try:
                    customer_obj = User.objects.filter(
                        models.Q(id=cust_val) | models.Q(username=cust_val) | models.Q(email=cust_val)
                    ).first()
                except (ValueError, TypeError, ValidationError, DatabaseError):
                    customer_obj = None

                if not customer_obj and str(cust_val).strip():
                    safe_username = str(cust_val).strip()[:140]
                    customer_obj, _ = User.objects.get_or_create(
                        username=safe_username,
                        defaults={
                            "role": User.Role.CUSTOMER,
                            "email": "%s@simulated.local" % safe_username,
                        },
                    )

            if not customer_obj:
                customer_obj = User.objects.filter(role=User.Role.CUSTOMER).first()

        if not customer_obj:
            customer_obj, _ = User.objects.get_or_create(
                username="sim_gateway_customer",
                defaults={"role": User.Role.CUSTOMER, "email": "customer@simulated.local"},
            )

        screening_input = {
            "amount": amount,
            "submitted_at": submitted_at,
            "customer_id": customer_obj.id if customer_obj else None,
            "product_cd": product_cd,
            "card4": card4,
            "card6": card6,
            "p_emaildomain": p_emaildomain,
            "r_emaildomain": r_emaildomain,
            "feature_snapshot": feature_snapshot,
        }
        res = screen_transaction(screening_input, customer=customer_obj)

        fraud_score = res["fraud_score"]
        threshold_cfg = ThresholdConfig.objects.first()
        auto_block = threshold_cfg.auto_block_threshold if threshold_cfg else 0.90
        flag_t = threshold_cfg.flag_threshold if threshold_cfg else 0.75

        if fraud_score >= auto_block:
            status_val = Transaction.Status.DECLINED
            outcome_val = "declined"
        elif fraud_score >= flag_t:
            status_val = Transaction.Status.UNDER_REVIEW
            outcome_val = "flagged_for_review"
        else:
            status_val = Transaction.Status.APPROVED
            outcome_val = "approved"

        model_version = res.get("layers", {}).get("model", {}).get("model_version", "1.0.0")

        snapshot = {
            "TransactionAmt": amount,
            "card4": card4,
            "card6": card6,
            "product_cd": product_cd,
            "p_emaildomain": p_emaildomain,
            "r_emaildomain": r_emaildomain,
            **feature_snapshot,
        }

        source_in = data.get("source")
        if source_in in [Transaction.Source.LIVE, Transaction.Source.REPLAY]:
            source_val = source_in
        elif customer_obj and (str(customer_obj.username).startswith("card_") or str(customer_obj.username).startswith("replay_")):
            source_val = Transaction.Source.REPLAY
        else:
            source_val = Transaction.Source.LIVE

        txn = Transaction.objects.create(
            customer=customer_obj,
            merchant=merchant_obj,
            amount=amount,
            submitted_at=submitted_at,
            fraud_score=fraud_score,
            status=status_val,
            flagged_by=res["flagged_by"],
            source=source_val,
            model_version=model_version,
            feature_snapshot=snapshot,
        )

        evaluate_and_notify_transaction(txn)

        return Response({
            "transaction_id": str(txn.id),
            "amount": float(txn.amount),
            "merchant": merchant_obj.business_name if merchant_obj else "Simulated Merchant",
            "merchant_id": str(merchant_obj.id) if merchant_obj else None,
            "customer": customer_obj.username if customer_obj else None,
            "status": txn.status,
            "outcome": outcome_val,
            "fraud_score": round(fraud_score, 4),
            "flagged_by": txn.flagged_by,
            "contributing_layer": res["contributing_layer"],
            "rule_flagged": res["rule_flagged"],
            "model_flagged": res["model_flagged"],
            "triggered_rules": res["triggered_rules"],
            "layers": res["layers"],
            "thresholds": {
                "flag_threshold": flag_t,
                "auto_block_threshold": auto_block,
            },
            "submitted_at": txn.submitted_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

