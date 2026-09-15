from django.urls import path

from . import views

app_name = "ml"

urlpatterns = [
    # ML model registry (analyst/admin)
    path("models/",            views.MLModelListView.as_view(),      name="model-list"),
    path("models/<int:pk>/",   views.MLModelDetailView.as_view(),    name="model-detail"),
    # Threshold config — list history and append new row (admin only)
    path("thresholds/",        views.ThresholdConfigListView.as_view(),  name="threshold-list"),
    path("thresholds/add/",    views.ThresholdConfigCreateView.as_view(), name="threshold-add"),
    # Real-time prediction (admin only)
    path("predict/",           views.predict,                        name="predict"),
]
