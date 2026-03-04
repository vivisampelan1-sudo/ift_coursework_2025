# Team RUSSEL — Coursework One: Investment Data Pipeline

ETL pipeline extracting **Value** and **Quality** factor data for 678 companies across three storage backends, followed by cross-sectional factor scoring using the Amundi / JPM methodology.

## Project Structure

```
coursework_one/
├── a_pipeline/                  # Pipeline A — Data Extraction
│   ├── Main.py                  # Entry point
│   ├── config/
│   │   └── conf.yaml            # Database + extraction settings
│   ├── modules/
│   │   ├── db/
│   │   │   └── db_connection.py # PostgreSQL + MongoDB connectors
│   │   ├── input/
│   │   │   └── data_extractor.py# Value + Quality factor extraction (yfinance)
│   │   ├── output/
│   │   │   ├── minio_storage.py # Parquet → MinIO
│   │   │   ├── mongo_storage.py # Documents → MongoDB
│   │   │   └── postgres_storage.py # Upsert → PostgreSQL
│   │   └── utils/
│   │       └── config_loader.py # YAML config loader
│   ├── scripts/                 # One-time / utility scripts
│   │   ├── backfill_current_ratio.py
│   │   ├── backfill_dividend_yield.py
│   │   ├── clean_mongodb.py
│   │   ├── compute_factor_scores.py
│   │   ├── create_annual_factor_data.py
│   │   ├── example_annual_queries.py
│   │   ├── extract_all_annual_data.py
│   │   ├── impute_missing_data.py
│   │   └── load_annual_fundamentals_to_db.py
│   └── test/
│       ├── conftest.py
│       ├── test_annual_data.py
│       ├── test_annually_fundamentals.py
│       ├── test_batch.py
│       ├── test_config_loader.py
│       ├── test_data_extractor.py
│       ├── test_db_connection.py
│       ├── test_minio_storage.py
│       ├── test_mongo_storage.py
│       ├── test_postgres_storage.py
│       └── test_quarterly_fundamentals.py
│
├── b_pipeline/                  # Pipeline B — Factor Scoring
│   ├── Main.py                  # Entry point
│   ├── config/
│   │   └── conf.yaml
│   ├── modules/
│   │   └── scoring/
│   │       └── scorer.py        # Amundi/JPM scoring engine
│   └── test/
│       └── test_scorer.py       # 60 unit tests for scorer
│
├── pyproject.toml
└── poetry.lock
```

## Pipeline A — Data Extraction

Extracts **Value** and **Quality** factor data from yfinance for 678 Russell 1000 companies and stores snapshots in three backends.

### Value Factors Extracted

| Metric | Field | Method |
|---|---|---|
| P/E Ratio | `pe_ratio` | Price / Trailing EPS |
| Forward P/E | `forward_pe` | Price / Forward EPS |
| P/B Ratio | `pb_ratio` | Price / Book Value per Share |
| P/S Ratio | `ps_ratio` | Market Cap / Revenue |
| EV/EBITDA | `ev_to_ebitda` | Enterprise Value / EBITDA |
| EV/Revenue | `ev_to_revenue` | Enterprise Value / Revenue |
| Dividend Yield | `dividend_yield` | Trailing 12-month DPS / Price |

### Quality Factors Extracted

| Metric | Field | Method |
|---|---|---|
| ROE | `roe` | Net Income / Equity |
| ROA | `roa` | Net Income / Total Assets |
| Profit Margin | `profit_margin` | Net Income / Revenue |
| Operating Margin | `operating_margin` | Operating Income / Revenue |
| Gross Margin | `gross_margin` | Gross Profit / Revenue |
| Debt/Equity | `debt_to_equity` | Total Debt / Equity |
| Current Ratio | `current_ratio` | Current Assets / Current Liabilities |
| Free Cash Flow | `free_cash_flow` | Operating CF − CapEx |

### Storage Backends

| Backend | Location | Format |
|---|---|---|
| MinIO | `current_data/YYYY/MM/DD/value_factors.parquet` | Parquet |
| MinIO | `historical_data/YYYY/MM/DD/price_history.parquet` | Parquet |
| MongoDB | `investment_data.company_metrics` | BSON documents |
| PostgreSQL | `systematic_equity.factor_data` | Relational (upsert) |

### Running Pipeline A

```bash
cd /Users/viviagustinisampelan/ift_coursework_2025/team_RUSSEL/coursework_one

# Full run — all 678 companies (~2-3 hours)
poetry run python a_pipeline/Main.py --config a_pipeline/config/conf.yaml > pipeline_a.log 2>&1 &
tail -f pipeline_a.log

# Single ticker test
poetry run python a_pipeline/Main.py --config a_pipeline/config/conf.yaml --ticker AAPL

# Specific date
poetry run python a_pipeline/Main.py --config a_pipeline/config/conf.yaml --date 2026-02-24
```

