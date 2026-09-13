"""Transform staging data → DWH panel + feature tables."""
from __future__ import annotations

import pandas as pd


def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    df = df.dropna(subset=["settlementdate"]).sort_values(["regionid", "settlementdate"])
    if "netinterchange" not in df.columns:
        df["netinterchange"] = 0.0
    df["hour"] = df["settlementdate"].dt.hour
    df["day"] = df["settlementdate"].dt.day
    df["month"] = df["settlementdate"].dt.month
    df["day_of_week"] = df["settlementdate"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    return df[
        [
            "settlementdate",
            "regionid",
            "rrp",
            "totaldemand",
            "netinterchange",
            "hour",
            "day",
            "month",
            "day_of_week",
            "is_weekend",
        ]
    ]


def build_features(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for region, g in panel.groupby("regionid", sort=False):
        g = g.sort_values("settlementdate").copy()
        g["demand_lag_1"] = g["totaldemand"].shift(1)
        g["demand_lag_12"] = g["totaldemand"].shift(12)
        g["demand_lag_288"] = g["totaldemand"].shift(288)
        g["demand_roll_mean_12"] = g["totaldemand"].rolling(12, min_periods=1).mean()
        g["demand_roll_std_12"] = g["totaldemand"].rolling(12, min_periods=1).std()
        g["price_lag_1"] = g["rrp"].shift(1)
        g["price_lag_12"] = g["rrp"].shift(12)
        g["netinterchange_lag_1"] = g["netinterchange"].shift(1)
        frames.append(g)
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["demand_lag_1", "price_lag_1"]).reset_index(drop=True)
    out["netinterchange_lag_1"] = out["netinterchange_lag_1"].fillna(0.0)
    cols = [
        "settlementdate",
        "regionid",
        "rrp",
        "totaldemand",
        "netinterchange",
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
        "netinterchange_lag_1",
    ]
    return out[cols]


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    return build_panel(df)
