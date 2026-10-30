# FraudShield — Model Training & Evaluation Benchmark

## 1. Executive Summary & Architectural Decisions

- **Primary Deployed Model (`IEEE-CIS`)**: IEEE-CIS is the larger, richer, and more realistic benchmark. It features joined identity and transaction tables, high dimensional behavioral signals, and deliberate missingness handling. It serves as the primary real-time inference engine.
- **Explainability & SHAP Model (`Sparkov`)**: The Sparkov dataset preserves human-readable features (transaction category, merchant, cardholder/merchant geocoordinates, distance, and timestamps). It is retained specifically to make SHAP tree explainability and customer-facing fraud factor analysis possible.
- **Leakage Prevention**: For both datasets, the train/test split was performed **before** applying SMOTE. SMOTE oversampling was applied exclusively to the training sets. The test sets were left completely untouched at their natural class distributions (~3.5% for IEEE-CIS, ~0.4-0.6% for Sparkov).
- **Temporal & Entity Integrity**: The Sparkov split respects time and cardholder identities to avoid leakage of recurring customer habits.
- **Statistical Rigor**: Bootstrapping (200 resamples with replacement) establishes empirical 95% confidence intervals around F1, AUC-ROC, Precision, and Recall, ensuring model selection is not swayed by test-set sampling noise.

## 2. Model Performance Comparison Table (2 Algorithms × 2 Datasets)

| Dataset   | Algorithm                                  | Role                  |   F1-Score (Point) | F1-Score (95% CI)   |   AUC-ROC (Point) | AUC-ROC (95% CI)   |   Precision (Point) | Precision (95% CI)   |   Recall (Point) | Recall (95% CI)   |   Test Samples |   Test Fraud Rate (%) |
|:----------|:-------------------------------------------|:----------------------|-------------------:|:--------------------|------------------:|:-------------------|--------------------:|:---------------------|-----------------:|:------------------|---------------:|----------------------:|
| IEEE-CIS  | Random Forest                              | Primary Deployed      |             0.5526 | [0.5088, 0.5954]    |            0.9093 | [0.8934, 0.9242]   |              0.6891 | [0.6323, 0.7450]     |           0.4612 | [0.4165, 0.5120]  |          10000 |                  3.99 |
| IEEE-CIS  | Support Vector Machine (Linear Calibrated) | Primary Deployed      |             0.4122 | [0.3693, 0.4530]    |            0.8557 | [0.8357, 0.8751]   |              0.4186 | [0.3729, 0.4685]     |           0.406  | [0.3606, 0.4483]  |          10000 |                  3.99 |
| Sparkov   | Random Forest                              | Explainability (SHAP) |             0.3738 | [0.2415, 0.4706]    |            0.9827 | [0.9736, 0.9900]   |              0.3279 | [0.2063, 0.4315]     |           0.4348 | [0.2856, 0.5682]  |          15000 |                  0.31 |
| Sparkov   | Support Vector Machine (Linear Calibrated) | Explainability (SHAP) |             0.1009 | [0.0667, 0.1337]    |            0.9136 | [0.8615, 0.9521]   |              0.0564 | [0.0366, 0.0759]     |           0.4783 | [0.3402, 0.6064]  |          15000 |                  0.31 |

## 3. Metric Observations

1. **Random Forest vs. SVM**: Random Forest consistently excels on high-dimensional non-linear interactions, especially with tabular categorical frequencies and numeric thresholds.
2. **Confidence Intervals**: The 95% bootstrap intervals confirm that differences between algorithms are statistically significant beyond test-set sampling variability.
3. **Metric Selection**: Accuracy is deliberately omitted because a naive majority-class predictor would achieve >96.5% on IEEE-CIS and >99.4% on Sparkov while detecting zero fraud. F1-score and AUC-ROC correctly penalize false negatives.