### Data Flow

```
yfinance API
     │
     ├─ Current snapshot  (1 row / company)  ─► MinIO + MongoDB + PostgreSQL
     │   Value + Quality metrics, today's date
     │
     └─ Historical OHLCV  (60 rows / company, monthly, ~5 years)
         Quarterly statements (recent) + Annual (older)
         merged via backward as-of join ────────► MinIO + MongoDB + PostgreSQL
```

### Key Design Decisions (Pipeline A)

- **Hybrid fundamentals**: Quarterly (TTM) for recent periods, annual for older — merged to monthly prices via backward as-of join
- **TTM Dividend Yield**: Computed per monthly row from `stock.dividends` history (trailing 12-month DPS / close), not static snapshot
- **Idempotent upserts**: `ON CONFLICT (ticker, date) DO UPDATE` — safe to re-run
- **USD-only filter**: Non-USD stocks skipped in historical extraction
- **Lazy DB connections**: Opened only when first needed

---

## Pipeline B — Factor Scoring

Reads Dec-31 annual snapshots from `systematic_equity.factor_data` (produced by Pipeline A) and computes cross-sectional factor scores using the Amundi / JPM methodology.

### Scoring Methodology

**Value score (JPM approach):**

| Metric | Formula | Weight |
|---|---|---|
| Book-to-Price | book_value / price | 15% |
| Earnings Yield | EPS / price | 35% |
| Cash Flow Yield | free_cash_flow / market_cap | 35% |
| Dividend Yield | trailing DPS / price | 15% |

**Quality score (Amundi approach):**

| Metric | Proxy | Weight |
|---|---|---|
| GPA | gross_margin × roa / profit_margin (fallback: gross_margin) | 33% |
| WCA | current_ratio | 17% |
| LTDE | −debt_to_equity (inverted, lower leverage = better) | 33% |
| ROA | roa | 17% |

**Scoring pipeline per metric:**
1. Winsorise at 5th / 95th percentile (remove outliers)
2. Percentile rank within sector group (sector-neutral, per JPM)
3. Inverse-normal transform: Z = Φ⁻¹(percentile)
4. Weighted average within dimension → re-rank → dimension Z-score
5. Composite = 50% Value_Z + 50% Quality_Z → re-rank → quintile Q1–Q5

**Eligibility rules:**
- EPS > 0 (exclude loss-making firms)
- Exclude Financials and Real Estate (non-standard balance sheets)

**Output table:** `systematic_equity.amundi_jpm_scores`

### Running Pipeline B

```bash
cd /Users/viviagustinisampelan/ift_coursework_2025/team_RUSSEL/coursework_one

# Score all available years
poetry run python b_pipeline/Main.py --config b_pipeline/config/conf.yaml

# Score a specific year only
poetry run python b_pipeline/Main.py --config b_pipeline/config/conf.yaml --year 2024
```

---

## Running Tests

```bash
cd /Users/viviagustinisampelan/ift_coursework_2025/team_RUSSEL/coursework_one

# All tests (Pipeline A + B)
poetry run pytest -v

# Pipeline A tests only
poetry run pytest a_pipeline/test/ -v

# Pipeline B tests only
poetry run pytest b_pipeline/test/ -v

# With coverage report
poetry run pytest --cov --cov-report=term-missing
```

---

## Useful PostgreSQL Queries

```sql
-- Latest snapshot per company
SELECT * FROM systematic_equity.factor_data_latest ORDER BY ticker;

-- Value ranking on latest date
SELECT ticker, pe_ratio, pb_ratio, roe
FROM systematic_equity.factor_data
WHERE date = (SELECT MAX(date) FROM systematic_equity.factor_data)
ORDER BY pe_ratio ASC NULLS LAST;

-- 5-year price history for one company
SELECT date, close, pe_ratio, roe
FROM systematic_equity.factor_data
WHERE ticker = 'AAPL'
ORDER BY date;

-- Top Q1 firms by composite score for a given year
SELECT ticker, company_name, db_sector, composite_score, composite_percentile
FROM systematic_equity.amundi_jpm_scores
WHERE rebalance_date = '2024-12-31'
  AND quintile = 'Q1'
ORDER BY composite_score DESC;

-- Factor score time series for one company
SELECT rebalance_date, value_score, quality_score, composite_score, quintile
FROM systematic_equity.amundi_jpm_scores
WHERE ticker = 'AAPL'
ORDER BY rebalance_date;
```
