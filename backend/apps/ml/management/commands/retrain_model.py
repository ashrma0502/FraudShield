"""Offline retraining management command for IEEE-CIS primary fraud detection model."""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score

from apps.ml.models import MLModel, ThresholdConfig
from apps.ml.services import get_model_bundle
from apps.transactions.models import Transaction
from ml_pipeline.ieee_cis_pipeline import load_and_join_ieee_cis, split_ieee_cis


class Command(BaseCommand):
    help = "Retrain the primary IEEE-CIS fraud detection model on combined dataset (X + Y)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-fraud",
            type=int,
            default=5,
            help="Configurable minimum number of analyst-confirmed fraud cases in Y required to train.",
        )
        parser.add_argument(
            "--sample-size",
            type=int,
            default=None,
            help="Optional row limit for training split X for fast training/verification.",
        )
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help="Directory path containing IEEE-CIS dataset.",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=None,
            help="Directory where retrained model and metadata JSON will be saved.",
        )
        parser.add_argument(
            "--model-version",
            type=str,
            default="2.0.0",
            help="Version string for the retrained model artifact (e.g. '2.0.0').",
        )
        parser.add_argument(
            "--bootstrap-rounds",
            type=int,
            default=200,
            help="Number of paired bootstrap iterations for recall difference confidence interval.",
        )
        parser.add_argument(
            "--allow-empty-y",
            action="store_true",
            help="Allow retraining run even if Y has insufficient fraud cases (for testing and calibration).",
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 76)
        self.stdout.write("  FraudShield — Offline IEEE-CIS Model Retraining Pipeline (X + Y)")
        self.stdout.write("=" * 76)

        new_version = options["model_version"]
        min_fraud = options["min_fraud"]
        bootstrap_rounds = options["bootstrap_rounds"]

        # 1. Load active/deployed model bundle to reuse fitted preprocessing
        bundle = get_model_bundle()
        if not bundle or not bundle.get("model") or not bundle.get("preprocessor"):
            raise CommandError("Could not locate active deployed model bundle and fitted preprocessor.")

        deployed_model = bundle["model"]
        deployed_preprocessor = bundle["preprocessor"]
        deployed_version = bundle.get("version", "1.0.0")

        self.stdout.write("  Active deployed model version: %s" % deployed_version)
        self.stdout.write("  Target retrained model version: %s" % new_version)

        # 2. Extract Y: Live transactions labeled through AnalystDecision
        # Strictly exclude replay transactions and unreviewed transactions
        query_y = Transaction.objects.filter(
            source=Transaction.Source.LIVE,
            analyst_decision__isnull=False,
        ).select_related("analyst_decision")

        rows_y = []
        labels_y = []
        skipped_snapshots = 0

        for txn in query_y:
            decision_val = txn.analyst_decision.decision.lower().strip()
            # decline = fraud (1), approve = legitimate (0)
            if decision_val in ["declined", "decline", "fraud"]:
                y_label = 1
            elif decision_val in ["approved", "approve", "clean"]:
                y_label = 0
            else:
                continue

            snapshot = txn.feature_snapshot
            if not isinstance(snapshot, dict) or not snapshot:
                skipped_snapshots += 1
                continue

            # Ensure minimal required numeric amount exists in snapshot
            amt = snapshot.get("TransactionAmt") or snapshot.get("amount") or float(txn.amount)
            try:
                amt = float(amt)
                if amt <= 0:
                    skipped_snapshots += 1
                    continue
            except (ValueError, TypeError):
                skipped_snapshots += 1
                continue

            row_dict = dict(snapshot)
            row_dict["TransactionAmt"] = amt
            if "TransactionDT" not in row_dict and txn.submitted_at:
                row_dict["TransactionDT"] = txn.submitted_at.timestamp()

            rows_y.append(row_dict)
            labels_y.append(y_label)

        size_y = len(rows_y)
        num_fraud_y = sum(labels_y)
        num_legit_y = size_y - num_fraud_y

        self.stdout.write("\n[Step 1] Live Analyst Labeled Data (Y):")
        self.stdout.write("  - Total analyst-labeled live transactions: %d" % size_y)
        self.stdout.write("  - Confirmed fraud (declined)            : %d" % num_fraud_y)
        self.stdout.write("  - Confirmed legitimate (approved)       : %d" % num_legit_y)
        if skipped_snapshots > 0:
            self.stdout.write("  - Skipped non-matching/corrupt snapshots : %d" % skipped_snapshots)

        if num_fraud_y < min_fraud and not options["allow_empty_y"]:
            msg = (
                "Refusing to retrain: Found %d analyst-confirmed fraud cases in Y, "
                "which is below the required minimum threshold of %d. "
                "Retraining requires a sufficient sample of reviewed fraud to prevent degradation."
                % (num_fraud_y, min_fraud)
            )
            self.stderr.write(self.style.ERROR(msg))
            raise CommandError(msg)

        # 3. Load baseline training split X and untouched test set
        repo_root = Path(settings.BASE_DIR).parent
        data_dir = Path(options["data_dir"]) if options["data_dir"] else repo_root / "notebooks" / "data"

        self.stdout.write("\n[Step 2] Loading baseline dataset split X …")
        df_full = load_and_join_ieee_cis(data_dir, sample_size=options["sample_size"])
        df_train, df_test, y_train, y_test = split_ieee_cis(df_full, test_ratio=0.20)

        size_x = len(df_train)
        self.stdout.write("  - Exact baseline train split X: %d rows (Fraud rate: %.2f%%)"
                          % (size_x, float(y_train.mean()) * 100))
        self.stdout.write("  - Untouched held-out test set : %d rows (Fraud rate: %.2f%%)"
                          % (len(df_test), float(y_test.mean()) * 100))

        # 4. Preprocess X and Y using the existing serving preprocessor (shared feature space)
        self.stdout.write("\n[Step 3] Reusing fitted serving preprocessor for X and Y …")
        X_train_scaled = deployed_preprocessor.transform(df_train)

        if size_y > 0:
            df_y = pd.DataFrame(rows_y)
            X_y_scaled = deployed_preprocessor.transform(df_y)
            X_combined = np.vstack([X_train_scaled, X_y_scaled])
            y_combined = np.concatenate([y_train.values, np.array(labels_y, dtype=int)])
            self.stdout.write("  Combined training set (X + Y): %d rows (Fraud: %d)"
                              % (len(X_combined), int(y_combined.sum())))
        else:
            X_combined = X_train_scaled
            y_combined = y_train.values

        # 5. Apply SMOTE to combined training set ONLY
        self.stdout.write("\n[Step 4] Applying SMOTE oversampling to combined training set only …")
        smote = SMOTE(sampling_strategy=0.25, random_state=42)
        X_res, y_res = smote.fit_resample(X_combined, y_combined)
        self.stdout.write("  Post-SMOTE combined training set: %d rows (%.2f%% fraud)"
                          % (len(X_res), float(y_res.mean()) * 100))

        # 6. Train Random Forest model with same hyperparameters
        self.stdout.write("\n[Step 5] Training Random Forest model with identical hyperparameters …")
        retrained_rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=42,
        )
        retrained_rf.fit(X_res, y_res)
        self.stdout.write("  Training completed successfully.")

        # 7. Evaluate both deployed and retrained models on untouched test set
        self.stdout.write("\n[Step 6] Evaluating deployed vs retrained model on untouched test set …")
        X_test_scaled = deployed_preprocessor.transform(df_test)

        threshold_cfg = ThresholdConfig.objects.first()
        flag_threshold = threshold_cfg.flag_threshold if threshold_cfg else 0.75
        self.stdout.write("  Active flag threshold cutoff: %.3f" % flag_threshold)

        y_test_arr = y_test.values if hasattr(y_test, "values") else np.array(y_test)

        deployed_probas = deployed_model.predict_proba(X_test_scaled)[:, 1]
        deployed_flagged = (deployed_probas >= flag_threshold).astype(int)

        retrained_probas = retrained_rf.predict_proba(X_test_scaled)[:, 1]
        retrained_flagged = (retrained_probas >= flag_threshold).astype(int)

        dep_prec = float(precision_score(y_test_arr, deployed_flagged, zero_division=0))
        dep_rec = float(recall_score(y_test_arr, deployed_flagged, zero_division=0))
        dep_f1 = float(f1_score(y_test_arr, deployed_flagged, zero_division=0))

        ret_prec = float(precision_score(y_test_arr, retrained_flagged, zero_division=0))
        ret_rec = float(recall_score(y_test_arr, retrained_flagged, zero_division=0))
        ret_f1 = float(f1_score(y_test_arr, retrained_flagged, zero_division=0))

        self.stdout.write("  Deployed Model  -> Precision: %.4f | Recall: %.4f | F1: %.4f"
                          % (dep_prec, dep_rec, dep_f1))
        self.stdout.write("  Retrained Model -> Precision: %.4f | Recall: %.4f | F1: %.4f"
                          % (ret_prec, ret_rec, ret_f1))

        # 8. Paired Bootstrap on Recall Difference
        self.stdout.write("\n[Step 7] Bootstrapping recall difference across %d paired resamples …" % bootstrap_rounds)
        rng = np.random.RandomState(42)
        n_test = len(y_test_arr)
        recall_diffs = []

        for _ in range(bootstrap_rounds):
            boot_idx = rng.choice(n_test, size=n_test, replace=True)
            y_boot = y_test_arr[boot_idx]
            if y_boot.sum() == 0:
                continue
            r_ret = recall_score(y_boot, retrained_flagged[boot_idx], zero_division=0)
            r_dep = recall_score(y_boot, deployed_flagged[boot_idx], zero_division=0)
            recall_diffs.append(r_ret - r_dep)

        if recall_diffs:
            ci_lower = float(np.percentile(recall_diffs, 2.5))
            ci_upper = float(np.percentile(recall_diffs, 97.5))
            diff_mean = float(np.mean(recall_diffs))
        else:
            ci_lower = 0.0
            ci_upper = 0.0
            diff_mean = 0.0

        self.stdout.write("  Recall Difference (Retrained - Deployed):")
        self.stdout.write("    Mean Delta : %+.4f" % diff_mean)
        self.stdout.write("    95%% CI    : [%+.4f, %+.4f]" % (ci_lower, ci_upper))

        promoted = ci_lower > 0.0
        if promoted:
            rationale = (
                "Statistically significant recall improvement confirmed: 95%% CI [%.4f, %.4f] "
                "is strictly positive. Retrained model recommended for promotion."
                % (ci_lower, ci_upper)
            )
            self.stdout.write(self.style.SUCCESS("  [PROMOTION CRITERIA MET] -> %s" % rationale))
        else:
            rationale = (
                "Lower bound of recall difference CI is <= 0 ([%.4f, %.4f]). "
                "Deployed model retained. Legitimate finding: small Y rarely moves a model trained on large X."
                % (ci_lower, ci_upper)
            )
            self.stdout.write(self.style.WARNING("  [RETAIN CURRENT MODEL] -> %s" % rationale))

        # 9. Save retrained model artifact and metadata
        output_dir = Path(options["output_dir"]) if options["output_dir"] else Path(settings.BASE_DIR) / "ml_models"
        output_dir.mkdir(parents=True, exist_ok=True)

        model_filename = "ieee_cis_rf_v%s.joblib" % new_version
        metadata_filename = "ieee_cis_rf_v%s_metadata.json" % new_version
        model_path = output_dir / model_filename
        metadata_path = output_dir / metadata_filename

        metadata = {
            "model_version": new_version,
            "base_model_version": deployed_version,
            "algorithm": "Random Forest",
            "hyperparameters": {
                "n_estimators": 100,
                "max_depth": 12,
                "min_samples_leaf": 5,
                "random_state": 42,
            },
            "size_X": size_x,
            "size_Y": size_y,
            "size_Y_fraud": num_fraud_y,
            "size_Y_legit": num_legit_y,
            "training_date": datetime.now(tz=UTC).isoformat(),
            "sklearn_version": sklearn.__version__,
            "deployed_metrics": {
                "precision": round(dep_prec, 4),
                "recall": round(dep_rec, 4),
                "f1": round(dep_f1, 4),
                "flag_threshold": flag_threshold,
            },
            "retrained_metrics": {
                "precision": round(ret_prec, 4),
                "recall": round(ret_rec, 4),
                "f1": round(ret_f1, 4),
                "flag_threshold": flag_threshold,
            },
            "recall_difference_ci": {
                "mean": round(diff_mean, 4),
                "ci_lower": round(ci_lower, 4),
                "ci_upper": round(ci_upper, 4),
                "confidence_level": 0.95,
            },
            "promoted": promoted,
            "selection_rationale": rationale,
            "sampling_bias_note": (
                "Y is inherently biased toward ambiguous transactions near the decision boundaries, "
                "as clear auto-approved (<0.75) and auto-declined (>=0.90) transactions are never "
                "routed to analysts for manual review."
            ),
        }

        retrained_bundle = {
            "model": retrained_rf,
            "preprocessor": deployed_preprocessor,
            "version": new_version,
            "name": "IEEE-CIS Random Forest",
            "sklearn_version": sklearn.__version__,
            "metrics": metadata,
        }

        # Save without overwriting the previous model file (preserving rollback capability)
        joblib.dump(retrained_bundle, model_path)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        self.stdout.write("\n[Step 8] Artifact Serialization:")
        self.stdout.write("  - Retrained model saved to : %s" % model_path)
        self.stdout.write("  - Metadata saved to        : %s" % metadata_path)
        self.stdout.write("  - Previous model preserved for rollback: True")

        # Register inactive entry in MLModel database table
        ml_entry, _ = MLModel.objects.update_or_create(
            name="IEEE-CIS Random Forest",
            version=new_version,
            defaults={
                "algorithm": MLModel.Algorithm.RANDOM_FOREST,
                "description": "Retrained offline on X (%d rows) + Y (%d rows)" % (size_x, size_y),
                "metrics": metadata,
                "is_active": False,  # Never swap automatically
                "trained_at": timezone.now(),
            },
        )
        self.stdout.write("  - Database MLModel registered (active=False): %s" % ml_entry)
        self.stdout.write(self.style.SUCCESS("\nRetraining process completed successfully."))
