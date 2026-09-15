from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("daily/", views.DailyStatsListView.as_view(), name="daily-stats"),
    path("summary/", views.dashboard_summary, name="summary"),
]
