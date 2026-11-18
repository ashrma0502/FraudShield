# FraudShield Revision History

This document records architectural decisions, database schema migrations, pipeline adaptations, and offline retraining audits for the FraudShield fraud prevention engine.

---

## Schema Revision & Offline Retraining Isolation

### 1. Context & Motivation
Held-out test benchmark data from the IEEE-CIS test split was previously submitted through the simulation endpoint (`/api/v1/transactions/simulate/`) for validation and demonstration. To ensure complete scientific validity during model retraining on live production data (Y), replayed benchmark rows must never contaminate analyst-labeled training data.

### 2. Schema Changes
- **Model**: `apps.transactions.models.Transaction`
- **Field Added**: `source = models.CharField(max_length=16, choices=[("live", "Live"), ("replay", "Replay")], null=True, blank=True, db_index=True)`
- **Migration**: `0004_transaction_source.py`
- **Data Backfill Migration**: `0005_backfill_transaction_source.py`
  - Scans all existing unclassified transactions.
  - Matches transaction amounts, card networks, and customer account prefixes against `notebooks/data/held_out_test_sample.csv`.
  - Flags matching benchmark records as `source='replay'`.
  - Labels organic customer and merchant payment activity as `source='live'`.

### 3. Pipeline & Ingestion Updates
- **`scripts/replay_test_transactions.py`**: Updated `row_to_payload()` to explicitly tag all simulated benchmark requests with `"source": "replay"`.
- **`apps.transactions.views.TransactionSimulateView`**: Enforces `source='replay'` for replay accounts and simulation runs unless authenticated as a live organic customer.
- **`apps.transactions.views.TransactionSubmitView`**: Guarantees all organic customer payment submissions are stamped with `source='live'`.

### 4. Retraining Isolation Guarantees
- The offline retraining pipeline (`apps.ml.management.commands.retrain_model`) strictly filters on:
  ```python
  Transaction.objects.filter(
      source=Transaction.Source.LIVE,
      analyst_decision__isnull=False
  )
  ```
- Any transaction marked `source='replay'` or missing an explicit human `AnalystDecision` record is strictly excluded from Y.

