# Overfitting Mitigation

This document outlines the strategies implemented to mitigate overfitting in the predictive models.

## 1. Feature Importance Analysis

To better understand the model's decision-making process and identify potentially irrelevant or noisy features, a feature importance analysis step has been integrated into the training pipeline.

### Implementation

During each model training run (manual or automated), the following artifacts are generated:

1.  **CSV Report**: A file named `feature_importances.csv` is saved in the `reports/` directory. This file lists all features used by the model and their corresponding importance scores, sorted in descending order. This provides a quantitative measure of each feature's contribution.

2.  **Plot**: A bar chart named `feature_importances.png` is saved in the `reports/` directory. This chart visualizes the importance scores, making it easy to compare the relative importance of different features.

### How to Use

After running the training script (`scripts/train_model.py` or `scripts/retrain_model.py`), navigate to the `reports/` directory to view the generated files. This analysis helps in:

-   **Feature Selection**: Identifying and potentially removing features with very low importance scores that may not be contributing to the model's predictive power.
-   **Model Interpretability**: Gaining insights into what market indicators the model finds most significant.
-   **Debugging**: Spotting if the model is relying too heavily on a single feature, which could be a sign of data leakage or other issues.

## 2. Time-Series Cross-Validation

To further prevent overfitting and more accurately simulate live trading, the hyperparameter tuning process now uses `TimeSeriesSplit` for cross-validation.

### The Problem with Standard Cross-Validation

Standard k-fold cross-validation shuffles and splits the data randomly. In financial time-series, this is problematic because it can lead to the model being trained on future data and validated on past data, an issue known as "lookahead bias." This can result in an overly optimistic performance evaluation that does not generalize to live market conditions.

### Solution: `TimeSeriesSplit`

`TimeSeriesSplit` works by creating folds that respect the temporal order of the data. For example, in the first fold, it trains on the first 10% of the data and validates on the next 10%. In the second fold, it trains on the first 20% and validates on the third 10%, and so on.

This "walk-forward" validation method ensures that the model is always trained on past data and tested on future data, just as it would be in a live trading environment. This leads to a more realistic and robust evaluation of the model's performance.
