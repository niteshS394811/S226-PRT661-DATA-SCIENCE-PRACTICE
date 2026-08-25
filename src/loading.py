import pandas as pd
from sqlalchemy import create_engine


DATABASE_URL = (
    "postgresql+psycopg://"
    "nemuser:nempassword@postgres:5432/nemdb"
)


def get_engine():
    return create_engine(DATABASE_URL)


def load_data(
    df: pd.DataFrame,
    table_name: str,
    if_exists: str = "append"
):
    engine = get_engine()

    df.to_sql(
        table_name,
        engine,
        if_exists=if_exists,
        index=False
    )

    engine.dispose()