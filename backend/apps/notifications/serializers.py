from rest_framework import serializers

from .models import NotificationLog


class NotificationLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for notification audit logs."""

    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "transaction",
            "notification_type",
            "urgency",
            "recipient",
            "subject",
            "message",
            "status",
            "sent_at",
        ]
        read_only_fields = fields

