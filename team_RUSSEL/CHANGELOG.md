# Changelog — Team RUSSEL

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-02-24

### Added
- `coursework_one/Main.py` — full ETL pipeline orchestration (yfinance → MinIO + MongoDB + PostgreSQL)
- `modules/input/data_extractor.py` — Value + Quality factor extraction (P/E, P/B, P/S, EV/EBITDA, EV/Revenue, Dividend Yield, ROE, ROA, Profit Margin, Operating Margin, Gross Margin, Debt/Equity, Current Ratio, FCF)
- `modules/output/postgres_storage.py` — idempotent upsert to `systematic_equity.factor_data` via `ON CONFLICT (ticker, date) DO UPDATE`
- `modules/output/mongo_storage.py` — upsert to MongoDB `investment_data.company_metrics` collection
- `modules/output/minio_storage.py` — Parquet storage to MinIO `investment-data` bucket
- `modules/db/db_connection.py` — lazy PostgreSQL + MongoDB connection manager with context manager support
- `modules/utils/config_loader.py` — YAML config loader
- `config/conf.yaml` — pipeline configuration (DB endpoints, extraction frequency, lookback years)
- `test/` — 103 pytest unit tests across all modules, 86% coverage
- `README.md` — project documentation, run instructions, architecture overview

### Changed
- Historical extraction uses hybrid annual + quarterly fundamentals merged to monthly prices via `pd.merge_asof` (backward as-of join)
- PostgreSQL upsert now includes `sector`, `industry`, `db_sector`, `db_industry` columns
- Three-layer infinity sanitisation in PostgreSQL storage prevents `invalid input syntax for type numeric: "Infinity"` errors

### Fixed
- Infinity values (`np.float32(inf)`, `float('inf')`) crashing PostgreSQL upserts
- `sector` column not being written to `factor_data` (missing from INSERT statement)
- Pipeline required to run from `team_RUSSEL/coursework_one/` for Poetry to find `pyproject.toml`

---

## [0.1.0] — 2026-02-10

### Added
- Initial project scaffold: `Main.py`, `modules/`, `config/`, `test/`, `pyproject.toml`
- Basic yfinance data extraction for current price and fundamental ratios
- PostgreSQL and MongoDB connection modules
