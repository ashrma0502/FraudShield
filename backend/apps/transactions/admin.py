from django.contrib import admin

from .models import AnalystDecision, Transaction


class AnalystDecisionInline(admin.StackedInline):
    """Show the analyst review inline on the Transaction detail page."""
    model  = AnalystDecision
    extra  = 0
    readonly_fields = ["decided_at"]
    can_delete = False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display   = ["transaction_id", "amount", "currency", "status",
                      "fraud_score", "flag_layer", "model_version", "occurred_at"]
    list_filter    = ["status", "flag_layer", "currency", "product_type"]
    search_fields  = ["transaction_id", "customer__email", "merchant__business_name",
                      "p_email_domain", "r_email_domain"]
    ordering       = ["-occurred_at"]
    readonly_fields = ["fraud_score", "flag_layer", "model_version",
                       "feature_snapshot", "created_at", "updated_at"]
    inlines        = [AnalystDecisionInline]

    fieldsets = (
        ("Identity",    {"fields": ("transaction_id", "status")}),
        ("Parties",     {"fields": ("customer", "merchant")}),
        ("Financials",  {"fields": ("amount", "currency", "occurred_at")}),
        ("Card & Product", {"fields": ("product_type", "card_number_bin", "card_expiry",
                                       "card_cvv_result", "card_type", "card_network", "card_bank")}),
        ("Email & Address", {"fields": ("p_email_domain", "r_email_domain",
                                        "addr1", "addr2", "dist1", "dist2")}),
        ("Device",      {"fields": ("ip_address", "device_info")}),
        ("IEEE-CIS Features", {"classes": ("collapse",),
                               "fields": ("c_features", "d_features", "m_features", "v_features")}),
        ("ML Output",   {"fields": ("fraud_score", "flag_layer", "model_version", "feature_snapshot")}),
        ("Timestamps",  {"fields": ("created_at", "updated_at")}),
    )


@admin.register(AnalystDecision)
class AnalystDecisionAdmin(admin.ModelAdmin):
    list_display   = ["transaction", "analyst", "decision", "decided_at"]
    list_filter    = ["decision"]
    search_fields  = ["transaction__transaction_id", "analyst__email"]
    readonly_fields = ["decided_at"]
