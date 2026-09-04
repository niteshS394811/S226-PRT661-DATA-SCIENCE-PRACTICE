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

### Run with Docker

Build the image:

```bash
docker compose build
```

Run the repository's default extraction pipeline:

```bash
docker compose run --rm app
```

The complete repository is copied into the image. The `src/data` directory is
mounted into the container, so downloaded files remain in `src/data/raw_cache`
and the merged output is written to
`src/data/processed/nemweb_price_demand_raw.csv`.

To run another repository script, override the command, for example:

```bash
docker compose run --rm app python test.py
```

## Data source modes

## Storage


## License / data attribution

All electricity market data is sourced from AEMO NEMWEB under its Copyright Permissions Notice. See the project proposal (`docs/`) for full ethics, privacy and attribution details.
