"""Data migration to backfill Transaction.source field.

Matches transactions against the held-out test sample and marks them as 'replay'.
All other historical transactions are marked as 'live'.
"""

import logging
from pathlib import Path

from django.db import migrations

logger = logging.getLogger(__name__)


def backfill_transaction_sources(apps, schema_editor):
    Transaction = apps.get_model("transactions", "Transaction")

    test_sample_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "notebooks" / "data" / "held_out_test_sample.csv"

    test_signatures = set()
    if test_sample_path.exists():
        import pandas as pd
        try:
            df = pd.read_csv(test_sample_path)
            for _, r in df.iterrows():
                amt = round(float(r["TransactionAmt"]), 2) if "TransactionAmt" in r and pd.notna(r["TransactionAmt"]) else None
                card4 = str(r["card4"]).lower().strip() if "card4" in r and pd.notna(r["card4"]) else None
                if amt is not None:
                    test_signatures.add((amt, card4))
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("Could not parse test sample during migration: %s", exc)

    for txn in Transaction.objects.filter(source__isnull=True):
        is_replay = False
        amt = round(float(txn.amount), 2)

        # Check customer username prefix commonly created during replay runs
        if txn.customer and (
            txn.customer.username.startswith("card_")
            or txn.customer.username.startswith("replay_")
            or txn.customer.username == "sim_gateway_customer"
        ):
            is_replay = True
        elif (amt, None) in test_signatures or any(s[0] == amt for s in test_signatures):
            # Check snapshot for card4 match if available
            snapshot = txn.feature_snapshot or {}
            card4 = str(snapshot.get("card4", "")).lower().strip()
            if (amt, card4) in test_signatures:
                is_replay = True

        txn.source = "replay" if is_replay else "live"
        txn.save(update_fields=["source"])


def reverse_backfill(apps, schema_editor):
    Transaction = apps.get_model("transactions", "Transaction")
    Transaction.objects.all().update(source=None)


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0004_transaction_source"),
    ]

    operations = [
        migrations.RunPython(backfill_transaction_sources, reverse_backfill),
    ]
