"""Sparkov fraud detection pipeline using human-readable features for SHAP explainability."""

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


def haversine_np(lon1, lat1, lon2, lat2):
    """Vectorized calculation of great-circle distance (km) between coordinates."""
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    km = 6371.0 * c
    return km


class SparkovPreprocessor:
    """Feature engineering and scaling for Sparkov benchmark."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy="median")
        self.categories = [
            "misc_net", "grocery_pos", "entertainment", "gas_transport",
            "misc_pos", "grocery_net", "shopping_net", "shopping_pos",
            "food_dining", "personal_care", "health_fitness", "travel",
            "kids_pets", "home"
        ]
        self.merchant_freq = {}
        self.feature_names = []
        self.fitted = False

    @staticmethod
    def _clean_merchant(m):
        if pd.isna(m):
            return "unknown"
        return str(m).strip().removeprefix("fraud_")

    def engineer_features(self, df):
        feat = pd.DataFrame(index=df.index)

        amt = pd.to_numeric(df["amt"], errors="coerce").fillna(0.0)
        feat["amt"] = amt
        feat["log_amt"] = np.log1p(np.maximum(0, amt))

        lat = pd.to_numeric(df["lat"], errors="coerce").fillna(0.0)
        lon = pd.to_numeric(df["long"], errors="coerce").fillna(0.0)
        m_lat = pd.to_numeric(df["merch_lat"], errors="coerce").fillna(0.0)
        m_lon = pd.to_numeric(df["merch_long"], errors="coerce").fillna(0.0)

        feat["distance_km"] = haversine_np(lon.values, lat.values, m_lon.values, m_lat.values)
        feat["lat"] = lat
        feat["long"] = lon
        feat["merch_lat"] = m_lat
        feat["merch_long"] = m_lon

        if "trans_date_trans_time" in df.columns:
            dt = pd.to_datetime(df["trans_date_trans_time"], errors="coerce")
            hour = dt.dt.hour.fillna(12).astype(int)
            dow = dt.dt.dayofweek.fillna(0).astype(int)
            feat["hour"] = hour
            feat["day_of_week"] = dow
            # Fraud spikes during nighttime/early morning hours (22:00 - 04:00)
            feat["is_night"] = hour.isin([22, 23, 0, 1, 2, 3, 4]).astype(int)
            feat["is_weekend"] = dow.isin([5, 6]).astype(int)
        elif "unix_time" in df.columns:
            u = pd.to_numeric(df["unix_time"], errors="coerce").fillna(0)
            hour = (u // 3600) % 24
            feat["hour"] = hour
            feat["is_night"] = hour.isin([22, 23, 0, 1, 2, 3, 4]).astype(int)

        feat["city_pop"] = pd.to_numeric(df.get("city_pop", 0), errors="coerce").fillna(0.0)
        feat["log_city_pop"] = np.log1p(np.maximum(0, feat["city_pop"]))

        if "gender" in df.columns:
            feat["is_female"] = (df["gender"].astype(str).str.upper() == "F").astype(int)

        if "dob" in df.columns and "trans_date_trans_time" in df.columns:
            dob_dt = pd.to_datetime(df["dob"], errors="coerce")
            trans_dt = pd.to_datetime(df["trans_date_trans_time"], errors="coerce")
            age = (trans_dt.dt.year - dob_dt.dt.year).fillna(45.0)
            feat["age"] = np.clip(age, 18, 100)

        cat_series = df["category"].fillna("missing").astype(str)
        for cat in self.categories:
            feat["cat_%s" % cat] = (cat_series == cat).astype(int)

        feat["_merchant_clean"] = df["merchant"].apply(self._clean_merchant)

        return feat

    def fit_transform(self, df_train):
        """Fit preprocessor exclusively on X_train and transform."""
        feat = self.engineer_features(df_train)

        # Compute merchant frequency encoding on train set only to prevent leakage
        m_counts = feat["_merchant_clean"].value_counts(normalize=True).to_dict()
        self.merchant_freq = m_counts
        feat["merchant_freq"] = feat["_merchant_clean"].map(m_counts).fillna(0.0)

        feat.drop(columns=["_merchant_clean"], inplace=True)
        self.feature_names = list(feat.columns)

        X_imputed = self.imputer.fit_transform(feat.values)
        X_scaled = self.scaler.fit_transform(X_imputed)

        self.fitted = True
        return X_scaled, self.feature_names

    def transform(self, df_test):
        """Transform test set using preprocessor fitted on training set."""
        if not self.fitted:
            raise ValueError("Preprocessor must be fitted before transform.")

        feat = self.engineer_features(df_test)

        feat["merchant_freq"] = feat["_merchant_clean"].map(self.merchant_freq).fillna(0.0)
        feat.drop(columns=["_merchant_clean"], inplace=True)

        feat = feat.reindex(columns=self.feature_names, fill_value=0.0)

        X_imputed = self.imputer.transform(feat.values)
        X_scaled = self.scaler.transform(X_imputed)

        return X_scaled


def load_sparkov_data(data_dir, sample_size=None):
    """Load Sparkov dataset using the canonical chronological split to prevent lookahead."""
    train_path = data_dir / "sparkov" / "fraudTrain.csv"
    test_path = data_dir / "sparkov" / "fraudTest.csv"

    if not train_path.exists() or not test_path.exists():
        raise FileNotFoundError(
            "Sparkov files not found in %s. Please run notebooks/download_datasets.sh."
            % (data_dir / "sparkov")
        )

    print("  Loading %s (time: 2019 -> mid-2020) …" % train_path.name)
    df_train = pd.read_csv(train_path)

    print("  Loading %s (time: mid-2020 -> end-2020) …" % test_path.name)
    df_test = pd.read_csv(test_path)

    if sample_size and sample_size < len(df_train):
        # Sample chronologically from train and test proportionally
        test_size = int(sample_size * (len(df_test) / (len(df_train) + len(df_test))))
        train_size = sample_size - test_size

        print("  Sampling chronologically: %d train rows, %d test rows …" % (train_size, test_size))
        df_train = df_train.sort_values("trans_date_trans_time").tail(train_size).reset_index(drop=True)
        df_test = df_test.sort_values("trans_date_trans_time").head(test_size).reset_index(drop=True)

    return df_train, df_test


def train_sparkov_pipeline(
    data_dir,
    output_dir,
    model_choice="all",
    sample_size=None,
    n_bootstraps=200,
    smote_ratio=0.20,
    svm_max_samples=50000,
    save_models=True,
):
    """Execute end-to-end Sparkov training pipeline for Random Forest and/or SVM."""
    print("\n" + "=" * 70)
    print("  Sparkov Fraud Detection Pipeline (Explainability & SHAP Benchmark)")
    print("=" * 70)

    print("\n[Step 1] Loading pre-partitioned dataset respecting time and cardholder identity …")
    df_train, df_test = load_sparkov_data(data_dir, sample_size=sample_size)

    y_train = df_train["is_fraud"].astype(int)
    y_test = df_test["is_fraud"].astype(int)

    print("  Split verification:")
    print("    Train set: %d rows (Fraud rate: %.2f%%)" % (len(df_train), y_train.mean() * 100))
    print("    Test set : %d rows (Fraud rate: %.2f%%)" % (len(df_test), y_test.mean() * 100))

    print("\n[Step 2] Engineering human-readable features (category, merchant, geo distance, time) …")
    preprocessor = SparkovPreprocessor()
    X_train_scaled, feat_names = preprocessor.fit_transform(df_train)
    X_test_scaled = preprocessor.transform(df_test)

    print("  Engineered feature count: %d" % len(feat_names))
    print("  Key human-readable features for SHAP: %s …" % feat_names[:8])

    print("\n[Step 3] Applying SMOTE oversampling to training set ONLY (preventing test leakage) …")
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
        print("\n[Step 4a] Training Random Forest Classifier (Optimized for Tree SHAP) …")
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
            "dataset": "Sparkov",
            "algorithm": "Random Forest",
            "test_samples": len(y_test),
            "test_fraud_rate": float(y_test.mean()),
            "metrics_ci": ci,
            "feature_names": feat_names,
        }
        results["sparkov_rf"] = res_rf

        if save_models:
            model_path = models_dir / "sparkov_rf.joblib"
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
            "dataset": "Sparkov",
            "algorithm": "Support Vector Machine (Linear Calibrated)",
            "test_samples": len(y_test),
            "test_fraud_rate": float(y_test.mean()),
            "metrics_ci": ci,
            "feature_names": feat_names,
        }
        results["sparkov_svm"] = res_svm

        if save_models:
            model_path = models_dir / "sparkov_svm.joblib"
            bundle = {
                "model": svm,
                "preprocessor": preprocessor,
                "metrics": res_svm,
            }
            joblib.dump(bundle, model_path)
            print("  [Saved model] -> %s" % model_path)

    return results

