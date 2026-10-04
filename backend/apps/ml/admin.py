from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from .models import MLModel, PredictionLog, ThresholdConfig

class ThresholdConfigForm(forms.ModelForm):
    class Meta:
        model = ThresholdConfig
        fields = ["auto_block_threshold", "flag_threshold", "rationale"]

    def clean_rationale(self):
        rationale = self.cleaned_data.get("rationale")
        if not rationale or not rationale.strip():
            raise ValidationError("A rationale must be provided explaining the reason for this threshold change.")
        return rationale

    def clean(self):
        cleaned_data = super().clean()
        block = cleaned_data.get("auto_block_threshold")
        flag = cleaned_data.get("flag_threshold")
        if block is not None and flag is not None:
            if flag >= block:
                raise ValidationError("Flag threshold must be strictly less than the auto-block threshold.")
        return cleaned_data


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    form = ThresholdConfigForm
    list_display  = ["auto_block_threshold", "flag_threshold", "updated_by", "rationale"]
    search_fields = ["rationale", "updated_by__email"]

    def save_model(self, request, obj, form, change):
        # Even if change is somehow True (e.g., bypass), we force creating a new row
        if change:
            obj.pk = None
        if not obj.updated_by_id:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        # Enforce append-only in the admin interface
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
    readonly_fields = ["created_at"]
