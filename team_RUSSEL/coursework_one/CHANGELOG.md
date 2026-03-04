# Changelog — Team RUSSEL Coursework One

All notable changes to this project are documented here.

---

## [Unreleased]

---

## [0.4.0] — 2026-03-03

### Added
- **Pipeline B test suite** (`b_pipeline/test/test_scorer.py`): 60 unit tests covering all scorer functions — `winsorize`, `to_percentile`, `percentile_to_zscore`, `metric_to_zscore` (universe-wide and sector-neutral), `compute_value_metrics`, `compute_quality_metrics`, `compute_scores`, and `_score_dimension`. All tests pass.
- **CHANGELOG** (`CHANGELOG.md`): This file.

### Changed
- **README** completely rewritten to reflect the actual `a_pipeline/` + `b_pipeline/` structure, correct run commands, full scoring methodology tables, and updated PostgreSQL query examples.
- `pyproject.toml` `testpaths` already included `b_pipeline/test/` — confirmed working.

---

## [0.3.0] — 2026-03-02

### Added
- **Sector-neutral z-scoring** in `b_pipeline/modules/scoring/scorer.py`: `metric_to_zscore` now accepts an optional `sectors` parameter. When provided, winsorise → percentile → z-score is computed **within each GICS sector group** (JPM methodology). Sectors with < 5 valid observations are pooled into a residual fallback group. NaN sectors are filled as `__unknown__` so those firms are still included.
- `_MIN_GROUP_SIZE = 5` constant for minimum observations per group.

### Fixed
- **Financials / Real Estate exclusion** in `b_pipeline/Main.py`: Eligibility filter regex updated from `Real Estate` to `Real Estate|Financials|Financial Services` — firms like CINF and ALL (Insurance sector labelled "Financials") are now correctly excluded from quintile ranking.
- **VARCHAR(2) overflow** for `quintile` column: Ineligible firms received `NaN` quintile from the left join, which converted to the string `"nan"` (3 chars), overflowing the DB column. Fixed by only writing values that start with `"Q"`.

---

## [0.2.0] — 2026-03-01

### Added
- **EPS > 0 eligibility filter** in `b_pipeline/Main.py`: Loss-making firms (negative EPS) are excluded from quintile ranking. They still appear in `amundi_jpm_scores` with NULL scores for transparency.
- **Real Estate sector exclusion** in `b_pipeline/Main.py`: Real Estate firms excluded alongside Financials — both have non-standard balance sheets where GPA and LTDE are not meaningful (consistent with Amundi/JPM papers).
- **Dividend yield backfill script** (`a_pipeline/scripts/backfill_dividend_yield.py`): Targeted script to compute and update trailing-12-month dividend yields for all 653 tickers already stored in `systematic_equity.factor_data`. Updated 27,143 rows in ~5 minutes without re-running the full pipeline.

### Fixed
- **Dividend yield = 0 for all historical rows** in `a_pipeline/modules/input/data_extractor.py`: Removed the hardcoded `merged['dividend_yield'] = None` that was overwriting computed yields. Replaced with TTM dividend yield computation from `stock.dividends` history: for each monthly price row, sums ex-dividend payments in the trailing 12 months and divides by close price.

---

## [0.1.0] — 2026-02-28

### Added
- **Pipeline A** (`a_pipeline/`): Full ETL pipeline for 678 Russell 1000 companies.
  - `data_extractor.py`: Extracts current snapshot (Value + Quality metrics) and 5-year monthly price history with hybrid fundamentals (quarterly TTM for recent periods, annual for older) merged via backward as-of join.
  - `postgres_storage.py`: Idempotent upserts to `systematic_equity.factor_data` using `ON CONFLICT (ticker, date) DO UPDATE`.
  - `mongo_storage.py`: BSON document storage to `investment_data.company_metrics`.
  - `minio_storage.py`: Parquet export to MinIO (`current_data/` and `historical_data/` buckets).
  - `db_connection.py`: Lazy PostgreSQL + MongoDB connection management.
  - `config_loader.py`: YAML config loader.
- **Pipeline A test suite** (`a_pipeline/test/`): Tests for all modules — config loader, DB connection, data extractor, MinIO/MongoDB/PostgreSQL storage, batch processing, and quarterly/annual fundamentals handling.
- **Pipeline B** (`b_pipeline/`): Amundi / JPM factor scoring engine.
  - `scorer.py`: Implements the full scoring pipeline — winsorise → percentile rank → inverse-normal z-score → weighted dimension average → composite score → Q1–Q5 quintiles.
  - `Main.py`: Loads Dec-31 annual snapshots from Pipeline A output, scores each year cross-sectionally, upserts results to `systematic_equity.amundi_jpm_scores`.
- **Utility scripts** (`a_pipeline/scripts/`):
  - `backfill_current_ratio.py`: Targeted backfill of `current_ratio` from yfinance balance sheets.
  - `create_annual_factor_data.py`, `extract_all_annual_data.py`, `load_annual_fundamentals_to_db.py`: One-time data loading utilities.
  - `clean_mongodb.py`: MongoDB collection reset utility.
  - `impute_missing_data.py`, `compute_factor_scores.py`: Data quality utilities.
- **`pyproject.toml`**: Poetry project config with all dependencies and pytest settings.
