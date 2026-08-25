import pandas as pd


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["SETTLEMENTDATE"] = pd.to_datetime(
        df["SETTLEMENTDATE"], errors="coerce"
    )
    df["hour"] = df["SETTLEMENTDATE"].dt.hour
    df["day"] = df["SETTLEMENTDATE"].dt.day
    df["month"] = df["SETTLEMENTDATE"].dt.month
    df["day_of_week"] = df["SETTLEMENTDATE"].dt.dayofweek

    return df