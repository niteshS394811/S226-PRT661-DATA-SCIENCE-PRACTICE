"""Clean extracted NEM data before staging load (rich column set)."""
from __future__ import annotations

import pandas as pd

RENAME = {
    "SETTLEMENTDATE": "settlementdate",
    "REGIONID": "regionid",
    "RRP": "rrp",
    "TOTALDEMAND": "totaldemand",
    "NETINTERCHANGE": "netinterchange",
    "DEMANDFORECAST": "demandforecast",
    "AVAILABLEGENERATION": "availablegeneration",
    "DISPATCHABLEGENERATION": "dispatchablegeneration",
    "INITIALSUPPLY": "initialsupply",
    "CLEAREDSUPPLY": "clearedsupply",
    "TOTALINTERMITTENTGENERATION": "totalintermittentgeneration",
    "UIGF": "uigf",
    "SEMISCHEDULE_CLEAREDMW": "semischedule_clearedmw",
    "SPARE_CAPACITY": "spare_capacity",
}

CORE = [
    "settlementdate",
    "regionid",
    "rrp",
    "totaldemand",
    "netinterchange",
    "demandforecast",
]
EXTRA = [
    "availablegeneration",
    "dispatchablegeneration",
    "initialsupply",
    "clearedsupply",
    "totalintermittentgeneration",
    "uigf",
    "semischedule_clearedmw",
    "spare_capacity",
]


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})

    df["settlementdate"] = pd.to_datetime(df["settlementdate"], errors="coerce")
    for c in CORE[2:] + [x for x in EXTRA if x in df.columns]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "netinterchange" not in df.columns:
        df["netinterchange"] = 0.0
    df["netinterchange"] = df["netinterchange"].fillna(0.0)
    if "demandforecast" not in df.columns:
        df["demandforecast"] = pd.NA

    if "spare_capacity" not in df.columns and "availablegeneration" in df.columns:
        df["spare_capacity"] = df["availablegeneration"] - df["totaldemand"]

    df = df.dropna(subset=["settlementdate", "regionid", "rrp", "totaldemand"])
    df = df.drop_duplicates(subset=["settlementdate", "regionid"])
    df = df.sort_values(["settlementdate", "regionid"]).reset_index(drop=True)

    cols = CORE + [c for c in EXTRA if c in df.columns]
    return df[cols]
