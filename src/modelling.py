"""
Train/compare models and write forecasts.

Two grains in one module:
  A) 5-minute  — SeasonalNaive / Ridge / HistGB, ~1 hour horizon (existing)
  B) Hourly    — aggregate panel → 1-day (24h) and 1-week (168h) forecasts (additive)
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.loading import load_data, read_sql, replace_table

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
HOURLY_MODEL_DIR = MODEL_DIR / "hourly"
HOURLY_MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
REGIONS = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"]
TARGETS = {"demand": "totaldemand", "price": "rrp"}


def _rmse(y_true, y_pred) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


# ===========================================================================
# A) 5-MINUTE  (existing behaviour — do not change call sites)
# ===========================================================================
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
HORIZON_STEPS = 12  # ~1 hour at 5-min grain
PRIMARY_MODEL = "HistGB"


def _load_features() -> pd.DataFrame:
    df = read_sql("SELECT * FROM dwh.features ORDER BY regionid, settlementdate")
    if df.empty:
        return df
    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0.0
    if "demand_roll_std_12" in df.columns:
        df["demand_roll_std_12"] = df["demand_roll_std_12"].fillna(0.0)
    df = df.dropna(subset=FEATURE_COLS)
    return df.reset_index(drop=True)


def _naive_predict(test: pd.DataFrame, target_col: str) -> np.ndarray:
    """Seasonal naive: lag_288 demand (1 day) or lag_12 price."""
    if target_col == "totaldemand" and "demand_lag_288" in test.columns:
        pred = test["demand_lag_288"].astype(float)
        if pred.notna().any():
            return pred.fillna(test.get("demand_lag_12", pred)).values
    if target_col == "rrp" and "price_lag_12" in test.columns:
        return test["price_lag_12"].astype(float).fillna(test.get("price_lag_1", 0)).values
    if "demand_lag_12" in test.columns and target_col == "totaldemand":
        return test["demand_lag_12"].astype(float).fillna(0).values
    return np.full(len(test), float(test[target_col].mean() if len(test) else 0.0))


def _walk_forward_scores(
    g: pd.DataFrame,
    target_col: str,
    model_kind: str,
    min_train_frac: float = 0.5,
    n_folds: int = 4,
) -> tuple[float, float]:
    g = g.dropna(subset=FEATURE_COLS + [target_col]).sort_values("settlementdate")
    n = len(g)
    if n < 80:
        return float("nan"), float("nan")
    min_train = max(40, int(n * min_train_frac))
    fold_size = max(12, (n - min_train) // n_folds)
    maes, rmses = [], []
    for i in range(n_folds):
        end = min_train + i * fold_size
        if end + fold_size > n:
            break
        train, test = g.iloc[:end], g.iloc[end : end + fold_size]
        if len(test) < 5:
            continue
        if model_kind == "SeasonalNaive":
            pred = _naive_predict(test, target_col)
        else:
            X_tr, y_tr = train[FEATURE_COLS], train[target_col]
            X_te = test[FEATURE_COLS]
            if model_kind == "Ridge":
                m = Ridge(alpha=1.0)
            else:
                m = HistGradientBoostingRegressor(max_depth=6, max_iter=100, random_state=42)
            m.fit(X_tr, y_tr)
            pred = m.predict(X_te)
        y = test[target_col].values
        maes.append(mean_absolute_error(y, pred))
        rmses.append(_rmse(y, pred))
    if not maes:
        return float("nan"), float("nan")
    return float(np.mean(maes)), float(np.mean(rmses))


def train_models(df: pd.DataFrame | None = None) -> dict:
    """Compare SeasonalNaive, Ridge, HistGB on 5-min features; save primary models."""
    if df is None:
        df = _load_features()
    if df.empty:
        print("No features available for training.")
        return {"models": {}, "metrics": pd.DataFrame()}

    metrics_rows = []
    models = {}
    trained_at = datetime.now(timezone.utc).replace(tzinfo=None)

    for region in REGIONS:
        g = df[df["regionid"] == region].sort_values("settlementdate")
        g = g.dropna(subset=FEATURE_COLS + ["rrp", "totaldemand"])
        if len(g) < 50:
            print(f"  skip {region}: only {len(g)} rows")
            continue

        split = int(len(g) * 0.8)
        train, test = g.iloc[:split], g.iloc[split:]
        if len(test) < 10:
            print(f"  skip {region}: test set too small")
            continue

        for target_name, col in TARGETS.items():
            X_train, X_test = train[FEATURE_COLS], test[FEATURE_COLS]
            y_train, y_test = train[col], test[col]

            candidates = {}
            naive_pred = _naive_predict(test, col)
            candidates["SeasonalNaive"] = ("naive", naive_pred, None)

            ridge = Ridge(alpha=1.0)
            ridge.fit(X_train, y_train)
            candidates["Ridge"] = ("sklearn", ridge.predict(X_test), ridge)

            hgb = HistGradientBoostingRegressor(
                max_depth=6, max_iter=120, learning_rate=0.08, random_state=42
            )
            hgb.fit(X_train, y_train)
            candidates["HistGB"] = ("sklearn", hgb.predict(X_test), hgb)

            for model_name, (_, pred, fitted) in candidates.items():
                mae = float(mean_absolute_error(y_test, pred))
                rmse = _rmse(y_test, pred)
                cv_mae, cv_rmse = _walk_forward_scores(g, col, model_name)
                metrics_rows.append(
                    {
                        "trained_at": trained_at,
                        "regionid": region,
                        "target": target_name,
                        "model_name": model_name,
                        "mae": mae,
                        "rmse": rmse,
                        "cv_mae": cv_mae if cv_mae == cv_mae else None,
                        "cv_rmse": cv_rmse if cv_rmse == cv_rmse else None,
                        "n_train": len(train),
                        "n_test": len(test),
                    }
                )
                msg = f"  {region} {target_name} {model_name}: MAE={mae:.2f} RMSE={rmse:.2f}"
                if cv_mae == cv_mae:
                    msg += f" cv_MAE={cv_mae:.2f}"
                print(msg)

            primary = candidates[PRIMARY_MODEL][2]
            if primary is None:
                primary = candidates["Ridge"][2]
            key = f"{region}_{target_name}"
            path = MODEL_DIR / f"{key}.joblib"
            joblib.dump(
                {"model": primary, "features": FEATURE_COLS, "model_name": PRIMARY_MODEL},
                path,
            )
            models[key] = primary

    metrics = pd.DataFrame(metrics_rows)
    if not metrics.empty:
        replace_table(metrics, schema="datamart", table_name="dm_model_metrics")
        try:
            winners = (
                metrics.sort_values("mae")
                .groupby(["regionid", "target"], as_index=False)
                .first()[["regionid", "target", "model_name", "mae", "rmse"]]
            )
            winners = winners.rename(columns={"model_name": "best_model"})
            print("\nBest model by MAE (hold-out):")
            print(winners.to_string(index=False))
        except Exception as e:
            print("winner summary skip:", e)

    return {"models": models, "metrics": metrics}


def generate_forecasts(df: pd.DataFrame | None = None, horizon: int = HORIZON_STEPS) -> pd.DataFrame:
    """5-min multi-step forecast (~1 hour by default)."""
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
            model_name = bundle.get("model_name", PRIMARY_MODEL)
            last = g.iloc[-1].copy()
            base_ts = pd.Timestamp(last["settlementdate"])
            for f in feats:
                if f not in last.index or pd.isna(last[f]):
                    last[f] = 0.0
            x_df = last[feats].astype(float).to_frame().T
            for step in range(1, horizon + 1):
                pred = float(model.predict(x_df)[0])
                ts = base_ts + pd.Timedelta(minutes=5 * step)
                rows.append(
                    {
                        "forecast_run_at": run_at,
                        "settlementdate": ts.to_pydatetime(),
                        "regionid": region,
                        "target": target_name,
                        "prediction": pred,
                        "model_name": model_name,
                        "horizon_steps": step,
                    }
                )
                feat_list = list(feats)
                if target_name == "demand" and "demand_lag_1" in feat_list:
                    x_df.iloc[0, feat_list.index("demand_lag_1")] = pred
                if target_name == "price" and "price_lag_1" in feat_list:
                    x_df.iloc[0, feat_list.index("price_lag_1")] = pred
                if "hour" in feat_list:
                    x_df.iloc[0, feat_list.index("hour")] = ts.hour
                if "day_of_week" in feat_list:
                    x_df.iloc[0, feat_list.index("day_of_week")] = ts.dayofweek
                if "is_weekend" in feat_list:
                    x_df.iloc[0, feat_list.index("is_weekend")] = 1 if ts.dayofweek >= 5 else 0

    forecasts = pd.DataFrame(rows)
    if not forecasts.empty:
        load_data(forecasts, "dm_forecasts", schema="datamart", if_exists="append")
    return forecasts


def train_and_forecast():
    """Existing entry: 5-min train + ~1h forecast only."""
    result = train_models()
    forecasts = generate_forecasts()
    return result, forecasts


# ===========================================================================
# B) HOURLY aggregated — 1 day (24h) and 1 week (168h)
# ===========================================================================
HOURLY_FEATURE_COLS = [
    "hour",
    "day_of_week",
    "is_weekend",
    "demand_lag_1",
    "demand_lag_24",
    "demand_roll_mean_24",
    "price_lag_1",
    "price_lag_24",
    "netinterchange",
    "netinterchange_lag_1",
]
HORIZON_1D = 24
HORIZON_1W = 168


def load_panel() -> pd.DataFrame:
    df = read_sql(
        """
        SELECT settlementdate, regionid, rrp, totaldemand, netinterchange
        FROM dwh.panel
        ORDER BY regionid, settlementdate
        """
    )
    if df.empty:
        return df
    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    df["rrp"] = pd.to_numeric(df["rrp"], errors="coerce")
    df["totaldemand"] = pd.to_numeric(df["totaldemand"], errors="coerce")
    if "netinterchange" not in df.columns:
        df["netinterchange"] = 0.0
    df["netinterchange"] = pd.to_numeric(df["netinterchange"], errors="coerce").fillna(0.0)
    return df.dropna(subset=["settlementdate", "regionid", "rrp", "totaldemand"])


def aggregate_hourly(panel: pd.DataFrame) -> pd.DataFrame:
    """5-min panel → hourly averages per region."""
    df = panel.copy()
    df["hour_start"] = df["settlementdate"].dt.floor("h")
    return (
        df.groupby(["regionid", "hour_start"], as_index=False)
        .agg(
            rrp=("rrp", "mean"),
            totaldemand=("totaldemand", "mean"),
            netinterchange=("netinterchange", "mean"),
            n_intervals=("rrp", "count"),
        )
        .sort_values(["regionid", "hour_start"])
        .reset_index(drop=True)
    )


def build_hourly_features(hourly: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for region, g in hourly.groupby("regionid", sort=False):
        g = g.sort_values("hour_start").copy()
        g["hour"] = g["hour_start"].dt.hour
        g["day_of_week"] = g["hour_start"].dt.dayofweek
        g["is_weekend"] = (g["day_of_week"] >= 5).astype(int)
        g["demand_lag_1"] = g["totaldemand"].shift(1)
        g["demand_lag_24"] = g["totaldemand"].shift(24)
        g["demand_roll_mean_24"] = g["totaldemand"].rolling(24, min_periods=1).mean()
        g["price_lag_1"] = g["rrp"].shift(1)
        g["price_lag_24"] = g["rrp"].shift(24)
        g["netinterchange_lag_1"] = g["netinterchange"].shift(1)
        frames.append(g)
    out = pd.concat(frames, ignore_index=True)
    return out.dropna(subset=HOURLY_FEATURE_COLS + ["rrp", "totaldemand"]).reset_index(drop=True)


def train_hourly_models(features: pd.DataFrame | None = None) -> pd.DataFrame:
    if features is None:
        panel = load_panel()
        if panel.empty:
            print("No panel data for hourly models.")
            return pd.DataFrame()
        features = build_hourly_features(aggregate_hourly(panel))
    if features.empty:
        print("No hourly features.")
        return pd.DataFrame()

    metrics_rows = []
    trained_at = datetime.now(timezone.utc).replace(tzinfo=None)

    for region in REGIONS:
        g = features[features["regionid"] == region].sort_values("hour_start")
        if len(g) < 48:
            print(f"  skip hourly {region}: only {len(g)} rows")
            continue
        split = int(len(g) * 0.8)
        train, test = g.iloc[:split], g.iloc[split:]
        if len(test) < 12:
            continue

        for target_name, col in TARGETS.items():
            X_tr, X_te = train[HOURLY_FEATURE_COLS], test[HOURLY_FEATURE_COLS]
            y_tr, y_te = train[col], test[col]
            model = HistGradientBoostingRegressor(
                max_depth=6, max_iter=120, learning_rate=0.08, random_state=42
            )
            model_name = "HistGB_hourly"
            try:
                model.fit(X_tr, y_tr)
            except Exception as e:
                print(f"  HistGB hourly failed {region} {target_name}: {e}; Ridge")
                model = Ridge(alpha=1.0)
                model.fit(X_tr, y_tr)
                model_name = "Ridge_hourly"

            pred = model.predict(X_te)
            mae = float(mean_absolute_error(y_te, pred))
            rmse = _rmse(y_te, pred)
            path = HOURLY_MODEL_DIR / f"{region}_{target_name}.joblib"
            joblib.dump(
                {"model": model, "features": HOURLY_FEATURE_COLS, "model_name": model_name},
                path,
            )
            metrics_rows.append(
                {
                    "trained_at": trained_at,
                    "regionid": region,
                    "target": target_name,
                    "model_name": model_name,
                    "grain": "hourly",
                    "mae": mae,
                    "rmse": rmse,
                    "n_train": len(train),
                    "n_test": len(test),
                }
            )
            print(f"  hourly {region} {target_name} {model_name}: MAE={mae:.2f} RMSE={rmse:.2f}")

    metrics = pd.DataFrame(metrics_rows)
    if not metrics.empty:
        replace_table(metrics, schema="datamart", table_name="dm_hourly_model_metrics")
    return metrics


def _forecast_hourly_horizon(
    features: pd.DataFrame,
    horizon_hours: int,
    horizon_label: str,
    run_at: datetime,
) -> list[dict]:
    rows = []
    for region in REGIONS:
        g = features[features["regionid"] == region].sort_values("hour_start")
        if g.empty:
            continue
        for target_name, col in TARGETS.items():
            path = HOURLY_MODEL_DIR / f"{region}_{target_name}.joblib"
            if not path.exists():
                print(f"  missing hourly model {path.name}")
                continue
            bundle = joblib.load(path)
            model = bundle["model"]
            feats = bundle["features"]
            model_name = bundle.get("model_name", "HistGB_hourly")
            last = g.iloc[-1].copy()
            base_ts = pd.Timestamp(last["hour_start"])
            for f in feats:
                if f not in last.index or pd.isna(last[f]):
                    last[f] = 0.0
            x_df = last[feats].astype(float).to_frame().T

            for step in range(1, horizon_hours + 1):
                pred = float(model.predict(x_df)[0])
                ts = base_ts + pd.Timedelta(hours=step)
                rows.append(
                    {
                        "forecast_run_at": run_at,
                        "forecast_hour": ts.to_pydatetime(),
                        "regionid": region,
                        "target": target_name,
                        "prediction": pred,
                        "model_name": model_name,
                        "horizon_hours": step,
                        "horizon_label": horizon_label,
                        "grain": "hourly",
                    }
                )
                feat_list = list(feats)
                if target_name == "demand" and "demand_lag_1" in feat_list:
                    x_df.iloc[0, feat_list.index("demand_lag_1")] = pred
                if target_name == "price" and "price_lag_1" in feat_list:
                    x_df.iloc[0, feat_list.index("price_lag_1")] = pred
                if "hour" in feat_list:
                    x_df.iloc[0, feat_list.index("hour")] = ts.hour
                if "day_of_week" in feat_list:
                    x_df.iloc[0, feat_list.index("day_of_week")] = ts.dayofweek
                if "is_weekend" in feat_list:
                    x_df.iloc[0, feat_list.index("is_weekend")] = 1 if ts.dayofweek >= 5 else 0
    return rows


def generate_hourly_forecasts(
    features: pd.DataFrame | None = None,
    do_1d: bool = True,
    do_1w: bool = True,
) -> pd.DataFrame:
    if features is None:
        panel = load_panel()
        if panel.empty:
            return pd.DataFrame()
        features = build_hourly_features(aggregate_hourly(panel))
    if features.empty:
        return pd.DataFrame()

    run_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rows: list[dict] = []
    if do_1d:
        rows.extend(_forecast_hourly_horizon(features, HORIZON_1D, "1d", run_at))
    if do_1w:
        rows.extend(_forecast_hourly_horizon(features, HORIZON_1W, "1w", run_at))

    forecasts = pd.DataFrame(rows)
    if not forecasts.empty:
        replace_table(forecasts, schema="datamart", table_name="dm_hourly_forecasts")
        print(f"  hourly forecasts written: {len(forecasts):,} rows")
    return forecasts



def ensure_hourly_tables() -> None:
    """Create hourly datamart tables if missing (no manual migrate required)."""
    from sqlalchemy import text
    from src.loading import get_engine

    ddl = [
        """
        CREATE TABLE IF NOT EXISTS datamart.dm_hourly_model_metrics (
            trained_at   TIMESTAMP NOT NULL,
            regionid     TEXT NOT NULL,
            target       TEXT NOT NULL,
            model_name   TEXT NOT NULL,
            grain        TEXT NOT NULL DEFAULT 'hourly',
            mae          DOUBLE PRECISION,
            rmse         DOUBLE PRECISION,
            n_train      INTEGER,
            n_test       INTEGER,
            PRIMARY KEY (trained_at, regionid, target, model_name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS datamart.dm_hourly_forecasts (
            forecast_run_at  TIMESTAMP NOT NULL,
            forecast_hour    TIMESTAMP NOT NULL,
            regionid         TEXT      NOT NULL,
            target           TEXT      NOT NULL,
            prediction       DOUBLE PRECISION,
            model_name       TEXT,
            horizon_hours    INTEGER,
            horizon_label    TEXT,
            grain            TEXT DEFAULT 'hourly',
            PRIMARY KEY (forecast_run_at, forecast_hour, regionid, target, horizon_label)
        )
        """,
    ]
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    engine.dispose()
    print("  hourly datamart tables ensured")


def train_and_forecast_hourly(do_1d: bool = True, do_1w: bool = True) -> dict:
    """Hourly aggregate train + 1d/1w forecasts (5-min pipeline unchanged)."""
    print("=" * 60)
    print("HOURLY aggregated forecast (1d / 1w)")
    print("=" * 60)
    ensure_hourly_tables()
    panel = load_panel()
    if panel.empty:
        print("No dwh.panel data.")
        return {"metrics": pd.DataFrame(), "forecasts": pd.DataFrame()}
    hourly = aggregate_hourly(panel)
    print(f"  aggregated {len(panel):,} 5-min rows → {len(hourly):,} hourly rows")
    features = build_hourly_features(hourly)
    print(f"  hourly feature rows: {len(features):,}")
    metrics = train_hourly_models(features)
    forecasts = generate_hourly_forecasts(features, do_1d=do_1d, do_1w=do_1w)
    return {"metrics": metrics, "forecasts": forecasts}


def train_and_forecast_all(include_hourly: bool = False, do_1d: bool = True, do_1w: bool = True):
    """
    Convenience: always run 5-min; optionally also hourly 1d/1w.
    Weekly DAG can keep calling train_and_forecast() only.
    """
    result, forecasts = train_and_forecast()
    hourly = None
    if include_hourly:
        hourly = train_and_forecast_hourly(do_1d=do_1d, do_1w=do_1w)
    return result, forecasts, hourly
