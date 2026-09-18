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
                  "password", "password_confirm"]

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

    class Meta(_BaseRegisterSerializer.Meta):
        fields = _BaseRegisterSerializer.Meta.fields + ["business_name"]

    def create(self, validated_data):
        business_name = validated_data.pop("business_name")
        user = self._create_user(validated_data, User.Role.MERCHANT)
        MerchantProfile.objects.create(user=user, business_name=business_name)
        return user

    def to_representation(self, instance):
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
                  "role", "date_joined"]
        read_only_fields = ["id", "role", "date_joined"]
