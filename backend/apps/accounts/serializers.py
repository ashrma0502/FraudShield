from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import MerchantProfile

User = get_user_model()


class _BaseRegisterSerializer(serializers.ModelSerializer):
    """Common registration fields; subclasses fix the role."""
    password         = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ["username", "email", "first_name", "last_name",
                  "phone", "password", "password_confirm"]

    def validate(self, data):
        if data["password"] != data.pop("password_confirm"):
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def _create_user(self, validated_data, role):
        return User.objects.create_user(role=role, **validated_data)


class CustomerRegisterSerializer(_BaseRegisterSerializer):
    """Registration for the Customer role."""

    def create(self, validated_data):
        return self._create_user(validated_data, User.Role.CUSTOMER)


class MerchantRegisterSerializer(_BaseRegisterSerializer):
    """Registration for the Merchant role — also creates a MerchantProfile."""
    business_name = serializers.CharField(max_length=128)
    business_type = serializers.CharField(max_length=64, required=False, allow_blank=True)
    website       = serializers.URLField(required=False, allow_blank=True)
    country       = serializers.CharField(max_length=2, required=False, allow_blank=True)

    class Meta(_BaseRegisterSerializer.Meta):
        fields = _BaseRegisterSerializer.Meta.fields + [
            "business_name", "business_type", "website", "country"
        ]

    def create(self, validated_data):
        profile_data = {
            "business_name": validated_data.pop("business_name"),
            "business_type": validated_data.pop("business_type", ""),
            "website":       validated_data.pop("website", ""),
            "country":       validated_data.pop("country", ""),
        }
        user = self._create_user(validated_data, User.Role.MERCHANT)
        MerchantProfile.objects.create(user=user, **profile_data)
        return user

    def to_representation(self, instance):
        # business_name lives on MerchantProfile, not User; delegate to UserSerializer
        return UserSerializer(instance).data


class AnalystRegisterSerializer(_BaseRegisterSerializer):
    """Registration for the Analyst role (admin-only)."""

    def create(self, validated_data):
        return self._create_user(validated_data, User.Role.ANALYST)


class AdminRegisterSerializer(_BaseRegisterSerializer):
    """Registration for the Admin role (admin-only)."""

    def create(self, validated_data):
        return self._create_user(validated_data, User.Role.ADMIN)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["id", "username", "email", "first_name", "last_name",
                  "role", "phone", "date_joined"]
        read_only_fields = ["id", "role", "date_joined"]
