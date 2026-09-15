from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminRegisterView,
    AnalystRegisterView,
    CustomerRegisterView,
    CustomTokenObtainPairView,
    MerchantRegisterView,
    MeView,
)

app_name = "accounts"

urlpatterns = [
    # Public registration (customer & merchant self-register)
    path("register/customer/", CustomerRegisterView.as_view(), name="register-customer"),
    path("register/merchant/", MerchantRegisterView.as_view(), name="register-merchant"),
    # Admin-only registration (analyst & admin accounts)
    path("register/analyst/", AnalystRegisterView.as_view(),  name="register-analyst"),
    path("register/admin/",   AdminRegisterView.as_view(),    name="register-admin"),
    # JWT auth
    path("token/",         CustomTokenObtainPairView.as_view(), name="token-obtain"),
    path("token/refresh/", TokenRefreshView.as_view(),          name="token-refresh"),
    # Profile
    path("me/", MeView.as_view(), name="me"),
]
