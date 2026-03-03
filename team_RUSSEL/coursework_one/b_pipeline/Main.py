#!/usr/bin/env python3
"""
Pipeline B — Amundi / JPM Factor Scoring.

Reads Dec-31 annual snapshots from systematic_equity.factor_data
(produced by Pipeline A) and computes factor scores using the
Amundi / JPM methodology:

    Value (JPM):    Book-to-Price, Earnings Yield, Cash Flow Yield, Dividend Yield
    Quality (Amundi): GPA, WCA, LTDE, ROA

    Scoring: Winsorize → Percentile → Z-score (inverse normal) → Weighted composite
    Output:  systematic_equity.amundi_jpm_scores

Usage:
    cd team_RUSSEL/coursework_one
    poetry run python b_pipeline/Main.py --config b_pipeline/config/conf.yaml
    poetry run python b_pipeline/Main.py --config b_pipeline/config/conf.yaml --year 2024
"""
import argparse
import logging
import os
import sys
from datetime import datetime

import pandas as pd
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from b_pipeline.modules.scoring.scorer import compute_scores

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── SQL to load annual snapshots ───────────────────────────────────────────

LOAD_SQL = """
SELECT DISTINCT ON (ticker, EXTRACT(YEAR FROM date)::int)
    ticker,
    company_name,
    db_sector,
    EXTRACT(YEAR FROM date)::int                    AS year,
    MAKE_DATE(EXTRACT(YEAR FROM date)::int, 12, 31) AS rebalance_date,
    close,
    eps,
    book_value,
    free_cash_flow,
    market_cap,
    dividend_yield,
    gross_margin,
    revenue,
    profit_margin,
    roa,
    debt_to_equity,
    current_ratio,
    operating_margin,
    total_debt,
    cash,
    ebitda,
    ev_to_ebitda,
    pb_ratio,
    pe_ratio
FROM systematic_equity.factor_data
WHERE date < CURRENT_DATE
  {year_filter}
ORDER BY ticker, EXTRACT(YEAR FROM date)::int, date DESC
"""

# ── Output table DDL ───────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS systematic_equity;

CREATE TABLE IF NOT EXISTS systematic_equity.amundi_jpm_scores (
    ticker               VARCHAR(12)  NOT NULL,
    rebalance_date       DATE         NOT NULL,
    company_name         TEXT,
    db_sector            TEXT,
    -- Raw Value metrics
    book_to_price        NUMERIC,
    earnings_yield       NUMERIC,
    cashflow_yield       NUMERIC,
    dividend_yield_raw   NUMERIC,
    -- Raw Quality metrics
    gpa                  NUMERIC,
    wca                  NUMERIC,
    ltde                 NUMERIC,
    roa_quality          NUMERIC,
    -- Per-metric z-scores (Value)
    book_to_price_z      NUMERIC,
    earnings_yield_z     NUMERIC,
    cashflow_yield_z     NUMERIC,
    dividend_yield_z     NUMERIC,
    -- Per-metric z-scores (Quality)
    gpa_z                NUMERIC,
    wca_z                NUMERIC,
    ltde_z               NUMERIC,
    roa_z                NUMERIC,
    -- Dimension and composite scores
    value_score          NUMERIC,
    quality_score        NUMERIC,
    composite_score      NUMERIC,
    composite_percentile NUMERIC,
    quintile             VARCHAR(2),
    -- Reference metrics from pipeline A
    pb_ratio             NUMERIC,
    pe_ratio             NUMERIC,
    ev_to_ebitda         NUMERIC,
    market_cap           BIGINT,
    eligible_firm_count  INTEGER,
    pipeline_run_id      VARCHAR(50),
    inserted_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, rebalance_date)
);

CREATE INDEX IF NOT EXISTS idx_amundi_date
    ON systematic_equity.amundi_jpm_scores (rebalance_date);
