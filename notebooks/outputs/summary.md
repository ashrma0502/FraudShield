# FraudShield — EDA Summary

```

======================================================================
  IEEE-CIS Fraud Detection
======================================================================
Loading train_transaction.csv …
Loading train_identity.csv …
  Transaction rows : 590540
  Identity rows    : 144233
  Transaction cols : 394
  Identity cols    : 41

Class balance (transactions):
  Legitimate : 569877  (96.50%)
  Fraud      : 20663  (3.50%)

Identity join coverage:
  Transactions with identity record: 144233 / 590540  (24.4%)
  Fraud rate — with identity    : 7.85%
  Fraud rate — without identity : 2.09%
  => Missingness correlates with fraud; use LEFT JOIN, keep all rows.

Merging (left join on TransactionID) …
  Merged shape: (590540, 435)

Top-30 columns by missing %% (merged dataset):
  id_24                           99.2%
  id_25                           99.1%
  id_07                           99.1%
  id_08                           99.1%
  id_21                           99.1%
  id_26                           99.1%
  id_23                           99.1%
  id_22                           99.1%
  id_27                           99.1%
  dist2                           93.6%
  D7                              93.4%
  id_18                           92.4%
  D13                             89.5%
  D14                             89.5%
  D12                             89.0%
  id_04                           88.8%
  id_03                           88.8%
  D6                              87.6%
  id_33                           87.6%
  D8                              87.3%
  D9                              87.3%
  id_10                           87.3%
  id_09                           87.3%
  id_30                           86.9%
  id_32                           86.9%
  id_34                           86.8%
  id_14                           86.4%
  V156                            86.1%
  V149                            86.1%
  V163                            86.1%

Columns with >80% missing: 74

V1 missingness vs fraud rate:
  V1 missing  → fraud rate: 5.21%
  V1 present  → fraud rate: 1.96%

TransactionAmt summary (by fraud label):
            count    mean     std   min    25%   50%    75%       max
isFraud                                                              
0        569877.0  134.51  239.40  0.25  43.97  68.5  120.0  31937.39
1         20663.0  149.24  232.21  0.29  35.04  75.0  161.0   5191.00

Readable columns (56): ['TransactionID', 'isFraud', 'TransactionDT', 'TransactionAmt', 'ProductCD', 'card1', 'card2', 'card3', 'card4', 'card5', 'card6', 'addr1', 'addr2', 'dist1', 'dist2', 'P_emaildomain', 'R_emaildomain', 'has_identity', 'id_01', 'id_02']
Anonymized V-columns   : 339

======================================================================
  Sparkov Simulated Credit Card Transactions
======================================================================
Loading fraudTrain.csv …
Loading fraudTest.csv …
  Train rows : 1296675  (2019-01-01 – 2020-06-21)
  Test rows  : 555719  (2020-06-21 – 2020-12-31)
  Combined   : 1852394 rows, 24 cols

Cardholder split analysis:
  Distinct cards train : 983
  Distinct cards test  : 924
  Cards in BOTH splits : 908
  => Same cardholders appear in train & test (by design).
     Random re-shuffle would leak cardholder history across splits.
     Recommendation: keep time-based split (2019 train / 2020 test)
     or do a strict cardholder-level split if cross-customer
     generalisation is the evaluation target.

Class balance (combined):
  Legitimate : 1842743  (99.48%)
  Fraud      : 9651  (0.52%)
  Train fraud rate: 0.58%
  Test fraud rate: 0.39%

amt summary by fraud:
              count    mean     std   min     25%     50%     75%       max
is_fraud                                                                   
0         1842743.0   67.65  153.55  1.00    9.61   47.24   82.56  28948.90
1            9651.0  530.66  391.03  1.06  240.08  390.00  902.36   1376.04

All columns: ['Unnamed: 0', 'trans_date_trans_time', 'cc_num', 'merchant', 'category', 'amt', 'first', 'last', 'gender', 'street', 'city', 'state', 'zip', 'lat', 'long', 'city_pop', 'job', 'dob', 'trans_num', 'unix_time', 'merch_lat', 'merch_long', 'is_fraud', 'split']
No anonymized columns — fully human-readable schema.
Key geo fields: lat, long, merch_lat, merch_long, city, state
Key categorical: category, merchant, gender, job

No missing data (Sparkov is synthetically generated).

Fraud rate by category (top 10):
category
shopping_net     1.59%
misc_net         1.30%
grocery_pos      1.26%
shopping_pos     0.63%
gas_transport    0.41%
misc_pos         0.28%
grocery_net      0.27%
travel           0.27%
personal_care    0.22%
entertainment    0.22%
Name: is_fraud, dtype: str

======================================================================
  Cross-Dataset Schema Comparison
======================================================================

┌─────────────────────────┬───────────────────────┬──────────────────────────┐
│ Dimension               │ IEEE-CIS              │ Sparkov                  │
├─────────────────────────┼───────────────────────┼──────────────────────────┤
│ Total columns           │ 435                   │ 25                       │
│ Anonymized V-columns    │ 339                   │ None — fully readable    │
│ Has geo (lat/long)      │ No                    │ Yes (4 coord columns)    │
│ Has cardholder details  │ card1-card6 (encoded) │ cc_num, name, gender     │
│ Has identity records    │ Yes (25% coverage)    │ N/A                      │
│ Fraud label             │ isFraud (0/1)         │ is_fraud (0/1)           │
│ Imbalance               │ ~3.5% fraud           │ ~0.5% fraud              │
│ Time coverage           │ ~6 months             │ 2 years (2019-2020)      │
│ Source                  │ Vesta / real          │ Sparkov synthetic        │
│ Can concatenate?        │ No — incompatible feature sets                   │
└─────────────────────────┴──────────────────────────────────────────────────┘

Key incompatibility reasons:
  1. IEEE-CIS V1-V339 have no Sparkov equivalents.
  2. Sparkov has real location/merchant text; IEEE-CIS encodes these as integers.
  3. Fraud prevalence differs 7x — naive concatenation would distort class ratios.
  4. IEEE-CIS has a two-table identity join; Sparkov is a single flat table.
  => Train separate models per dataset; ensemble or compare afterwards.
```
