"""Clean extracted NEM price + demand + netinterchange data before staging load."""
from __future__ import annotations

import pandas as pd


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    rename = {
        "SETTLEMENTDATE": "settlementdate",
        "REGIONID": "regionid",
        "RRP": "rrp",
        "TOTALDEMAND": "totaldemand",
        "NETINTERCHANGE": "netinterchange",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    df["rrp"] = pd.to_numeric(df["rrp"], errors="coerce")
    df["totaldemand"] = pd.to_numeric(df["totaldemand"], errors="coerce")
    if "netinterchange" not in df.columns:
        df["netinterchange"] = 0.0
    df["netinterchange"] = pd.to_numeric(df["netinterchange"], errors="coerce").fillna(0.0)

    df = df.dropna(subset=["settlementdate", "regionid", "rrp", "totaldemand"])
    df = df.drop_duplicates(subset=["settlementdate", "regionid"])
    df = df.sort_values(["settlementdate", "regionid"]).reset_index(drop=True)
    return df[["settlementdate", "regionid", "rrp", "totaldemand", "netinterchange"]]
