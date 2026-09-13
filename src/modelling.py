"""Train Ridge models and write forecasts to datamart."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.loading import load_data, read_sql, replace_table

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "hour",
    "day_of_week",
    "is_weekend",
    "demand_lag_1",
    "demand_lag_12",
    "demand_lag_288",
    "demand_roll_mean_12",
    "demand_roll_std_12",
    "price_lag_1",
    "price_lag_12",
    "netinterchange",
    "netinterchange_lag_1",
]
REGIONS = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"]
TARGETS = {"demand": "totaldemand", "price": "rrp"}
HORIZON_STEPS = 12


def _load_features() -> pd.DataFrame:
    df = read_sql("SELECT * FROM dwh.features ORDER BY regionid, settlementdate")
    if df.empty:
        return df
    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0.0
    return df.dropna(subset=FEATURE_COLS)


def train_models(df: pd.DataFrame | None = None) -> dict:
    if df is None:
        df = _load_features()
    if df.empty:
        print("No features available for training.")
        return {"models": {}, "metrics": pd.DataFrame()}

    metrics_rows = []
    models = {}
    for region in REGIONS:
        g = df[df["regionid"] == region].sort_values("settlementdate")
        if len(g) < 50:
            print(f"  skip {region}: only {len(g)} rows")
            continue
        split = int(len(g) * 0.8)
        train, test = g.iloc[:split], g.iloc[split:]
        X_train, X_test = train[FEATURE_COLS], test[FEATURE_COLS]
        for target_name, col in TARGETS.items():
            y_train, y_test = train[col], test[col]
            model = Ridge(alpha=1.0)
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
            mae = float(mean_absolute_error(y_test, pred))
            rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
            key = f"{region}_{target_name}"
            path = MODEL_DIR / f"{key}.joblib"
            joblib.dump({"model": model, "features": FEATURE_COLS}, path)
            models[key] = model
            metrics_rows.append(
                {
                    "trained_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "regionid": region,
                    "target": target_name,
                    "mae": mae,
                    "rmse": rmse,
                    "n_train": len(train),
                    "n_test": len(test),
                    "model_name": "Ridge",
                }
            )
            print(f"  {key}: MAE={mae:.2f} RMSE={rmse:.2f}")

    metrics = pd.DataFrame(metrics_rows)
    if not metrics.empty:
        replace_table(metrics, schema="datamart", table_name="dm_model_metrics")
    return {"models": models, "metrics": metrics}


def generate_forecasts(df: pd.DataFrame | None = None, horizon: int = HORIZON_STEPS) -> pd.DataFrame:
    if df is None:
        df = _load_features()
    if df.empty:
        print("No features for forecasting.")
        return pd.DataFrame()

    run_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for region in REGIONS:
        g = df[df["regionid"] == region].sort_values("settlementdate")
        if g.empty:
            continue
        for target_name, col in TARGETS.items():
            path = MODEL_DIR / f"{region}_{target_name}.joblib"
            if not path.exists():
                print(f"  missing model {path.name}")
                continue
            bundle = joblib.load(path)
            model, feats = bundle["model"], bundle["features"]
            last = g.iloc[-1].copy()
            base_ts = pd.Timestamp(last["settlementdate"])
            # ensure all feature keys exist
            for f in feats:
                if f not in last.index or pd.isna(last[f]):
                    last[f] = 0.0
            x = last[feats].astype(float).values.reshape(1, -1)
            for step in range(1, horizon + 1):
                pred = float(model.predict(x)[0])
                ts = base_ts + pd.Timedelta(minutes=5 * step)
                rows.append(
                    {
                        "forecast_run_at": run_at,
                        "settlementdate": ts.to_pydatetime(),
                        "regionid": region,
                        "target": target_name,
                        "prediction": pred,
                        "model_name": "Ridge",
                        "horizon_steps": step,
                    }
                )
                feat_list = list(feats)
                if target_name == "demand" and "demand_lag_1" in feat_list:
                    x[0, feat_list.index("demand_lag_1")] = pred
                if target_name == "price" and "price_lag_1" in feat_list:
                    x[0, feat_list.index("price_lag_1")] = pred
                if "hour" in feat_list:
                    x[0, feat_list.index("hour")] = ts.hour
                if "day_of_week" in feat_list:
                    x[0, feat_list.index("day_of_week")] = ts.dayofweek
                if "is_weekend" in feat_list:
                    x[0, feat_list.index("is_weekend")] = 1 if ts.dayofweek >= 5 else 0

    forecasts = pd.DataFrame(rows)
    if not forecasts.empty:
        load_data(forecasts, "dm_forecasts", schema="datamart", if_exists="append")
    return forecasts


def train_and_forecast():
    result = train_models()
    forecasts = generate_forecasts()
    return result, forecasts
