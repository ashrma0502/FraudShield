from django.contrib import admin

from .models import AnalystDecision, Transaction


class AnalystDecisionInline(admin.StackedInline):
    model      = AnalystDecision
    extra      = 0
    can_delete = False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ["id", "amount", "status", "fraud_score", "flagged_by", "model_version", "submitted_at"]
    list_filter   = ["status", "flagged_by"]
    search_fields = ["id", "customer__email", "merchant__business_name"]
    ordering      = ["-submitted_at"]
    readonly_fields = ["fraud_score", "flagged_by", "model_version", "feature_snapshot"]
    inlines       = [AnalystDecisionInline]

    fieldsets = (
        ("Parties",    {"fields": ("customer", "merchant")}),
        ("Financials", {"fields": ("amount", "submitted_at", "status")}),
        ("ML Output",  {"fields": ("fraud_score", "flagged_by", "model_version", "feature_snapshot")}),
    )


@admin.register(AnalystDecision)
class AnalystDecisionAdmin(admin.ModelAdmin):
    list_display  = ["transaction", "analyst", "decision"]
    list_filter   = ["decision"]
    search_fields = ["analyst__email"]
