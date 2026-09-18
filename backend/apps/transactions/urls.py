from django.urls import path

from . import views

app_name = "transactions"

urlpatterns = [
    # Customer: submit a transaction
    path("submit/",       views.TransactionSubmitView.as_view(),       name="submit"),
    # Merchant: view their own transaction outcomes
    path("mine/",         views.MerchantTransactionListView.as_view(), name="mine"),
    # Analyst/Admin: review queue
    path("review-queue/", views.ReviewQueueView.as_view(),             name="review-queue"),
    # Analyst: record a decision (must be above <str:transaction_id>/ to avoid catch-all)
    path("decide/",       views.AnalystDecisionCreateView.as_view(),   name="decide"),
    # Analyst/Admin: transaction detail by UUID
    path("<uuid:pk>/", views.TransactionDetailView.as_view(), name="detail"),
]
