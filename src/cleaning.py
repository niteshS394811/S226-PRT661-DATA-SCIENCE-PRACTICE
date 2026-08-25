import pandas as pd


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["SETTLEMENTDATE"] = pd.to_datetime(
        df["SETTLEMENTDATE"],
        errors="coerce"
    )

    df["RRP"] = pd.to_numeric(
        df["RRP"],
        errors="coerce"
    )

    df["TOTALDEMAND"] = pd.to_numeric(
        df["TOTALDEMAND"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "SETTLEMENTDATE",
            "REGIONID",
            "RRP",
            "TOTALDEMAND"
        ]
    )

    df = df.drop_duplicates()

    return df