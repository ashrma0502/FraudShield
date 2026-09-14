from django.contrib import admin

from .models import DailyStats


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ["date", "total_transactions", "total_amount", "flagged_count", "blocked_count", "avg_fraud_score"]
    ordering = ["-date"]
    readonly_fields = ["computed_at"]
