# Team RUSSEL — Coursework One: Investment Data Pipeline

ETL pipeline extracting **Value** and **Quality** factor data for 678 companies across three storage backends.

## Project Structure

```
coursework_one/
├── Main.py                  # Pipeline entry point
├── config/
│   └── conf.yaml            # Database + extraction settings
├── modules/
│   ├── db/
│   │   └── db_connection.py # PostgreSQL + MongoDB connectors
│   ├── input/
│   │   └── data_extractor.py# Value + Quality factor extraction (yfinance)
│   ├── output/
│   │   ├── minio_storage.py # Parquet → MinIO
│   │   ├── mongo_storage.py # Documents → MongoDB
│   │   └── postgres_storage.py # Upsert → PostgreSQL
│   └── utils/
│       └── config_loader.py # YAML config loader
├── scripts/                 # One-time / utility scripts
│   ├── create_annual_factor_data.py
│   ├── extract_all_annual_data.py
│   ├── load_annual_fundamentals_to_db.py
│   ├── example_annual_queries.py
│   └── clean_mongodb.py
├── test/
│   ├── conftest.py
│   ├── test_annual_data.py
│   ├── test_annually_fundamentals.py
│   ├── test_batch.py
│   └── test_quarterly_fundamentals.py
├── pyproject.toml
└── poetry.lock
```

## Factors Extracted

### Value Factors
| Metric | Field | Method |
|---|---|---|
| P/E Ratio | `pe_ratio` | Price / Trailing EPS |
| Forward P/E | `forward_pe` | Price / Forward EPS |
| P/B Ratio | `pb_ratio` | Price / Book Value per Share |
| P/S Ratio | `ps_ratio` | Market Cap / Revenue |
| EV/EBITDA | `ev_to_ebitda` | Enterprise Value / EBITDA |
| EV/Revenue | `ev_to_revenue` | Enterprise Value / Revenue |
| Dividend Yield | `dividend_yield` | Dividend / Price |

### Quality Factors
| Metric | Field | Method |
|---|---|---|
| ROE | `roe` | Net Income / Equity |
| ROA | `roa` | Net Income / Total Assets |
| Profit Margin | `profit_margin` | Net Income / Revenue |
| Operating Margin | `operating_margin` | Operating Income / Revenue |
| Gross Margin | `gross_margin` | Gross Profit / Revenue |
| Debt/Equity | `debt_to_equity` | Total Debt / Equity |
| Current Ratio | `current_ratio` | Current Assets / Current Liabilities |
| Free Cash Flow | `free_cash_flow` | Operating CF - CapEx |

## Running the Pipeline

All commands must be run from `team_RUSSEL/coursework_one/`:

```bash
cd /Users/viviagustinisampelan/ift_coursework_2025/team_RUSSEL/coursework_one

# Full run — all 678 companies (background, ~2-3 hours)
poetry run python Main.py --config config/conf.yaml > pipeline.log 2>&1 &
tail -f pipeline.log

# Single ticker test
poetry run python Main.py --config config/conf.yaml --ticker AAPL

# Specific date
poetry run python Main.py --config config/conf.yaml --date 2026-02-24
```

## Storage Backends

| Backend | Location | Format |
|---|---|---|
| MinIO | `current_data/YYYY/MM/DD/value_factors.parquet` | Parquet |
| MinIO | `historical_data/YYYY/MM/DD/price_history.parquet` | Parquet |
| MongoDB | `investment_data.company_metrics` | BSON documents |
| PostgreSQL | `systematic_equity.factor_data` | Relational (upsert) |

## Data Flow

```
yfinance API
     │
     ├─ Current snapshot  (1 row / company)  ─► MinIO + MongoDB + PostgreSQL
     │   Value + Quality metrics, today's date
     │
     └─ Historical OHLCV  (60 rows / company, monthly)
         Quarterly statements (recent) + Annual (older)
         merged via as-of join ─────────────────────► MinIO + MongoDB + PostgreSQL
```

## Key Design Decisions

- **Hybrid fundamentals**: Quarterly (TTM) for recent periods, annual for older — merged to monthly prices via backward as-of join
- **Idempotent upserts**: `ON CONFLICT (ticker, date) DO UPDATE` — safe to re-run
- **USD-only filter**: Non-USD stocks skipped in historical extraction
- **Lazy DB connections**: Opened only when first needed

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
```

## Running Tests

```bash
cd /Users/viviagustinisampelan/ift_coursework_2025/team_RUSSEL/coursework_one
poetry run pytest test/ -v
```
