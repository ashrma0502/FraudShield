from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import MerchantProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ["username", "email", "role", "is_staff", "date_joined"]
    list_filter   = ["role", "is_staff", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("FraudShield", {"fields": ("role", "phone")}),
    )


@admin.register(MerchantProfile)
class MerchantProfileAdmin(admin.ModelAdmin):
    list_display  = ["business_name", "user", "business_type", "country", "created_at"]
    search_fields = ["business_name", "user__email"]
    list_filter   = ["business_type", "country"]
    readonly_fields = ["created_at"]