CREATE INDEX IF NOT EXISTS idx_amundi_composite
    ON systematic_equity.amundi_jpm_scores (rebalance_date, composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_amundi_quintile
    ON systematic_equity.amundi_jpm_scores (rebalance_date, quintile);
"""

UPSERT_SQL = """
INSERT INTO systematic_equity.amundi_jpm_scores (
    ticker, rebalance_date, company_name, db_sector,
    book_to_price, earnings_yield, cashflow_yield, dividend_yield_raw,
    gpa, wca, ltde, roa_quality,
    book_to_price_z, earnings_yield_z, cashflow_yield_z, dividend_yield_z,
    gpa_z, wca_z, ltde_z, roa_z,
    value_score, quality_score, composite_score, composite_percentile, quintile,
    pb_ratio, pe_ratio, ev_to_ebitda, market_cap,
    eligible_firm_count, pipeline_run_id
) VALUES (
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s
)
ON CONFLICT (ticker, rebalance_date) DO UPDATE SET
    company_name         = EXCLUDED.company_name,
    db_sector            = EXCLUDED.db_sector,
    book_to_price        = EXCLUDED.book_to_price,
    earnings_yield       = EXCLUDED.earnings_yield,
    cashflow_yield       = EXCLUDED.cashflow_yield,
    dividend_yield_raw   = EXCLUDED.dividend_yield_raw,
    gpa                  = EXCLUDED.gpa,
    wca                  = EXCLUDED.wca,
    ltde                 = EXCLUDED.ltde,
    roa_quality          = EXCLUDED.roa_quality,
    book_to_price_z      = EXCLUDED.book_to_price_z,
    earnings_yield_z     = EXCLUDED.earnings_yield_z,
    cashflow_yield_z     = EXCLUDED.cashflow_yield_z,
    dividend_yield_z     = EXCLUDED.dividend_yield_z,
    gpa_z                = EXCLUDED.gpa_z,
    wca_z                = EXCLUDED.wca_z,
    ltde_z               = EXCLUDED.ltde_z,
    roa_z                = EXCLUDED.roa_z,
    value_score          = EXCLUDED.value_score,
    quality_score        = EXCLUDED.quality_score,
    composite_score      = EXCLUDED.composite_score,
    composite_percentile = EXCLUDED.composite_percentile,
    quintile             = EXCLUDED.quintile,
    pb_ratio             = EXCLUDED.pb_ratio,
    pe_ratio             = EXCLUDED.pe_ratio,
    ev_to_ebitda         = EXCLUDED.ev_to_ebitda,
    market_cap           = EXCLUDED.market_cap,
    eligible_firm_count  = EXCLUDED.eligible_firm_count,
    pipeline_run_id      = EXCLUDED.pipeline_run_id;
"""


# ── Helpers ────────────────────────────────────────────────────────────────

def _n(v):
    """Convert NaN/inf to None for psycopg2."""
    import math
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _load_config(config_path: str) -> dict:
    import yaml
    with open(config_path) as f:
        return yaml.safe_load(f)


def _connect(config: dict):
    pg = config["postgres"]
    return psycopg2.connect(
        host=pg["host"], port=pg["port"], dbname=pg["database"],
        user=pg["user"], password=pg["password"]
    )


# ── Main pipeline ──────────────────────────────────────────────────────────

def run(config_path: str, target_year: int | None = None) -> None:
    config = _load_config(config_path)
    conn = _connect(config)
    cur = conn.cursor()

    run_id = datetime.now().strftime("b_run_%Y%m%d_%H%M%S")
    logger.info("=" * 60)
    logger.info("Pipeline B — Amundi/JPM Factor Scoring")
    logger.info(f"Run ID: {run_id}")
    logger.info("=" * 60)

    # Ensure output table exists
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    # Load annual snapshots
    year_filter = f"AND EXTRACT(YEAR FROM date)::int = {target_year}" if target_year else ""
    cur.execute(LOAD_SQL.format(year_filter=year_filter))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    raw = pd.DataFrame(rows, columns=cols)

    if raw.empty:
        logger.warning("No data loaded — check that pipeline A has been run first.")
        return

    # Cast all numeric columns from decimal.Decimal → float (psycopg2 returns Decimal)
    numeric_cols = [c for c in raw.columns if c not in
                    ("ticker", "company_name", "db_sector", "rebalance_date")]
    for col in numeric_cols:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    logger.info(f"Loaded {len(raw)} firm-year rows for {raw['ticker'].nunique()} tickers")

    # Score each rebalance year independently (cross-sectional)
    all_results = []
    for year, group in raw.groupby("year"):
        # Eligibility rule: require EPS > 0 to exclude loss-making firms from
        # quintile ranking (negative EPS distorts earnings yield and can allow
        # loss-making firms to rank highly on cash flow / quality alone).
        eps_num = pd.to_numeric(group['eps'], errors='coerce')
        eligible = group[eps_num.fillna(0) > 0].copy()
        logger.info(f"  Scoring {year}: {len(eligible)} eligible (EPS>0) of {len(group)} companies...")
        scores = compute_scores(eligible.set_index("ticker"))
        scores = scores.reset_index()
        # Attach metadata
        meta = group[["ticker", "company_name", "db_sector", "rebalance_date",
                       "pb_ratio", "pe_ratio", "ev_to_ebitda", "market_cap"]].copy()
        merged = meta.merge(scores, on="ticker", how="left")
        merged["year"] = year
        ranked = scores["composite_score"].notna().sum()
        logger.info(f"    → {ranked} firms ranked, "
                    f"{scores['quintile'].value_counts().to_dict()}")
        all_results.append(merged)

    final = pd.concat(all_results, ignore_index=True)
    logger.info(f"Total: {len(final)} firm-year observations computed")

    # Upsert to PostgreSQL
    upserted = 0
    for _, row in final.iterrows():
        n_eligible = int(final[final["year"] == row["year"]]["composite_score"].notna().sum())
        cur.execute(UPSERT_SQL, (
            row["ticker"], row["rebalance_date"], row["company_name"], row["db_sector"],
            _n(row.get("book_to_price")), _n(row.get("earnings_yield")),
            _n(row.get("cashflow_yield")), _n(row.get("dividend_yield")),
            _n(row.get("gpa")), _n(row.get("wca")),
            _n(row.get("ltde")), _n(row.get("roa_q")),
            _n(row.get("book_to_price_z")), _n(row.get("earnings_yield_z")),
            _n(row.get("cashflow_yield_z")), _n(row.get("dividend_yield_z")),
            _n(row.get("gpa_z")), _n(row.get("wca_z")),
            _n(row.get("ltde_z")), _n(row.get("roa_z")),
            _n(row.get("value_score")), _n(row.get("quality_score")),
            _n(row.get("composite_score")), _n(row.get("composite_percentile")),
            row.get("quintile") if isinstance(row.get("quintile"), str) and row.get("quintile").startswith("Q") else None,
            _n(row.get("pb_ratio")), _n(row.get("pe_ratio")),
            _n(row.get("ev_to_ebitda")), _n(row.get("market_cap")),
            n_eligible, run_id,
        ))
        upserted += 1

    conn.commit()
    logger.info(f"Upserted {upserted} rows into systematic_equity.amundi_jpm_scores")

    # Print top 10 for most recent complete year
    latest_year = final[final["composite_score"].notna()]["year"].max()
    top10 = (
        final[(final["year"] == latest_year) & final["composite_score"].notna()]
        .nlargest(10, "composite_score")
    )
    print(f"\n{'─'*110}")
    print(f"Top 10 — {latest_year} | Amundi/JPM Composite Score")
    print(f"{'─'*110}")
    print(f"{'Ticker':<8} {'Sector':<25} {'Q':<3} "
          f"{'B/P':>6} {'E/Y':>6} {'CF/Y':>6} {'DY':>5} "
          f"{'GPA':>5} {'LTDE':>6} "
          f"{'Value_Z':>8} {'Qual_Z':>8} {'Comp_Z':>8}")
    print(f"{'─'*110}")
    for _, r in top10.iterrows():
        print(
            f"{r['ticker']:<8} {str(r['db_sector'] or '')[:24]:<25} {str(r.get('quintile','')):<3} "
            f"{_n(r.get('book_to_price')) or 0:>6.3f} "
            f"{_n(r.get('earnings_yield')) or 0:>6.3f} "
            f"{_n(r.get('cashflow_yield')) or 0:>6.3f} "
            f"{_n(r.get('dividend_yield')) or 0:>5.3f} "
            f"{_n(r.get('gpa')) or 0:>5.3f} "
            f"{_n(r.get('ltde')) or 0:>6.2f} "
            f"{_n(r.get('value_score')) or 0:>8.3f} "
            f"{_n(r.get('quality_score')) or 0:>8.3f} "
            f"{_n(r.get('composite_score')) or 0:>8.3f}"
        )
    print(f"{'─'*110}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline B — Amundi/JPM Factor Scoring")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--year", type=int, help="Score a specific year only (optional)")
    args = parser.parse_args()
    run(args.config, args.year)
