# Custom DRF permission classes — one per role, plus analyst-or-admin composite.

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsCustomer(BasePermission):
    message = "Only customers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.Role.CUSTOMER
        )


class IsMerchant(BasePermission):
    message = "Only merchants can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.Role.MERCHANT
        )


class IsAnalyst(BasePermission):
    message = "Only analysts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.Role.ANALYST
        )


class IsAdmin(BasePermission):
    message = "Only admins can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsAnalystOrAdmin(BasePermission):
    message = "Only analysts or admins can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in (User.Role.ANALYST, User.Role.ADMIN)
        )
