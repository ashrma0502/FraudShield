from django.db import OperationalError, connection
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAdmin
from .serializers import (
    AdminRegisterSerializer,
    AnalystRegisterSerializer,
    CustomerRegisterSerializer,
    MerchantRegisterSerializer,
    UserSerializer,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"]  = user.role
        token["email"] = user.email
        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login — returns JWT access + refresh tokens with role embedded."""
    serializer_class = CustomTokenObtainPairSerializer


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Returns server status and DB connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError as exc:
        return Response(
            {"status": "degraded", "db": "error: %s" % exc},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ok", "db": "connected"})


class CustomerRegisterView(generics.CreateAPIView):
    serializer_class   = CustomerRegisterSerializer
    permission_classes = [permissions.AllowAny]


class MerchantRegisterView(generics.CreateAPIView):
    serializer_class   = MerchantRegisterSerializer
    permission_classes = [permissions.AllowAny]


class AnalystRegisterView(generics.CreateAPIView):
    """Admin-only: create an analyst account."""
    serializer_class   = AnalystRegisterSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]


class AdminRegisterView(generics.CreateAPIView):
    """Admin-only: create another admin account."""
    serializer_class   = AdminRegisterSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]


class MeView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated user's profile."""
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
