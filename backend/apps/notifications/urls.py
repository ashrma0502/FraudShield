from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationLogListView.as_view(), name="notification-list"),
]

