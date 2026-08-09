##PRT661 – Data Science Practice ##
Danala Group 8 Theme 2

Repository Layout
```
nem-forecasting/
├── src/
│   ├── ingestion/       # BaseDataClient, NemwebClient
│   ├── etl/             # Transformer, FeatureBuilder
│   ├── models/          # BaseForecaster, LstmForecaster, GruForecaster, metrics
│   ├── storage/         # BaseRepository, SqlServerRepository, SQLiteRepository
│   ├── visualisation/   # TableauExporter
│   └── pipeline.py      # ForecastPipeline orchestrator
├── dags/                # Airflow DAG (nem_forecast_dag.py)
├── scripts/             # run_pipeline.py CLI entry point
├── tests/               # pytest unit tests (run offline, synthetic data)
├── docs/                # architecture & workflow docs
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Quickstart

## Data source modes

## Storage


## License / data attribution

All electricity market data is sourced from AEMO NEMWEB under its Copyright Permissions Notice. See the project proposal (`docs/`) for full ethics, privacy and attribution details.
