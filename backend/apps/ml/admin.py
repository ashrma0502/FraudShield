from django.contrib import admin

from .models import MLModel, PredictionLog, ThresholdConfig


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    list_display   = ["name", "value", "changed_by", "changed_at", "rationale"]
    list_filter    = ["name"]
    search_fields  = ["name", "rationale", "changed_by__email"]
    readonly_fields = ["changed_at"]
    ordering       = ["-changed_at"]

    def has_change_permission(self, request, obj=None):
        # Enforce append-only in admin — no editing existing rows.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display  = ["name", "version", "algorithm", "is_active", "trained_at", "created_at"]
    list_filter   = ["is_active", "algorithm"]
    search_fields = ["name", "version"]
    readonly_fields = ["created_at"]


@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display  = ["transaction_id", "fraud_score", "is_fraud", "latency_ms", "created_at"]
    list_filter   = ["is_fraud"]
    search_fields = ["transaction_id"]
    readonly_fields = ["created_at"]
