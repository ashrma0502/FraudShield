from rest_framework import generics, permissions

from apps.accounts.permissions import IsAnalystOrAdmin

from .models import NotificationLog
from .serializers import NotificationLogSerializer


class NotificationLogListView(generics.ListAPIView):
    """List recent notification alerts dispatched to analysts."""

    queryset = NotificationLog.objects.select_related("transaction").all()
    serializer_class = NotificationLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAnalystOrAdmin]

