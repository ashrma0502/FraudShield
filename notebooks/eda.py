"""
Fraud Dataset EDA
=================
Standalone exploration script for two fraud datasets:
  1. IEEE-CIS Fraud Detection   (Kaggle competition, two-file join)
  2. Sparkov Credit Card Txns   (1.85M rows, time-split, geo coordinates)

Run from project root:
    ./backend/venv/bin/python notebooks/eda.py

Outputs go to: notebooks/outputs/
  - figures/*.png
  - summary.md
"""

import os
import sys
import textwrap
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # headless — no display needed
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).parent
DATA    = ROOT / "data"
OUT     = ROOT / "outputs"
FIGURES = OUT / "figures"
OUT.mkdir(exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

IEEE_TXN   = DATA / "ieee_cis" / "train_transaction.csv"
IEEE_ID    = DATA / "ieee_cis" / "train_identity.csv"
SPARKOV_TR = DATA / "sparkov" / "fraudTrain.csv"
SPARKOV_TE = DATA / "sparkov" / "fraudTest.csv"

# ── Helpers ────────────────────────────────────────────────────────────────────

sns.set_theme(style="whitegrid", palette="muted")

_summary_parts = []

def log(text: str):
    print(text)
    _summary_parts.append(text)

def section(title: str):
    bar = "=" * 70
    log("\n%s\n  %s\n%s" % (bar, title, bar))

def savefig(name: str):
    p = FIGURES / ("%s.png" % name)
    plt.tight_layout()
    plt.savefig(p, dpi=150)
    plt.close()
    print("  [saved] %s" % p.name)

def check_file(path: Path) -> bool:
    if not path.exists():
        log("  MISSING: %s" % path)
        log("  Run: bash notebooks/download_datasets.sh first.\n")
        return False
    return True

def fraud_rate(df: pd.DataFrame, col: str, label: str = "isFraud") -> pd.Series:
    return df.groupby(col)[label].mean().sort_values(ascending=False)


# ══════════════════════════════════════════════════════════════════════════════
#  1. IEEE-CIS
# ══════════════════════════════════════════════════════════════════════════════

def explore_ieee():
    section("IEEE-CIS Fraud Detection")

    if not check_file(IEEE_TXN) or not check_file(IEEE_ID):
        return None, None

    # ── Load ──────────────────────────────────────────────────────────────────
    log("Loading train_transaction.csv …")
    txn = pd.read_csv(IEEE_TXN)
    log("Loading train_identity.csv …")
    idn = pd.read_csv(IEEE_ID)

    log("  Transaction rows : %d" % len(txn))
    log("  Identity rows    : %d" % len(idn))
    log("  Transaction cols : %d" % txn.shape[1])
    log("  Identity cols    : %d" % idn.shape[1])

    # ── Class imbalance ───────────────────────────────────────────────────────
    fraud_counts = txn["isFraud"].value_counts()
    fraud_pct    = txn["isFraud"].mean() * 100
    log("\nClass balance (transactions):")
    log("  Legitimate : %d  (%.2f%%)" % (fraud_counts[0], 100 - fraud_pct))
    log("  Fraud      : %d  (%.2f%%)" % (fraud_counts[1], fraud_pct))

    # ── Identity join coverage ────────────────────────────────────────────────
    matched = txn["TransactionID"].isin(idn["TransactionID"]).sum()
    log("\nIdentity join coverage:")
    log("  Transactions with identity record: %d / %d  (%.1f%%)"
        % (matched, len(txn), matched / len(txn) * 100))

    # Fraud rate among matched vs unmatched
    txn["has_identity"] = txn["TransactionID"].isin(idn["TransactionID"])
    fr_matched   = txn.loc[txn["has_identity"],  "isFraud"].mean() * 100
    fr_unmatched = txn.loc[~txn["has_identity"], "isFraud"].mean() * 100
    log("  Fraud rate — with identity    : %.2f%%" % fr_matched)
    log("  Fraud rate — without identity : %.2f%%" % fr_unmatched)
    log("  => Missingness correlates with fraud; use LEFT JOIN, keep all rows.")

    # ── Left-join ─────────────────────────────────────────────────────────────
    log("\nMerging (left join on TransactionID) …")
    df = txn.merge(idn, on="TransactionID", how="left")
    log("  Merged shape: %s" % str(df.shape))

    # ── Missing data audit ────────────────────────────────────────────────────
    log("\nTop-30 columns by missing %% (merged dataset):")
    miss = (df.isnull().mean() * 100).sort_values(ascending=False)
    for col, pct in miss.head(30).items():
        log("  %-30s  %.1f%%" % (col, pct))

    # Columns with >80% missing
    heavy_miss = miss[miss > 80]
    log("\nColumns with >80%% missing: %d" % len(heavy_miss))

    # Does missingness in V-columns correlate with fraud? Sample: V1
    if "V1" in df.columns:
        v1_miss_fraud = df.loc[df["V1"].isnull(), "isFraud"].mean() * 100
        v1_pres_fraud = df.loc[df["V1"].notna(),  "isFraud"].mean() * 100
        log("\nV1 missingness vs fraud rate:")
        log("  V1 missing  → fraud rate: %.2f%%" % v1_miss_fraud)
        log("  V1 present  → fraud rate: %.2f%%" % v1_pres_fraud)

    # ── Amount distribution ───────────────────────────────────────────────────
    log("\nTransactionAmt summary (by fraud label):")
    log(str(df.groupby("isFraud")["TransactionAmt"].describe().round(2)))

    # ── Schema overview ───────────────────────────────────────────────────────
    readable_cols = [c for c in df.columns
                     if not c.startswith("V") and not c.startswith("C")
                     and not c.startswith("D") and not c.startswith("M")]
    v_cols        = [c for c in df.columns if c.startswith("V")]
    log("\nReadable columns (%d): %s" % (len(readable_cols), readable_cols[:20]))
    log("Anonymized V-columns   : %d" % len(v_cols))

    # ── Figure 1: class balance bar ────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle("IEEE-CIS: Class Balance and Amount Distribution", fontsize=13)

    ax = axes[0]
    colors = ["steelblue", "crimson"]
    bars = ax.bar(["Legitimate", "Fraud"], fraud_counts[[0, 1]], color=colors)
    ax.set_title("Class Balance")
    ax.set_ylabel("Transactions")
    for bar, count, pct in zip(bars, fraud_counts[[0, 1]],
                                [100 - fraud_pct, fraud_pct]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                "%.1f%%" % pct, ha="center", va="bottom", fontsize=10)

    ax = axes[1]
    legit = df.loc[df["isFraud"] == 0, "TransactionAmt"].clip(upper=2000)
    ax.hist(legit, bins=60, color="steelblue", edgecolor="none", alpha=0.8)
    ax.set_title("Amount — Legitimate (clipped $2k)")
    ax.set_xlabel("Amount ($)")
    ax.set_ylabel("Count")

    ax = axes[2]
    fraud_amt = df.loc[df["isFraud"] == 1, "TransactionAmt"].clip(upper=2000)
    ax.hist(fraud_amt, bins=60, color="crimson", edgecolor="none", alpha=0.8)
    ax.set_title("Amount — Fraud (clipped $2k)")
    ax.set_xlabel("Amount ($)")

    savefig("ieee_cis_overview")

    # ── Figure 2: missing-data heatmap (top 40 cols) ──────────────────────────
    top40_miss = miss[miss > 0].head(40).index
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.barh(top40_miss[::-1], miss[top40_miss][::-1], color="coral")
    ax.set_xlabel("Missing (%)")
    ax.set_title("IEEE-CIS: Top 40 Columns by Missing Data %")
    ax.axvline(80, color="crimson", linestyle="--", linewidth=1, label="80% threshold")
    ax.legend()
    savefig("ieee_cis_missing")

    # ── Figure 3: fraud rate by ProductCD ─────────────────────────────────────
    if "ProductCD" in df.columns:
        fig, ax = plt.subplots(figsize=(7, 4))
        rate = fraud_rate(df, "ProductCD")
        rate.plot(kind="bar", ax=ax, color="darkorange", rot=0)
        ax.set_title("IEEE-CIS: Fraud Rate by ProductCD")
        ax.set_ylabel("Fraud Rate")
        savefig("ieee_cis_fraud_by_product")

    # ── Figure 4: fraud rate by card4 (network) ────────────────────────────────
    if "card4" in df.columns:
        fig, ax = plt.subplots(figsize=(7, 4))
        rate = fraud_rate(df, "card4")
        rate.plot(kind="bar", ax=ax, color="purple", rot=0)
        ax.set_title("IEEE-CIS: Fraud Rate by Card Network (card4)")
        ax.set_ylabel("Fraud Rate")
        savefig("ieee_cis_fraud_by_card_network")

    return df, miss


# ══════════════════════════════════════════════════════════════════════════════
#  2. Sparkov
# ══════════════════════════════════════════════════════════════════════════════

def explore_sparkov():
    section("Sparkov Simulated Credit Card Transactions")

    if not check_file(SPARKOV_TR) or not check_file(SPARKOV_TE):
        return None

    # ── Load — keep splits separate, then annotate ────────────────────────────
    log("Loading fraudTrain.csv …")
    train = pd.read_csv(SPARKOV_TR, parse_dates=["trans_date_trans_time"])
    log("Loading fraudTest.csv …")
    test  = pd.read_csv(SPARKOV_TE,  parse_dates=["trans_date_trans_time"])

    train["split"] = "train"
    test["split"]  = "test"
    df = pd.concat([train, test], ignore_index=True)

    log("  Train rows : %d  (%s – %s)"
        % (len(train),
           train["trans_date_trans_time"].min().date(),
           train["trans_date_trans_time"].max().date()))
    log("  Test rows  : %d  (%s – %s)"
        % (len(test),
           test["trans_date_trans_time"].min().date(),
           test["trans_date_trans_time"].max().date()))
    log("  Combined   : %d rows, %d cols" % df.shape)

    # ── Cardholder overlap warning ────────────────────────────────────────────
    train_cards = set(train["cc_num"].unique())
    test_cards  = set(test["cc_num"].unique())
    overlap     = train_cards & test_cards
    log("\nCardholder split analysis:")
    log("  Distinct cards train : %d" % len(train_cards))
    log("  Distinct cards test  : %d" % len(test_cards))
    log("  Cards in BOTH splits : %d" % len(overlap))
    log("  => Same cardholders appear in train & test (by design).")
    log("     Random re-shuffle would leak cardholder history across splits.")
    log("     Recommendation: keep time-based split (2019 train / 2020 test)")
    log("     or do a strict cardholder-level split if cross-customer")
    log("     generalisation is the evaluation target.")

    # ── Class imbalance ───────────────────────────────────────────────────────
    fraud_counts = df["is_fraud"].value_counts()
    fraud_pct    = df["is_fraud"].mean() * 100
    log("\nClass balance (combined):")
    log("  Legitimate : %d  (%.2f%%)" % (fraud_counts[0], 100 - fraud_pct))
    log("  Fraud      : %d  (%.2f%%)" % (fraud_counts[1], fraud_pct))

    for name, subset in [("Train", train), ("Test", test)]:
        p = subset["is_fraud"].mean() * 100
        log("  %s fraud rate: %.2f%%" % (name, p))

    # ── Amount distribution ───────────────────────────────────────────────────
    log("\namt summary by fraud:")
    log(str(df.groupby("is_fraud")["amt"].describe().round(2)))

    # ── Readable schema ───────────────────────────────────────────────────────
    log("\nAll columns: %s" % list(df.columns))
    log("No anonymized columns — fully human-readable schema.")
    log("Key geo fields: lat, long, merch_lat, merch_long, city, state")
    log("Key categorical: category, merchant, gender, job")

    miss = (df.isnull().mean() * 100).sort_values(ascending=False)
    any_missing = miss[miss > 0]
    if len(any_missing):
        log("\nColumns with missing data:")
        for col, pct in any_missing.items():
            log("  %-30s  %.2f%%" % (col, pct))
    else:
        log("\nNo missing data (Sparkov is synthetically generated).")

    # ── Category fraud rates ───────────────────────────────────────────────────
    log("\nFraud rate by category (top 10):")
    cat_rate = fraud_rate(df, "category", label="is_fraud").head(10)
    log(str(cat_rate.apply(lambda x: "%.2f%%" % (x * 100))))

    # ── Figure 5: class balance + amount ──────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle("Sparkov: Class Balance and Amount Distribution", fontsize=13)

    ax = axes[0]
    colors = ["steelblue", "crimson"]
    bars = ax.bar(["Legitimate", "Fraud"], fraud_counts[[0, 1]], color=colors)
    ax.set_title("Class Balance (combined)")
    ax.set_ylabel("Transactions")
    for bar, count, pct in zip(bars, fraud_counts[[0, 1]],
                                [100 - fraud_pct, fraud_pct]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                "%.1f%%" % pct, ha="center", va="bottom", fontsize=10)

    ax = axes[1]
    ax.hist(df.loc[df["is_fraud"] == 0, "amt"].clip(upper=500),
            bins=60, color="steelblue", edgecolor="none", alpha=0.8)
    ax.set_title("Amount — Legitimate (clipped $500)")
    ax.set_xlabel("Amount ($)")
    ax.set_ylabel("Count")

    ax = axes[2]
    ax.hist(df.loc[df["is_fraud"] == 1, "amt"].clip(upper=500),
            bins=60, color="crimson", edgecolor="none", alpha=0.8)
    ax.set_title("Amount — Fraud (clipped $500)")
    ax.set_xlabel("Amount ($)")

    savefig("sparkov_overview")

    # ── Figure 6: fraud rate by category ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    all_rate = fraud_rate(df, "category", label="is_fraud")
    all_rate.plot(kind="bar", ax=ax, color="darkorange", rot=45)
    ax.set_title("Sparkov: Fraud Rate by Transaction Category")
    ax.set_ylabel("Fraud Rate")
    savefig("sparkov_fraud_by_category")

    # ── Figure 7: transaction volume by month, split by fraud ─────────────────
    df["year_month"] = df["trans_date_trans_time"].dt.to_period("M")
    monthly = df.groupby(["year_month", "is_fraud"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(14, 4))
    monthly.plot(ax=ax, color=["steelblue", "crimson"])
    ax.set_title("Sparkov: Monthly Transaction Volume (0=legit, 1=fraud)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Transactions")
    ax.legend(["Legitimate", "Fraud"])
    savefig("sparkov_volume_over_time")

    # ── Figure 8: geographic scatter map (US bounding box) ────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fraud_df  = df[df["is_fraud"] == 1].sample(min(5000, (df["is_fraud"] == 1).sum()), random_state=42)
    legit_df  = df[df["is_fraud"] == 0].sample(min(5000, (df["is_fraud"] == 0).sum()), random_state=42)

    ax = axes[0]
    ax.scatter(legit_df["long"], legit_df["lat"],
               s=1, alpha=0.2, color="steelblue", label="Legitimate")
    ax.set_title("Legitimate Transaction Locations (sample 5k)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_xlim(-130, -65)
    ax.set_ylim(23, 50)

    ax = axes[1]
    ax.scatter(fraud_df["long"], fraud_df["lat"],
               s=3, alpha=0.4, color="crimson", label="Fraud")
    ax.set_title("Fraud Transaction Locations (sample 5k)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_xlim(-130, -65)
    ax.set_ylim(23, 50)

    savefig("sparkov_geo_fraud_map")

    # ── Figure 9: fraud by state (top 15) ────────────────────────────────────
    if "state" in df.columns:
        state_rate = fraud_rate(df, "state", label="is_fraud").head(15)
        fig, ax = plt.subplots(figsize=(10, 5))
        state_rate.plot(kind="bar", ax=ax, color="crimson", rot=0)
        ax.set_title("Sparkov: Fraud Rate by State (top 15)")
        ax.set_ylabel("Fraud Rate")
        savefig("sparkov_fraud_by_state")

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  Schema comparison
# ══════════════════════════════════════════════════════════════════════════════

def compare_schemas(ieee_df, sparkov_df):
    section("Cross-Dataset Schema Comparison")

    ieee_anon = [c for c in (ieee_df.columns if ieee_df is not None else [])
                 if c.startswith("V")]

    log("""
┌─────────────────────────┬───────────────────────┬──────────────────────────┐
│ Dimension               │ IEEE-CIS              │ Sparkov                  │
├─────────────────────────┼───────────────────────┼──────────────────────────┤
│ Total columns           │ %-21s │ %-23s  │
│ Anonymized V-columns    │ %-21s │ None — fully readable    │
│ Has geo (lat/long)      │ No                    │ Yes (4 coord columns)    │
│ Has cardholder details  │ card1-card6 (encoded) │ cc_num, name, gender     │
│ Has identity records    │ Yes (25%% coverage)    │ N/A                      │
│ Fraud label             │ isFraud (0/1)         │ is_fraud (0/1)           │
│ Imbalance               │ ~3.5%% fraud           │ ~0.5%% fraud              │
│ Time coverage           │ ~6 months             │ 2 years (2019-2020)      │
│ Source                  │ Vesta / real          │ Sparkov synthetic        │
│ Can concatenate?        │ No — incompatible feature sets                   │
└─────────────────────────┴──────────────────────────────────────────────────┘
""" % (
        str(len(ieee_df.columns)) if ieee_df is not None else "N/A",
        str(len(sparkov_df.columns)) if sparkov_df is not None else "N/A",
        str(len(ieee_anon)),
    ))

    log("Key incompatibility reasons:")
    log("  1. IEEE-CIS V1-V339 have no Sparkov equivalents.")
    log("  2. Sparkov has real location/merchant text; IEEE-CIS encodes these as integers.")
    log("  3. Fraud prevalence differs 7x — naive concatenation would distort class ratios.")
    log("  4. IEEE-CIS has a two-table identity join; Sparkov is a single flat table.")
    log("  => Train separate models per dataset; ensemble or compare afterwards.")


# ══════════════════════════════════════════════════════════════════════════════
#  Write summary markdown
# ══════════════════════════════════════════════════════════════════════════════

def write_summary():
    md = OUT / "summary.md"
    text = "\n".join(_summary_parts)
    md.write_text("# FraudShield — EDA Summary\n\n```\n%s\n```\n" % text, encoding="utf-8")
    print("\n[saved] summary written to %s" % md)


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("FraudShield EDA — outputs will be saved to %s\n" % OUT)

    ieee_df, ieee_miss = explore_ieee()
    sparkov_df         = explore_sparkov()

    if ieee_df is not None and sparkov_df is not None:
        compare_schemas(ieee_df, sparkov_df)

    write_summary()

    print("\nDone. Figures:")
    for f in sorted(FIGURES.glob("*.png")):
        print("  %s" % f)
