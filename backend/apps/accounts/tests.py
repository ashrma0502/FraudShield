"""
Tests for auth endpoints (registration, login, token) and the
role-permission boundaries on all protected routes.
"""
import pytest
from rest_framework import status

from apps.accounts.models import MerchantProfile, User

# ── Registration ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerRegistration:
    url = "/api/v1/accounts/register/customer/"

    def test_register_success(self, api_client):
        res = api_client.post(self.url, {
            "username": "newcustomer", "email": "new@test.com",
            "password": "securepass1", "password_confirm": "securepass1",
        })
        assert res.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(username="newcustomer", role=User.Role.CUSTOMER).exists()

    def test_password_mismatch_rejected(self, api_client):
        res = api_client.post(self.url, {
            "username": "c2", "email": "c2@test.com",
            "password": "pass1111", "password_confirm": "pass9999",
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_short_password_rejected(self, api_client):
        res = api_client.post(self.url, {
            "username": "c3", "email": "c3@test.com",
            "password": "short", "password_confirm": "short",
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMerchantRegistration:
    url = "/api/v1/accounts/register/merchant/"

    def test_register_creates_profile(self, api_client):
        res = api_client.post(self.url, {
            "username": "newmerchant", "email": "merch@test.com",
            "password": "securepass1", "password_confirm": "securepass1",
            "business_name": "Shop Ltd", "business_type": "retail",
        })
        assert res.status_code == status.HTTP_201_CREATED
        user = User.objects.get(username="newmerchant")
        assert user.role == User.Role.MERCHANT
        assert MerchantProfile.objects.filter(user=user, business_name="Shop Ltd").exists()


@pytest.mark.django_db
class TestPrivilegedRegistration:
    """Analyst/Admin registration requires an authenticated admin."""

    def test_analyst_register_requires_admin(self, api_client):
        res = api_client.post("/api/v1/accounts/register/analyst/", {
            "username": "a1", "email": "a1@test.com",
            "password": "securepass1", "password_confirm": "securepass1",
        })
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_analyst_register_by_non_admin_forbidden(self, customer_client):
        res = customer_client.post("/api/v1/accounts/register/analyst/", {
            "username": "a2", "email": "a2@test.com",
            "password": "securepass1", "password_confirm": "securepass1",
        })
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_analyst_register_by_admin_succeeds(self, admin_client):
        res = admin_client.post("/api/v1/accounts/register/analyst/", {
            "username": "a3", "email": "a3@test.com",
            "password": "securepass1", "password_confirm": "securepass1",
        })
        assert res.status_code == status.HTTP_201_CREATED
        assert User.objects.get(username="a3").role == User.Role.ANALYST

    def test_admin_register_by_admin_succeeds(self, admin_client):
        res = admin_client.post("/api/v1/accounts/register/admin/", {
            "username": "adm2", "email": "adm2@test.com",
            "password": "securepass1", "password_confirm": "securepass1",
        })
        assert res.status_code == status.HTTP_201_CREATED


# ── Login / JWT ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/accounts/token/"

    def test_login_returns_tokens(self, customer):
        from rest_framework.test import APIClient
        res = APIClient().post(self.url, {
            "username": customer.username, "password": "testpass123"
        })
        assert res.status_code == status.HTTP_200_OK
        assert "access" in res.data and "refresh" in res.data

    def test_token_contains_role(self, customer):
        import jwt
        from rest_framework.test import APIClient
        res = APIClient().post(self.url, {
            "username": customer.username, "password": "testpass123"
        })
        payload = jwt.decode(
            res.data["access"],
            options={"verify_signature": False},
        )
        assert payload["role"] == User.Role.CUSTOMER

    def test_wrong_password_rejected(self, customer):
        from rest_framework.test import APIClient
        res = APIClient().post(self.url, {
            "username": customer.username, "password": "wrongpassword"
        })
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ── Profile (me/) ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMeEndpoint:
    url = "/api/v1/accounts/me/"

    def test_unauthenticated_denied(self, api_client):
        assert api_client.get(self.url).status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_returns_profile(self, customer_client, customer):
        res = customer_client.get(self.url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["username"] == customer.username
        assert res.data["role"] == User.Role.CUSTOMER

    def test_role_is_read_only(self, customer_client):
        res = customer_client.patch(self.url, {"role": "admin"})
        assert res.status_code == status.HTTP_200_OK
        # Role must not have changed
        from apps.accounts.models import User as U
        assert U.objects.get(username="customer1").role == User.Role.CUSTOMER
