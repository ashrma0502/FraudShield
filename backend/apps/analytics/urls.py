from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("daily/", views.DailyStatsListView.as_view(), name="daily-stats"),
    path("summary/", views.dashboard_summary, name="summary"),
    path("model-performance/", views.model_performance_analytics, name="model-performance"),
    path("performance/", views.model_performance_analytics, name="performance"),
]
