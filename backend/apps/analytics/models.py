from django.db import models


class DailyStats(models.Model):
    """Pre-aggregated daily stats for the analytics dashboard."""

    date = models.DateField(unique=True)
    total_transactions = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    flagged_count = models.IntegerField(default=0)
    blocked_count = models.IntegerField(default=0)
    cleared_count = models.IntegerField(default=0)
    avg_fraud_score = models.FloatField(null=True, blank=True)
    max_fraud_score = models.FloatField(null=True, blank=True)
    top_flagged_merchant = models.CharField(max_length=128, blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Daily Stats"
        verbose_name_plural = "Daily Stats"

    def __str__(self):
        return "Stats %s: %s txns, %s flagged" % (self.date, self.total_transactions, self.flagged_count)
