from django.urls import path

from . import views

app_name = "ml"

urlpatterns = [
    path("models/", views.MLModelListView.as_view(), name="model-list"),
    path("models/<int:pk>/", views.MLModelDetailView.as_view(), name="model-detail"),
    path("thresholds/", views.ThresholdConfigListView.as_view(), name="threshold-list"),
    path("thresholds/add/", views.ThresholdConfigCreateView.as_view(), name="threshold-add"),
    path("predict/", views.predict, name="predict"),
]
