"""
Compute yearly Value + Quality factor scores per investment specification.

Implements the composite factor construction defined in the investment spec:
  - Value Score  = mean(Percentile_PB, Percentile_PE, Percentile_EV_EBITDA)
  - Quality Score = Percentile_ROE
  - Composite    = 0.75 * Value Score + 0.25 * Quality Score

Percentile formula (cross-sectional, per year):
  Percentile = 1 - (Rank - 1) / (N - 1)
  where lower valuation ratios and higher ROE receive higher percentiles.

Eligibility rules (per spec section 6):
  - Book Value > 0  (pb_ratio > 0 implies this)
  - Net Income > 0  (pe_ratio > 0 implies this)
  - EBITDA > 0      (ev_to_ebitda > 0 implies this)
  - All required variables present

Rebalance date: last trading day of each calendar year (Dec 31 snapshot).
Financial data is already lagged 3 months via the merge_asof backward join
in the extraction pipeline.

Usage:
    poetry run python scripts/compute_factor_scores.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pandas as pd
import psycopg2
from datetime import datetime
import logging

from a_pipeline.modules.utils.config_loader import load_config
from a_pipeline.modules.db.db_connection import DatabaseConnector

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

SCORE_SQL = """
WITH all_data AS (
    -- All companies: last available row per ticker per year.
    -- Rebalance date pinned to Dec 31 (yearly rebalance per spec).
    -- No eligibility filter here — full 678-company universe included.
    SELECT DISTINCT ON (ticker, EXTRACT(YEAR FROM date)::int)
        ticker,
        company_name,
        db_sector,
        EXTRACT(YEAR FROM date)::int                   AS year,
        MAKE_DATE(EXTRACT(YEAR FROM date)::int, 12, 31) AS rebalance_date,
        pb_ratio,
        pe_ratio,
        ev_to_ebitda,
        roe,
        market_cap,
        book_value,
        -- EV = Market Cap + Total Debt - Cash (per investment spec)
        CASE
            WHEN market_cap IS NOT NULL
            THEN market_cap + COALESCE(total_debt, 0) - COALESCE(cash, 0)
        END AS enterprise_value
    FROM systematic_equity.factor_data
    WHERE date < CURRENT_DATE           -- exclude intraday snapshot rows
    ORDER BY ticker, EXTRACT(YEAR FROM date)::int, date DESC
),
eligible_ranked AS (
    -- Percentile ranks computed only over the eligible subset:
    -- pb > 0, pe > 0, ev_to_ebitda > 0, roe not null.
    -- Percentile = 1 - (Rank-1)/(N-1): lower ratio = higher percentile (better value).
    SELECT
        ticker,
        year,
        COUNT(*) OVER (PARTITION BY year)                                           AS eligible_count,
        1.0 - (ROW_NUMBER() OVER (PARTITION BY year ORDER BY pb_ratio      ASC) - 1.0)
            / NULLIF(COUNT(*) OVER (PARTITION BY year) - 1, 0)                     AS pb_percentile,
        1.0 - (ROW_NUMBER() OVER (PARTITION BY year ORDER BY pe_ratio      ASC) - 1.0)
            / NULLIF(COUNT(*) OVER (PARTITION BY year) - 1, 0)                     AS pe_percentile,
        1.0 - (ROW_NUMBER() OVER (PARTITION BY year ORDER BY ev_to_ebitda  ASC) - 1.0)
            / NULLIF(COUNT(*) OVER (PARTITION BY year) - 1, 0)                     AS ev_ebitda_percentile,
        -- Quality: higher ROE = better = higher percentile
        1.0 - (ROW_NUMBER() OVER (PARTITION BY year ORDER BY roe           DESC) - 1.0)
            / NULLIF(COUNT(*) OVER (PARTITION BY year) - 1, 0)                     AS roe_percentile
    FROM all_data
    WHERE pb_ratio > 0
      AND pe_ratio > 0
      AND ev_to_ebitda > 0
      AND roe IS NOT NULL
)
SELECT
    a.ticker,
    a.rebalance_date,
    a.company_name,
    a.db_sector,
    ROUND(a.pb_ratio::numeric,       4)  AS pb_ratio,
    ROUND(a.pe_ratio::numeric,       4)  AS pe_ratio,
    ROUND(a.ev_to_ebitda::numeric,   4)  AS ev_to_ebitda,
    ROUND(a.roe::numeric,            4)  AS roe,
    a.market_cap,
    ROUND(a.book_value::numeric,     4)  AS book_value,
    a.enterprise_value,
    -- Percentiles NULL for ineligible firms
    ROUND(r.pb_percentile::numeric,       4)  AS pb_percentile,
    ROUND(r.pe_percentile::numeric,       4)  AS pe_percentile,
    ROUND(r.ev_ebitda_percentile::numeric, 4) AS ev_ebitda_percentile,
    ROUND(r.roe_percentile::numeric,      4)  AS roe_percentile,
    -- Scores NULL for ineligible firms
    CASE WHEN r.pb_percentile IS NOT NULL THEN
        ROUND(((r.pb_percentile + r.pe_percentile + r.ev_ebitda_percentile) / 3.0)::numeric, 4)
    END AS value_score,
    ROUND(r.roe_percentile::numeric, 4) AS quality_score,
    CASE WHEN r.pb_percentile IS NOT NULL THEN
        ROUND((0.75 * (r.pb_percentile + r.pe_percentile + r.ev_ebitda_percentile) / 3.0
               + 0.25 * r.roe_percentile)::numeric, 4)
    END AS composite_score,
    r.eligible_count AS eligible_firm_count
