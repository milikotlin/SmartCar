"""
Stage 2 - Component risk classifiers: three independent XGBoost binary
classifiers (Engine / Brakes / Electrical), each trained on exactly the
feature vector the SRS specifies for the live pipeline: Vehicle_Age, Mileage,
Days_Since_Last_Maintenance, Brand_Reliability_Index.

Data source (substituting the SRS's "Kaggle Dataset 1 - Logistics Vehicle
Maintenance History", a numbered course reference we didn't have access to):
  "Vehicle Maintenance Data" (chavindudulaj), 50,000 rows, MIT license.
  https://www.kaggle.com/datasets/chavindudulaj/vehicle-maintenance-data
  Includes Truck/Van/Bus vehicle types, giving it a genuine fleet/logistics flavor.

Label construction:
  - Brakes:      Brake_Condition == "Worn Out"
  - Electrical:  Battery_Status == "Weak"
  - Engine:      the dataset has no dedicated engine-condition column, so we
                 reuse the overall Need_Maintenance label as the closest
                 available proxy. Documented as a known limitation.

Brand_Reliability_Index: the dataset has no brand/make column (only a coarse
vehicle *type*), so this feature is injected as an UNINFORMATIVE random value
during training - see brand_reliability.py for why, and the feature
importance printout below for confirmation the model correctly learns to
mostly ignore it.
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, recall_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
FEATURE_COLUMNS = ["vehicle_age", "mileage", "days_since_last_maintenance", "brand_reliability_index"]

CONFIDENCE_THRESHOLD = 0.60  # SRS: below this, the API falls back to a rule-based schedule


def load_and_engineer_features() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "vehicle_maintenance_data.csv")

    before = len(df)
    df = df.dropna(subset=["Mileage", "Vehicle_Age", "Last_Service_Date", "Brake_Condition", "Battery_Status", "Need_Maintenance"])
    duplicates = df.duplicated().sum()
    df = df.drop_duplicates()
    print(f"Rows: {before} -> {len(df)} (dropped {before - len(df)} null/duplicate rows, {duplicates} exact dupes found)")

    df["Last_Service_Date"] = pd.to_datetime(df["Last_Service_Date"])
    reference_date = df["Last_Service_Date"].max() + pd.Timedelta(days=1)
    df["days_since_last_maintenance"] = (reference_date - df["Last_Service_Date"]).dt.days

    rng = np.random.default_rng(42)
    df["brand_reliability_index"] = rng.integers(40, 96, size=len(df))

    df = df.rename(columns={"Vehicle_Age": "vehicle_age", "Mileage": "mileage"})

    df["target_brakes"] = (df["Brake_Condition"] == "Worn Out").astype(int)
    df["target_electrical"] = (df["Battery_Status"] == "Weak").astype(int)
    df["target_engine"] = df["Need_Maintenance"].astype(int)

    return df


def train_and_evaluate(df: pd.DataFrame, target_col: str, component_name: str, train_idx, test_idx) -> XGBClassifier:
    X = df[FEATURE_COLUMNS]
    y = df[target_col]
    X_train, X_test = X.loc[train_idx], X.loc[test_idx]
    y_train, y_test = y.loc[train_idx], y.loc[test_idx]

    print(f"\n{'=' * 60}\n{component_name} - target class balance (train): {y_train.mean():.1%} positive\n{'=' * 60}")

    baseline = LogisticRegression(max_iter=1000, class_weight="balanced")
    baseline.fit(X_train, y_train)
    baseline_preds = baseline.predict(X_test)
    print(f"\n[Baseline: Logistic Regression]")
    print(classification_report(y_test, baseline_preds, target_names=["no-risk", "at-risk"], digits=3))

    neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=neg / pos,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)
    xgb_preds = model.predict(X_test)
    xgb_probs = model.predict_proba(X_test)[:, 1]

    print(f"\n[Candidate: XGBoost]")
    print(classification_report(y_test, xgb_preds, target_names=["no-risk", "at-risk"], digits=3))
    print(f"Confusion matrix (rows=actual, cols=predicted):\n{confusion_matrix(y_test, xgb_preds)}")
    print(f"Recall on the at-risk class: {recall_score(y_test, xgb_preds):.3f}  <- the metric the SRS asks to optimize")

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_))
    print(f"Feature importances: {', '.join(f'{k}={v:.3f}' for k, v in importances.items())}")

    low_confidence = ((xgb_probs > (1 - CONFIDENCE_THRESHOLD)) & (xgb_probs < CONFIDENCE_THRESHOLD)).mean()
    print(f"Share of test predictions below the {CONFIDENCE_THRESHOLD:.0%} confidence threshold (-> rule-based fallback): {low_confidence:.1%}")

    return model


def main() -> None:
    df = load_and_engineer_features()
    print(f"\nDays_Since_Last_Maintenance range: {df['days_since_last_maintenance'].min()}-{df['days_since_last_maintenance'].max()} days")
    print(f"Class balance - Brakes (worn out): {df['target_brakes'].mean():.1%}")
    print(f"Class balance - Electrical (weak battery): {df['target_electrical'].mean():.1%}")
    print(f"Class balance - Engine (Need_Maintenance proxy): {df['target_engine'].mean():.1%}")

    train_idx, test_idx = train_test_split(df.index, test_size=0.2, random_state=42, stratify=df["target_engine"])

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for target_col, component_name, filename in [
        ("target_brakes", "Brakes", "classifier_brakes.joblib"),
        ("target_electrical", "Electrical", "classifier_electrical.joblib"),
        ("target_engine", "Engine", "classifier_engine.joblib"),
    ]:
        model = train_and_evaluate(df, target_col, component_name, train_idx, test_idx)
        joblib.dump(model, MODELS_DIR / filename)
        print(f"Saved {MODELS_DIR / filename}")


if __name__ == "__main__":
    main()
