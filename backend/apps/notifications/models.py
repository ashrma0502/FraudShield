import uuid

from django.db import models


class NotificationLog(models.Model):
    """Audit log of dispatched notification events."""

    class Urgency(models.TextChoices):
        LOW      = "LOW",      "Low"
        MEDIUM   = "MEDIUM",   "Medium"
        HIGH     = "HIGH",     "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        SENT   = "sent",   "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=64, default="analyst_review_alert")
    urgency = models.CharField(max_length=16, choices=Urgency.choices, default=Urgency.HIGH)
    recipient = models.CharField(max_length=512)
    subject = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SENT)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"

    def __str__(self):
        return "[%s] %s to %s" % (self.urgency, self.subject, self.recipient)

