import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.accounts.models import User, MerchantProfile
from apps.transactions.models import Transaction

def seed():
    # 1. Create Analyst
    analyst, _ = User.objects.get_or_create(username='analyst1', email='analyst@example.com', defaults={
        'role': User.Role.ANALYST
    })
    analyst.set_password('password123')
    analyst.save()

    # 2. Create Merchant
    merchant_user, _ = User.objects.get_or_create(username='merchant1', email='merchant@example.com', defaults={
        'role': User.Role.MERCHANT
    })
    merchant_user.set_password('password123')
    merchant_user.save()

    merchant_profile, _ = MerchantProfile.objects.get_or_create(user=merchant_user, defaults={
        'business_name': 'Acme Electronics'
    })

    # 3. Create Customer
    customer, _ = User.objects.get_or_create(username='customer1', email='customer@example.com', defaults={
        'role': User.Role.CUSTOMER
    })
    customer.set_password('password123')
    customer.save()

    # 4. Create Transactions
    if Transaction.objects.count() == 0:
        now = timezone.now()
        txs = [
            Transaction(
                customer=customer,
                merchant=merchant_profile,
                amount='1499.99',
                submitted_at=now - timedelta(minutes=10),
                status=Transaction.Status.UNDER_REVIEW,
                fraud_score=0.89,
                flagged_by=Transaction.FlaggedBy.MODEL,
                feature_snapshot={"device_changes": 2, "ip_distance": 500}
            ),
            Transaction(
                customer=customer,
                merchant=merchant_profile,
                amount='45.00',
                submitted_at=now - timedelta(minutes=35),
                status=Transaction.Status.APPROVED,
                fraud_score=0.12,
                flagged_by=Transaction.FlaggedBy.NONE,
                feature_snapshot={"device_changes": 0, "ip_distance": 5}
            ),
            Transaction(
                customer=customer,
                merchant=merchant_profile,
                amount='250.00',
                submitted_at=now - timedelta(minutes=120),
                status=Transaction.Status.DECLINED,
                fraud_score=0.95,
                flagged_by=Transaction.FlaggedBy.RULE,
                feature_snapshot={"device_changes": 5, "ip_distance": 2000}
            ),
            Transaction(
                customer=customer,
                merchant=merchant_profile,
                amount='85.50',
                submitted_at=now - timedelta(minutes=5),
                status=Transaction.Status.UNDER_REVIEW,
                fraud_score=0.55,
                flagged_by=Transaction.FlaggedBy.MODEL,
                feature_snapshot={"device_changes": 1, "ip_distance": 150}
            ),
        ]
        Transaction.objects.bulk_create(txs)
        print(f"Created {len(txs)} transactions.")

if __name__ == '__main__':
    seed()
    print("Database seeded successfully. You can login with analyst1 / password123 or merchant1 / password123")
