#!/usr/bin/env python3
"""
Backfill current_ratio in factor_data from yfinance balance sheets.

Fetches Current Assets / Current Liabilities for every ticker that has
NULL current_ratio in factor_data and updates all rows for that ticker/year.

Usage:
    cd team_RUSSEL/coursework_one
    poetry run python a_pipeline/scripts/backfill_current_ratio.py
"""
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
import yfinance as yf
import pandas as pd

from a_pipeline.modules.utils.config_loader import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _safe_divide(num, den):
    try:
        if num is None or den is None or den == 0:
            return None
        result = float(num) / float(den)
        import math
        return None if (math.isnan(result) or math.isinf(result)) else result
    except Exception:
        return None


def get_balance_sheet_current_ratio(ticker: str) -> dict:
    """
    Returns {year: current_ratio} from annual + quarterly balance sheets.
    Uses Current Assets / Current Liabilities.
    """
    try:
        stock = yf.Ticker(ticker)
        results = {}

        for bal, label in [
            (stock.balance_sheet, "annual"),
            (stock.quarterly_balance_sheet, "quarterly"),
        ]:
            if bal is None or bal.empty:
                continue
            ca_row = next((r for r in bal.index if r == 'Current Assets'), None)
            cl_row = next((r for r in bal.index if r == 'Current Liabilities'), None)
            if ca_row is None or cl_row is None:
                continue
            for col in bal.columns:
                try:
                    ca = bal.loc[ca_row, col]
                    cl = bal.loc[cl_row, col]
                    ratio = _safe_divide(
                        float(ca) if pd.notna(ca) else None,
                        float(cl) if pd.notna(cl) else None,
                    )
                    if ratio is not None:
                        year = pd.to_datetime(col).year
                        # Quarterly: use fiscal year of the period end
                        if year not in results:
                            results[year] = ratio
                except Exception:
                    continue
        return results
    except Exception as e:
        logger.warning(f"{ticker}: failed — {e}")
        return {}


def main():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "conf.yaml"
    )
    config = load_config(config_path)
    pg = config["postgres"]
    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"], dbname=pg["database"],
        user=pg["user"], password=pg["password"]
    )
    cur = conn.cursor()

    # Get all tickers that still have NULL current_ratio in any Dec snapshot
    cur.execute("""
        SELECT DISTINCT ticker
        FROM systematic_equity.factor_data
        WHERE current_ratio IS NULL
          AND EXTRACT(MONTH FROM date) = 12
          AND date < CURRENT_DATE
        ORDER BY ticker
    """)
    tickers = [r[0].strip() for r in cur.fetchall()]
    logger.info(f"Tickers with missing current_ratio: {len(tickers)}")

    updated_tickers = 0
    updated_rows = 0

    for i, ticker in enumerate(tickers, 1):
        ratios = get_balance_sheet_current_ratio(ticker)
        if not ratios:
            logger.info(f"[{i}/{len(tickers)}] {ticker}: no balance sheet data")
            continue

        ticker_rows = 0
        for year, ratio in ratios.items():
            cur.execute("""
                UPDATE systematic_equity.factor_data
                SET current_ratio = %s
                WHERE ticker = %s
                  AND EXTRACT(YEAR FROM date)::int = %s
                  AND current_ratio IS NULL
            """, (ratio, ticker, year))
            ticker_rows += cur.rowcount

        if ticker_rows > 0:
            conn.commit()
            updated_tickers += 1
            updated_rows += ticker_rows
            logger.info(f"[{i}/{len(tickers)}] {ticker}: updated {ticker_rows} rows "
                        f"({', '.join(f'{y}:{r:.3f}' for y, r in sorted(ratios.items()))})")
        else:
            logger.info(f"[{i}/{len(tickers)}] {ticker}: no matching NULL rows")

    logger.info(f"\nDone — {updated_tickers} tickers, {updated_rows} rows updated")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
