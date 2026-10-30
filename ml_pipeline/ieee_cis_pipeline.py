"""IEEE-CIS Fraud Detection Pipeline (Primary Deployed Model)."""

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

from .evaluation import bootstrap_confidence_intervals, compute_point_metrics


class IEEECISPreprocessor:
    """Feature engineering, missingness indicators, and encoding for IEEE-CIS."""

    def __init__(self):
        self.imputer = SimpleImputer(strategy="median")
        self.scaler = StandardScaler()
        self.p_domain_freq = {}
        self.r_domain_freq = {}
        self.feature_names = []
        self.fitted = False

    @staticmethod
    def _clean_email_domain(val):
        if pd.isna(val) or not str(val).strip():
            return "missing"
        val_str = str(val).lower().strip()
        parts = val_str.split(".")
        return parts[0] if parts else "missing"

    def engineer_features(self, df):
        feat = pd.DataFrame(index=df.index)

        # Missingness is informative: transactions with identity have ~3x higher fraud rate
        if "id_01" in df.columns:
            feat["has_identity"] = df["id_01"].notna().astype(int)
            feat["id_01_isna"] = df["id_01"].isna().astype(int)
        else:
            feat["has_identity"] = 0
            feat["id_01_isna"] = 1

        if "id_02" in df.columns:
            feat["id_02_isna"] = df["id_02"].isna().astype(int)

        if "dist1" in df.columns:
            feat["dist1_isna"] = df["dist1"].isna().astype(int)

        if "dist2" in df.columns:
            feat["dist2_isna"] = df["dist2"].isna().astype(int)

        if "R_emaildomain" in df.columns:
            feat["R_email_isna"] = df["R_emaildomain"].isna().astype(int)

        if "P_emaildomain" in df.columns:
            feat["P_email_isna"] = df["P_emaildomain"].isna().astype(int)

        if "D1" in df.columns:
            feat["D1_isna"] = df["D1"].isna().astype(int)

        if "V1" in df.columns:
            feat["V1_isna"] = df["V1"].isna().astype(int)

        feat["TransactionAmt"] = df["TransactionAmt"].fillna(0.0)
        feat["log_amt"] = np.log1p(np.maximum(0, feat["TransactionAmt"]))

        if "TransactionDT" in df.columns:
            # TransactionDT is seconds elapsed from dataset reference point
            feat["trans_hour"] = (df["TransactionDT"] // 3600) % 24
            feat["trans_day"] = (df["TransactionDT"] // (3600 * 24)) % 7

        if "ProductCD" in df.columns:
            product_series = df["ProductCD"].fillna("missing").astype(str)
        else:
            product_series = pd.Series(["missing"] * len(df), index=df.index)
        for code in ["W", "C", "R", "H", "S"]:
            feat["ProductCD_%s" % code] = (product_series == code).astype(int)

        if "card4" in df.columns:
            card4_series = df["card4"].fillna("missing").astype(str).str.lower()
        else:
            card4_series = pd.Series(["missing"] * len(df), index=df.index)
        for net in ["visa", "mastercard", "discover", "american express"]:
            feat["card4_%s" % net] = (card4_series == net).astype(int)

        if "card6" in df.columns:
            card6_series = df["card6"].fillna("missing").astype(str).str.lower()
        else:
            card6_series = pd.Series(["missing"] * len(df), index=df.index)
        for ctype in ["credit", "debit"]:
            feat["card6_%s" % ctype] = (card6_series == ctype).astype(int)

        p_series = df["P_emaildomain"] if "P_emaildomain" in df.columns else pd.Series([None] * len(df), index=df.index)
        r_series = df["R_emaildomain"] if "R_emaildomain" in df.columns else pd.Series([None] * len(df), index=df.index)
        p_clean = p_series.apply(self._clean_email_domain)
        r_clean = r_series.apply(self._clean_email_domain)

        # High-signal email domain indicators
        for dom in ["gmail", "yahoo", "hotmail", "anonymous", "aol"]:
            feat["P_dom_%s" % dom] = (p_clean == dom).astype(int)
            feat["R_dom_%s" % dom] = (r_clean == dom).astype(int)

        feat["same_email_domain"] = ((p_clean == r_clean) & (p_clean != "missing")).astype(int)

        feat["_p_domain_raw"] = p_clean
        feat["_r_domain_raw"] = r_clean

        for col in ["card1", "card2", "card3", "card5", "addr1", "addr2", "dist1"]:
            if col in df.columns:
                feat[col] = pd.to_numeric(df[col], errors="coerce")

        for col in ["C1", "C2", "C5", "C6", "C9", "C11", "C13", "C14"]:
            if col in df.columns:
                feat[col] = pd.to_numeric(df[col], errors="coerce")

        for col in ["D1", "D2", "D3", "D4", "D10", "D11", "D15"]:
            if col in df.columns:
                feat[col] = pd.to_numeric(df[col], errors="coerce")

        selected_v = [
            "V12", "V35", "V45", "V53", "V75", "V83", "V90",
            "V127", "V130", "V136", "V258", "V283", "V285", "V307", "V310"
        ]
        for col in selected_v:
            if col in df.columns:
                feat[col] = pd.to_numeric(df[col], errors="coerce")

        for col in ["id_01", "id_02"]:
            if col in df.columns:
                feat[col] = pd.to_numeric(df[col], errors="coerce")

        return feat

    def fit_transform(self, df_train):
        """Fit preprocessor exclusively on training data and transform."""
        feat = self.engineer_features(df_train)

        # Frequency encoding computed on train set only to prevent leakage
        p_counts = feat["_p_domain_raw"].value_counts(normalize=True).to_dict()
        r_counts = feat["_r_domain_raw"].value_counts(normalize=True).to_dict()
        self.p_domain_freq = p_counts
        self.r_domain_freq = r_counts

        feat["p_domain_freq"] = feat["_p_domain_raw"].map(p_counts).fillna(0.0)
        feat["r_domain_freq"] = feat["_r_domain_raw"].map(r_counts).fillna(0.0)

        feat.drop(columns=["_p_domain_raw", "_r_domain_raw"], inplace=True)

        self.feature_names = list(feat.columns)

        X_imputed = self.imputer.fit_transform(feat.values)
        X_scaled = self.scaler.fit_transform(X_imputed)

        self.fitted = True
        return X_scaled, self.feature_names

    def transform(self, df_test):
        """Transform test set using fitted statistics (no leakage)."""
        if not self.fitted:
            raise ValueError("Preprocessor must be fitted before transform.")

        feat = self.engineer_features(df_test)

        feat["p_domain_freq"] = feat["_p_domain_raw"].map(self.p_domain_freq).fillna(0.0)
        feat["r_domain_freq"] = feat["_r_domain_raw"].map(self.r_domain_freq).fillna(0.0)

        feat.drop(columns=["_p_domain_raw", "_r_domain_raw"], inplace=True)

        # Ensure identical column alignment
        feat = feat.reindex(columns=self.feature_names, fill_value=0.0)

        X_imputed = self.imputer.transform(feat.values)
        X_scaled = self.scaler.transform(X_imputed)

        return X_scaled


def load_and_join_ieee_cis(data_dir, sample_size=None):
    """Load transaction and identity tables and execute LEFT JOIN on TransactionID."""
    txn_path = data_dir / "ieee_cis" / "train_transaction.csv"
    idn_path = data_dir / "ieee_cis" / "train_identity.csv"

    if not txn_path.exists() or not idn_path.exists():
        raise FileNotFoundError(
            "IEEE-CIS files not found in %s. Please run notebooks/download_datasets.sh."
            % (data_dir / "ieee_cis")
        )

    print("  Loading %s …" % txn_path.name)
    txn = pd.read_csv(txn_path)
    print("  Loading %s …" % idn_path.name)
    idn = pd.read_csv(idn_path)

    print("  Executing LEFT JOIN on TransactionID …")
    merged = txn.merge(idn, on="TransactionID", how="left")
    print("  Joined dataset shape: %s" % str(merged.shape))

    if sample_size and sample_size < len(merged):
        # Sort by TransactionDT to preserve chronological order during sampling
        print("  Sampling %d rows chronologically for accelerated training …" % sample_size)
        merged = merged.sort_values("TransactionDT").tail(sample_size).reset_index(drop=True)

    return merged


def split_ieee_cis(df, test_ratio=0.20):
    """Perform chronological train/test split on TransactionDT.

    Respects time to prevent lookahead leakage (past transactions predict future).
    """
    df_sorted = df.sort_values("TransactionDT").reset_index(drop=True)
    n_total = len(df_sorted)
    split_idx = int(n_total * (1.0 - test_ratio))

    df_train = df_sorted.iloc[:split_idx].copy()
    df_test = df_sorted.iloc[split_idx:].copy()

    y_train = df_train["isFraud"].astype(int)
    y_test = df_test["isFraud"].astype(int)

    print("  Chronological split completed:")
    print("    Train set: %d rows (Fraud rate: %.2f%%)" % (len(df_train), y_train.mean() * 100))
    print("    Test set : %d rows (Fraud rate: %.2f%%)" % (len(df_test), y_test.mean() * 100))

    return df_train, df_test, y_train, y_test


def train_ieee_pipeline(
    data_dir,
    output_dir,
    model_choice="all",
    sample_size=None,
    n_bootstraps=200,
    smote_ratio=0.25,
    svm_max_samples=50000,
    save_models=True,
):
    """Execute end-to-end IEEE-CIS training pipeline for Random Forest and/or SVM."""
    print("\n" + "=" * 70)
    print("  IEEE-CIS Fraud Detection Pipeline (Primary Deployed Benchmark)")
    print("=" * 70)

    df = load_and_join_ieee_cis(data_dir, sample_size=sample_size)

    print("\n[Step 1] Partitioning into Train and Test splits before preprocessing …")
    df_train, df_test, y_train, y_test = split_ieee_cis(df)

    print("\n[Step 2] Feature engineering and scaling fitted exclusively on X_train …")
    preprocessor = IEEECISPreprocessor()
    X_train_scaled, feat_names = preprocessor.fit_transform(df_train)
    X_test_scaled = preprocessor.transform(df_test)

    print("  Engineered feature count: %d" % len(feat_names))

    print("\n[Step 3] Applying SMOTE oversampling to training set ONLY (preventing leakage) …")
    print("  Pre-SMOTE train distribution: 0=%d, 1=%d (%.2f%% fraud)"
          % ((y_train == 0).sum(), (y_train == 1).sum(), y_train.mean() * 100))

    smote = SMOTE(sampling_strategy=smote_ratio, random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)

    print("  Post-SMOTE train distribution: 0=%d, 1=%d (%.2f%% fraud)"
          % ((y_train_res == 0).sum(), (y_train_res == 1).sum(), y_train_res.mean() * 100))
    print("  [Verified] Test set remains untouched: %d rows (%.2f%% fraud)"
          % (len(y_test), y_test.mean() * 100))

    results = {}
    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    if model_choice in ["rf", "all"]:
        print("\n[Step 4a] Training Random Forest Classifier …")
        rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=42,
        )
        rf.fit(X_train_res, y_train_res)

        print("  Evaluating RF on untouched test set …")
        y_pred = rf.predict(X_test_scaled)
        y_proba = rf.predict_proba(X_test_scaled)[:, 1]

        point = compute_point_metrics(y_test.values, y_pred, y_proba)
        print("  Point Estimates -> F1: %.4f | AUC-ROC: %.4f | Precision: %.4f | Recall: %.4f"
              % (point["f1"], point["auc_roc"], point["precision"], point["recall"]))

        print("  Bootstrapping test set (%d resamples with replacement) …" % n_bootstraps)
        ci = bootstrap_confidence_intervals(y_test.values, y_pred, y_proba, n_bootstraps=n_bootstraps)

        res_rf = {
            "dataset": "IEEE-CIS",
            "algorithm": "Random Forest",
            "test_samples": len(y_test),
            "test_fraud_rate": float(y_test.mean()),
            "metrics_ci": ci,
            "feature_names": feat_names,
        }
        results["ieee_rf"] = res_rf

        if save_models:
            model_path = models_dir / "ieee_cis_rf.joblib"
            bundle = {
                "model": rf,
                "preprocessor": preprocessor,
                "metrics": res_rf,
            }
            joblib.dump(bundle, model_path)
            print("  [Saved model] -> %s" % model_path)

    if model_choice in ["svm", "all"]:
        print("\n[Step 4b] Training Calibrated Linear SVM Classifier …")

        # Subsample massive training set to ensure linear SVM convergence
        if len(X_train_res) > svm_max_samples:
            print("  Subsampling training set to %d rows for SVM convergence …" % svm_max_samples)
            rng = np.random.RandomState(42)
            sub_idx = rng.choice(len(X_train_res), size=svm_max_samples, replace=False)
            X_svm_train = X_train_res[sub_idx]
            y_svm_train = y_train_res.iloc[sub_idx] if hasattr(y_train_res, "iloc") else y_train_res[sub_idx]
        else:
            X_svm_train = X_train_res
            y_svm_train = y_train_res

        base_svm = LinearSVC(dual=False, max_iter=2000, random_state=42, C=1.0)
        svm = CalibratedClassifierCV(estimator=base_svm, method="sigmoid", cv=3)
        svm.fit(X_svm_train, y_svm_train)

        print("  Evaluating SVM on untouched test set …")
        y_pred = svm.predict(X_test_scaled)
        y_proba = svm.predict_proba(X_test_scaled)[:, 1]

        point = compute_point_metrics(y_test.values, y_pred, y_proba)
        print("  Point Estimates -> F1: %.4f | AUC-ROC: %.4f | Precision: %.4f | Recall: %.4f"
              % (point["f1"], point["auc_roc"], point["precision"], point["recall"]))

        print("  Bootstrapping test set (%d resamples with replacement) …" % n_bootstraps)
        ci = bootstrap_confidence_intervals(y_test.values, y_pred, y_proba, n_bootstraps=n_bootstraps)

        res_svm = {
            "dataset": "IEEE-CIS",
            "algorithm": "Support Vector Machine (Linear Calibrated)",
            "test_samples": len(y_test),
            "test_fraud_rate": float(y_test.mean()),
            "metrics_ci": ci,
            "feature_names": feat_names,
        }
        results["ieee_svm"] = res_svm

        if save_models:
            model_path = models_dir / "ieee_cis_svm.joblib"
            bundle = {
                "model": svm,
                "preprocessor": preprocessor,
                "metrics": res_svm,
            }
            joblib.dump(bundle, model_path)
            print("  [Saved model] -> %s" % model_path)

    return results
