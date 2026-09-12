import pytest
from apps.accounts.models import MerchantProfile, User
from apps.transactions.models import Transaction
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


def _make_user(role, username, **kwargs):
    return User.objects.create_user(
        username=username,
        password="testpass123",
        email="%s@test.com" % username,
        role=role,
        **kwargs,
    )


@pytest.fixture
def customer(db):
    return _make_user(User.Role.CUSTOMER, "customer1")


@pytest.fixture
def merchant_user(db):
    user = _make_user(User.Role.MERCHANT, "merchant1")
    MerchantProfile.objects.create(user=user, business_name="Acme Corp")
    return user


@pytest.fixture
def analyst(db):
    return _make_user(User.Role.ANALYST, "analyst1")


@pytest.fixture
def admin_user(db):
    return _make_user(User.Role.ADMIN, "admin1")


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def customer_client(customer):
    return _auth_client(customer)


@pytest.fixture
def merchant_client(merchant_user):
    return _auth_client(merchant_user)


@pytest.fixture
def analyst_client(analyst):
    return _auth_client(analyst)


@pytest.fixture
def admin_client(admin_user):
    return _auth_client(admin_user)


@pytest.fixture
def transaction(db, customer, merchant_user):
    return Transaction.objects.create(
        transaction_id="txn-001",
        customer=customer,
        merchant=merchant_user.merchant_profile,
        amount="250.00",
        currency="USD",
        occurred_at=timezone.now(),
        status=Transaction.Status.PENDING,
        fraud_score=0.85,
        flag_layer=Transaction.FlagLayer.MODEL,
    )
