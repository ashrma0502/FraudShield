from django.urls import path

from . import views

app_name = "transactions"

urlpatterns = [
    path("submit/", views.TransactionSubmitView.as_view(), name="submit"),
    path("mine/", views.MerchantTransactionListView.as_view(), name="mine"),
    path("review-queue/", views.ReviewQueueView.as_view(), name="review-queue"),
    path("decide/", views.AnalystDecisionCreateView.as_view(), name="decide"),
    path("<uuid:pk>/", views.TransactionDetailView.as_view(), name="detail"),
]
