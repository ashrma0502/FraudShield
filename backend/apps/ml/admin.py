from django.contrib import admin

from .models import MLModel, PredictionLog, ThresholdConfig


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    list_display  = ["value", "updated_by", "rationale"]
    search_fields = ["rationale", "updated_by__email"]


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
    readonly_fields = ["created_at"]
