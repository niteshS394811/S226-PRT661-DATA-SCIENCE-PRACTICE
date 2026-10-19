"""Hourly rollups, price regimes, and analytics tables."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["SETTLEMENTDATE"] = pd.to_datetime(d["SETTLEMENTDATE"])
    d = d.set_index("SETTLEMENTDATE")
    num_cols = [
        c
        for c in d.columns
        if c != "REGIONID" and pd.api.types.is_numeric_dtype(d[c])
    ]
    parts = []
    for region, g in d.groupby("REGIONID"):
        h = g[num_cols].resample("h").mean()
        h["REGIONID"] = region
        parts.append(h.reset_index())
    out = pd.concat(parts, ignore_index=True)
    out["hour"] = out["SETTLEMENTDATE"].dt.hour
    out["dow"] = out["SETTLEMENTDATE"].dt.dayofweek  # 0=Mon
    out["month"] = out["SETTLEMENTDATE"].dt.month
    out["year"] = out["SETTLEMENTDATE"].dt.year
    out["date"] = out["SETTLEMENTDATE"].dt.date
    out["is_weekend"] = (out["dow"] >= 5).astype(int)
    return out


def label_price_regime(series: pd.Series, train_fraction: float = 0.8) -> pd.Series:
    """Low / Normal / High / Spike from quantiles.

    Thresholds are estimated on the first train_fraction of rows (time-ordered)
    and applied to the full series — avoids using future test data for cut-offs.
    """
    s = series.astype(float)
    n = len(s)
    cut = max(int(n * train_fraction), 1)
    train_s = s.iloc[:cut]
    q25, q75, q95 = train_s.quantile([0.25, 0.75, 0.95])
    labels = pd.Series(index=series.index, dtype=object)
    labels[s <= q25] = "Low"
    labels[(s > q25) & (s <= q75)] = "Normal"
    labels[(s > q75) & (s <= q95)] = "High"
    labels[s > q95] = "Spike"
    return labels


def build_hourly_panel(raw: pd.DataFrame) -> pd.DataFrame:
    hourly = to_hourly(raw)
    # regime within each region; thresholds from early (train) window only
    hourly = hourly.sort_values(["REGIONID", "SETTLEMENTDATE"])
    hourly["price_regime"] = hourly.groupby("REGIONID")["RRP"].transform(
        lambda s: label_price_regime(s, train_fraction=0.8)
    )
    if "SPARE_CAPACITY" in hourly.columns:
        def _tight(s: pd.Series) -> pd.Series:
            cut = max(int(len(s) * 0.8), 1)
            thr = s.iloc[:cut].quantile(0.25)
            return (s < thr).astype(int)
        hourly["tight_system"] = hourly.groupby("REGIONID")["SPARE_CAPACITY"].transform(_tight)
    else:
        hourly["tight_system"] = 0
    if "NETINTERCHANGE" in hourly.columns:
        hourly["net_importer"] = (hourly["NETINTERCHANGE"] > 0).astype(int)
    return hourly


def summary_by_region(hourly: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "RRP": ["mean", "median", "std", "max"],
        "TOTALDEMAND": ["mean", "max"],
    }
    if "SEMISCHEDULE_CLEAREDMW" in hourly.columns:
        agg["SEMISCHEDULE_CLEAREDMW"] = ["mean"]
    if "SPARE_CAPACITY" in hourly.columns:
        agg["SPARE_CAPACITY"] = ["mean"]
    s = hourly.groupby("REGIONID").agg(agg)
    s.columns = ["_".join(c).strip("_") for c in s.columns.to_flat_index()]
    return s.reset_index()


def heatmap_price_hour_dow(hourly: pd.DataFrame, region: Optional[str] = None) -> pd.DataFrame:
    d = hourly if region is None else hourly[hourly["REGIONID"] == region]
    return d.pivot_table(index="hour", columns="dow", values="RRP", aggfunc="mean")


def daily_avg(hourly: pd.DataFrame) -> pd.DataFrame:
    keys = ["date", "REGIONID"]
    cols = [c for c in ["RRP", "TOTALDEMAND", "NETINTERCHANGE", "SEMISCHEDULE_CLEAREDMW", "SPARE_CAPACITY"] if c in hourly.columns]
    return hourly.groupby(keys)[cols].mean().reset_index()