FROM all_data a
LEFT JOIN eligible_ranked r ON a.ticker = r.ticker AND a.year = r.year
ORDER BY a.rebalance_date, composite_score DESC NULLS LAST;
"""

UPSERT_SCORE_SQL = """
INSERT INTO systematic_equity.factor_scores (
    ticker, rebalance_date, company_name, db_sector,
    pb_ratio, pe_ratio, ev_to_ebitda, roe,
    market_cap, book_value, enterprise_value,
    pb_percentile, pe_percentile, ev_ebitda_percentile, roe_percentile,
    value_score, quality_score, composite_score,
    eligible_firm_count, pipeline_run_id
) VALUES (
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s
)
ON CONFLICT (ticker, rebalance_date) DO UPDATE SET
    company_name         = EXCLUDED.company_name,
    db_sector            = EXCLUDED.db_sector,
    pb_ratio             = EXCLUDED.pb_ratio,
    pe_ratio             = EXCLUDED.pe_ratio,
    ev_to_ebitda         = EXCLUDED.ev_to_ebitda,
    roe                  = EXCLUDED.roe,
    market_cap           = EXCLUDED.market_cap,
    book_value           = EXCLUDED.book_value,
    enterprise_value     = EXCLUDED.enterprise_value,
    pb_percentile        = EXCLUDED.pb_percentile,
    pe_percentile        = EXCLUDED.pe_percentile,
    ev_ebitda_percentile = EXCLUDED.ev_ebitda_percentile,
    roe_percentile       = EXCLUDED.roe_percentile,
    value_score          = EXCLUDED.value_score,
    quality_score        = EXCLUDED.quality_score,
    composite_score      = EXCLUDED.composite_score,
    eligible_firm_count  = EXCLUDED.eligible_firm_count,
    pipeline_run_id      = EXCLUDED.pipeline_run_id;
"""


def compute_and_store_scores():
    config = load_config()
    db = DatabaseConnector(config)
    conn = db.get_postgres_connection()
    cur = conn.cursor()

    run_id = datetime.now().strftime('run_%Y%m%d_%H%M%S')
    logger.info(f"Computing factor scores — pipeline_run_id: {run_id}")

    # Fetch scores
    cur.execute(SCORE_SQL)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    df = pd.DataFrame(rows, columns=cols)
    logger.info(f"Computed scores for {len(df)} firm-year observations")

    # Summary by year
    for year, grp in df.groupby(df['rebalance_date'].apply(lambda d: d.year)):
        logger.info(f"  {year}: {len(grp)} eligible firms")

    # Upsert into factor_scores
    def _n(v):
        """Return None for NaN/NaT so psycopg2 inserts NULL."""
        import math
        if v is None:
            return None
        try:
            if math.isnan(float(v)):
                return None
        except (TypeError, ValueError):
            pass
        return v

    params = [
        (
            row['ticker'], row['rebalance_date'], row['company_name'], row['db_sector'],
            _n(row['pb_ratio']), _n(row['pe_ratio']), _n(row['ev_to_ebitda']), _n(row['roe']),
            _n(row['market_cap']), _n(row['book_value']), _n(row['enterprise_value']),
            _n(row['pb_percentile']), _n(row['pe_percentile']), _n(row['ev_ebitda_percentile']),
            _n(row['roe_percentile']), _n(row['value_score']), _n(row['quality_score']),
            _n(row['composite_score']), _n(row['eligible_firm_count']), run_id,
        )
        for _, row in df.iterrows()
    ]
    cur.executemany(UPSERT_SCORE_SQL, params)
    conn.commit()
    logger.info(f"Upserted {len(params)} rows into systematic_equity.factor_scores")

    # Print top 10 composite scores for the most recent year
    latest = df[df['rebalance_date'] == df['rebalance_date'].max()]
    print(f"\nTop 10 — {df['rebalance_date'].max()} (Composite Score):")
    print(f"{'Ticker':<8} {'Name':<30} {'Sector':<25} {'PB':>6} {'PE':>6} "
          f"{'EV/EBITDA':>10} {'ROE':>6} {'Composite':>10}")
    print("-" * 105)
    for _, r in latest.head(10).iterrows():
        print(f"{r['ticker']:<8} {str(r['company_name'])[:29]:<30} "
              f"{str(r['db_sector'] or '')[:24]:<25} "
              f"{float(r['pb_ratio']):>6.2f} {float(r['pe_ratio']):>6.1f} "
              f"{float(r['ev_to_ebitda']):>10.2f} {float(r['roe']):>6.3f} "
              f"{float(r['composite_score']):>10.4f}")

    cur.close()


if __name__ == '__main__':
    compute_and_store_scores()
