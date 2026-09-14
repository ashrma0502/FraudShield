from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with role-based access (Customer, Merchant, Analyst, Admin)."""

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        MERCHANT = "merchant", "Merchant"
        ANALYST  = "analyst",  "Analyst"
        ADMIN    = "admin",    "Admin"

    role  = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email or self.username


class MerchantProfile(models.Model):
    """Business profile for users with the Merchant role."""

    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name="merchant_profile")
    business_name = models.CharField(max_length=128)
    business_type = models.CharField(max_length=64, blank=True)
    website       = models.URLField(blank=True)
    country       = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Merchant Profile"
        verbose_name_plural = "Merchant Profiles"

    def __str__(self):
        return "%s (%s)" % (self.business_name, self.user.email)
